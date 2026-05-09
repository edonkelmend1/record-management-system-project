import json
import tempfile
import unittest
from pathlib import Path

from record_management_system.records import build_airline_record
from record_management_system.storage import load_records, save_records


class StorageTests(unittest.TestCase):
    def test_load_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.json"

            self.assertEqual(load_records(path), [])

    def test_save_and_load_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            records = [build_airline_record({"Company Name": "Example Air"}, 1)]

            save_records(path, records)

            self.assertEqual(load_records(path), records)

    def test_load_rejects_non_list_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            path.write_text(json.dumps({"bad": "data"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_records(path)


if __name__ == "__main__":
    unittest.main()

