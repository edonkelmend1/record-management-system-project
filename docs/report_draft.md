# Record Management System - Project Report

University of Liverpool, *Software Development In Practice*

## 1. Introduction

This report accompanies a Python Record Management System built for a
specialist travel agent.  The application supports the four mandatory
operations - Create, Delete, Update and Search/Display - over three
record types: clients, airline companies and flight bookings.  The
records are held in memory as a single list of dictionaries and
persisted to the file system as JSON, matching the storage options
allowed by the project brief.

The aim of the system is to replace the informal collection of
spreadsheets and paper notes that a small travel agency would
otherwise rely on.  Booking staff need to find a customer's contact
details quickly, attach those details to a specific airline, and
confirm a flight booking with the start city, end city and travel
date.  The application gives them a single graphical window in which
to do all of that, while protecting the underlying data against
typical mistakes such as deleting a customer who still has open
bookings.

## 2. Requirements Coverage

The project brief specifies several mandatory requirements.  The table
below lists each one against the part of the codebase that implements
it, so that the implementation can be cross-checked against the brief
during marking.

| Requirement | Implementation |
|-------------|----------------|
| Graphical user interface | `record_management_system/gui.py` |
| Create / Update / Delete / Search/Display | Buttons on the form panel; backed by `RecordManager` methods |
| Internal list of dictionaries | `RecordManager.records: list[dict]` |
| Saved to file system as JSON | `record_management_system/storage.py` |
| Saved when the application closes | `RecordManagementGUI.close()` bound to `WM_DELETE_WINDOW` |
| Storage check on application start | `RecordManager.from_file()` calls `load_records()` which returns `[]` when the file is missing |
| Three record types with specified fields | `records.py` defines `CLIENT_FIELDS`, `AIRLINE_FIELDS`, `FLIGHT_FIELDS` |
| Unit tests for each module | `tests/test_records.py`, `test_storage.py`, `test_manager.py`, `test_gui.py`, `test_main.py` |
| Source control (Git) | Repository initialised at the project root |
| PyInstaller-style commit messages | Documented in `docs/github_setup.md` |

## 3. System Architecture

The project is split into five Python modules inside the
`record_management_system` package.  Each module has a single,
well-defined responsibility, which makes the code easier to test and
also matches the team's role allocation.

* `records.py` defines the three record types, their field lists and a
  family of pure builder functions (`build_client_record`,
  `build_airline_record`, `build_flight_record`) that return a fully
  validated dictionary.  It also exposes lower-level helpers
  (`clean_text`, `parse_int`, `validate_phone`, `validate_zipcode`,
  `normalise_datetime`) so the same validation rules are applied
  everywhere a value is accepted from the user.
* `storage.py` is responsible for reading and writing the JSON file.
  It performs an atomic write by saving to a temporary file first and
  then renaming it over the previous file, and it copies the existing
  file to `records.json.bak` before each save so a corrupted write can
  always be recovered.
* `manager.py` contains the `RecordManager` class - the single object
  the GUI interacts with.  The manager owns the in-memory list and
  exposes the high-level operations the brief asks for: `create`,
  `update`, `delete`, `search`, `list`, `save`, plus convenience
  queries such as `flights_for_client`, `statistics` and
  `client_choices` (used by the GUI combo boxes).
* `gui.py` builds the Tkinter window: a header banner, a toolbar with
  filter and search widgets, a sortable records table, an edit form
  whose fields adapt to the chosen record type, and a status bar.
  The colour palette and ttk styles are defined in one dictionary
  (`PALETTE`) so the look-and-feel can be tweaked without touching
  the rest of the file.
* `main.py` wires everything together.  It configures Python's
  `logging` package, computes the default path for `records.json`,
  builds a `RecordManager` from that path and hands it to the GUI.

This layered architecture is deliberate.  Pure functions live in
`records.py`, persistence is isolated in `storage.py`, business logic
lives in `manager.py`, and only `gui.py` and `main.py` depend on
Tkinter.  The whole application can therefore be exercised by unit
tests without ever opening a window, which is essential for fast
feedback during development and grading.

## 4. Data Model And Validation

The records are stored internally as `list[dict[str, Any]]`.  Each
dictionary has a `Type` key (`"Client"`, `"Airline"` or `"Flight"`)
that tells the rest of the system how to interpret the remaining
fields.  Although the brief does not explicitly list `Type` for
flight records, the application stores it internally because all
three record types share a single list; without `Type` we would have
no reliable way to filter the list by record kind.  The decision is
defended in section 9.

Validation is centralised in `records.py` and runs in three places:

1. When the user submits the form, the relevant `build_*` function is
   called, which checks types, required fields and value formats.
2. When records are loaded from disk, `validate_record` is called on
   every entry so a corrupted file is rejected with a clear message
   instead of silently breaking the application.
3. The same `validate_record` runs again before each save, so the
   in-memory list cannot drift away from the on-disk schema.

Specific rules of interest:

* IDs are integers, generated by `next_id()` which returns
  `max(existing_ids) + 1` per record type.  Records with malformed
  IDs are skipped so a single corrupt entry cannot break ID
  generation.
* Phone numbers must contain only digits, spaces, dashes, dots,
  parentheses and an optional leading `+`.
* Postcodes are optional but, when supplied, must be 2-12 characters
  of letters, digits, spaces and dashes - lax enough to match the
  many international postcode formats but tight enough to reject
  obvious junk.
* Dates use ISO format (`2026-05-09` or `2026-05-09 14:30`) and the
  parser accepts `/` as a date separator and `T` as a date/time
  separator, normalising everything back to ISO for storage.
* Flight bookings must reference an *existing* client and an
  *existing* airline.  Likewise a client or airline that is
  referenced by any flight cannot be deleted until that flight is
  removed first.  This referential integrity check is what makes the
  application reliable for real bookings.

## 5. Persistence Layer

The records are written to `data/records.json` next to the project
folder.  The file is created automatically on the first save, and on
startup the application loads it if it exists (returning an empty
list when it does not).  Both the create-on-save behaviour and the
empty-on-missing behaviour are covered by unit tests.

Two design choices in `storage.py` deserve a mention.  Saves are
performed atomically: the new content is written to a temporary file
in the same directory, fsynced, and then renamed over the target.  If
the program is interrupted (for example because Tkinter is force
killed) the existing JSON file is preserved.  In addition, before
each save the previous file is copied to `records.json.bak` so any
catastrophic save can be reverted by hand.  Both features are
straightforward operations that materially raise the reliability of
the system without complicating its public interface.

## 6. Graphical User Interface

The GUI is divided into four regions stacked vertically:

1. A **header banner** with the application name and a one-line
   description, styled in the project's dark navy colour.
2. A **toolbar** containing a type filter combobox, a search entry
   that updates the table as the user types, a "Clear" button to
   reset both filter and search, and a "Save" button to write to
   disk on demand.
3. A **records table** built from `ttk.Treeview`.  Each row shows the
   internal index, the record type, a one-line summary, and a
   compact detail string.  Clicking any column header sorts the
   table by that field; clicking it again reverses the order.
   Selecting a row populates the edit form below.
4. A **record form** whose fields change based on the chosen record
   type, plus four buttons - Create, Update Selected, Delete
   Selected, Clear Form.  For flight records the `Client_ID` and
   `Airline_ID` text fields are replaced with combo boxes that list
   every existing client or airline by ID and name, removing the
   need for the user to remember numeric identifiers.

A persistent **status bar** at the bottom of the window summarises
the record counts (total, by type, filtered) and reports the result
of the last operation, providing constant feedback without modal
dialogs.

The application also has a small **menu bar** with File and Help
menus.  The File menu offers "Save Now" (also bound to `Ctrl+S`),
"Export Filtered to CSV…" - which writes the currently filtered view
to a user-chosen CSV file - and "Exit".  These are extras beyond the
strict project brief but they make the application noticeably more
useful for a working travel agent without changing the data model.

An additional browser-based front end was added in `web_frontend/`
using HTML, CSS and JavaScript. It follows the supplied preview design
more closely, with top tabs for Clients, Airlines and Flights, a
full-width record table, a Filters panel above the table, and a form
panel that only appears when the user creates a new record or selects
a record and chooses "Edit Selected". The selected table row is shown
in dark blue so the user can clearly see which record is active.

The browser front end does not replace the Tkinter application. It is
a separate interface that demonstrates the same record-management
workflow in a web-style layout. It supports create, update, delete,
search, filtering, sorting, flight dropdowns, example data, local
storage, and Import Data / Export Data controls.

## 7. Testing Strategy

The repository contains a `tests/` folder with five test modules, one
per source module, and 79 individual test cases written using
Python's built-in `unittest` framework.  No third-party packages are
required to run them.

Coverage falls into four groups:

* **Builder and validation tests** in `test_records.py` exercise
  every helper function with both well-formed and intentionally
  broken inputs, including edge cases such as boolean values being
  passed where integers are expected and date strings using `/` or
  `T` as separators.
* **Persistence tests** in `test_storage.py` cover the missing-file
  case, valid round-trips, parent-directory creation, the backup
  file produced on overwrite, and several rejection cases.
* **Manager tests** in `test_manager.py` cover the full CRUD
  lifecycle, search and filter, referential-integrity checks (a
  client used by a flight cannot be deleted), statistics, and the
  sort helper.
* **GUI helper tests** in `test_gui.py` cover the pure helper
  `form_fields_for` and the palette dictionary, which are
  Tkinter-independent.  The full GUI is not instantiated in tests
  because `tkinter.Tk()` cannot be created on a headless test
  runner.

Tests can be run from the project root with:

```text
python -m unittest discover -s tests -v
```

All 75 tests pass on a clean install of Python 3.10.

## 8. Source Control And Workflow

Git is used for version control.  The repository follows the
PyInstaller commit message conventions specified in the brief:

* one logical change per commit;
* subject line under 50 characters;
* subject prefixed by a subsystem name (`gui`, `manager`, `storage`,
  `tests`, `docs`);
* present tense and a closing period on the subject line;
* an optional body, separated by a blank line, wrapped at about 72
  characters.

`docs/github_setup.md` contains the exact commands the repository
owner runs to push the project to GitHub and to add the lecturer as a
collaborator.  Each team member pulls before working on a new change
and pushes a small, well-described commit when their change is
complete.

## 9. Design Decisions And Trade-offs

Three decisions are worth explaining in detail because they shaped
the rest of the project.

**Single list with a Type field rather than three separate lists.**
The brief states that records are stored as `records: list = [{}, {}]`.
A natural alternative would be to keep clients, airlines and flights
in three separate lists, but that would not match the wording of the
brief and would make `Search and Display a Record` harder to
implement because a single search box would have to consult three
data structures.  Adding a `Type` key to every record keeps the
storage format honest with the brief while allowing the table to
present every record type in one view.

**JSON instead of pickle or JSONL.**  Pickle would save bytes but
the resulting file is opaque, ties the application to a specific
Python version, and is unsafe to load from untrusted sources.  JSONL
makes sense for log-like data sets that grow unbounded, but a travel
agent's record set is small and is overwritten in full on save,
which is exactly the workload regular JSON serves best.  The single
JSON file is also easy to email to the lecturer for inspection.

**Atomic writes and `.bak` backups.**  These features are not in the
brief but they are inexpensive to add and they prevent the most
common cause of lost data - a crash mid-write.  They are an example
of how the system has been hardened beyond the minimum requirements
without changing the public interface.

## 10. Team Roles

Each member of the group holds one or more of the four required
roles.  Because the modules were designed around clear seams, role
ownership maps directly onto specific files:

* **Programmer** - owns the Python logic in `records.py`,
  `storage.py`, `manager.py` and `main.py`, runs the linter, and
  reviews pull requests touching these files.
* **GUI / UX Designer** - owns `gui.py`, the colour palette, the
  layout grids, the keyboard shortcuts and the menu.  Works with
  the Programmer when a new manager method is needed to support a
  GUI behaviour.
* **Tester** - owns the `tests/` folder, extends test coverage as
  features are added, and runs the full suite before each push.
  Also drives a short manual checklist (create one of each record
  type, restart the app, confirm everything reloaded correctly).
* **Project Manager** - maintains the issue list, makes sure the
  brief is being met, owns `docs/`, the report and the final zip
  submission, and confirms that all team members have an identical
  copy of the code at submission time.

The roles overlap whenever it helps - for example the Tester often
spots a usability issue and discusses it with the GUI/UX Designer
before opening a ticket.

## 11. Future Improvements

The current system meets the brief and adds several quality-of-life
features.  Further work could include drop-down date pickers for the
flight date field, CSV import for users who prefer spreadsheet-based
workflows, and a swap from JSON to a local SQLite database using
Python's built-in `sqlite3` module if the travel agent's data set grew
beyond a few thousand records.  None of these are necessary for the
project but each is a low-risk extension of the current
architecture.

## 12. Conclusion

The Record Management System delivers the four CRUD operations
required by the brief over three record types, persists the data as
JSON, reloads automatically on startup, validates everything that
crosses its public interface and is covered by 79 passing unit
tests.  The codebase is small enough to be read end-to-end in an
afternoon while still being structured into clear, single-purpose
modules.  The architecture supports the team's role allocation and
the project's source-control conventions, and leaves obvious room for
future improvement without rework.
