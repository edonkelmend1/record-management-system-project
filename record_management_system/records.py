"""Record definitions and validation helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

CLIENT = "Client"
AIRLINE = "Airline"
FLIGHT = "Flight"

CLIENT_FIELDS = [
    "ID",
    "Type",
    "Name",
    "Address Line 1",
    "Address Line 2",
    "Address Line 3",
    "City",
    "State",
    "Zip Code",
    "Country",
    "Phone Number",
]

AIRLINE_FIELDS = [
    "ID",
    "Type",
    "Company Name",
]

FLIGHT_FIELDS = [
    "Type",
    "Client_ID",
    "Airline_ID",
    "Date",
    "Start City",
    "End City",
]

RECORD_FIELDS = {
    CLIENT: CLIENT_FIELDS,
    AIRLINE: AIRLINE_FIELDS,
    FLIGHT: FLIGHT_FIELDS,
}

RECORD_TYPES = tuple(RECORD_FIELDS)


def clean_text(value: Any) -> str:
    """Return a stripped string value."""

    if value is None:
        return ""
    return str(value).strip()


def parse_int(value: Any, field_name: str) -> int:
    """Parse an integer field and reject booleans."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def normalise_datetime(value: Any) -> str:
    """Return a JSON-friendly ISO date or date-time string."""

    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()

    text = clean_text(value)
    if not text:
        raise ValueError("Date is required.")

    candidates = [
        text,
        text.replace("/", "-"),
        text.replace("T", " "),
    ]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.isoformat(sep=" ", timespec="minutes")
        except ValueError:
            try:
                parsed_date = date.fromisoformat(candidate)
                return parsed_date.isoformat()
            except ValueError:
                continue

    raise ValueError("Date must use ISO format, for example 2026-05-09.")


def next_id(records: list[dict[str, Any]], record_type: str) -> int:
    """Return the next integer ID for client or airline records."""

    highest = 0
    for record in records:
        if record.get("Type") == record_type and "ID" in record:
            try:
                highest = max(highest, parse_int(record["ID"], "ID"))
            except ValueError:
                continue
    return highest + 1


def build_client_record(values: dict[str, Any], record_id: int) -> dict[str, Any]:
    """Build a validated client record dictionary."""

    name = clean_text(values.get("Name"))
    phone = clean_text(values.get("Phone Number"))
    if not name:
        raise ValueError("Name is required.")
    if not phone:
        raise ValueError("Phone Number is required.")

    return {
        "ID": parse_int(record_id, "ID"),
        "Type": CLIENT,
        "Name": name,
        "Address Line 1": clean_text(values.get("Address Line 1")),
        "Address Line 2": clean_text(values.get("Address Line 2")),
        "Address Line 3": clean_text(values.get("Address Line 3")),
        "City": clean_text(values.get("City")),
        "State": clean_text(values.get("State")),
        "Zip Code": clean_text(values.get("Zip Code")),
        "Country": clean_text(values.get("Country")),
        "Phone Number": phone,
    }


def build_airline_record(values: dict[str, Any], record_id: int) -> dict[str, Any]:
    """Build a validated airline record dictionary."""

    company_name = clean_text(values.get("Company Name"))
    if not company_name:
        raise ValueError("Company Name is required.")

    return {
        "ID": parse_int(record_id, "ID"),
        "Type": AIRLINE,
        "Company Name": company_name,
    }


def build_flight_record(values: dict[str, Any]) -> dict[str, Any]:
    """Build a validated flight record dictionary."""

    start_city = clean_text(values.get("Start City"))
    end_city = clean_text(values.get("End City"))
    if not start_city:
        raise ValueError("Start City is required.")
    if not end_city:
        raise ValueError("End City is required.")

    return {
        "Type": FLIGHT,
        "Client_ID": parse_int(values.get("Client_ID"), "Client_ID"),
        "Airline_ID": parse_int(values.get("Airline_ID"), "Airline_ID"),
        "Date": normalise_datetime(values.get("Date")),
        "Start City": start_city,
        "End City": end_city,
    }


def validate_record(record: dict[str, Any]) -> None:
    """Validate that a record has the required structure."""

    if not isinstance(record, dict):
        raise ValueError("Record must be a dictionary.")

    record_type = record.get("Type")
    if record_type not in RECORD_FIELDS:
        raise ValueError("Record Type is invalid.")

    missing = [field for field in RECORD_FIELDS[record_type] if field not in record]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}.")

    if record_type == CLIENT:
        build_client_record(record, parse_int(record["ID"], "ID"))
    elif record_type == AIRLINE:
        build_airline_record(record, parse_int(record["ID"], "ID"))
    elif record_type == FLIGHT:
        build_flight_record(record)


def summarize_record(record: dict[str, Any]) -> str:
    """Return a short display summary for a record."""

    record_type = record.get("Type", "Record")
    if record_type == CLIENT:
        return f"Client #{record.get('ID')}: {record.get('Name', '')}"
    if record_type == AIRLINE:
        return f"Airline #{record.get('ID')}: {record.get('Company Name', '')}"
    if record_type == FLIGHT:
        return (
            f"Flight: client {record.get('Client_ID')} with airline "
            f"{record.get('Airline_ID')}"
        )
    return str(record_type)


def record_details(record: dict[str, Any]) -> str:
    """Return a compact details string for table display."""

    record_type = record.get("Type")
    if record_type == CLIENT:
        parts = [
            record.get("City", ""),
            record.get("Country", ""),
            record.get("Phone Number", ""),
        ]
        return " | ".join(clean_text(part) for part in parts if clean_text(part))
    if record_type == AIRLINE:
        return clean_text(record.get("Company Name"))
    if record_type == FLIGHT:
        return (
            f"{record.get('Date', '')}: "
            f"{record.get('Start City', '')} to {record.get('End City', '')}"
        )
    return ""

