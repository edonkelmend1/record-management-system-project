"""Application entry point."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .gui import RecordManagementGUI
from .manager import RecordManager


def default_data_path() -> Path:
    """Return the default JSON storage path."""

    return Path(__file__).resolve().parents[1] / "data" / "records.json"


def build_manager(storage_path: Path | str | None = None) -> RecordManager:
    """Build the application record manager."""

    return RecordManager.from_file(storage_path or default_data_path())


def main() -> None:
    """Run the Tkinter application."""

    root = tk.Tk()
    app = RecordManagementGUI(root, build_manager())
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()

