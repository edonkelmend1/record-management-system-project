"""Unit tests for ``record_management_system.gui``."""

from __future__ import annotations

import unittest

from record_management_system.gui import FORM_FIELDS, PALETTE, form_fields_for
from record_management_system.records import AIRLINE, CLIENT, FLIGHT


class FormFieldsTests(unittest.TestCase):
    def test_client_form_excludes_generated_fields(self):
        fields = form_fields_for(CLIENT)
        self.assertIn("Name", fields)
        self.assertNotIn("ID", fields)
        self.assertNotIn("Type", fields)

    def test_airline_form(self):
        self.assertEqual(form_fields_for(AIRLINE), ["Company Name"])

    def test_flight_form(self):
        self.assertEqual(
            form_fields_for(FLIGHT),
            ["Client_ID", "Airline_ID", "Date", "Start City", "End City"],
        )

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            form_fields_for("Unknown")

    def test_form_definitions_cover_all_record_types(self):
        self.assertEqual(set(FORM_FIELDS), {CLIENT, AIRLINE, FLIGHT})


class PaletteTests(unittest.TestCase):
    def test_palette_has_required_keys(self):
        required = {
            "background",
            "surface",
            "header",
            "header_text",
            "accent",
            "accent_text",
            "muted_text",
            "danger",
        }
        self.assertTrue(required.issubset(PALETTE.keys()))


if __name__ == "__main__":
    unittest.main()
