"""JSON storage for record dictionaries.

The application keeps records in memory as a ``list`` of ``dict``
objects.  This module is responsible for persisting that list to the
file system as JSON and for loading it back when the application starts.

Two design choices are worth highlighting:

* **Atomic writes** - the new file is written to a temporary path and
  then renamed.  This protects the existing data even if the program is
  interrupted (for example because the user force-closes the window)
  while saving.
* **Automatic backups** - before each successful save the previous
  ``records.json`` is copied to ``records.json.bak`` so that a corrupted
  edit can always be recovered manually.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .records import validate_record

_LOGGER = logging.getLogger(__name__)


def load_records(path: Path | str) -> list[dict[str, Any]]:
    """Load records from JSON and return them as a list of dictionaries.

    If the file does not exist (for example on the very first run) an
    empty list is returned.  Existing files are validated; any record
    that does not match the expected schema raises ``ValueError`` with a
    descriptive message.
    """

    storage_path = Path(path)
    if not storage_path.exists():
        _LOGGER.info("No storage file at %s; starting with empty record list.", storage_path)
        return []

    try:
        with storage_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not read JSON from {storage_path}: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})."
        ) from exc

    if not isinstance(data, list):
        raise ValueError(
            "Storage file must contain a list of records at the top level."
        )

    for index, record in enumerate(data, start=1):
        try:
            validate_record(record)
        except ValueError as exc:
            raise ValueError(
                f"Record number {index} in {storage_path} is invalid: {exc}"
            ) from exc

    _LOGGER.info("Loaded %d record(s) from %s.", len(data), storage_path)
    return data


def save_records(path: Path | str, records: list[dict[str, Any]]) -> None:
    """Save records to JSON on the file system.

    The write is performed atomically: the data is first written to a
    temporary file in the same directory and then renamed over the
    target.  If a previous ``records.json`` exists it is copied to
    ``records.json.bak`` before the new file replaces it.
    """

    if not isinstance(records, list):
        raise ValueError("Records must be stored as a list.")

    for index, record in enumerate(records, start=1):
        try:
            validate_record(record)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to save: record number {index} is invalid: {exc}"
            ) from exc

    storage_path = Path(path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Make a backup of the previous file before we replace it so a
    # bad save can always be recovered by hand.
    if storage_path.exists():
        backup_path = storage_path.with_suffix(storage_path.suffix + ".bak")
        try:
            shutil.copy2(storage_path, backup_path)
        except OSError as exc:  # pragma: no cover - best effort only
            _LOGGER.warning("Could not create backup at %s: %s", backup_path, exc)

    # Atomic write: tempfile then rename.
    fd, tmp_path = tempfile.mkstemp(
        prefix=storage_path.name + ".",
        suffix=".tmp",
        dir=str(storage_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(records, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, storage_path)
    except Exception:
        # If anything went wrong we make sure the temporary file is
        # cleaned up so we do not leave litter behind.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    _LOGGER.info("Saved %d record(s) to %s.", len(records), storage_path)
