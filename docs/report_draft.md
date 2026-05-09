# Record Management System Report Draft

## Introduction

This project is a record management system designed for a specialist travel
agent. The application gives staff a simple graphical interface for managing
the key records used in daily travel booking work. The system stores client
records, airline company records, and flight records. These three areas were
chosen because they represent the basic information needed to connect a
customer to a travel booking and the airline company involved in that booking.

The main purpose of the application is to make record handling clearer and
more reliable than keeping information in separate documents or informal
notes. A user can create new records, search and display existing records,
update records when information changes, and delete records that are no longer
needed. The design is intentionally straightforward so it can be used by a
small office without requiring database administration knowledge.

## System Design

The system is written in Python and uses Tkinter for the graphical user
interface. Tkinter was chosen because it is included with standard Python
installations and does not require additional third-party packages. This keeps
the application easier to run on different computers and makes it suitable for
an academic group project.

The records are stored internally as a list of dictionaries. This matches the
project requirement and keeps the data model easy to understand. Each
dictionary represents one record. Client records contain an ID, type, name,
address lines, city, state, zip code, country, and phone number. Airline
records contain an ID, type, and company name. Flight records contain a type,
client ID, airline ID, date, start city, and end city. The flight type is
stored internally so flight records can be held in the same list as the other
record types.

The system saves records to a JSON file called `records.json` inside the
`data` folder. JSON was selected because it is readable, easy to inspect, and
well supported by Python. When the application starts, it checks whether the
file exists. If the file exists, the records are loaded. If it does not exist,
the application starts with an empty list. When the user closes the
application, the current records are written back to the file system.

## Modules

The program is divided into several modules to keep the code organized.
`records.py` defines the record fields and validation functions. This module
is responsible for building correctly formatted client, airline, and flight
record dictionaries. `storage.py` handles loading from and saving to JSON.
`manager.py` contains the main record management logic. It creates, updates,
deletes, searches, and lists records. `gui.py` contains the Tkinter graphical
interface. `main.py` is the entry point that connects the storage, manager,
and GUI together.

This separation makes the project easier to test. The business logic can be
tested without opening the GUI. It also makes team work easier because each
team member can focus on a different part of the application.

## User Interface

The graphical interface is designed around a table of records and an edit
form. The user can filter the table by record type or search using text. When
a record is selected, the form is filled with its values. The user can then
update or delete the selected record. To add a new record, the user chooses a
record type, fills in the form, and selects the create option.

The GUI supports the main required operations: create, delete, update, search,
and display. It also reduces mistakes by showing only the fields that belong
to the selected record type. For example, choosing a client record displays
client address and phone fields, while choosing a flight record displays
client ID, airline ID, date, start city, and end city.

## Validation

The system includes validation to protect the record list from invalid data.
Client and airline records receive automatically generated integer IDs. Flight
records require integer client and airline IDs. The manager checks that these
IDs refer to existing records before a flight can be created or updated. This
helps prevent flight bookings from being stored without a linked client or
airline company.

The date field is stored as an ISO formatted string so it can be saved in JSON
and read again consistently. The user may enter a date or date and time, such
as `2026-05-09` or `2026-05-09 14:30`.

## Testing

The project includes unit tests for the important modules. The tests cover
record creation, validation, JSON loading and saving, searching, updating, and
deleting. The tests use Python's built-in `unittest` framework, so no external
testing library is required. Testing the business logic separately from the
GUI makes the tests faster and more reliable.

## Source Control

The project should be managed using GitHub. Each team member should pull the
latest version before making changes and commit small logical updates. Commit
messages should follow the PyInstaller-style guidance requested in the brief:
use a subsystem prefix, present tense, a short summary line, and a period at
the end. Example prefixes for this project include `gui`, `manager`,
`storage`, `tests`, and `docs`.

## Team Roles

The group roles support the way the codebase is divided. The project manager
can maintain the task list, check that the brief is being met, and make sure
the final repository and report are submitted correctly. The programmer can
focus on the manager, record validation, storage, and the connection between
the modules. The GUI/UX designer can improve the Tkinter layout, button
placement, labels, and workflow so that the system is comfortable to use. The
tester can run the unit tests, add edge-case tests, and manually check the
interface using realistic travel-agent scenarios.

Clear role ownership reduces duplicated work. It also helps the team explain
individual contributions in the report and during any project discussion. At
the same time, the roles can overlap when needed. For example, a tester may
identify a GUI issue and work with the programmer to make the behavior easier
to test.

## Future Improvements

The current system meets the required brief, but there are several ways it
could be improved. A future version could add drop-down lists for selecting
existing clients and airlines when creating a flight. This would reduce typing
errors because the user would not need to enter numeric IDs manually. Another
improvement would be stronger reporting, such as showing all flights for one
client or all bookings connected to one airline company.

The storage layer could also be replaced with a database if the travel agent
needed to handle a much larger number of records. For this assignment, JSON is
appropriate because the brief requires file-system storage and the data set is
small. Keeping the current JSON approach also makes the saved records easy for
the team and lecturer to inspect.

## Conclusion

The record management system meets the core requirements of the project by
providing a graphical interface, supporting create/read/update/delete
operations, storing records as a list of dictionaries, saving data to the file
system, and including unit tests. The modular structure also supports the
group roles of programmer, GUI/UX designer, tester, and project manager.
