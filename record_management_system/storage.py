"""JSON storage for record dictionaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .records import validate_record


def load_records(path: Path | str) -> list[dict[str, Any]]:
    """Load records from JSON, returning an empty list when missing."""

    storage_path = Path(path)
    if not storage_path.exists():
        return []

    try:
        with storage_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not read JSON from {storage_path}.") from exc

    if not isinstance(data, list):
        raise ValueError("Storage file must contain a list of records.")

    for record in data:
        validate_record(record)
    return data


def save_records(path: Path | str, records: list[dict[str, Any]]) -> None:
    """Save records to JSON on the file system."""

    if not isinstance(records, list):
        raise ValueError("Records must be stored as a list.")

    for record in records:
        validate_record(record)

    storage_path = Path(path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with storage_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

