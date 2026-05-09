import tempfile
import unittest
from pathlib import Path

from record_management_system.manager import RecordManager
from record_management_system.records import AIRLINE, CLIENT, FLIGHT


class ManagerTests(unittest.TestCase):
    def test_create_search_update_and_delete_record(self):
        manager = RecordManager()

        client = manager.create_record(
            CLIENT,
            {"Name": "Mina Murray", "Phone Number": "555-0100"},
        )
        self.assertEqual(client["ID"], 1)

        matches = manager.search_records("mina")
        self.assertEqual(len(matches), 1)

        manager.update_record(
            0,
            {"Name": "Mina Harker", "Phone Number": "555-0101"},
        )
        self.assertEqual(manager.get_record(0)["Name"], "Mina Harker")

        deleted = manager.delete_record(0)
        self.assertEqual(deleted["Type"], CLIENT)
        self.assertEqual(manager.records, [])

    def test_create_flight_requires_existing_references(self):
        manager = RecordManager()
        manager.create_record(CLIENT, {"Name": "Sam", "Phone Number": "1"})

        with self.assertRaises(ValueError):
            manager.create_record(
                FLIGHT,
                {
                    "Client_ID": 1,
                    "Airline_ID": 99,
                    "Date": "2026-05-09",
                    "Start City": "Rome",
                    "End City": "Berlin",
                },
            )

    def test_create_valid_flight(self):
        manager = RecordManager()
        manager.create_record(CLIENT, {"Name": "Sam", "Phone Number": "1"})
        manager.create_record(AIRLINE, {"Company Name": "Sky Test"})

        flight = manager.create_record(
            FLIGHT,
            {
                "Client_ID": 1,
                "Airline_ID": 1,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            },
        )

        self.assertEqual(flight["Type"], FLIGHT)

    def test_delete_record_rejects_records_used_by_flights(self):
        manager = RecordManager()
        manager.create_record(CLIENT, {"Name": "Sam", "Phone Number": "1"})
        manager.create_record(AIRLINE, {"Company Name": "Sky Test"})
        manager.create_record(
            FLIGHT,
            {
                "Client_ID": 1,
                "Airline_ID": 1,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            },
        )

        with self.assertRaises(ValueError):
            manager.delete_record(0)

    def test_save_uses_configured_storage_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            manager = RecordManager(storage_path=path)
            manager.create_record(AIRLINE, {"Company Name": "Sky Test"})

            manager.save()

            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
