"""Tests for the Flask web entry point."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from record_management_system.web import create_app


class WebAppTests(unittest.TestCase):
    def test_get_records_returns_json_records(self):
        with tempfile.TemporaryDirectory() as folder:
            data_path = Path(folder) / "records.json"
            frontend_path = Path(folder) / "frontend"
            frontend_path.mkdir()
            (frontend_path / "index.html").write_text("ok", encoding="utf-8")
            app = create_app(data_path, frontend_path)

            response = app.test_client().get("/api/records")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"records": []})

    def test_put_records_validates_and_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            data_path = Path(folder) / "records.json"
            frontend_path = Path(folder) / "frontend"
            frontend_path.mkdir()
            (frontend_path / "index.html").write_text("ok", encoding="utf-8")
            app = create_app(data_path, frontend_path)
            records = [
                {
                    "ID": 1,
                    "Type": "Airline",
                    "Company Name": "Example Air",
                }
            ]

            response = app.test_client().put("/api/records", json={"records": records})

            self.assertEqual(response.status_code, 200)
            self.assertTrue(data_path.exists())
            self.assertEqual(response.get_json()["records"], records)

    def test_put_records_rejects_invalid_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            data_path = Path(folder) / "records.json"
            frontend_path = Path(folder) / "frontend"
            frontend_path.mkdir()
            (frontend_path / "index.html").write_text("ok", encoding="utf-8")
            app = create_app(data_path, frontend_path)

            response = app.test_client().put("/api/records", json={"records": "bad"})

            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
