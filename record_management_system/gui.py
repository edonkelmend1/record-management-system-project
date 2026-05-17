"""Tkinter graphical user interface for the record management system.

The interface follows a familiar three-pane layout:

* a **toolbar** at the top containing search and filter widgets;
* a **records table** in the middle that lists every record matching
  the current filter and supports sorting by clicking column headers;
* an **edit form** at the bottom whose fields automatically change to
  match the currently selected record type.

The colour palette and ttk styling are kept conservative and
professional - dark navy headers, a clean white surface and a blue
accent colour for interactive widgets - to make the application
suitable for use in a travel-agent office context.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .manager import RecordManager, sort_records
from .records import (
    AIRLINE,
    CLIENT,
    FLIGHT,
    RECORD_TYPES,
    record_details,
    summarize_record,
)

# ---------------------------------------------------------------------------
# Form definitions
# ---------------------------------------------------------------------------

# The fields the user can edit for each record type.  System-generated
# fields (``ID`` and ``Type``) are omitted because the manager handles
# them automatically.
FORM_FIELDS: dict[str, list[str]] = {
    CLIENT: [
        "Name",
        "Address Line 1",
        "Address Line 2",
        "Address Line 3",
        "City",
        "State",
        "Zip Code",
        "Country",
        "Phone Number",
    ],
    AIRLINE: ["Company Name"],
    FLIGHT: ["Client_ID", "Airline_ID", "Date", "Start City", "End City"],
}

# Colour palette - kept here so the entire window can be re-themed by
# changing a single dictionary.
PALETTE = {
    "background": "#f4f6fb",
    "surface": "#ffffff",
    "header": "#1f3354",
    "header_text": "#ffffff",
    "accent": "#2c6cdf",
    "accent_text": "#ffffff",
    "muted_text": "#516079",
    "danger": "#b3261e",
}


def form_fields_for(record_type: str) -> list[str]:
    """Return the editable form fields for ``record_type``."""

    if record_type not in FORM_FIELDS:
        raise ValueError("Unknown record type.")
    return list(FORM_FIELDS[record_type])


# ---------------------------------------------------------------------------
# GUI class
# ---------------------------------------------------------------------------


class RecordManagementGUI:
    """A Tkinter GUI for CRUD operations over travel records."""

    TABLE_COLUMNS = ("index", "type", "summary", "details")
    TABLE_HEADINGS = {
        "index": "#",
        "type": "Type",
        "summary": "Summary",
        "details": "Details",
    }

    def __init__(self, root: tk.Tk, manager: RecordManager) -> None:
        self.root = root
        self.manager = manager
        self.form_entries: dict[str, tk.Widget] = {}
        self.form_type = tk.StringVar(value=CLIENT)
        self.filter_type = tk.StringVar(value="All")
        self.search_text = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready.")
        self._sort_column: str | None = None
        self._sort_reverse = False

        # Tk variables used to back the flight combo boxes.
        self._client_choice = tk.StringVar()
        self._airline_choice = tk.StringVar()

        self.root.title("Travel Agent - Record Management System")
        self.root.minsize(1000, 660)
        self.root.configure(bg=PALETTE["background"])

        self._configure_styles()
        self._build_menu()
        self._build_layout()
        self._refresh_table()
        self._update_status()

    # ------------------------------------------------------------------
    # Theme / menu setup
    # ------------------------------------------------------------------

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        # ``clam`` is the most consistent theme across Windows/macOS/Linux
        # for the ttk widgets we are using here.
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=PALETTE["background"],
            foreground="#1c1c1c",
            font=("Segoe UI", 10),
        )
        style.configure("TFrame", background=PALETTE["background"])
        style.configure("Surface.TFrame", background=PALETTE["surface"])
        style.configure(
            "Header.TLabel",
            background=PALETTE["header"],
            foreground=PALETTE["header_text"],
            font=("Segoe UI", 14, "bold"),
            padding=(16, 10),
        )
        style.configure(
            "SubHeader.TLabel",
            background=PALETTE["header"],
            foreground=PALETTE["header_text"],
            font=("Segoe UI", 9),
            padding=(16, 0, 16, 10),
        )
        style.configure(
            "Status.TLabel",
            background=PALETTE["header"],
            foreground=PALETTE["header_text"],
            padding=(10, 4),
        )
        style.configure("TLabelframe", background=PALETTE["background"])
        style.configure(
            "TLabelframe.Label",
            background=PALETTE["background"],
            foreground=PALETTE["header"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Accent.TButton",
            background=PALETTE["accent"],
            foreground=PALETTE["accent_text"],
            padding=(12, 6),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#1f5ac1"), ("disabled", "#9fbdef")],
        )
        style.configure(
            "Danger.TButton",
            background=PALETTE["danger"],
            foreground="#ffffff",
            padding=(12, 6),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#8d1c17"), ("disabled", "#d7a7a4")],
        )
        style.configure("TButton", padding=(10, 5))
        style.configure(
            "Treeview",
            background=PALETTE["surface"],
            fieldbackground=PALETTE["surface"],
            rowheight=26,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=PALETTE["header"],
            foreground=PALETTE["header_text"],
            font=("Segoe UI", 10, "bold"),
            padding=(8, 6),
        )
        style.map(
            "Treeview",
            background=[("selected", PALETTE["accent"])],
            foreground=[("selected", "#ffffff")],
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Save Now", command=self._save_records, accelerator="Ctrl+S")
        file_menu.add_command(label="Export Filtered to CSV...", command=self._export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.bind_all("<Control-s>", lambda _event: self._save_records())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # ---------------------- header banner -------------------------
        header = ttk.Frame(self.root)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="Travel Agent - Record Management System",
            style="Header.TLabel",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="Manage clients, airlines and flight bookings",
            style="SubHeader.TLabel",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew")

        # ---------------------- toolbar -------------------------------
        toolbar = ttk.Frame(self.root, padding=(14, 10, 14, 6))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(3, weight=1)

        ttk.Label(toolbar, text="Filter by type:").grid(row=0, column=0, padx=(0, 6))
        filter_menu = ttk.Combobox(
            toolbar,
            textvariable=self.filter_type,
            values=("All", *RECORD_TYPES),
            width=12,
            state="readonly",
        )
        filter_menu.grid(row=0, column=1, padx=(0, 16))
        filter_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_table())

        ttk.Label(toolbar, text="Search:").grid(row=0, column=2, padx=(0, 6))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_text)
        search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8))
        search_entry.bind("<Return>", lambda _e: self._refresh_table())
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_table())

        ttk.Button(
            toolbar,
            text="Clear",
            command=self._clear_search,
        ).grid(row=0, column=4, padx=4)
        ttk.Button(
            toolbar,
            text="Save",
            style="Accent.TButton",
            command=self._save_records,
        ).grid(row=0, column=5, padx=(12, 0))

        # ---------------------- records table -------------------------
        table_frame = ttk.Frame(self.root, padding=(14, 0, 14, 8))
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.table = ttk.Treeview(
            table_frame,
            columns=self.TABLE_COLUMNS,
            show="headings",
            selectmode="browse",
        )
        for column in self.TABLE_COLUMNS:
            self.table.heading(
                column,
                text=self.TABLE_HEADINGS[column],
                command=lambda col=column: self._sort_by(col),
            )
        self.table.column("index", width=60, anchor="center", stretch=False)
        self.table.column("type", width=100, anchor="center", stretch=False)
        self.table.column("summary", width=320, anchor="w")
        self.table.column("details", width=460, anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<<TreeviewSelect>>", self._load_selected_record)

        # Row striping for readability
        self.table.tag_configure("oddrow", background="#f8f9fc")
        self.table.tag_configure("evenrow", background=PALETTE["surface"])

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.table.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)

        # ---------------------- form ----------------------------------
        self.form_frame = ttk.LabelFrame(self.root, text="Record Form", padding=14)
        self.form_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.form_frame.columnconfigure(1, weight=1)
        self.form_frame.columnconfigure(3, weight=1)

        ttk.Label(self.form_frame, text="Record Type:").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 8)
        )
        type_menu = ttk.Combobox(
            self.form_frame,
            textvariable=self.form_type,
            values=RECORD_TYPES,
            width=18,
            state="readonly",
        )
        type_menu.grid(row=0, column=1, sticky="w", pady=(0, 8))
        type_menu.bind("<<ComboboxSelected>>", lambda _e: self._draw_form_fields())

        self.fields_container = ttk.Frame(self.form_frame)
        self.fields_container.grid(row=1, column=0, columnspan=4, sticky="ew")
        self.fields_container.columnconfigure(1, weight=1)
        self.fields_container.columnconfigure(3, weight=1)

        buttons = ttk.Frame(self.form_frame)
        buttons.grid(row=2, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(
            buttons,
            text="Create",
            style="Accent.TButton",
            command=self._create_record,
        ).grid(row=0, column=0, padx=4)
        ttk.Button(
            buttons,
            text="Update Selected",
            command=self._update_record,
        ).grid(row=0, column=1, padx=4)
        ttk.Button(
            buttons,
            text="Delete Selected",
            style="Danger.TButton",
            command=self._delete_record,
        ).grid(row=0, column=2, padx=4)
        ttk.Button(
            buttons,
            text="Clear Form",
            command=self._clear_form,
        ).grid(row=0, column=3, padx=4)

        # ---------------------- status bar ----------------------------
        status = ttk.Label(
            self.root,
            textvariable=self.status_text,
            style="Status.TLabel",
            anchor="w",
        )
        status.grid(row=4, column=0, sticky="ew")

        self._draw_form_fields()

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _draw_form_fields(self) -> None:
        for child in self.fields_container.winfo_children():
            child.destroy()

        self.form_entries.clear()
        record_type = self.form_type.get()
        fields = form_fields_for(record_type)

        for index, field in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(self.fields_container, text=field + ":").grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 6),
                pady=4,
            )

            # For flight records, replace the raw Client_ID / Airline_ID
            # entries with comboboxes containing the existing options.
            if record_type == FLIGHT and field == "Client_ID":
                widget = self._make_id_combobox(self._client_choice, self.manager.client_choices())
            elif record_type == FLIGHT and field == "Airline_ID":
                widget = self._make_id_combobox(self._airline_choice, self.manager.airline_choices())
            else:
                widget = ttk.Entry(self.fields_container)

            widget.grid(
                row=row,
                column=column + 1,
                sticky="ew",
                padx=(0, 14),
                pady=4,
            )
            self.form_entries[field] = widget

    def _make_id_combobox(self, variable: tk.StringVar, choices: list[tuple[int, str]]) -> ttk.Combobox:
        values = [label for _id, label in choices]
        combo = ttk.Combobox(
            self.fields_container,
            textvariable=variable,
            values=values,
            state="normal",
        )
        return combo

    def _form_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field, widget in self.form_entries.items():
            value = widget.get() if hasattr(widget, "get") else ""
            # Comboboxes for Client_ID / Airline_ID may show the
            # "#1 Name" label - extract the numeric prefix.
            if field in {"Client_ID", "Airline_ID"} and isinstance(value, str):
                value = value.strip()
                if value.startswith("#"):
                    value = value[1:].split(" ", 1)[0]
            values[field] = value
        return values

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)

        results = self.manager.search_records(
            self.search_text.get(),
            self.filter_type.get(),
        )
        if self._sort_column:
            sort_key = self._column_to_field(self._sort_column)
            if sort_key:
                results = sort_records(results, sort_key, self._sort_reverse)

        for row_index, (index, record) in enumerate(results):
            tag = "evenrow" if row_index % 2 == 0 else "oddrow"
            self.table.insert(
                "",
                "end",
                values=(
                    index,
                    record.get("Type", ""),
                    summarize_record(record, self.manager.records),
                    record_details(record, self.manager.records),
                ),
                tags=(tag,),
            )
        self._update_status(filtered=len(results))

    def _column_to_field(self, column: str) -> str | None:
        return {
            "index": "ID",
            "type": "Type",
            "summary": "Name",
            "details": "City",
        }.get(column)

    def _sort_by(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._refresh_table()

    def _clear_search(self) -> None:
        self.search_text.set("")
        self.filter_type.set("All")
        self._sort_column = None
        self._sort_reverse = False
        self._refresh_table()

    def _clear_form(self) -> None:
        for widget in self.form_entries.values():
            if isinstance(widget, ttk.Combobox):
                widget.set("")
            elif hasattr(widget, "delete"):
                widget.delete(0, tk.END)
        self.table.selection_remove(self.table.selection())

    # ------------------------------------------------------------------
    # CRUD button handlers
    # ------------------------------------------------------------------

    def _create_record(self) -> None:
        try:
            record = self.manager.create_record(
                self.form_type.get(),
                self._form_values(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not create record", str(exc))
            return
        self._refresh_table()
        self._clear_form()
        self._draw_form_fields()
        self.status_text.set(f"Created {record.get('Type', 'record')}.")

    def _update_record(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Select a record", "Choose a record in the table to update.")
            return

        try:
            self.manager.update_record(index, self._form_values())
        except (IndexError, ValueError) as exc:
            messagebox.showerror("Could not update record", str(exc))
            return
        self._refresh_table()
        self.status_text.set("Updated selected record.")

    def _delete_record(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Select a record", "Choose a record in the table to delete.")
            return

        if not messagebox.askyesno(
            "Delete record",
            "Delete the selected record? This action cannot be undone.",
        ):
            return

        try:
            self.manager.delete_record(index)
        except (IndexError, ValueError) as exc:
            messagebox.showerror("Could not delete record", str(exc))
            return
        self._refresh_table()
        self._clear_form()
        self._draw_form_fields()
        self.status_text.set("Deleted selected record.")

    # ------------------------------------------------------------------
    # Selection / status
    # ------------------------------------------------------------------

    def _load_selected_record(self, _event: tk.Event | None = None) -> None:
        index = self._selected_index()
        if index is None:
            return

        try:
            record = self.manager.get_record(index)
        except IndexError:
            return

        self.form_type.set(record["Type"])
        self._draw_form_fields()
        for field, widget in self.form_entries.items():
            value = str(record.get(field, ""))
            if isinstance(widget, ttk.Combobox) and field in {"Client_ID", "Airline_ID"}:
                widget.set(value)
            elif hasattr(widget, "delete") and hasattr(widget, "insert"):
                widget.delete(0, tk.END)
                widget.insert(0, value)

    def _selected_index(self) -> int | None:
        selection = self.table.selection()
        if not selection:
            return None
        values = self.table.item(selection[0], "values")
        if not values:
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def _update_status(self, filtered: int | None = None) -> None:
        stats = self.manager.statistics()
        message = (
            f"{stats['Total']} total - "
            f"{stats[CLIENT]} clients - "
            f"{stats[AIRLINE]} airlines - "
            f"{stats[FLIGHT]} flights"
        )
        if filtered is not None and filtered != stats["Total"]:
            message = f"Showing {filtered} of " + message
        self.status_text.set(message)

    # ------------------------------------------------------------------
    # File menu actions
    # ------------------------------------------------------------------

    def _save_records(self) -> None:
        try:
            self.manager.save()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save records", str(exc))
            return
        self.status_text.set("Records saved.")

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="records_export.csv",
            title="Export filtered records to CSV",
        )
        if not path:
            return

        import csv

        results = self.manager.search_records(
            self.search_text.get(),
            self.filter_type.get(),
        )

        columns: list[str] = ["Index"]
        for _index, record in results:
            for key in record:
                if key not in columns:
                    columns.append(key)

        try:
            with open(path, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(columns)
                for index, record in results:
                    writer.writerow([index] + [record.get(col, "") for col in columns[1:]])
        except OSError as exc:
            messagebox.showerror("Could not export records", str(exc))
            return

        self.status_text.set(f"Exported {len(results)} record(s) to CSV.")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Travel Agent Record Management System\n"
            "University of Liverpool - Software Development In Practice\n\n"
            "A Python / Tkinter application for managing client, airline\n"
            "and flight records using a JSON file store.",
        )

    # ------------------------------------------------------------------
    # Application close
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Save records and close the window."""

        try:
            self.manager.save()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save records", str(exc))
            return
        self.root.destroy()
