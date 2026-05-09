import tempfile
import unittest
from pathlib import Path

from record_management_system.main import build_manager, default_data_path
from record_management_system.manager import RecordManager


class MainTests(unittest.TestCase):
    def test_default_data_path_points_to_records_json(self):
        path = default_data_path()

        self.assertEqual(path.name, "records.json")
        self.assertEqual(path.parent.name, "data")

    def test_build_manager_loads_from_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"

            manager = build_manager(path)

            self.assertIsInstance(manager, RecordManager)
            self.assertEqual(manager.records, [])


if __name__ == "__main__":
    unittest.main()

