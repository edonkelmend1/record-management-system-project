"""Record definitions, builders and validation helpers.

This module describes the three record types managed by the application
(Client, Airline and Flight) and exposes pure functions that build and
validate dictionary records.  Keeping the record model in a dedicated
module means the rest of the application can rely on a single source of
truth for field names and validation rules.

The module is intentionally free of any I/O, GUI or persistence logic so
that it remains trivial to unit test.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Record type constants
# ---------------------------------------------------------------------------

CLIENT = "Client"
AIRLINE = "Airline"
FLIGHT = "Flight"

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

CLIENT_FIELDS: list[str] = [
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

AIRLINE_FIELDS: list[str] = [
    "ID",
    "Type",
    "Company Name",
]

FLIGHT_FIELDS: list[str] = [
    "Type",
    "Client_ID",
    "Airline_ID",
    "Date",
    "Start City",
    "End City",
]

RECORD_FIELDS: dict[str, list[str]] = {
    CLIENT: CLIENT_FIELDS,
    AIRLINE: AIRLINE_FIELDS,
    FLIGHT: FLIGHT_FIELDS,
}

RECORD_TYPES: tuple[str, ...] = tuple(RECORD_FIELDS)

# ---------------------------------------------------------------------------
# Validation primitives
# ---------------------------------------------------------------------------

# Allow international phone numbers: optional leading "+", digits, spaces,
# dashes, dots and parentheses.  At least one digit must be present.
_PHONE_RE = re.compile(r"^\+?[0-9 ().\-]+$")

# Zip / postal codes worldwide are quite varied so we are deliberately lax:
# letters, digits, spaces and hyphens between 2 and 12 characters.
_ZIPCODE_RE = re.compile(r"^[A-Za-z0-9 \-]{2,12}$")


def clean_text(value: Any) -> str:
    """Return a stripped string value, treating ``None`` as empty string.

    The GUI uses ``Entry.get()`` which always returns a string, but other
    callers (such as the storage layer) may pass through raw JSON values
    that can be ``None``.  Normalising both cases here keeps validation
    code further down very simple.
    """

    if value is None:
        return ""
    return str(value).strip()


def parse_int(value: Any, field_name: str) -> int:
    """Parse ``value`` as an integer, rejecting booleans and empty input.

    The dedicated ``field_name`` argument lets us produce a friendly
    validation message that the GUI can display directly to the user.
    """

    if isinstance(value, bool):
        # ``bool`` is a subclass of ``int`` so we must guard against it.
        raise ValueError(f"{field_name} must be an integer.")
    text = clean_text(value)
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def validate_phone(value: str) -> str:
    """Validate a phone number string and return it cleaned."""

    text = clean_text(value)
    if not text:
        raise ValueError("Phone Number is required.")
    if not _PHONE_RE.match(text):
        raise ValueError(
            "Phone Number must contain only digits, spaces, dashes, "
            "parentheses and an optional leading '+'."
        )
    return text


def validate_zipcode(value: str) -> str:
    """Validate a zip / postal code value and return it cleaned.

    Empty values are allowed because not every client record has a known
    postcode (for example walk-in customers).  When a value is provided
    it must look like a reasonable international postcode.
    """

    text = clean_text(value)
    if not text:
        return ""
    if not _ZIPCODE_RE.match(text):
        raise ValueError(
            "Zip Code may only contain letters, digits, spaces and "
            "dashes (2-12 characters)."
        )
    return text


def normalise_datetime(value: Any) -> str:
    """Return a JSON-friendly ISO date or date-time string.

    Accepts ``date``/``datetime`` objects as well as a variety of
    string representations (``2026-05-09``, ``2026/05/09``,
    ``2026-05-09T14:30``, ``2026-05-09 14:30``).
    """

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
        text.replace("/", "-").replace("T", " "),
    ]
    # We try the date format first because Python's
    # ``datetime.fromisoformat`` happily parses bare dates like
    # ``2026-05-09`` and turns them into datetimes at midnight.  We want
    # to keep bare dates as ISO dates and only return the datetime form
    # when a time was explicitly supplied.
    for candidate in candidates:
        try:
            parsed_date = date.fromisoformat(candidate)
            return parsed_date.isoformat()
        except ValueError:
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.isoformat(sep=" ", timespec="minutes")
            except ValueError:
                continue

    raise ValueError(
        "Date must use ISO format, for example 2026-05-09 or "
        "2026-05-09 14:30."
    )


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def next_id(records: Iterable[dict[str, Any]], record_type: str) -> int:
    """Return the next integer ID for client or airline records.

    The function inspects the existing records of ``record_type`` and
    returns ``max(id) + 1``.  Records with malformed IDs are skipped so
    that a single corrupt entry cannot break ID generation.
    """

    highest = 0
    for record in records:
        if record.get("Type") != record_type or "ID" not in record:
            continue
        try:
            highest = max(highest, parse_int(record["ID"], "ID"))
        except ValueError:
            continue
    return highest + 1


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def build_client_record(values: dict[str, Any], record_id: int) -> dict[str, Any]:
    """Build a validated client record dictionary.

    ``Name`` and ``Phone Number`` are required; the other fields are
    cleaned and stored even when empty so that the JSON file always has
    the same shape for client records.
    """

    name = clean_text(values.get("Name"))
    if not name:
        raise ValueError("Name is required.")

    return {
        "ID": parse_int(record_id, "ID"),
        "Type": CLIENT,
        "Name": name,
        "Address Line 1": clean_text(values.get("Address Line 1")),
        "Address Line 2": clean_text(values.get("Address Line 2")),
        "Address Line 3": clean_text(values.get("Address Line 3")),
        "City": clean_text(values.get("City")),
        "State": clean_text(values.get("State")),
        "Zip Code": validate_zipcode(values.get("Zip Code", "")),
        "Country": clean_text(values.get("Country")),
        "Phone Number": validate_phone(values.get("Phone Number", "")),
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
    """Build a validated flight record dictionary.

    Flights do not carry their own integer ID; they reference an
    existing client and airline.  The ``Type`` key is added internally
    so flights can live in the same list of dictionaries as the other
    record types.
    """

    start_city = clean_text(values.get("Start City"))
    end_city = clean_text(values.get("End City"))
    if not start_city:
        raise ValueError("Start City is required.")
    if not end_city:
        raise ValueError("End City is required.")
    if start_city.lower() == end_city.lower():
        raise ValueError("Start City and End City must be different.")

    return {
        "Type": FLIGHT,
        "Client_ID": parse_int(values.get("Client_ID"), "Client_ID"),
        "Airline_ID": parse_int(values.get("Airline_ID"), "Airline_ID"),
        "Date": normalise_datetime(values.get("Date")),
        "Start City": start_city,
        "End City": end_city,
    }


# ---------------------------------------------------------------------------
# Top-level validation
# ---------------------------------------------------------------------------


def validate_record(record: dict[str, Any]) -> None:
    """Validate that a record has the required structure.

    This is used by the storage layer when loading JSON files so that
    a single corrupt entry produces a clear error message rather than a
    confusing failure deep inside the application.
    """

    if not isinstance(record, dict):
        raise ValueError("Record must be a dictionary.")

    record_type = record.get("Type")
    if record_type not in RECORD_FIELDS:
        raise ValueError(
            f"Record Type is invalid; expected one of "
            f"{', '.join(RECORD_TYPES)}."
        )

    missing = [field for field in RECORD_FIELDS[record_type] if field not in record]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}.")

    # Re-build via the dedicated builders to make sure all values match
    # the validation rules.  This guarantees on-disk records can be
    # round-tripped without surprises.
    if record_type == CLIENT:
        build_client_record(record, parse_int(record["ID"], "ID"))
    elif record_type == AIRLINE:
        build_airline_record(record, parse_int(record["ID"], "ID"))
    elif record_type == FLIGHT:
        build_flight_record(record)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def summarize_record(record: dict[str, Any]) -> str:
    """Return a short display summary for a record (used by the GUI table)."""

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
    """Return a compact details string used as a secondary table column."""

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
            f"{record.get('Start City', '')} -> {record.get('End City', '')}"
        )
    return ""
