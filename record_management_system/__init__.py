"""Record management system package.

A Python / Tkinter application that lets a specialist travel agent
manage client, airline and flight records from a single window.

The public entry point is :func:`record_management_system.main.main`,
exposed for convenience here as well.
"""

from .manager import RecordManager  # noqa: F401  - re-exported for tests

__all__ = ["__version__", "RecordManager"]

__version__ = "1.0.0"
