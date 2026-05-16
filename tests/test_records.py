"""Unit tests for ``record_management_system.records``."""

from __future__ import annotations

import unittest
from datetime import date, datetime

from record_management_system.records import (
    AIRLINE,
    CLIENT,
    FLIGHT,
    RECORD_FIELDS,
    RECORD_TYPES,
    build_airline_record,
    build_client_record,
    build_flight_record,
    clean_text,
    next_id,
    normalise_datetime,
    parse_int,
    record_details,
    summarize_record,
    validate_phone,
    validate_record,
    validate_zipcode,
)


class CleanTextTests(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(clean_text(None), "")

    def test_strips_whitespace(self):
        self.assertEqual(clean_text("  hello  "), "hello")

    def test_non_string_coerced(self):
        self.assertEqual(clean_text(12), "12")


class ParseIntTests(unittest.TestCase):
    def test_accepts_numeric_string(self):
        self.assertEqual(parse_int(" 42 ", "ID"), 42)

    def test_rejects_boolean(self):
        with self.assertRaises(ValueError):
            parse_int(True, "ID")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_int("", "ID")

    def test_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            parse_int("abc", "ID")


class PhoneValidationTests(unittest.TestCase):
    def test_accepts_international_format(self):
        self.assertEqual(validate_phone("+44 (20) 7946-0958"), "+44 (20) 7946-0958")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            validate_phone("")

    def test_rejects_letters(self):
        with self.assertRaises(ValueError):
            validate_phone("CALL-ME")


class ZipcodeValidationTests(unittest.TestCase):
    def test_empty_allowed(self):
        self.assertEqual(validate_zipcode(""), "")

    def test_valid_alpha_numeric(self):
        self.assertEqual(validate_zipcode("SW1A 1AA"), "SW1A 1AA")

    def test_rejects_special_chars(self):
        with self.assertRaises(ValueError):
            validate_zipcode("12345@@@")


class DateTimeNormalisationTests(unittest.TestCase):
    def test_accepts_date_object(self):
        self.assertEqual(normalise_datetime(date(2026, 5, 9)), "2026-05-09")

    def test_accepts_datetime_object(self):
        self.assertEqual(
            normalise_datetime(datetime(2026, 5, 9, 14, 30)),
            "2026-05-09 14:30",
        )

    def test_accepts_string_with_slash(self):
        self.assertEqual(normalise_datetime("2026/05/09"), "2026-05-09")

    def test_accepts_iso_with_t(self):
        self.assertEqual(
            normalise_datetime("2026-05-09T14:30"),
            "2026-05-09 14:30",
        )

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            normalise_datetime("not-a-date")


class RecordBuilderTests(unittest.TestCase):
    def test_build_client_record_returns_full_schema(self):
        record = build_client_record(
            {
                "Name": "Ada Lovelace",
                "Address Line 1": "1 Example Street",
                "City": "London",
                "Country": "UK",
                "Zip Code": "SW1 1AA",
                "Phone Number": "+44 20 7946 0958",
            },
            1,
        )

        for field in RECORD_FIELDS[CLIENT]:
            self.assertIn(field, record)
        self.assertEqual(record["ID"], 1)
        self.assertEqual(record["Type"], CLIENT)
        self.assertEqual(record["Name"], "Ada Lovelace")

    def test_build_client_requires_name(self):
        with self.assertRaises(ValueError):
            build_client_record({"Phone Number": "12345"}, 1)

    def test_build_client_requires_phone(self):
        with self.assertRaises(ValueError):
            build_client_record({"Name": "Ada"}, 1)

    def test_build_airline_record(self):
        record = build_airline_record({"Company Name": "Example Air"}, 2)

        self.assertEqual(record["ID"], 2)
        self.assertEqual(record["Type"], AIRLINE)
        self.assertEqual(record["Company Name"], "Example Air")

    def test_build_airline_requires_company_name(self):
        with self.assertRaises(ValueError):
            build_airline_record({"Company Name": "   "}, 2)

    def test_build_flight_record(self):
        record = build_flight_record(
            {
                "Client_ID": "1",
                "Airline_ID": "2",
                "Date": "2026-05-09",
                "Start City": "London",
                "End City": "Paris",
            }
        )

        self.assertEqual(record["Type"], FLIGHT)
        self.assertEqual(record["Client_ID"], 1)
        self.assertEqual(record["Airline_ID"], 2)
        self.assertEqual(record["Date"], "2026-05-09")

    def test_build_flight_rejects_same_cities(self):
        with self.assertRaises(ValueError):
            build_flight_record(
                {
                    "Client_ID": "1",
                    "Airline_ID": "2",
                    "Date": "2026-05-09",
                    "Start City": "London",
                    "End City": "london",
                }
            )

    def test_build_flight_rejects_missing_city(self):
        with self.assertRaises(ValueError):
            build_flight_record(
                {
                    "Client_ID": "1",
                    "Airline_ID": "2",
                    "Date": "2026-05-09",
                    "Start City": "",
                    "End City": "Paris",
                }
            )


class ValidateRecordTests(unittest.TestCase):
    def test_rejects_non_dict(self):
        with self.assertRaises(ValueError):
            validate_record(["not", "a", "dict"])

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            validate_record({"Type": "Unknown"})

    def test_detects_missing_fields(self):
        with self.assertRaises(ValueError):
            validate_record({"Type": CLIENT, "ID": 1})

    def test_accepts_well_formed_client(self):
        record = build_client_record(
            {"Name": "Ada", "Phone Number": "1234"}, 1
        )
        validate_record(record)

    def test_accepts_well_formed_flight(self):
        record = build_flight_record(
            {
                "Client_ID": 1,
                "Airline_ID": 2,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            }
        )
        validate_record(record)


class NextIdTests(unittest.TestCase):
    def test_returns_one_for_empty_list(self):
        self.assertEqual(next_id([], CLIENT), 1)

    def test_ignores_other_record_types(self):
        records = [
            build_client_record({"Name": "A", "Phone Number": "1"}, 1),
            build_airline_record({"Company Name": "B"}, 10),
        ]

        self.assertEqual(next_id(records, CLIENT), 2)
        self.assertEqual(next_id(records, AIRLINE), 11)

    def test_skips_records_with_invalid_id(self):
        records = [
            {"Type": CLIENT, "ID": "oops", "Name": "X", "Phone Number": "1"},
            build_client_record({"Name": "Y", "Phone Number": "2"}, 5),
        ]
        self.assertEqual(next_id(records, CLIENT), 6)


class DisplayHelperTests(unittest.TestCase):
    def test_summary_for_each_type(self):
        client = build_client_record({"Name": "Ada", "Phone Number": "1"}, 1)
        airline = build_airline_record({"Company Name": "Air"}, 1)
        flight = build_flight_record(
            {
                "Client_ID": 1,
                "Airline_ID": 1,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            }
        )

        self.assertIn("Client #1", summarize_record(client))
        self.assertIn("Airline #1", summarize_record(airline))
        self.assertIn("Flight", summarize_record(flight))

    def test_details_for_each_type(self):
        client = build_client_record(
            {"Name": "Ada", "Phone Number": "1", "City": "London"}, 1
        )
        airline = build_airline_record({"Company Name": "Air"}, 1)
        flight = build_flight_record(
            {
                "Client_ID": 1,
                "Airline_ID": 1,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            }
        )

        self.assertIn("London", record_details(client))
        self.assertEqual(record_details(airline), "Air")
        self.assertIn("Rome", record_details(flight))


class ConstantsTests(unittest.TestCase):
    def test_record_types_complete(self):
        self.assertEqual(set(RECORD_TYPES), {CLIENT, AIRLINE, FLIGHT})


if __name__ == "__main__":
    unittest.main()
