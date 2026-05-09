"""Application business logic for managing records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .records import (
    AIRLINE,
    CLIENT,
    FLIGHT,
    RECORD_TYPES,
    build_airline_record,
    build_client_record,
    build_flight_record,
    next_id,
    validate_record,
)
from .storage import load_records, save_records


class RecordManager:
    """Manage the list of record dictionaries used by the application."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        storage_path: Path | str | None = None,
    ) -> None:
        self.records = list(records or [])
        self.storage_path = Path(storage_path) if storage_path else None
        for record in self.records:
            validate_record(record)

    @classmethod
    def from_file(cls, storage_path: Path | str) -> "RecordManager":
        """Create a manager and load records from a JSON file."""

        return cls(load_records(storage_path), storage_path)

    def save(self) -> None:
        """Save records if this manager has a storage path."""

        if self.storage_path is None:
            raise ValueError("No storage path is configured.")
        save_records(self.storage_path, self.records)

    def create_record(self, record_type: str, values: dict[str, Any]) -> dict[str, Any]:
        """Create a record and append it to the internal list."""

        record = self._build_record(record_type, values)
        self.records.append(record)
        return record

    def update_record(self, index: int, values: dict[str, Any]) -> dict[str, Any]:
        """Replace the record at the supplied list index."""

        existing = self.get_record(index)
        record_type = existing["Type"]

        if record_type in (CLIENT, AIRLINE):
            values = {**values, "ID": existing["ID"]}

        replacement = self._build_record(record_type, values)
        self.records[index] = replacement
        return replacement

    def delete_record(self, index: int) -> dict[str, Any]:
        """Delete and return the record at the supplied list index."""

        record = self.get_record(index)
        self._ensure_record_can_be_deleted(record)
        return self.records.pop(index)

    def get_record(self, index: int) -> dict[str, Any]:
        """Return a record by list index."""

        if index < 0 or index >= len(self.records):
            raise IndexError("Record index is out of range.")
        return self.records[index]

    def list_records(
        self,
        record_type: str | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        """Return records as index/record pairs, optionally filtered by type."""

        return [
            (index, record)
            for index, record in enumerate(self.records)
            if record_type in (None, "All", record.get("Type"))
        ]

    def search_records(
        self,
        query: str = "",
        record_type: str | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        """Search records by type and text found in any field value."""

        query = str(query).strip().lower()
        matches = []

        for index, record in self.list_records(record_type):
            if not query:
                matches.append((index, record))
                continue

            values = [str(value).lower() for value in record.values()]
            if any(query in value for value in values):
                matches.append((index, record))

        return matches

    def _build_record(
        self,
        record_type: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a record and run cross-record validation where needed."""

        if record_type == CLIENT:
            record_id = values.get("ID", next_id(self.records, CLIENT))
            return build_client_record(values, record_id)

        if record_type == AIRLINE:
            record_id = values.get("ID", next_id(self.records, AIRLINE))
            return build_airline_record(values, record_id)

        if record_type == FLIGHT:
            record = build_flight_record(values)
            self._validate_flight_references(record)
            return record

        valid_types = ", ".join(RECORD_TYPES)
        raise ValueError(f"Record type must be one of: {valid_types}.")

    def _validate_flight_references(self, record: dict[str, Any]) -> None:
        """Ensure a flight points to existing client and airline records."""

        if not self._record_id_exists(CLIENT, record["Client_ID"]):
            raise ValueError("Client_ID must refer to an existing client record.")
        if not self._record_id_exists(AIRLINE, record["Airline_ID"]):
            raise ValueError("Airline_ID must refer to an existing airline record.")

    def _record_id_exists(self, record_type: str, record_id: int) -> bool:
        return any(
            record.get("Type") == record_type and record.get("ID") == record_id
            for record in self.records
        )

    def _ensure_record_can_be_deleted(self, record: dict[str, Any]) -> None:
        record_type = record.get("Type")
        if record_type == CLIENT:
            field_name = "Client_ID"
        elif record_type == AIRLINE:
            field_name = "Airline_ID"
        else:
            return

        record_id = record.get("ID")
        is_referenced = any(
            item.get("Type") == FLIGHT and item.get(field_name) == record_id
            for item in self.records
        )
        if is_referenced:
            raise ValueError(
                f"Cannot delete {record_type.lower()} record while flights use it."
            )
