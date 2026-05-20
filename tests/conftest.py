"""Pytest session hooks for the Record Management System test suite.

When a test session includes any tests from ``perf.py``, the performance
line chart is displayed in a blocking window after the session finishes.
"""

from __future__ import annotations

import sys


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """Show the performance chart after a session that ran perf tests."""
    ran_perf = any(
        "perf" in str(getattr(item, "fspath", ""))
        for item in session.items
    )
    if not ran_perf:
        return

    # The perf module will already be in sys.modules because pytest
    # imported it to collect tests.  Search by the attribute rather than
    # by a fixed module name so it works regardless of how pytest resolves
    # the path (e.g. 'perf' vs 'tests.perf').
    perf_mod = next(
        (
            mod
            for mod in sys.modules.values()
            if (getattr(mod, "__file__", None) or "").endswith("perf.py")
            and hasattr(mod, "show_performance_chart")
        ),
        None,
    )
    if perf_mod is not None:
        perf_mod.show_performance_chart()
