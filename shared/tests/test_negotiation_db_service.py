"""Tests for NegotiationDBService load reads against KCH `public.loads`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.negotiation_db_service import (
    LANE_SEARCH_CANDIDATE_LIMIT,
    NegotiationDBService,
    _decorate_load_record,
)


def _build_mock_client(
    rows_by_query: dict[tuple[str, str], list[dict]],
    *,
    biddable_rows: list[dict] | None = None,
    capture_chain: list[tuple] | None = None,
) -> MagicMock:
    """Build a fake Supabase client.

    Two query patterns are supported:

    - ``.select(...).eq(col, val).limit(n).execute()`` — used by `get_load*`
      lookups. Returns the rows mapped to that ``(col, val)`` pair from
      ``rows_by_query``.
    - ``.select(...).eq("ready_to_cover", True).limit(n).execute()`` — used
      by lane search. Returns ``biddable_rows``. Set ``capture_chain`` to a
      list to record the ``("eq", col, val)`` and ``("limit", n)`` calls
      made along the chain so tests can assert them.
    """
    client = MagicMock()
    table = client.table.return_value
    biddable = biddable_rows or []

    def select_side_effect(*_args, **_kwargs):
        select = MagicMock()

        def eq_side_effect(column: str, value):
            if capture_chain is not None:
                capture_chain.append(("eq", column, value))
            eq = MagicMock()

            def limit_side_effect(n: int):
                if capture_chain is not None:
                    capture_chain.append(("limit", n))
                limit = MagicMock()
                if column == "ready_to_cover":
                    limit.execute.return_value = MagicMock(data=biddable)
                else:
                    limit.execute.return_value = MagicMock(
                        data=rows_by_query.get((column, value), [])
                    )
                return limit

            eq.limit.side_effect = limit_side_effect
            return eq

        select.eq.side_effect = eq_side_effect
        return select

    table.select.side_effect = select_side_effect
    return client


class GetLoadTests(unittest.TestCase):
    def setUp(self):
        pass

    def _patch_db(self, rows_by_query: dict[tuple[str, str], list[dict]]):
        client = _build_mock_client(rows_by_query)
        return patch.object(NegotiationDBService, "_db", return_value=client)

    def test_matches_by_load_number_first(self):
        with self._patch_db(
            {("load_number", "KCH-1001"): [{"load_number": "KCH-1001", "customer_name": "Acme"}]}
        ):
            result = NegotiationDBService.get_load("KCH-1001")
        assert result is not None
        self.assertEqual(result["load_number"], "KCH-1001")
        self.assertEqual(result["id"], "KCH-1001")
        self.assertEqual(result["load_id"], "KCH-1001")

    def test_falls_back_to_salesforce_load_id(self):
        with self._patch_db(
            {
                ("load_number", "a1GTQ0000001"): [],
                ("salesforce_load_id", "a1GTQ0000001"): [
                    {"load_number": "KCH-1001", "salesforce_load_id": "a1GTQ0000001"}
                ],
            }
        ):
            result = NegotiationDBService.get_load("a1GTQ0000001")
        assert result is not None
        self.assertEqual(result["load_number"], "KCH-1001")

    def test_returns_none_when_neither_matches(self):
        with self._patch_db(
            {
                ("load_number", "missing"): [],
                ("salesforce_load_id", "missing"): [],
            }
        ):
            self.assertIsNone(NegotiationDBService.get_load("missing"))

    def test_empty_load_id_returns_none_without_db_call(self):
        with patch.object(NegotiationDBService, "_db") as db:
            self.assertIsNone(NegotiationDBService.get_load(""))
            db.assert_not_called()


class GetLoadByReferenceTests(unittest.TestCase):
    def test_uses_load_number_lookup(self):
        client = _build_mock_client(
            {("load_number", "KCH-1001"): [{"load_number": "KCH-1001"}]}
        )
        with patch.object(NegotiationDBService, "_db", return_value=client):
            result = NegotiationDBService.get_load_by_reference("KCH-1001")
        assert result is not None
        self.assertEqual(result["load_number"], "KCH-1001")
        self.assertEqual(result["id"], "KCH-1001")


class SearchLoadsByLocationTests(unittest.TestCase):
    def test_returns_empty_without_any_lane_filters(self):
        with patch.object(NegotiationDBService, "_db") as db:
            result = NegotiationDBService.search_loads_by_location()

        self.assertEqual(result, [])
        db.assert_not_called()

    def test_matches_pickup_and_dropoff_stops(self):
        client = _build_mock_client(
            {},
            biddable_rows=[
                {
                    "load_number": "KCH-1001",
                    "stops": [
                        {
                            "stop_number": 1,
                            "stop_city": "Atlanta",
                            "state_code": "GA",
                            "is_pickup": True,
                            "is_dropoff": False,
                        },
                        {
                            "stop_number": 2,
                            "stop_city": "Chicago",
                            "state_code": "IL",
                            "is_pickup": False,
                            "is_dropoff": True,
                        },
                    ],
                },
                {
                    "load_number": "KCH-1002",
                    "stops": [
                        {
                            "stop_number": 1,
                            "stop_city": "Dallas",
                            "state_code": "TX",
                            "is_pickup": True,
                            "is_dropoff": False,
                        },
                        {
                            "stop_number": 2,
                            "stop_city": "Denver",
                            "state_code": "CO",
                            "is_pickup": False,
                            "is_dropoff": True,
                        },
                    ],
                },
            ],
        )
        with patch.object(NegotiationDBService, "_db", return_value=client):
            result = NegotiationDBService.search_loads_by_location(
                origin_city="Atl",
                origin_state="GA",
                destination_city="Chicago",
                destination_state="IL",
            )

        self.assertEqual([load["load_number"] for load in result], ["KCH-1001"])
        self.assertEqual(result[0]["id"], "KCH-1001")

    def test_returns_empty_when_lane_does_not_match(self):
        client = _build_mock_client(
            {},
            biddable_rows=[
                {
                    "load_number": "KCH-1001",
                    "stops": [
                        {"stop_number": 1, "stop_city": "Atlanta", "state_code": "GA", "is_pickup": True},
                        {"stop_number": 2, "stop_city": "Chicago", "state_code": "IL", "is_dropoff": True},
                    ],
                }
            ],
        )
        with patch.object(NegotiationDBService, "_db", return_value=client):
            result = NegotiationDBService.search_loads_by_location(destination_city="Dallas")
        self.assertEqual(result, [])

    def test_query_filters_ready_to_cover_and_caps_results_server_side(self):
        """Email auto-match must never see non-biddable loads, and the candidate
        fetch must be deterministically bounded — not silently relying on
        PostgREST's default page size."""
        captured: list[tuple] = []
        client = _build_mock_client(
            {},
            biddable_rows=[],
            capture_chain=captured,
        )
        with patch.object(NegotiationDBService, "_db", return_value=client):
            NegotiationDBService.search_loads_by_location(origin_city="Atlanta")

        self.assertIn(("eq", "ready_to_cover", True), captured)
        self.assertIn(("limit", LANE_SEARCH_CANDIDATE_LIMIT), captured)


class DecorateLoadRecordTests(unittest.TestCase):
    def test_aliases_load_number_to_id_and_load_id(self):
        record = {"load_number": "KCH-1001", "customer_name": "Acme"}
        decorated = _decorate_load_record(record)
        assert decorated is not None
        self.assertEqual(decorated["id"], "KCH-1001")
        self.assertEqual(decorated["load_id"], "KCH-1001")

    def test_does_not_overwrite_existing_id(self):
        record = {"load_number": "KCH-1001", "id": "preset"}
        decorated = _decorate_load_record(record)
        assert decorated is not None
        self.assertEqual(decorated["id"], "preset")

    def test_passes_through_none(self):
        self.assertIsNone(_decorate_load_record(None))


if __name__ == "__main__":
    unittest.main()
