import unittest

from record_management_system.records import (
    AIRLINE,
    CLIENT,
    FLIGHT,
    build_airline_record,
    build_client_record,
    build_flight_record,
    next_id,
    normalise_datetime,
    record_details,
    summarize_record,
    validate_record,
)


class RecordTests(unittest.TestCase):
    def test_build_client_record(self):
        record = build_client_record(
            {
                "Name": "Ada Lovelace",
                "Address Line 1": "1 Example Street",
                "Phone Number": "12345",
            },
            1,
        )

        self.assertEqual(record["ID"], 1)
        self.assertEqual(record["Type"], CLIENT)
        self.assertEqual(record["Name"], "Ada Lovelace")

    def test_build_airline_record(self):
        record = build_airline_record({"Company Name": "Example Air"}, 2)

        self.assertEqual(record["ID"], 2)
        self.assertEqual(record["Type"], AIRLINE)
        self.assertEqual(record["Company Name"], "Example Air")

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
        self.assertEqual(record["Date"], "2026-05-09 00:00")

    def test_validate_record_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            validate_record({"Type": "Unknown"})

    def test_next_id_ignores_other_record_types(self):
        records = [
            build_client_record({"Name": "A", "Phone Number": "1"}, 1),
            build_airline_record({"Company Name": "B"}, 10),
        ]

        self.assertEqual(next_id(records, CLIENT), 2)
        self.assertEqual(next_id(records, AIRLINE), 11)

    def test_normalise_datetime_accepts_date_time(self):
        self.assertEqual(
            normalise_datetime("2026-05-09 14:30"),
            "2026-05-09 14:30",
        )

    def test_summary_and_details(self):
        record = build_airline_record({"Company Name": "Test Air"}, 3)

        self.assertIn("Airline #3", summarize_record(record))
        self.assertEqual(record_details(record), "Test Air")


if __name__ == "__main__":
    unittest.main()

