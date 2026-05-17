"""Unit tests for ``record_management_system.manager``."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from record_management_system.manager import RecordManager, sort_records
from record_management_system.records import AIRLINE, CLIENT, FLIGHT


def _seed_manager() -> RecordManager:
    """Return a manager pre-populated with two clients and an airline."""

    manager = RecordManager()
    manager.create_record(CLIENT, {"Name": "Ada", "Phone Number": "111"})
    manager.create_record(CLIENT, {"Name": "Mina", "Phone Number": "222"})
    manager.create_record(AIRLINE, {"Company Name": "Sky Test"})
    return manager


class CRUDTests(unittest.TestCase):
    def test_create_assigns_sequential_ids(self):
        manager = _seed_manager()
        self.assertEqual(manager.records[0]["ID"], 1)
        self.assertEqual(manager.records[1]["ID"], 2)
        self.assertEqual(manager.records[2]["ID"], 1)

    def test_update_preserves_client_id(self):
        manager = _seed_manager()
        original_id = manager.records[0]["ID"]

        manager.update_record(0, {"Name": "Ada Lovelace", "Phone Number": "999"})

        self.assertEqual(manager.records[0]["ID"], original_id)
        self.assertEqual(manager.records[0]["Name"], "Ada Lovelace")

    def test_delete_record_returns_record(self):
        manager = _seed_manager()
        deleted = manager.delete_record(0)
        self.assertEqual(deleted["Type"], CLIENT)
        self.assertEqual(len(manager.records), 2)

    def test_get_record_index_out_of_range(self):
        manager = _seed_manager()
        with self.assertRaises(IndexError):
            manager.get_record(99)


class FlightReferenceTests(unittest.TestCase):
    def test_flight_requires_existing_client(self):
        manager = _seed_manager()
        with self.assertRaises(ValueError):
            manager.create_record(
                FLIGHT,
                {
                    "Client_ID": 99,
                    "Airline_ID": 1,
                    "Date": "2026-05-09",
                    "Start City": "Rome",
                    "End City": "Berlin",
                },
            )

    def test_flight_requires_existing_airline(self):
        manager = _seed_manager()
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

    def test_loaded_flight_requires_existing_references(self):
        records = [
            {
                "ID": 1,
                "Type": CLIENT,
                "Name": "Sam",
                "Address Line 1": "",
                "Address Line 2": "",
                "Address Line 3": "",
                "City": "",
                "State": "",
                "Zip Code": "",
                "Country": "",
                "Phone Number": "1",
            },
            {
                "Type": FLIGHT,
                "Client_ID": 1,
                "Airline_ID": 99,
                "Date": "2026-05-09",
                "Start City": "Rome",
                "End City": "Berlin",
            },
        ]

        with self.assertRaises(ValueError):
            RecordManager(records)

    def test_valid_flight_creates_record(self):
        manager = _seed_manager()
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

    def test_delete_rejects_client_used_by_flight(self):
        manager = _seed_manager()
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

    def test_delete_rejects_airline_used_by_flight(self):
        manager = _seed_manager()
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
            manager.delete_record(2)

    def test_flight_can_be_deleted_independently(self):
        manager = _seed_manager()
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
        manager.delete_record(3)
        self.assertEqual(len(manager.flights_for_client(1)), 0)


class QueryTests(unittest.TestCase):
    def test_search_filters_by_text(self):
        manager = _seed_manager()
        matches = manager.search_records("mina")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1]["Name"], "Mina")

    def test_search_filters_by_type(self):
        manager = _seed_manager()
        matches = manager.search_records("", AIRLINE)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1]["Type"], AIRLINE)

    def test_statistics_returns_counts(self):
        manager = _seed_manager()
        stats = manager.statistics()
        self.assertEqual(stats[CLIENT], 2)
        self.assertEqual(stats[AIRLINE], 1)
        self.assertEqual(stats[FLIGHT], 0)
        self.assertEqual(stats["Total"], 3)

    def test_client_and_airline_choices(self):
        manager = _seed_manager()
        clients = manager.client_choices()
        airlines = manager.airline_choices()
        self.assertEqual(len(clients), 2)
        self.assertEqual(len(airlines), 1)
        self.assertTrue(clients[0][1].startswith("#1"))

    def test_find_client_returns_matching_record(self):
        manager = _seed_manager()
        record = manager.find_client(1)
        self.assertIsNotNone(record)
        self.assertEqual(record["Name"], "Ada")
        self.assertIsNone(manager.find_client(99))


class PersistenceTests(unittest.TestCase):
    def test_save_uses_configured_storage_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            manager = RecordManager(storage_path=path)
            manager.create_record(AIRLINE, {"Company Name": "Sky Test"})

            manager.save()

            self.assertTrue(path.exists())

    def test_save_without_path_raises(self):
        with self.assertRaises(ValueError):
            RecordManager().save()

    def test_from_file_loads_existing_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            manager = RecordManager(storage_path=path)
            manager.create_record(AIRLINE, {"Company Name": "Sky Test"})
            manager.save()

            reloaded = RecordManager.from_file(path)
            self.assertEqual(len(reloaded.records), 1)


class SortRecordsTests(unittest.TestCase):
    def test_sort_by_name_ascending(self):
        manager = _seed_manager()
        sorted_pairs = sort_records(manager.list_records(CLIENT), "Name")
        self.assertEqual(sorted_pairs[0][1]["Name"], "Ada")
        self.assertEqual(sorted_pairs[1][1]["Name"], "Mina")

    def test_sort_records_reverse(self):
        manager = _seed_manager()
        sorted_pairs = sort_records(manager.list_records(CLIENT), "Name", reverse=True)
        self.assertEqual(sorted_pairs[0][1]["Name"], "Mina")


if __name__ == "__main__":
    unittest.main()
