"""Application entry point.

This module wires the storage, manager and GUI layers together and
provides the ``main()`` function used both by ``python -m
record_management_system.main`` and by the ``__main__.py`` shim.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .manager import RecordManager


def default_data_path() -> Path:
    """Return the default JSON storage path.

    The path is computed relative to the project folder so the app
    behaves the same whether it is launched from the IDE or from a
    terminal.
    """

    return Path(__file__).resolve().parents[1] / "data" / "records.json"


def configure_logging() -> None:
    """Configure root logging for the running application."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_manager(storage_path: Path | str | None = None) -> RecordManager:
    """Build the application record manager bound to ``storage_path``."""

    return RecordManager.from_file(storage_path or default_data_path())


def main() -> None:
    """Run the Tkinter application.

    Tkinter is imported lazily so that the rest of the package can be
    imported (and tested) on systems where tkinter is not installed.
    """

    import tkinter as tk

    from .gui import RecordManagementGUI

    configure_logging()
    root = tk.Tk()
    app = RecordManagementGUI(root, build_manager())
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
