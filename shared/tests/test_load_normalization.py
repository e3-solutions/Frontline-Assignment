"""Focused tests for load normalization."""

from __future__ import annotations

import unittest

from src.load_normalization import (
    _normalize_caps_text,
    normalize_load_data,
    normalize_load_record,
)


class LoadNormalizationTests(unittest.TestCase):
    def test_normalizes_column_based_record(self):
        raw_load = {
            "load_id": "9206420",
            "origin_city": "Atlanta",
            "origin_state": "GA",
            "destination_city": "Chicago",
            "destination_state": "IL",
            "start_rate": None,
            "book_now_rate": None,
            "max_rate": None,
            "equipment": "Van",
            "commodity": "General Goods",
            "special_instructions": "Must deliver before noon",
            "tracker_required": True,
        }

        normalized = normalize_load_record(raw_load)

        self.assertEqual(normalized["id"], "9206420")
        self.assertEqual(normalized["load_id"], "9206420")
        self.assertEqual(normalized["origin"]["city"], "Atlanta")
        self.assertEqual(normalized["destination"]["state"], "IL")
        self.assertEqual(normalized["startRate"], 0)
        self.assertEqual(normalized["bookNowRate"], 0)
        self.assertEqual(normalized["maxRate"], 0)
        self.assertEqual(normalized["specialInstructions"], "Must deliver before noon")
        self.assertTrue(normalized["trackerRequired"])

    def test_normalizes_legacy_data_for_backfill_tools(self):
        raw_data = {
            "load_id": "32819321",
            "origin_location": "Dallas, TX",
            "destination_location": "New York, NY",
            "broker_initial_offer": "1200",
            "broker_target_rate": "1500",
            "broker_max_rate": "2000",
            "requirements": "Must check in at pickup",
            "pickup_date": "2026-03-24",
            "transfer_call_to": "(123) 132-1312",
            "transfer_country_code": "+1",
            "tracker_required": True,
        }

        normalized = normalize_load_data(raw_data)

        self.assertEqual(normalized["id"], "32819321")
        self.assertEqual(normalized["load_id"], "32819321")
        self.assertEqual(normalized["origin"]["city"], "Dallas")
        self.assertEqual(normalized["origin"]["state"], "TX")
        self.assertEqual(normalized["destination"]["city"], "New York")
        self.assertEqual(normalized["pickupTime"], "2026-03-24")
        self.assertEqual(normalized["startRate"], 1200)
        self.assertEqual(normalized["bookNowRate"], 1500)
        self.assertEqual(normalized["maxRate"], 2000)
        self.assertEqual(normalized["specialInstructions"], "Must check in at pickup")
        self.assertTrue(normalized["trackerRequired"])
        self.assertEqual(normalized["transfer_call_to"], "(123) 132-1312")

    def test_ignores_legacy_data_when_normalizing_db_record(self):
        raw_load = {
            "load_id": "5050",
            "origin_city": "Memphis",
            "origin_state": "TN",
            "destination_city": "Nashville",
            "destination_state": "TN",
            "start_rate": 1620,
            "book_now_rate": 1620,
            "max_rate": 1800,
            "data": {
                "id": "9305685",
                "origin": {"city": "Atlanta", "state": "GA"},
                "destination": {"city": "Chicago", "state": "IL"},
                "startRate": 1000,
                "bookNowRate": 1100,
                "maxRate": 1200,
            },
        }

        normalized = normalize_load_record(raw_load)

        self.assertEqual(normalized["id"], "5050")
        self.assertEqual(normalized["load_id"], "5050")
        self.assertEqual(normalized["origin"]["city"], "Memphis")
        self.assertEqual(normalized["destination"]["city"], "Nashville")
        self.assertEqual(normalized["startRate"], 1620)
        self.assertEqual(normalized["bookNowRate"], 1620)
        self.assertEqual(normalized["maxRate"], 1800)
        self.assertFalse(normalized["trackerRequired"])


    def test_normalizes_salesforce_rtms_load(self):
        sf_record = {
            "attributes": {"type": "rtms__Load__c", "url": "/services/data/v61.0/sobjects/rtms__Load__c/a1GTQ000008EiIE2A0"},
            "Id": "a1GTQ000008EiIE2A0",
            "Name": "9391159",
            "rtms__Origin__c": "Evans, Georgia",
            "rtms__Destination__c": "San Antonio, Texas",
            "rtms__Expected_Ship_Date2__c": "2026-04-10",
            "rtms__Expected_Delivery_Date2__c": "2026-04-13",
            "Pickup_Date_Time__c": None,
            "Delivery_Date_Time__c": None,
            "KCH_Equipment_Type_Name__c": "Dry Van 53'",
            "rtms__Cargo_Summary__c": "Test, 40000 lbs",
            "rtms__Hazardous_Materials__c": False,
            "Carrier_Ratecon_Comments__c": "DRIVER MUST ACCEPT TRACKING TOOLS",
            "After_Hour_Tracking_Required__c": False,
            "rtms__Offer_Rate__c": 700,
            "Greenscreens_Target_Buy_Rate__c": 800,
            "rtms__Max_Pay_Amount__c": 900,
            "rtms__Carrier_Quote_Total__c": 800,
            "First_Stop_Location_Name__c": "KURTIS TEST CUSTOMER",
            "rtms__Total_Weight__c": 40000,
            "Dispatch_Phone__c": "630-828-6311 ext 118",
        }

        normalized = normalize_load_record(sf_record)

        self.assertEqual(normalized["id"], "9391159")
        self.assertEqual(normalized["load_id"], "9391159")
        self.assertEqual(normalized["id"], normalized["load_id"])
        self.assertEqual(normalized["origin"]["city"], "Evans")
        self.assertEqual(normalized["origin"]["state"], "Georgia")
        self.assertEqual(normalized["destination"]["city"], "San Antonio")
        self.assertEqual(normalized["destination"]["state"], "Texas")
        self.assertEqual(normalized["pickupTime"], "2026-04-10")
        self.assertEqual(normalized["dropoffTime"], "2026-04-13")
        self.assertEqual(normalized["equipment"], "Dry Van 53'")
        self.assertEqual(normalized["commodity"], "Test, 40000 lbs")
        self.assertFalse(normalized["isHazmat"])
        self.assertEqual(normalized["startRate"], 700)
        self.assertEqual(normalized["bookNowRate"], 800)
        self.assertEqual(normalized["maxRate"], 900)
        self.assertEqual(normalized["bookedRate"], 800)
        self.assertEqual(normalized["customerName"], "KURTIS TEST CUSTOMER")
        self.assertEqual(normalized["weight"], 40000)
        self.assertEqual(normalized["transfer_call_to"], "630-828-6311 ext 118")

    def test_detects_salesforce_load_without_attributes_envelope(self):
        record = {
            "Id": "a1GTQ000008EiIE2A0",
            "Name": "9391159",
            "rtms__Origin__c": "Evans, GA",
            "rtms__Destination__c": "San Antonio, TX",
            "rtms__Load_Status__c": "Tendered",
        }

        normalized = normalize_load_record(record)

        self.assertEqual(normalized["id"], "9391159")
        self.assertEqual(normalized["load_id"], "9391159")
        self.assertEqual(normalized["origin"]["state"], "GA")

    def test_salesforce_name_wins_for_prompt_facing_identifier(self):
        record = {
            "attributes": {"type": "rtms__Load__c"},
            "Id": "a1GTQ000008EiIE2A0",
            "Name": "9391159",
        }

        normalized = normalize_load_record(record)

        self.assertEqual(normalized["id"], "9391159")
        self.assertEqual(normalized["load_id"], "9391159")

    def test_salesforce_identifier_falls_back_to_id_when_name_missing(self):
        record = {
            "attributes": {"type": "rtms__Load__c"},
            "Id": "a1GTQ000008EiIE2A0",
            "Name": "",
        }

        normalized = normalize_load_record(record)

        self.assertEqual(normalized["id"], "a1GTQ000008EiIE2A0")
        self.assertEqual(normalized["load_id"], "a1GTQ000008EiIE2A0")


class NormalizeCapsTextTests(unittest.TestCase):
    def test_cor_951_transcript_repro(self):
        raw = (
            "TIME in at delivery must be put on BOL Job # required. "
            "DRIVER MUST ACCEPT TRACKING TOOLS, APPOINTMENT REQUIRED FOR ALL DELIVERYS."
        )
        expected = (
            "Time in at delivery must be put on BOL Job # required. "
            "Driver must accept tracking tools, appointment required for all deliverys."
        )
        self.assertEqual(_normalize_caps_text(raw), expected)

    def test_preserves_whitelisted_acronyms(self):
        raw = "POD required on delivery. ETA by noon. Call DOT if delayed."
        self.assertEqual(_normalize_caps_text(raw), raw)

    def test_sentence_case_input_unchanged(self):
        raw = "Must deliver before noon"
        self.assertEqual(_normalize_caps_text(raw), raw)

    def test_preserves_mixed_alphanumeric_identifier(self):
        raw = "SEND BOL TO DISPATCH, REFERENCE a1GTQ000008EiIE2A0."
        expected = "Send BOL to dispatch, reference a1GTQ000008EiIE2A0."
        self.assertEqual(_normalize_caps_text(raw), expected)

    def test_none_and_empty_passthrough(self):
        self.assertIsNone(_normalize_caps_text(None))
        self.assertIsNone(_normalize_caps_text(""))
        self.assertIsNone(_normalize_caps_text("   "))

    def test_is_idempotent(self):
        raw = "DRIVER MUST CONFIRM PICKUP BEFORE LEAVING."
        once = _normalize_caps_text(raw)
        twice = _normalize_caps_text(once)
        self.assertEqual(once, "Driver must confirm pickup before leaving.")
        self.assertEqual(once, twice)

    def test_salesforce_load_instructions_and_commodity_normalized(self):
        sf_record = {
            "attributes": {"type": "rtms__Load__c"},
            "Id": "a1GTQ000008EiIE2A0",
            "Name": "9391159",
            "rtms__Origin__c": "Evans, Georgia",
            "rtms__Destination__c": "San Antonio, Texas",
            "rtms__Cargo_Summary__c": "FROZEN FOOD",
            "Carrier_Ratecon_Comments__c": (
                "DRIVER MUST ACCEPT TRACKING TOOLS, APPOINTMENT REQUIRED FOR ALL DELIVERYS. "
                "BOL REQUIRED AT DELIVERY."
            ),
        }
        normalized = normalize_load_record(sf_record)
        self.assertEqual(normalized["commodity"], "Frozen food")
        self.assertEqual(
            normalized["specialInstructions"],
            (
                "Driver must accept tracking tools, appointment required for all deliverys. "
                "BOL required at delivery."
            ),
        )

    def test_legacy_column_record_instructions_and_commodity_normalized(self):
        raw_load = {
            "load_id": "9391159",
            "origin_city": "Evans",
            "origin_state": "GA",
            "destination_city": "San Antonio",
            "destination_state": "TX",
            "commodity": "FROZEN FOOD",
            "special_instructions": "DRIVER MUST CONFIRM PICKUP",
        }
        normalized = normalize_load_record(raw_load)
        self.assertEqual(normalized["commodity"], "Frozen food")
        self.assertEqual(normalized["specialInstructions"], "Driver must confirm pickup")

    def test_normalize_load_data_applies_to_requirements(self):
        raw_data = {
            "load_id": "32819321",
            "origin_location": "Dallas, TX",
            "destination_location": "New York, NY",
            "requirements": "DRIVER MUST CONFIRM PICKUP",
            "commodity": "FROZEN FOOD",
        }
        normalized = normalize_load_data(raw_data)
        self.assertEqual(normalized["commodity"], "Frozen food")
        self.assertEqual(normalized["specialInstructions"], "Driver must confirm pickup")


class KchLoadsNormalizationTests(unittest.TestCase):
    """Tests for the KCH `public.loads` row → canonical NormalizedLoad mapping."""

    def _base_row(self) -> dict:
        return {
            "load_number": "KCH-1001",
            "salesforce_load_id": None,
            "equipment_type_name": "Dry Van",
            "mode_name": None,
            "cargo_summary": "Palletized goods",
            "commodity_description_posting": None,
            "offer_rate": 1500,
            "max_pay_amount": 1800,
            "carrier_only_quote_total": None,
            "customer_name": "KCH Test Shipper",
            "total_weight": 42000,
            "hazardous_materials": False,
            "carrier_sales_rep_phone": "+12058752486",
            "special_requirements": "Tracker required",
            "load_posting_description": "Straps",
            "stops": [
                {
                    "stop_number": 1,
                    "expected_date": "2026-05-01",
                    "shipping_receiving_hours": "08:00-15:00",
                    "appointment_time": None,
                    "stop_city": "Atlanta",
                    "state_code": "GA",
                    "country_code": "US",
                    "is_pickup": True,
                    "is_dropoff": False,
                    "location_timezone": "America/New_York",
                },
                {
                    "stop_number": 2,
                    "expected_date": "2026-05-03",
                    "shipping_receiving_hours": None,
                    "appointment_time": "10:00",
                    "stop_city": "Chicago",
                    "state_code": "IL",
                    "country_code": "US",
                    "is_pickup": False,
                    "is_dropoff": True,
                    "location_timezone": "America/Chicago",
                },
            ],
        }

    def test_normalizes_kch_load_record_with_full_fields(self):
        normalized = normalize_load_record(self._base_row())
        self.assertEqual(normalized["id"], "KCH-1001")
        self.assertEqual(normalized["load_id"], "KCH-1001")
        self.assertEqual(normalized["origin"]["city"], "Atlanta")
        self.assertEqual(normalized["origin"]["state"], "GA")
        self.assertEqual(normalized["destination"]["city"], "Chicago")
        self.assertEqual(normalized["destination"]["timezone"], "America/Chicago")
        self.assertEqual(normalized["pickupTime"], "2026-05-01 08:00-15:00")
        self.assertEqual(normalized["dropoffTime"], "2026-05-03 10:00")
        self.assertEqual(normalized["equipment"], "Dry Van")
        self.assertEqual(normalized["commodity"], "Palletized goods")
        self.assertFalse(normalized["isHazmat"])
        self.assertEqual(normalized["specialInstructions"], "Tracker required\nStraps")
        self.assertTrue(normalized["trackerRequired"])
        self.assertEqual(normalized["startRate"], 1500)
        self.assertEqual(normalized["bookNowRate"], 1500)
        self.assertEqual(normalized["maxRate"], 1800)
        self.assertEqual(normalized["customerName"], "KCH Test Shipper")
        self.assertEqual(normalized["weight"], 42000)

    def test_falls_back_to_mode_name_when_equipment_type_missing(self):
        row = self._base_row()
        row["equipment_type_name"] = None
        row["mode_name"] = "TL"
        normalized = normalize_load_record(row)
        self.assertEqual(normalized["equipment"], "TL")

    def test_falls_back_to_commodity_description_when_cargo_summary_missing(self):
        row = self._base_row()
        row["cargo_summary"] = None
        row["commodity_description_posting"] = "Frozen produce"
        normalized = normalize_load_record(row)
        self.assertEqual(normalized["commodity"], "Frozen produce")

    def test_origin_destination_empty_when_stops_not_embedded(self):
        row = self._base_row()
        row.pop("stops")
        normalized = normalize_load_record(row)
        self.assertEqual(normalized["origin"]["city"], "")
        self.assertEqual(normalized["destination"]["city"], "")
        self.assertIsNone(normalized["pickupTime"])
        self.assertIsNone(normalized["dropoffTime"])

    def test_phone_passes_through_e164_unchanged(self):
        normalized = normalize_load_record(self._base_row())
        self.assertEqual(normalized["transfer_call_to"], "+12058752486")
        self.assertIsNone(normalized["transfer_country_code"])

    def test_carrier_sales_rep_phone_empty_yields_none_transfer(self):
        row = self._base_row()
        row["carrier_sales_rep_phone"] = None
        normalized = normalize_load_record(row)
        self.assertIsNone(normalized["transfer_call_to"])

    def test_booked_rate_uses_carrier_only_quote_total(self):
        row = self._base_row()
        row["carrier_only_quote_total"] = 1650
        normalized = normalize_load_record(row)
        self.assertEqual(normalized["bookedRate"], 1650)


if __name__ == "__main__":
    unittest.main()
