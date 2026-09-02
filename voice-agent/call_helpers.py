"""Helper functions for call operations.

This module provides simple helper functions to:
- Parse and normalize call data
- Build structured summaries
- Execute call-related operations with proper formatting
- LLM function handlers for Pipecat
"""

import asyncio
import copy
import json
import os
from typing import Any
from uuid import UUID

from loguru import logger
from pipecat.frames.frames import EndFrame, FunctionCallResultProperties

from carrier_service import CarrierServiceError, fetch_carrier_by_mc, get_carrier_name
from db_operations import (
    CallRecordResult,
    DatabaseOperationError,
    create_call_record,
    end_call_record,
    link_negotiation_to_call,
    update_call_load,
    update_call_mc,
)
from load_context_utils import build_negotiation_prompt, normalize_load_data
from src import (
    NegotiationDBService,
    build_transfer_phone_number,
    coerce_e164_transfer_number,
)


# Characters allowed in a load reference: letters, digits, hyphens,
# underscores. Real Salesforce reference IDs follow shapes like
# "TEST-001", "REF1234", "L_2026_001". Speech-transcript junk like
# "Noted down" or "your load" contains spaces / has no digits, which
# this helper screens out before the value reaches the SF query.
_LOAD_REF_ALLOWED = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _is_plausible_load_reference(load_id: str) -> bool:
    """Cheap structural check on a load reference before we hit Salesforce.

    Rules (intentionally generous — the goal is to reject obvious junk
    the LLM fabricated from prior-turn speech, not to validate every
    real reference shape):
      - Non-empty after stripping.
      - Every character in [A-Za-z0-9_-]. Spaces, periods, slashes →
        reject (these are common in transcribed prose, not refs).
      - At least one digit present. Real references are numbered;
        all-letters means the LLM hallucinated.

    Returns True iff the input passes all three checks.
    """
    if not load_id:
        return False
    if not all(c in _LOAD_REF_ALLOWED for c in load_id):
        return False
    if not any(c.isdigit() for c in load_id):
        return False
    return True


def start_call(
    load_id: UUID | None = None,
    daily_call_id: str | None = None,
    caller_number: str | None = None,
    caller_country_code: str | None = None,
    caller_mc: str | None = None,
    bot_phone: str | None = None,
) -> CallRecordResult | None:
    """Create a call record in the database.

    Args:
        load_id: UUID of the load being discussed (optional, can be set later)
        daily_call_id: Daily's call identifier (optional)
        caller_number: Phone number of caller (optional)
        caller_country_code: Country code of caller (optional, defaults to +1)
        caller_mc: MC (Motor Carrier) number of the caller (optional)
        bot_phone: Phone number the caller dialed (used for org_id lookup)

    Returns:
        CallRecordResult: Contains call_id and org_id, or None if creation failed
    """
    # Default to US country code if not provided
    if caller_country_code is None:
        caller_country_code = "+1"

    try:
        return create_call_record(
            load_id,
            daily_call_id,
            caller_number,
            caller_country_code,
            caller_mc,
            bot_phone,
        )
    except DatabaseOperationError:
        return None


def save_agreement(
    load_id: str,
    agreed_price: float,
    call_id: str | None = None,
    above_max: bool = False,
    carrier_contact_name: str | None = None,
    carrier_contact_phone: str | None = None,
) -> UUID | None:
    """Record a negotiation agreement or above-max bid.

    Args:
        load_id: UUID string of the load
        agreed_price: The final agreed price (or proposed price for above_max)
        call_id: UUID string of the call (optional)
        above_max: True if storing an above-max bid for follow-up
        carrier_contact_name: Contact name for above_max follow-up
        carrier_contact_phone: Contact phone for above_max follow-up

    Returns:
        Optional[UUID]: The created negotiation ID, or None if creation failed
    """
    try:
        result = NegotiationDBService.create_negotiation(
            load_id=load_id,
            agreed_price=agreed_price,
            above_max=above_max,
            carrier_contact_name=carrier_contact_name,
            carrier_contact_phone=carrier_contact_phone,
            call_id=call_id,
        )

        negotiation_id = UUID(result["id"]) if result.get("id") else None

        if negotiation_id and call_id:
            link_negotiation_to_call(UUID(call_id), negotiation_id)

        return negotiation_id

    except Exception as e:
        logger.warning(
            f"Failed to record {'above-max bid' if above_max else 'agreement'}: {e}"
        )
        return None


def finish_call(
    call_id: UUID,
    call_summary: dict[str, Any],
    end_reason: str | None = None,
    transcription: list[dict[str, Any]] | None = None,
) -> bool:
    """End a call and store final results.

    Args:
        call_id: UUID of the call to end
        call_summary: Final call data including transcription, summary, outcome, etc.
        end_reason: Reason for call ending - one of: 'abrupt', 'agreement', 'no_agreement', 'error'
        transcription: Structured transcript as list of {role, content, timestamp} dicts

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        end_call_record(call_id, call_summary, end_reason, transcription)
        return True
    except DatabaseOperationError:
        return False


def build_call_summary(
    outcome: str,
    transcription: str | None = None,
    agreed_price: float | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build a structured call summary for storage.

    Args:
        outcome: Call outcome (e.g., "agreement", "no_agreement", "disconnected")
        transcription: Full conversation transcription (optional)
        agreed_price: Final agreed price if agreement reached (optional)
        notes: Additional notes about the call (optional)

    Returns:
        Dict: Structured call summary data
    """
    summary = {"outcome": outcome}

    if transcription:
        summary["transcription"] = transcription

    if agreed_price is not None:
        summary["agreed_price"] = agreed_price

    if notes:
        summary["notes"] = notes

    return summary


def sanitize_universal_context_for_storage(
    messages: list[Any],
) -> list[dict[str, Any]]:
    """Sanitize universal context for safe JSON storage.

    Redacts binary payloads (e.g., inline image/audio data) and
    converts non-dict messages to a string representation.
    """
    sanitized: list[dict[str, Any]] = []

    for message in messages:
        if not isinstance(message, dict):
            sanitized.append(
                {
                    "type": "non_dict_message",
                    "value": str(message),
                }
            )
            continue

        msg = copy.deepcopy(message)

        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "image_url":
                    image_url = item.get("image_url", {})
                    if isinstance(image_url, dict):
                        url = image_url.get("url")
                        if isinstance(url, str) and url.startswith("data:image/"):
                            image_url["url"] = "data:image/..."
                if item.get("type") == "input_audio":
                    input_audio = item.get("input_audio", {})
                    if isinstance(input_audio, dict) and "data" in input_audio:
                        input_audio["data"] = "..."

        mime_type = msg.get("mime_type")
        if isinstance(mime_type, str) and mime_type.startswith("image/"):
            if "data" in msg:
                msg["data"] = "..."

        sanitized.append(msg)

    return sanitized


def snapshot_universal_context(context: Any) -> list[dict[str, Any]] | None:
    """Capture the final universal context from the LLM context object."""
    if context is None or not hasattr(context, "get_messages"):
        return None

    try:
        messages = context.get_messages()
    except Exception as e:
        logger.warning(f"Failed to read LLM context messages: {e}")
        return None

    return sanitize_universal_context_for_storage(messages)


# LLM Function Handlers for Pipecat


def _ensure_persistence_lock(context: Any) -> asyncio.Lock:
    """Lazily attach an asyncio.Lock to the LLMContext.

    The lock serializes phone_carrier_lookup writes from
    the backend carrier-confirmation path and the get_load_context
    defense-in-depth path. Without serialization a transient upsert
    failure in the first path races against the second path's flag check,
    so the second path
    skips its write before observing that the first one failed and the
    mapping is silently dropped for the rest of the call. With the lock
    plus the "set carrier_identity_confirmed only on success" rule, the
    second path acquires the lock only after the first path's upsert
    has fully completed, sees the up-to-date flag, and either skips
    (first succeeded) or retries (first failed).

    Lazy creation is safe under asyncio: there are no awaits between
    the getattr and the assignment, so two coroutines cannot interleave
    inside this helper.
    """
    lock = getattr(context, "_persistence_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        context._persistence_lock = lock
    return lock


async def _persist_phone_carrier_mapping(context: Any) -> bool:
    """Upsert the (caller_phone, MC) mapping to `phone_carrier_lookup`.

    Called from the backend carrier-confirmation path and
    `get_load_context` (defense-in-depth). By deferring the write to here
    (instead of writing eagerly inside `verify_carrier` immediately on
    tool success), we avoid caching MCs the caller never confirmed.

    Reads required state from the context:
      - caller_phone (set in run_bot)
      - caller_mc + carrier_name (set by verify_carrier on success, OR by
        the phone-first lookup in run_bot for a known-carrier greeting)
      - caller_dot_number (set by verify_carrier when present; None on
        the phone-first path since CarrierLookupResult doesn't carry it)
      - org_id (set in run_bot)

    Idempotent: the (org_id, phone_e164) unique constraint means repeat
    upserts overwrite the row in place. No-ops when any required field is
    missing (e.g. verify_carrier returned not_found, so no carrier_name).

    Returns True iff the upsert succeeded. Returns False on a transient
    Supabase failure or when required fields are missing. Callers use
    this to decide whether to revert the `carrier_identity_confirmed`
    flag so a later defense-in-depth retry can fire — see the call sites
    in `persist_confirmed_carrier_identity` and `get_load_context`.

    Failures are logged and swallowed — the LLM tool response should never
    break because of a Supabase write failure.
    """
    phone = getattr(context, "caller_phone", None)
    mc = getattr(context, "caller_mc", None)
    name = getattr(context, "carrier_name", None)
    org = getattr(context, "org_id", None)
    dot = getattr(context, "caller_dot_number", None)
    if not (phone and mc and name and org):
        logger.info(
            "Skipping phone_carrier_lookup upsert: "
            f"phone={phone!r} mc={mc!r} name={name!r} org={org!r}"
        )
        return False
    try:
        await asyncio.to_thread(
            NegotiationDBService.upsert_carrier_phone,
            phone_e164=phone,
            mc_number=mc,
            carrier_name=name,
            dot_number=dot,
            org_id=org,
        )
        logger.info(
            f"Recorded phone_carrier_lookup row: phone={phone} "
            f"mc={mc} carrier={name!r}"
        )
        return True
    except Exception:
        logger.exception("Failed to upsert phone_carrier_lookup; continuing")
        return False


async def persist_confirmed_carrier_identity(context: Any) -> bool:
    """Persist the currently staged carrier identity after verbal confirmation.

    This is intentionally backend-owned. The LLM should ask the natural
    follow-up question ("do you have a reference number?") but should not call
    a bookkeeping tool in the same streamed response.
    """
    lock = _ensure_persistence_lock(context)
    async with lock:
        if getattr(context, "carrier_identity_confirmed", False):
            return True
        if getattr(context, "identity_source", None) == "supabase":
            # Row already exists with identical data; flag the call as
            # confirmed so the defense-in-depth path also skips.
            context.carrier_identity_confirmed = True
            return True

        succeeded = await _persist_phone_carrier_mapping(context)
        if succeeded:
            context.carrier_identity_confirmed = True
        return succeeded


async def confirm_carrier_identity(
    function_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    llm: Any,
    context: Any,
    result_callback,
):
    """Legacy LLM tool wrapper kept for compatibility with older tests.

    Production no longer exposes this function to the LLM. Carrier identity
    confirmation is now handled from the transcript event path so the assistant
    never has to mix spoken text and this bookkeeping tool in one streamed turn.
    """
    _ = function_name, tool_call_id, llm, arguments
    await persist_confirmed_carrier_identity(context)
    await result_callback(
        json.dumps({"status": "ok"}),
        properties=FunctionCallResultProperties(run_llm=False),
    )


async def verify_carrier(
    function_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    llm: Any,
    context: Any,
    result_callback,
):
    """Function called by the LLM to verify carrier identity using MC number.

    This function handles:
    - Fetching carrier data from the carrier API using MC number
    - Extracting carrier name
    - Storing the MC number in context for later call record creation
    - Returning carrier name for confirmation
    - Proper error handling with appropriate responses

    Args:
        function_name: Name of the function being called (unused, required by Pipecat)
        tool_call_id: Unique identifier for this tool call (unused, required by Pipecat)
        arguments: Function arguments containing mc_number
        llm: LLM service instance (unused, required by Pipecat)
        context: Current conversation context
        result_callback: Callback to send results back to LLM
    """
    # Suppress unused parameter warnings
    _ = function_name, tool_call_id, llm

    mc_number = arguments.get("mc_number", "").strip()
    logger.info(f"Verifying carrier with MC number: {mc_number}")

    try:
        # Store MC in context regardless of whether it's found
        # This allows us to track invalid MC numbers in call records
        context.caller_mc = mc_number

        # Update the call record with MC if call_id exists
        if hasattr(context, "call_id") and context.call_id:
            try:
                update_call_mc(context.call_id, mc_number)
                logger.info(f"Updated call {context.call_id} with MC {mc_number}")
            except DatabaseOperationError as e:
                logger.error(f"Failed to update call with MC: {e}")

        # Fetch carrier data from API using MC number
        carrier_data = await fetch_carrier_by_mc(mc_number)

        if not carrier_data:
            result = {
                "status": "not_found",
                "message": f"No carrier found with MC number {mc_number}",
            }
            logger.warning(f"Carrier not found for MC: {mc_number}")
            await result_callback(json.dumps(result))
            return

        # Extract carrier name
        carrier_name = get_carrier_name(carrier_data)

        # Stage the verification result on context. The actual Supabase upsert
        # happens after the caller verbally confirms this staged carrier, with
        # get_load_context as a defense-in-depth fallback. Writing here would
        # cache carriers the human caller hasn't confirmed yet.
        context.carrier_name = carrier_name
        # A fresh verify_carrier supersedes any prior identity source — even
        # if the phone was originally Supabase-verified, this is a corrected
        # MC that needs to overwrite the stale row.
        context.identity_source = "verify_carrier"
        # New verification → previous confirmation no longer reflects truth.
        context.carrier_identity_confirmed = False
        context.awaiting_carrier_identity_confirmation = True
        inner = (
            carrier_data.get("data", carrier_data)
            if isinstance(carrier_data, dict)
            else {}
        )
        dot_value = inner.get("dotNumber") or inner.get("dot_number")
        context.caller_dot_number = str(dot_value) if dot_value is not None else None

        # Return success response with carrier name
        result = {
            "status": "success",
            "message": f"Carrier found: {carrier_name}",
            "carrier_name": carrier_name,
            "mc_number": mc_number,
        }

        logger.info(f"Successfully verified carrier: {carrier_name} (MC: {mc_number})")
        await result_callback(json.dumps(result))

    except CarrierServiceError as e:
        result = {"status": "error", "message": str(e)}
        logger.error(f"Carrier service error for MC {mc_number}: {e}")
        await result_callback(json.dumps(result))

    except Exception as e:
        result = {"status": "error", "message": f"Unexpected error: {e!s}"}
        logger.error(f"Unexpected error verifying carrier MC {mc_number}: {e}")
        await result_callback(json.dumps(result))


async def get_load_context(
    function_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    llm: Any,
    context: Any,
    result_callback,
    daily_call_id: str = None,
    caller_phone: str = None,
):
    """Function called by the LLM to retrieve load information from database.

    This function handles:
    - Fetching load data from Supabase
    - Normalizing the data
    - Building and updating the negotiation prompt
    - Creating call record with metadata
    - Proper error handling with appropriate responses

    Args:
        function_name: Name of the function being called (unused, required by Pipecat)
        tool_call_id: Unique identifier for this tool call (unused, required by Pipecat)
        arguments: Function arguments containing load_id
        llm: LLM service instance (unused, required by Pipecat)
        context: Current conversation context
        result_callback: Callback to send results back to LLM
        daily_call_id: Daily's call identifier (optional)
        caller_phone: Caller's phone number (optional)
    """
    # Suppress unused parameter warnings - these are required by Pipecat's function signature
    _ = function_name, tool_call_id, llm
    load_id = arguments.get("load_id", "").strip()

    # Reject empty or obviously-bogus load_id up front. The LLM sometimes
    # emits get_load_context before the caller has actually given a
    # reference number and fabricates a load_id from earlier-turn words
    # (e.g. "Noted down" pulled from "Yeah. Noted down. One two three four
    # five six."). Without this guard, the bogus value propagates into the
    # Salesforce query and produces a misleading "No load found" error,
    # AND consumes one of the caller's load-not-found retry strikes.
    #
    # A real reference is alphanumeric (with optional hyphens or
    # underscores) and contains at least one digit. Anything with spaces
    # or no digits at all is almost certainly speech-transcript junk the
    # LLM should have ignored.
    if not _is_plausible_load_reference(load_id):
        logger.warning(
            f"get_load_context called with implausible load_id={load_id!r} "
            "— likely a premature LLM tool call or fabricated from prior-turn "
            "words. Returning error so the LLM asks the caller for the "
            "reference."
        )
        await result_callback(json.dumps({
            "status": "error",
            "message": (
                "A reference number is required to look up the load. "
                "Please ask the caller to provide their reference number first."
            ),
        }))
        return

    logger.info(f"Retrieving load context for load_id: {load_id}")

    # Defense-in-depth: persist the carrier identity if the transcript-driven
    # confirmation path didn't already run for this call. This fallback only
    # fires after the caller provides a plausible load reference.
    #
    # Gated by the phone-first feature flag so flag=false produces zero
    # behavior change vs. the pre-PR baseline (no Supabase write triggered
    # from get_load_context). When the flag is off the entire phone_carrier
    # cache is dormant — both the upfront lookup AND this write path.
    #
    # Race- AND retry-safety: the shared asyncio.Lock + "set flag only on
    # success" rule means this fallback retries when the confirmation upsert
    # failed, and skips when confirmation succeeded.
    phone_first_enabled = (
        os.getenv("HIGHWAY_PHONE_LOOKUP_ENABLED", "false").lower() == "true"
    )
    if phone_first_enabled:
        await persist_confirmed_carrier_identity(context)

    # Get org_id from context for multi-tenant isolation
    org_id = getattr(context, "org_id", None)

    try:
        # Fetch load from database with org_id filter
        raw_load = NegotiationDBService.get_load_by_reference(load_id, org_id)
        if not raw_load:
            raise DatabaseOperationError(f"No load found with ID: {load_id}")

        # Normalize the data structure
        load_context = normalize_load_data(raw_load)

        # Build negotiation prompt with load details
        updated_system_prompt = build_negotiation_prompt(load_context)

        # Update the system message in context
        context.messages[0] = {"role": "system", "content": updated_system_prompt}

        # Store load UUID in context for later use
        context.load_uuid = raw_load["id"]

        # Store load context for Room2 transfer (human agent needs pricing info)
        context.load_context = load_context

        # Store caller phone in context for fallback in record_agreement
        context.caller_phone = caller_phone

        # Store transfer number for call transfer functionality.
        # KCH `public.loads.carrier_sales_rep_phone` is already E.164; the legacy
        # split (`transfer_country_code` + `transfer_call_to` digits) is kept
        # for fixtures that still mock that shape.
        context.transfer_call_to = (
            coerce_e164_transfer_number(load_context.get("transfer_call_to"))
            or build_transfer_phone_number(
                load_context.get("transfer_country_code"),
                load_context.get("transfer_call_to"),
            )
        )

        # Update the existing call record with the load_id
        try:
            update_call_load(context.call_id, raw_load["id"])
            logger.info(f"Updated call {context.call_id} with load {context.load_uuid}")
        except DatabaseOperationError as e:
            logger.error(f"Failed to update call with load_id: {e}")

        # Return success response
        result = {
            "status": "success",
            "message": f"Load {load_id} information retrieved successfully",
            "load_data": load_context,
            "call_id": str(context.call_id),
        }

        logger.info(f"Successfully loaded context for {load_id}")
        await result_callback(json.dumps(result))

    except DatabaseOperationError as e:
        result = {"status": "error", "message": str(e)}
        logger.error(f"Database error for load {load_id}: {e}")
        await result_callback(json.dumps(result))

    except Exception as e:
        result = {"status": "error", "message": f"Unexpected error: {e!s}"}
        logger.error(f"Unexpected error retrieving load {load_id}: {e}")
        await result_callback(json.dumps(result))


async def record_agreement(
    function_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    llm: Any,
    context: Any,
    result_callback,
):
    """Function called by the LLM to record a negotiation agreement or above-max bid."""
    _ = function_name, tool_call_id, llm

    agreed_price = arguments.get("agreed_price")
    above_max = arguments.get("above_max", False)
    carrier_contact_name = arguments.get("carrier_contact_name")
    carrier_contact_phone = arguments.get("carrier_contact_phone")

    # Use context values (stored by previous functions)
    load_uuid = getattr(context, "load_uuid", None)
    call_id = str(context.call_id) if hasattr(context, "call_id") else None

    # Fallback to caller's phone if carrier_contact_phone is empty
    if not carrier_contact_phone:
        carrier_contact_phone = getattr(context, "caller_phone", None)

    if not agreed_price or not load_uuid:
        await result_callback(
            json.dumps(
                {
                    "status": "error",
                    "message": "Missing agreed_price or load not loaded",
                }
            )
        )
        return

    if above_max and (not carrier_contact_name or not carrier_contact_phone):
        await result_callback(
            json.dumps(
                {
                    "status": "error",
                    "message": "above_max requires contact name and phone",
                }
            )
        )
        return

    try:
        price = float(agreed_price)
    except (ValueError, TypeError):
        await result_callback(
            json.dumps({"status": "error", "message": "Invalid price format"})
        )
        return

    try:
        negotiation_id = save_agreement(
            load_uuid,
            price,
            call_id,
            above_max,
            carrier_contact_name,
            carrier_contact_phone,
        )

        if not negotiation_id:
            await result_callback(
                json.dumps(
                    {"status": "error", "message": "Failed to record in database"}
                )
            )
            return

        if not above_max:
            load_context = getattr(context, "load_context", None) or {}
            load_name = load_context.get("load_id") or ""
            caller_mc = getattr(context, "caller_mc", None)
            caller_phone = getattr(context, "caller_phone", None)
            NegotiationDBService.notify_carrier_quote(
                load_name=load_name,
                agreed_price=price,
                mc_number=caller_mc,
                source_type="call",
                carrier_name=carrier_contact_name,
                carrier_phone=carrier_contact_phone or caller_phone,
            )

        msg = (
            f"Above-max bid stored. We'll contact {carrier_contact_name} if conditions change."
            if above_max
            else f"Agreement recorded at ${price}"
        )
        logger.info(
            f"{'Above-max bid' if above_max else 'Agreement'}: ${price}"
            + (f" from {carrier_contact_name}" if above_max else "")
        )
        await result_callback(
            json.dumps(
                {
                    "status": "success",
                    "message": msg,
                    "negotiation_id": str(negotiation_id),
                }
            )
        )

    except (DatabaseOperationError, Exception) as e:
        logger.error(f"Error recording agreement: {e}")
        await result_callback(json.dumps({"status": "error", "message": str(e)}))


async def end_call(
    function_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    llm: Any,
    context: Any,
    result_callback,
    task: Any = None,
):
    """Function called by the LLM to end the call with a specific reason.

    This function stores the end reason in the context and queues an EndFrame to terminate the call.

    Args:
        function_name: Name of the function being called (unused, required by Pipecat)
        tool_call_id: Unique identifier for this tool call (unused, required by Pipecat)
        arguments: Function arguments containing reason
        llm: LLM service instance (unused, required by Pipecat)
        context: Current conversation context
        result_callback: Callback to send results back to LLM
        task: Pipeline task to queue EndFrame (optional)

    Expected arguments:
        reason: One of 'abrupt', 'agreement', 'no_agreement', 'error', 'load_not_found', 'mc_not_found'
    """
    _ = function_name, tool_call_id, llm

    if getattr(context, "call_mode", None) == "HUMAN_ONLY":
        logger.info("Blocking end_call: call already transferred to human")

        await result_callback(
            json.dumps(
                {
                    "status": "ignored",
                    "message": "Call already transferred to human. end_call ignored.",
                }
            )
        )
        return

    print("Bot called end_call function")

    reason = arguments.get("reason")

    # Validate reason
    valid_reasons = [
        "abrupt",
        "agreement",
        "no_agreement",
        "error",
        "load_not_found",
        "mc_not_found",
        "bid_placed",
    ]
    if not reason or reason not in valid_reasons:
        result = {
            "status": "error",
            "message": f"Invalid reason. Must be one of: {', '.join(valid_reasons)}",
        }
        await result_callback(json.dumps(result))
        return

    try:
        # Store the end reason in the context for later use
        # Don't save here - let on_client_disconnected save after all messages are captured
        context.end_reason = reason
        logger.info(f"End reason set to: {reason}")

        # Queue EndFrame to terminate the call if task is provided
        if task:
            await task.queue_frames([EndFrame()])
            logger.info("EndFrame queued - call will terminate")

        result = {
            "status": "success",
            "message": f"Call ending with reason: {reason}",
        }
        logger.info(f"End call requested with reason: {reason}")

        await result_callback(json.dumps(result))

    except Exception as e:
        result = {"status": "error", "message": f"Unexpected error: {e!s}"}
        logger.error(f"Unexpected error in end_call: {e}")
        await result_callback(json.dumps(result))
