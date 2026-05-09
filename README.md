# Record Management System

A Python/Tkinter record management system for a specialist travel agent.
The application manages three record types:

- Client records
- Airline company records
- Flight records

Records are stored internally as a `list` of dictionaries and saved to
`data/records.json` when the application closes.

## Features

- Create client, airline, and flight records.
- Search and display records by record type or free-text search.
- Update a selected record.
- Delete a selected record.
- Save records to JSON and load them again on startup.
- Unit tests for the core modules.

## Project Structure

```text
record_management_system/
  __init__.py
  gui.py
  main.py
  manager.py
  records.py
  storage.py
tests/
  test_gui.py
  test_main.py
  test_manager.py
  test_records.py
  test_storage.py
data/
  records.json
docs/
  github_setup.md
  report_draft.md
```

## Run The Application

From the project folder:

```powershell
python -m record_management_system.main
```

If Windows has the Python launcher installed instead:

```powershell
py -m record_management_system.main
```

## Run The Tests

```powershell
python -m unittest discover -s tests
```

## Notes For The Team

- The GUI is in `record_management_system/gui.py`.
- The main business logic is in `record_management_system/manager.py`.
- Record validation and dictionary formatting are in
  `record_management_system/records.py`.
- JSON loading and saving is in `record_management_system/storage.py`.

Flight records include `Type: "Flight"` internally so they can be stored in
the same list as client and airline records. Client and airline IDs are
generated automatically. Flight records store `Client_ID` and `Airline_ID`
references to existing records.

