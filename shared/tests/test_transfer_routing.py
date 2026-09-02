"""Tests for transfer routing helpers."""

from __future__ import annotations

import unittest

from src.transfer_routing import (
    build_transfer_phone_number,
    coerce_e164_transfer_number,
    sanitize_phone_digits,
)


class CoerceE164TransferNumberTests(unittest.TestCase):
    def test_passes_through_canonical_value(self):
        self.assertEqual(
            coerce_e164_transfer_number("+12058752486"),
            "+12058752486",
        )

    def test_strips_whitespace(self):
        self.assertEqual(
            coerce_e164_transfer_number("  +12058752486  "),
            "+12058752486",
        )

    def test_adds_plus_prefix_when_missing(self):
        self.assertEqual(
            coerce_e164_transfer_number("12058752486"),
            "+12058752486",
        )

    def test_rejects_invalid_with_letters(self):
        self.assertIsNone(coerce_e164_transfer_number("+1abc205"))

    def test_rejects_too_short(self):
        # Fewer than 8 digits after the plus
        self.assertIsNone(coerce_e164_transfer_number("+1234"))

    def test_rejects_too_long(self):
        # More than 15 digits after the plus
        self.assertIsNone(coerce_e164_transfer_number("+1234567890123456"))

    def test_returns_none_for_empty(self):
        self.assertIsNone(coerce_e164_transfer_number(""))
        self.assertIsNone(coerce_e164_transfer_number("   "))
        self.assertIsNone(coerce_e164_transfer_number(None))


class BuildTransferPhoneNumberTests(unittest.TestCase):
    """Legacy split-format helper still used for fixtures."""

    def test_concatenates_country_code_and_digits(self):
        self.assertEqual(
            build_transfer_phone_number("+1", "(205) 875-2486"),
            "+12058752486",
        )

    def test_returns_none_when_country_code_missing(self):
        self.assertIsNone(build_transfer_phone_number("", "2058752486"))

    def test_returns_none_when_digits_missing(self):
        self.assertIsNone(build_transfer_phone_number("+1", ""))


class SanitizePhoneDigitsTests(unittest.TestCase):
    def test_strips_formatting(self):
        self.assertEqual(sanitize_phone_digits("(205) 875-2486"), "2058752486")

    def test_handles_none(self):
        self.assertEqual(sanitize_phone_digits(None), "")


if __name__ == "__main__":
    unittest.main()
