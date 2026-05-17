"""Flask web entry point for the browser front end."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .main import default_data_path
from .manager import RecordManager


def default_frontend_path() -> Path:
    """Return the folder containing the static browser front end."""

    return Path(__file__).resolve().parents[1] / "web_frontend"


def create_app(
    storage_path: Path | str | None = None,
    frontend_path: Path | str | None = None,
) -> Flask:
    """Create the Flask app used by the browser interface."""

    data_path = Path(storage_path) if storage_path else default_data_path()
    static_path = Path(frontend_path) if frontend_path else default_frontend_path()
    app = Flask(__name__, static_folder=None)

    def load_manager() -> RecordManager:
        return RecordManager.from_file(data_path)

    @app.get("/")
    def index():
        return send_from_directory(static_path, "index.html")

    @app.get("/<path:filename>")
    def frontend_file(filename: str):
        return send_from_directory(static_path, filename)

    @app.get("/api/records")
    def get_records():
        manager = load_manager()
        return jsonify({"records": manager.records})

    @app.put("/api/records")
    def replace_records():
        payload: Any = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            return jsonify({"error": "Request body must contain a records list."}), 400

        try:
            manager = RecordManager(payload["records"], data_path)
            manager.save()
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({"records": manager.records})

    return app


def main() -> None:
    """Run the Flask development server."""

    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
