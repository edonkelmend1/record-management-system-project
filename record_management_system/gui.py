"""Tkinter graphical user interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .manager import RecordManager
from .records import (
    AIRLINE,
    CLIENT,
    FLIGHT,
    RECORD_TYPES,
    record_details,
    summarize_record,
)

FORM_FIELDS = {
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


def form_fields_for(record_type: str) -> list[str]:
    """Return editable form fields for a record type."""

    if record_type not in FORM_FIELDS:
        raise ValueError("Unknown record type.")
    return list(FORM_FIELDS[record_type])


class RecordManagementGUI:
    """A Tkinter GUI for CRUD operations over travel records."""

    def __init__(self, root: tk.Tk, manager: RecordManager) -> None:
        self.root = root
        self.manager = manager
        self.form_entries: dict[str, ttk.Entry] = {}
        self.form_type = tk.StringVar(value=CLIENT)
        self.filter_type = tk.StringVar(value="All")
        self.search_text = tk.StringVar()

        self.root.title("Record Management System")
        self.root.minsize(920, 600)

        self._build_layout()
        self._refresh_table()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(4, weight=1)

        ttk.Label(toolbar, text="Filter").grid(row=0, column=0, padx=(0, 4))
        filter_menu = ttk.Combobox(
            toolbar,
            textvariable=self.filter_type,
            values=("All", *RECORD_TYPES),
            width=12,
            state="readonly",
        )
        filter_menu.grid(row=0, column=1, padx=(0, 12))
        filter_menu.bind("<<ComboboxSelected>>", lambda _event: self._refresh_table())

        ttk.Label(toolbar, text="Search").grid(row=0, column=2, padx=(0, 4))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_text)
        search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8))
        search_entry.bind("<Return>", lambda _event: self._refresh_table())
        toolbar.columnconfigure(3, weight=1)

        ttk.Button(toolbar, text="Search", command=self._refresh_table).grid(
            row=0,
            column=4,
            padx=4,
        )
        ttk.Button(toolbar, text="Clear", command=self._clear_search).grid(
            row=0,
            column=5,
            padx=4,
        )
        ttk.Button(toolbar, text="Save", command=self._save_records).grid(
            row=0,
            column=6,
            padx=(12, 0),
        )

        table_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("index", "type", "summary", "details")
        self.table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.table.heading("index", text="Index")
        self.table.heading("type", text="Type")
        self.table.heading("summary", text="Summary")
        self.table.heading("details", text="Details")
        self.table.column("index", width=70, anchor="center")
        self.table.column("type", width=100, anchor="center")
        self.table.column("summary", width=280)
        self.table.column("details", width=420)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<<TreeviewSelect>>", self._load_selected_record)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.table.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)

        self.form_frame = ttk.LabelFrame(self.root, text="Record Form", padding=10)
        self.form_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.form_frame.columnconfigure(1, weight=1)
        self.form_frame.columnconfigure(3, weight=1)

        type_menu = ttk.Combobox(
            self.form_frame,
            textvariable=self.form_type,
            values=RECORD_TYPES,
            width=16,
            state="readonly",
        )
        ttk.Label(self.form_frame, text="Record Type").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 6),
            pady=4,
        )
        type_menu.grid(row=0, column=1, sticky="w", pady=4)
        type_menu.bind("<<ComboboxSelected>>", lambda _event: self._draw_form_fields())

        self.fields_container = ttk.Frame(self.form_frame)
        self.fields_container.grid(row=1, column=0, columnspan=4, sticky="ew")
        self.fields_container.columnconfigure(1, weight=1)
        self.fields_container.columnconfigure(3, weight=1)

        buttons = ttk.Frame(self.form_frame)
        buttons.grid(row=2, column=0, columnspan=4, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Create", command=self._create_record).grid(
            row=0,
            column=0,
            padx=4,
        )
        ttk.Button(buttons, text="Update Selected", command=self._update_record).grid(
            row=0,
            column=1,
            padx=4,
        )
        ttk.Button(buttons, text="Delete Selected", command=self._delete_record).grid(
            row=0,
            column=2,
            padx=4,
        )
        ttk.Button(buttons, text="Clear Form", command=self._clear_form).grid(
            row=0,
            column=3,
            padx=4,
        )

        self._draw_form_fields()

    def _draw_form_fields(self) -> None:
        for child in self.fields_container.winfo_children():
            child.destroy()

        self.form_entries.clear()
        fields = form_fields_for(self.form_type.get())

        for index, field in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(self.fields_container, text=field).grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 6),
                pady=4,
            )
            entry = ttk.Entry(self.fields_container)
            entry.grid(
                row=row,
                column=column + 1,
                sticky="ew",
                padx=(0, 12),
                pady=4,
            )
            self.form_entries[field] = entry

    def _form_values(self) -> dict[str, Any]:
        return {
            field: entry.get()
            for field, entry in self.form_entries.items()
        }

    def _refresh_table(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)

        for index, record in self.manager.search_records(
            self.search_text.get(),
            self.filter_type.get(),
        ):
            self.table.insert(
                "",
                "end",
                values=(
                    index,
                    record.get("Type", ""),
                    summarize_record(record),
                    record_details(record),
                ),
            )

    def _clear_search(self) -> None:
        self.search_text.set("")
        self.filter_type.set("All")
        self._refresh_table()

    def _clear_form(self) -> None:
        for entry in self.form_entries.values():
            entry.delete(0, tk.END)
        self.table.selection_remove(self.table.selection())

    def _create_record(self) -> None:
        try:
            self.manager.create_record(self.form_type.get(), self._form_values())
        except ValueError as exc:
            messagebox.showerror("Could not create record", str(exc))
            return
        self._refresh_table()
        self._clear_form()

    def _update_record(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Select a record", "Choose a record to update.")
            return

        try:
            self.manager.update_record(index, self._form_values())
        except (IndexError, ValueError) as exc:
            messagebox.showerror("Could not update record", str(exc))
            return
        self._refresh_table()

    def _delete_record(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Select a record", "Choose a record to delete.")
            return

        if not messagebox.askyesno("Delete record", "Delete the selected record?"):
            return

        try:
            self.manager.delete_record(index)
        except (IndexError, ValueError) as exc:
            messagebox.showerror("Could not delete record", str(exc))
            return
        self._refresh_table()
        self._clear_form()

    def _load_selected_record(self, _event: tk.Event[Any] | None = None) -> None:
        index = self._selected_index()
        if index is None:
            return

        try:
            record = self.manager.get_record(index)
        except IndexError:
            return

        self.form_type.set(record["Type"])
        self._draw_form_fields()
        for field, entry in self.form_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(record.get(field, "")))

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

    def _save_records(self) -> None:
        try:
            self.manager.save()
        except ValueError as exc:
            messagebox.showerror("Could not save records", str(exc))
            return
        messagebox.showinfo("Saved", "Records were saved.")

    def close(self) -> None:
        """Save records and close the window."""

        try:
            self.manager.save()
        except ValueError as exc:
            messagebox.showerror("Could not save records", str(exc))
            return
        self.root.destroy()
