# Record Management System

A Python record management application that lets a specialist travel
agent manage client, airline and flight records through either a
Tkinter desktop GUI and a browser-based front end. The
project was developed for the **Software Development In Practice**
module at the University of Liverpool.

The application supports the four required operations - Create,
Delete, Update and Search/Display - over three record types and
persists data to the file system as JSON when the window is closed.

## Features

- Create, update, delete and search client, airline and flight records.
- Filter the records table by record type and free-text search.
- Sortable columns - click any column heading in the records table.
- Combo boxes for selecting an existing client or airline when adding
  a flight, removing the need to remember numeric IDs.
- Referential integrity - a client or airline cannot be deleted while
  any flight still references it.
- Strong field validation: phone numbers, postcodes, dates, required
  fields and ID types are all checked before a record is saved.
- Atomic JSON saves with an automatic `.bak` backup of the previous
  file, so a crashed write cannot lose existing data.
- Export the current filtered view to CSV from the File menu.
- Status bar showing total / filtered record counts.
- Separate browser front end in `web_frontend/` with HTML, CSS and
  JavaScript, including Flask-backed JSON storage, local-storage demo
  fallback, and data import/export controls.
- Unit tests for every non-GUI module using Python's `unittest`.

## Project Structure

```text
record_management_system/
  __init__.py        Package metadata and convenience re-exports.
  records.py         Record model: field lists, builders, validation.
  storage.py         JSON load/save with backup and atomic writes.
  manager.py         RecordManager - CRUD, search, queries, statistics.
  gui.py             Tkinter user interface.
  main.py            Application entry point and logging setup.
  web.py             Flask entry point for the browser front end.
tests/
  test_records.py    Builder, validator and helper tests.
  test_storage.py    JSON load / save round-trip tests.
  test_manager.py    CRUD, search and reference-integrity tests.
  test_gui.py        Pure GUI helpers (Tkinter independent).
  test_main.py       Entry-point smoke tests.
  test_web.py        Flask API and browser backend tests.
data/
  records.json       Created on first save.
docs/
  report_draft.md    Coursework report.
  github_setup.md    Setup and commit-message guide for the team.
web_frontend/
  index.html         Browser-based front end.
  styles.css         Browser front-end styling.
  app.js             Browser front-end behaviour and validation.
```

## Run The Application

From the project folder run:

```powershell
python -m record_management_system.main
```

If your Windows install only has the Python launcher:

```powershell
py -m record_management_system.main
```

The first run creates `data/records.json` automatically when the window
is closed.

## Run The Browser Front End

For the full browser front end backed by Python and `records.json`, run:

```powershell
python -m record_management_system.web
```

Then open:

```text
http://127.0.0.1:5000
```
If Flask is not installed, run:

```powershell
python -m pip install flask
```

You can also open this file directly in a browser for a local-storage
only demo:

```text
web_frontend/index.html
```

When served through Flask, the browser front end reads and writes the
same JSON record structure through `/api/records`. When opened directly
as a file, it falls back to browser local storage.

## Run The Tests

```powershell
python -m unittest discover -s tests -v
```

All 82 unit tests should pass.

## Record Format

The internal data structure is a single `list` of dictionaries
(`records: list = [{}, {}]`) as required by the brief.  Each dictionary
is one of three record types:

### Client Record

| Field | Type | Notes |
|-------|------|-------|
| ID | int | Auto-generated on creation |
| Type | str | Always `"Client"` |
| Name | str | Required |
| Address Line 1, 2, 3 | str | Optional |
| City, State, Country | str | Optional |
| Zip Code | str | Optional, validated when supplied |
| Phone Number | str | Required, validated |

### Airline Record

| Field | Type | Notes |
|-------|------|-------|
| ID | int | Auto-generated on creation |
| Type | str | Always `"Airline"` |
| Company Name | str | Required |

### Flight Record

| Field | Type | Notes |
|-------|------|-------|
| Type | str | Always `"Flight"` (kept for the shared list) |
| Client_ID | int | Must reference an existing client |
| Airline_ID | int | Must reference an existing airline |
| Date | str | ISO date or date-time |
| Start City | str | Required |
| End City | str | Required, must differ from Start City |

## Implementation Notes

- **Tkinter / ttk** is used for the GUI because it is part of the
  Python standard library and runs the same way on every platform.
- **JSON** was chosen as the storage format because the file produced
  is easy to inspect, easy to edit by hand for debugging, and easy to
  open in any text editor.
- The GUI module is intentionally a thin shell around the
  `RecordManager` so that almost all business logic can be exercised
  by fast, headless unit tests.
- The application saves automatically when the window is closed
  (`WM_DELETE_WINDOW` is bound to `RecordManagementGUI.close`) and
  there is also a Save button and `Ctrl+S` shortcut for manual saves.

## Team Roles And Source Control

See [`docs/github_setup.md`](docs/github_setup.md) for the GitHub
workflow and the PyInstaller-style commit message standard used by the
team.  Roles (GUI/UX, Programmer, Project Manager, Tester) are
described in [`docs/report_draft.md`](docs/report_draft.md).
