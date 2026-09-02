"""Database operations for calls and negotiations.

This module provides pure database operations without business logic.
All functions raise exceptions on errors for proper error handling.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from loguru import logger
from supabase import Client

from src import SupabaseService


@dataclass
class CallRecordResult:
    """Result from creating a call record."""

    call_id: UUID
    org_id: str | None


class DatabaseOperationError(Exception):
    """Raised when a database operation fails."""

    pass


def _get_supabase_client() -> Client:
    """Get Supabase client."""
    return SupabaseService.get_client()


def get_org_id_for_phone(bot_phone: str) -> str | None:
    """Lookup org_id from phone_numbers table based on bot phone number."""
    if not bot_phone:
        return None

    try:
        supabase = _get_supabase_client()
        response = (
            supabase.table("phone_numbers")
            .select("org_id")
            .eq("phone_number", bot_phone)
            .single()
            .execute()
        )
        return response.data.get("org_id") if response.data else None
    except Exception:
        logger.warning(f"Phone {bot_phone} not found in phone_numbers table")
        return None


def get_org_name_for_phone(bot_phone: str) -> str | None:
    """Lookup organization name from phone_numbers table based on bot phone number.

    Args:
        bot_phone: The phone number the caller dialed

    Returns:
        Organization name if found, None otherwise
    """
    if not bot_phone:
        return None

    try:
        supabase = _get_supabase_client()
        response = (
            supabase.table("phone_numbers")
            .select("org_id, organizations(name)")
            .eq("phone_number", bot_phone)
            .single()
            .execute()
        )
        if response.data and response.data.get("organizations"):
            return response.data["organizations"].get("name")
        return None
    except Exception:
        logger.warning(f"Could not get org name for phone {bot_phone}")
        return None


def create_call_record(
    load_id: UUID | None = None,
    daily_call_id: str | None = None,
    caller_number: str | None = None,
    caller_country_code: str | None = None,
    caller_mc: str | None = None,
    bot_phone: str | None = None,
) -> CallRecordResult:
    """Create a new call record in the database.

    Args:
        load_id: UUID of the load being negotiated (optional, can be added later)
        daily_call_id: Daily's call identifier (optional)
        caller_number: Phone number of the caller (optional)
        caller_country_code: Country code of the caller (optional)
        caller_mc: MC (Motor Carrier) number of the caller (optional)
        bot_phone: Phone number the caller dialed (used for org_id lookup)

    Returns:
        CallRecordResult: Contains call_id and org_id for multi-tenant context

    Raises:
        DatabaseOperationError: If database is unavailable or insert fails
    """
    supabase = _get_supabase_client()

    try:
        org_id = get_org_id_for_phone(bot_phone)

        call_data = {
            "load_id": str(load_id) if load_id else None,
            "daily_call_id": daily_call_id,
            "caller_number": caller_number,
            "caller_country_code": caller_country_code,
            "org_id": org_id,
            "result": {},
        }

        if caller_mc:
            call_data["caller_mc"] = caller_mc

        response = supabase.table("calls").insert(call_data).execute()

        if not response.data or len(response.data) == 0:
            raise DatabaseOperationError("Insert returned no data")

        call_id = response.data[0]["id"]
        logger.info(
            f"Created call record: {call_id} (Daily: {daily_call_id}, Org: {org_id})"
        )
        return CallRecordResult(call_id=UUID(call_id), org_id=org_id)

    except Exception as e:
        logger.error(f"Failed to create call record: {e}")
        raise DatabaseOperationError(f"Failed to create call record: {e!s}")


def update_call_load(call_id: UUID, load_id: str | UUID) -> None:
    """Update the load_id for an existing call record.

    Args:
        call_id: UUID of the call to update
        load_id: Load identifier (Salesforce 18-char Id or UUID string)

    Raises:
        DatabaseOperationError: If database is unavailable or update fails
    """
    supabase = _get_supabase_client()

    try:
        supabase.table("calls").update({"load_id": str(load_id)}).eq(
            "id", str(call_id)
        ).execute()

        logger.info(f"Updated call {call_id} with load_id: {load_id}")

    except Exception as e:
        logger.error(f"Failed to update call load_id: {e}")
        raise DatabaseOperationError(f"Failed to update call load_id: {e!s}")


def update_call_mc(call_id: UUID, caller_mc: str) -> None:
    """Update the caller_mc for an existing call record.

    Args:
        call_id: UUID of the call to update
        caller_mc: MC (Motor Carrier) number of the caller

    Raises:
        DatabaseOperationError: If database is unavailable or update fails
    """
    supabase = _get_supabase_client()

    try:
        supabase.table("calls").update({"caller_mc": caller_mc}).eq(
            "id", str(call_id)
        ).execute()

        logger.info(f"Updated call {call_id} with MC: {caller_mc}")

    except Exception as e:
        logger.error(f"Failed to update caller_mc: {e}")
        raise DatabaseOperationError(f"Failed to update caller_mc: {e!s}")


def update_call_result(call_id: UUID, result_data: dict[str, Any]) -> None:
    """Update the result data for a call.

    Args:
        call_id: UUID of the call to update
        result_data: Dictionary containing call result data (transcription, summary, etc.)

    Raises:
        DatabaseOperationError: If database is unavailable or update fails
    """
    supabase = _get_supabase_client()

    try:
        supabase.table("calls").update({"result": result_data}).eq(
            "id", str(call_id)
        ).execute()

        logger.info(f"Updated call result for: {call_id}")

    except Exception as e:
        logger.error(f"Failed to update call result: {e}")
        raise DatabaseOperationError(f"Failed to update call result: {e!s}")


def end_call_record(
    call_id: UUID,
    result_data: dict[str, Any],
    end_reason: str | None = None,
    transcription: list[dict[str, Any]] | None = None,
) -> None:
    """Mark a call as ended and store final result data.

    Args:
        call_id: UUID of the call to end
        result_data: Final call data including transcription and summary
        end_reason: Reason for call ending - one of: 'abrupt', 'agreement', 'no_agreement', 'error'
        transcription: Structured transcript as list of {role, content, timestamp} dicts

    Raises:
        DatabaseOperationError: If database is unavailable or update fails
    """
    supabase = _get_supabase_client()

    try:
        result_payload = dict(result_data)
        universal_context = result_payload.pop("universal_context", None)
        universal_context_captured_at = result_payload.pop(
            "universal_context_captured_at", None
        )

        update_data: dict[str, Any] = {"result": result_payload, "ended_at": "NOW()"}
        if end_reason:
            update_data["end_reason"] = end_reason
        if transcription is not None:
            update_data["transcription"] = (
                transcription  # JSONB column accepts list directly
            )
        if universal_context is not None:
            update_data["universal_context"] = universal_context
        if universal_context_captured_at is not None:
            update_data["universal_context_captured_at"] = (
                universal_context_captured_at
            )

        supabase.table("calls").update(update_data).eq("id", str(call_id)).execute()

        logger.info(f"Ended call record: {call_id} with reason: {end_reason}")

    except Exception as e:
        logger.error(f"Failed to end call record: {e}")
        raise DatabaseOperationError(f"Failed to end call record: {e!s}")


def link_negotiation_to_call(call_id: UUID, negotiation_id: UUID) -> None:
    """Link a negotiation result to a call.

    Args:
        call_id: UUID of the call
        negotiation_id: UUID of the negotiation to link

    Raises:
        DatabaseOperationError: If database is unavailable or update fails
    """
    supabase = _get_supabase_client()

    try:
        supabase.table("calls").update({"negotiation_result": str(negotiation_id)}).eq(
            "id", str(call_id)
        ).execute()

        logger.info(f"Linked negotiation {negotiation_id} to call {call_id}")

    except Exception as e:
        logger.error(f"Failed to link negotiation to call: {e}")
        raise DatabaseOperationError(f"Failed to link negotiation to call: {e!s}")
