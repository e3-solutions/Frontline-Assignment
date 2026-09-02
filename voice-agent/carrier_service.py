"""
Carrier verification service for MC and USDOT number lookup.

MC lookups dispatch to one of two backends based on the CARRIER_MC_BACKEND env
var: "carrier_api" (default, legacy Railway endpoint) or "highway" (new, via
the Highway API client in the shared package). Return shape is identical in
both paths so `call_helpers.verify_carrier` needs no changes.
"""

import os
from typing import Any

import httpx
from loguru import logger

from src import HighwayAPI, HighwayAPIError, humanize_carrier_name


class CarrierServiceError(Exception):
    """Exception raised for carrier service errors."""
    pass


CARRIER_API_BASE_URL = "https://carrier-api-production-cc59.up.railway.app"


async def _fetch_carrier_record(url: str) -> dict[str, Any] | None:
    """
    Internal helper to fetch carrier data from the API with unified error handling.

    Args:
        url: The full API URL to fetch

    Returns:
        Dictionary containing carrier information, or None if not found

    Raises:
        CarrierServiceError: If the API request fails
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                raise CarrierServiceError(
                    f"Carrier API returned status {response.status_code}"
                )

            return response.json()

    except CarrierServiceError:
        raise
    except httpx.TimeoutException as e:
        raise CarrierServiceError("Carrier API request timed out") from e
    except httpx.RequestError as e:
        raise CarrierServiceError(f"Carrier API request failed: {e}") from e
    except Exception as e:
        raise CarrierServiceError(f"Unexpected error: {e}") from e


def _clean_number(value: str) -> str:
    """Remove any non-numeric characters from a string."""
    return "".join(filter(str.isdigit, str(value)))


async def fetch_carrier_by_dot(dot_number: str) -> dict[str, Any] | None:
    """
    Fetch carrier information from the carrier API using USDOT number.

    Args:
        dot_number: The USDOT number (can be string or numeric)

    Returns:
        Dictionary containing carrier information, or None if not found

    Raises:
        CarrierServiceError: If the API request fails
    """
    clean_dot = _clean_number(dot_number)

    if not clean_dot:
        raise CarrierServiceError(f"Invalid USDOT number: {dot_number}")

    return await _fetch_carrier_record(f"{CARRIER_API_BASE_URL}/records/DOT/{clean_dot}")


async def fetch_carrier_by_mc(mc_number: str) -> dict[str, Any] | None:
    """
    Fetch carrier information using MC (Motor Carrier) number.

    Routes to Highway or the legacy Carrier API based on CARRIER_MC_BACKEND.
    Default backend is "carrier_api" (zero-risk rollout). Unknown values log a
    warning and fall back to carrier_api.

    Args:
        mc_number: The MC number (can be string or numeric)

    Returns:
        Dictionary containing carrier information, or None if not found.
        Shape is consistent across backends: {"data": {"dbaName": ..., ...}}.

    Raises:
        CarrierServiceError: If the backend request fails
    """
    clean_mc = _clean_number(mc_number)

    if not clean_mc:
        raise CarrierServiceError(f"Invalid MC number: {mc_number}")

    backend = os.getenv("CARRIER_MC_BACKEND", "carrier_api").lower()
    if backend == "highway":
        return await _fetch_via_highway(clean_mc)
    if backend != "carrier_api":
        logger.warning(
            f"Unknown CARRIER_MC_BACKEND={backend!r}, falling back to carrier_api"
        )

    return await _fetch_carrier_record(f"{CARRIER_API_BASE_URL}/records/mc/{clean_mc}")


async def _fetch_via_highway(mc: str) -> dict[str, Any] | None:
    """Look up an MC via the Highway client and translate to the carrier_api shape."""
    api = HighwayAPI()
    try:
        result = await api.lookup_carrier_by_mc(mc)
    except HighwayAPIError as exc:
        raise CarrierServiceError(f"Highway MC lookup failed: {exc}") from exc
    finally:
        await api.close()

    if result.status != "known_carrier":
        return None

    return {
        "data": {
            "dbaName": result.carrier_name,
            "mcNumber": result.mc_number,
        }
    }


def get_carrier_name(carrier_data: dict[str, Any]) -> str:
    """
    Extract carrier name from carrier data.
    Prioritizes dbaName (doing business as) over legalName for better recognition.

    Args:
        carrier_data: Dictionary containing carrier information from the API

    Returns:
        Carrier name as string
    """
    # Check data wrapper first (API returns {success: true, data: {...}})
    data = carrier_data.get("data", carrier_data)

    # Prioritize DBA name as it's what carriers commonly use
    if data.get("dbaName"):
        return humanize_carrier_name(str(data["dbaName"])) or "Unknown Carrier"

    # Fall back to legal name
    if data.get("legalName"):
        return humanize_carrier_name(str(data["legalName"])) or "Unknown Carrier"

    return "Unknown Carrier"
