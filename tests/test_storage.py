"""Unit tests for ``record_management_system.storage``."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from record_management_system.records import (
    build_airline_record,
    build_client_record,
)
from record_management_system.storage import load_records, save_records


class LoadRecordsTests(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.json"
            self.assertEqual(load_records(path), [])

    def test_rejects_non_list_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            path.write_text(json.dumps({"bad": "data"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_records(path)

    def test_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            path.write_text("this is not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_records(path)

    def test_rejects_record_with_wrong_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            path.write_text(
                json.dumps([{"Type": "Client", "ID": 1}]),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_records(path)


class SaveRecordsTests(unittest.TestCase):
    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            records = [
                build_client_record({"Name": "Mina", "Phone Number": "1"}, 1),
                build_airline_record({"Company Name": "Example Air"}, 1),
            ]

            save_records(path, records)

            self.assertTrue(path.exists())
            self.assertEqual(load_records(path), records)

    def test_save_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "deep" / "records.json"
            save_records(path, [])

            self.assertTrue(path.exists())

    def test_save_writes_backup_on_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            first = [build_airline_record({"Company Name": "First"}, 1)]
            second = [build_airline_record({"Company Name": "Second"}, 1)]

            save_records(path, first)
            save_records(path, second)

            backup = path.with_suffix(path.suffix + ".bak")
            self.assertTrue(backup.exists())
            self.assertEqual(load_records(backup), first)
            self.assertEqual(load_records(path), second)

    def test_save_rejects_non_list(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            with self.assertRaises(ValueError):
                save_records(path, {"oops": True})

    def test_save_rejects_invalid_record(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            with self.assertRaises(ValueError):
                save_records(path, [{"Type": "Unknown"}])


if __name__ == "__main__":
    unittest.main()
