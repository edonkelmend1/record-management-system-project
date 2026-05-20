"""Performance profiling suite for the Record Management System.

Three test categories are provided:

``TestProcessPerformance``
    Launches ``python -m record_management_system.main`` as a child process,
    samples its RSS memory and CPU utilisation every 100 ms for five seconds,
    then terminates it gracefully.  This measures real-world startup cost
    including Tkinter and all package imports.

``TestWebPerformance``
    Launches ``python -m record_management_system.web`` and drives HTTP
    traffic against it.  Measures response latency, body size, HTTP status
    codes, HTML structural integrity (``GET /``), JSON API correctness
    (``GET /api/records``, ``PUT /api/records``), concurrent throughput,
    and server-side CPU/RSS under load.

``TestComponentPerformance``
    In-process micro-benchmarks for ``RecordManager`` CRUD, search, and
    persistence operations.  Because no GUI is involved these results
    reflect pure business-logic cost.

Results from every test run are appended to::

    ~/Desktop/desktop_perf.log

Usage::

    python tests/perf.py
    python -m pytest tests/perf.py -v

Requirements::

    pip install psutil
"""

from __future__ import annotations

import html.parser
import json
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple

# ---------------------------------------------------------------------------
# psutil guard
# ---------------------------------------------------------------------------

try:
    import psutil
except ImportError:
    print(
        "psutil is required for performance tests.  "
        "Install it with:  pip install psutil",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Where all performance results are written (same directory as this file).
LOG_PATH: Path = Path(__file__).resolve().parent / "desktop_perf.log"

#: Seconds between resource samples while the target process is running.
SAMPLE_INTERVAL_S: float = 0.1

#: How long to let the application run before measuring and terminating it.
MONITOR_DURATION_S: float = 5.0

#: Root directory of the project (one level above this file's tests/ folder).
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

#: Host and port the Flask development server binds to (must match web.py).
WEB_HOST: str = "127.0.0.1"
WEB_PORT: int = 5000
WEB_BASE_URL: str = f"http://{WEB_HOST}:{WEB_PORT}"

#: Maximum seconds to wait for the Flask server to accept its first request.
SERVER_READY_TIMEOUT_S: float = 15.0

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _build_logger() -> logging.Logger:
    """Configure and return the module-level performance logger.

    Output goes to both ``LOG_PATH`` (append mode) and stdout so results
    are visible in the terminal as well as persisted on disk.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("perf")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # avoid duplicate handlers on repeated imports

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


log: logging.Logger = _build_logger()

# ---------------------------------------------------------------------------
# Chart data collector
# ---------------------------------------------------------------------------

#: Accumulated (group, label, value, threshold, unit) tuples for the plot.
_perf_data: list[tuple[str, str, float, float, str]] = []

#: Title of the chart block currently being written (set by log_chart_header).
_current_chart_group: str = ""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Sample(NamedTuple):
    """A single point-in-time resource snapshot for a monitored process."""

    timestamp: float      # monotonic clock value in seconds
    cpu_percent: float    # instantaneous CPU usage across all cores (%)
    rss_bytes: int        # resident set size in bytes
    vms_bytes: int        # virtual memory size in bytes
    num_threads: int      # number of OS threads in the process


class HttpResult(NamedTuple):
    """Metrics captured from a single HTTP request."""

    method: str           # HTTP verb (GET, PUT, …)
    url: str              # full URL requested
    status_code: int      # HTTP response status code
    elapsed_ms: float     # round-trip time in milliseconds
    body_bytes: int       # response body size in bytes
    content_type: str     # Content-Type response header value
    body: bytes           # raw response body


# ---------------------------------------------------------------------------
# HTML helper
# ---------------------------------------------------------------------------


class _TagCollector(html.parser.HTMLParser):
    """Minimal HTML parser that records tag names and the <title> text.

    Used to validate structural integrity of ``GET /`` responses without
    pulling in an external dependency such as *beautifulsoup4*.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tags: set[str] = set()
        self.title_text: str = ""
        self._in_title: bool = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.tags.add(tag.lower())
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_get(url: str, timeout: float = 5.0) -> HttpResult:
    """Issue a GET request and return an :class:`HttpResult`.

    :class:`urllib.error.HTTPError` responses (4xx/5xx) are captured and
    returned as results rather than raised, so callers can assert on the
    status code directly.
    """
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return HttpResult(
                method="GET",
                url=url,
                status_code=resp.status,
                elapsed_ms=elapsed_ms,
                body_bytes=len(body),
                content_type=resp.headers.get("Content-Type", ""),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return HttpResult(
            method="GET",
            url=url,
            status_code=exc.code,
            elapsed_ms=elapsed_ms,
            body_bytes=len(body),
            content_type=exc.headers.get("Content-Type", ""),
            body=body,
        )


def _http_put(
    url: str,
    payload: dict,
    timeout: float = 5.0,
) -> HttpResult:
    """Issue a PUT request with a JSON payload and return an
    :class:`HttpResult`.

    The request body is serialised to UTF-8 JSON.  4xx/5xx responses are
    captured rather than raised.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return HttpResult(
                method="PUT",
                url=url,
                status_code=resp.status,
                elapsed_ms=elapsed_ms,
                body_bytes=len(body),
                content_type=resp.headers.get("Content-Type", ""),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return HttpResult(
            method="PUT",
            url=url,
            status_code=exc.code,
            elapsed_ms=elapsed_ms,
            body_bytes=len(body),
            content_type=exc.headers.get("Content-Type", ""),
            body=body,
        )


def _wait_for_server(
    url: str,
    max_wait_s: float = SERVER_READY_TIMEOUT_S,
    interval_s: float = 0.25,
) -> bool:
    """Poll *url* until the server responds or the timeout expires.

    :returns: ``True`` if the server replied before the deadline, else
              ``False``.
    """
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1.0)
            return True
        except urllib.error.HTTPError:
            # Any HTTP response (even 4xx) means the server is up.
            return True
        except Exception:
            time.sleep(interval_s)
    return False


def log_http_result(result: HttpResult, label: str) -> None:
    """Write a formatted HTTP metrics block to the log.

    :param result: The :class:`HttpResult` to log.
    :param label:  Human-readable description of the request.
    """
    log.info("  [HTTP] %-46s", label)
    log.info(
        "    Status       : %d  |  Time : %.1f ms  |  Size : %d B",
        result.status_code,
        result.elapsed_ms,
        result.body_bytes,
    )
    log.info("    Content-Type : %s", result.content_type or "(none)")


# ---------------------------------------------------------------------------
# Monitoring helpers
# ---------------------------------------------------------------------------


def monitor_process(
    proc: subprocess.Popen,
    duration: float,
    interval: float,
) -> List[Sample]:
    """Poll *proc* for CPU and memory metrics until *duration* seconds elapse.

    Sampling uses :mod:`psutil` and runs in the calling thread.  The first
    ``cpu_percent`` call always returns 0.0 (OS limitation), so we issue a
    warm-up call before the main loop starts.

    :param proc: Running subprocess to monitor.
    :param duration: Maximum number of seconds to monitor.
    :param interval: Seconds to sleep between successive samples.
    :returns: List of :class:`Sample` objects, possibly empty if the process
              exits immediately.
    """
    samples: List[Sample] = []
    deadline = time.monotonic() + duration

    try:
        ps = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        log.warning("Process %d vanished before monitoring could start.", proc.pid)
        return samples

    # Warm-up: first call always yields 0.0 and must be discarded.
    try:
        ps.cpu_percent(interval=None)
    except psutil.NoSuchProcess:
        return samples

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log.info("Process exited early (return code %d).", proc.returncode)
            break
        try:
            mem_info = ps.memory_info()
            samples.append(
                Sample(
                    timestamp=time.monotonic(),
                    cpu_percent=ps.cpu_percent(interval=None),
                    rss_bytes=mem_info.rss,
                    vms_bytes=mem_info.vms,
                    num_threads=ps.num_threads(),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process may have exited between the poll() check and here.
            break
        time.sleep(interval)

    return samples


def log_summary(samples: List[Sample], label: str) -> dict:
    """Compute descriptive statistics from *samples* and write them to the log.

    :param samples: Non-empty list of :class:`Sample` objects.
    :param label:   Human-readable name for this measurement run.
    :returns:       Dictionary of computed metrics, or empty dict when no
                    samples were collected.
    """
    if not samples:
        log.warning("[%s] No samples were collected.", label)
        return {}

    cpu_values = [s.cpu_percent for s in samples]
    rss_values = [s.rss_bytes for s in samples]
    duration_s = samples[-1].timestamp - samples[0].timestamp

    metrics = {
        "sample_count": len(samples),
        "duration_s": duration_s,
        "cpu_mean_pct": statistics.mean(cpu_values),
        "cpu_peak_pct": max(cpu_values),
        "rss_min_mb": min(rss_values) / 1_048_576,
        "rss_mean_mb": statistics.mean(rss_values) / 1_048_576,
        "rss_peak_mb": max(rss_values) / 1_048_576,
        "threads_peak": max(s.num_threads for s in samples),
    }

    log.info("--- %s ---", label)
    log.info(
        "  Samples : %d  (%.1f s window)",
        metrics["sample_count"],
        metrics["duration_s"],
    )
    log.info(
        "  CPU     : mean=%.1f%%  peak=%.1f%%",
        metrics["cpu_mean_pct"],
        metrics["cpu_peak_pct"],
    )
    log.info(
        "  RSS MB  : min=%.1f  mean=%.1f  peak=%.1f",
        metrics["rss_min_mb"],
        metrics["rss_mean_mb"],
        metrics["rss_peak_mb"],
    )
    log.info("  Threads : peak=%d", metrics["threads_peak"])

    return metrics


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------


def _render_bar(value: float, maximum: float, width: int = 32) -> str:
    """Return a fixed-width block-character progress bar.

    The filled portion is proportional to ``value / maximum``.  When
    *value* exceeds *maximum* the bar is rendered fully filled so an
    overflow condition is immediately obvious.

    :param value:   Current metric value.
    :param maximum: Scale ceiling, typically the pass/fail threshold.
    :param width:   Total bar width in characters.
    :returns:       String of ``█`` (filled) and ``░`` (empty) characters.
    """
    if maximum <= 0:
        ratio = 1.0
    else:
        ratio = min(value / maximum, 1.0)
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def log_chart_header(title: str) -> None:
    """Write a labelled opening divider for a chart block.

    Also sets the active group name used by :func:`log_perf_bar` when
    appending entries to the plot data collector.

    Output goes to both the log file and directly to the terminal via
    ``sys.__stdout__`` so the chart is always visible regardless of
    pytest's stdout capture.
    """
    global _current_chart_group
    _current_chart_group = title
    line = f"  .-- Chart: {title}"
    log.info(line)
    print(line, file=sys.__stdout__, flush=True)


def log_chart_footer() -> None:
    """Write the closing divider of a chart block to file and screen."""
    line = "  '" + "-" * 67
    log.info(line)
    print(line, file=sys.__stdout__, flush=True)


def log_perf_bar(
    label: str,
    value: float,
    threshold: float,
    unit: str,
    fmt: str = "%.1f",
    width: int = 32,
) -> None:
    """Write one metric as a labelled bar chart row with PASS/FAIL status.

    Output goes to both the log file and directly to the terminal via
    ``sys.__stdout__`` so charts are visible under pytest without ``-s``.

    Output format::

        | label          [████████████████░░░░░░░░░░░░░░░░]  val / max  unit  [PASS]

    A fully-filled bar (``█`` × *width*) accompanied by ``[FAIL]``
    indicates the measured value exceeded the threshold.

    :param label:     Metric name, truncated/padded to 14 characters.
    :param value:     Measured value.
    :param threshold: Pass/fail ceiling; also sets bar scale.
    :param unit:      Unit label, e.g. ``'ms'``, ``'MB'``, ``'%'``, ``'s'``.
    :param fmt:       ``printf``-style format for value and threshold numbers.
    :param width:     Number of block characters in the bar.
    """
    bar = _render_bar(value, threshold, width)
    status = "[PASS]" if value <= threshold else "[FAIL]"
    val_s = (fmt % value).rjust(9)
    thr_s = (fmt % threshold).ljust(9)
    line = (
        f"  | {label[:14]:<14} [{bar}]"
        f"  {val_s} / {thr_s} {unit:<4}  {status}"
    )
    log.info(line)
    print(line, file=sys.__stdout__, flush=True)

    # Feed the plot data collector so show_performance_chart() can plot this.
    _perf_data.append(
        (_current_chart_group, label, value, threshold, unit)
    )


# ---------------------------------------------------------------------------
# Test suite 1 – full process measurement
# ---------------------------------------------------------------------------


class TestProcessPerformance(unittest.TestCase):
    """Measure CPU and RSS memory while the full application is running.

    The test launches ``python -m record_management_system.main`` as a
    child process, samples resource usage every :data:`SAMPLE_INTERVAL_S`
    seconds for :data:`MONITOR_DURATION_S` seconds, then terminates the
    process.  Assertions verify that peak RSS and mean CPU stay within the
    thresholds defined as class attributes.

    Adjust :attr:`MAX_RSS_PEAK_MB` and :attr:`MAX_CPU_MEAN_PCT` to match
    acceptable baselines for the target hardware.
    """

    # ---------------------------------------------------------------
    # Thresholds — tune these to match your hardware baseline.
    # ---------------------------------------------------------------

    #: Peak RSS allowed before the test fails (megabytes).
    MAX_RSS_PEAK_MB: float = 300.0

    #: Mean CPU utilisation allowed before the test fails (percent).
    MAX_CPU_MEAN_PCT: float = 80.0

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _launch_app(self) -> subprocess.Popen:
        """Start the application as a detached child process.

        ``TK_SILENCE_DEPRECATION`` suppresses the macOS deprecation banner
        so it does not pollute the log.
        """
        env = os.environ.copy()
        env.setdefault("TK_SILENCE_DEPRECATION", "1")

        return subprocess.Popen(
            [sys.executable, "-m", "record_management_system.main"],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _terminate(self, proc: subprocess.Popen) -> None:
        """Attempt a graceful SIGTERM; escalate to SIGKILL if needed."""
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            log.warning("Process did not terminate cleanly; sending SIGKILL.")
            proc.kill()
            proc.wait()

    # ---------------------------------------------------------------
    # Tests
    # ---------------------------------------------------------------

    def test_startup_resource_usage(self):
        """Monitor resource usage for MONITOR_DURATION_S seconds after launch.

        Asserts that:

        * Peak RSS stays below :attr:`MAX_RSS_PEAK_MB`.
        * Mean CPU stays below :attr:`MAX_CPU_MEAN_PCT`.
        """
        log.info("=" * 60)
        log.info("TEST  TestProcessPerformance.test_startup_resource_usage")
        log.info("Launching: python -m record_management_system.main")

        proc = self._launch_app()
        wall_start = time.monotonic()

        try:
            samples = monitor_process(
                proc, MONITOR_DURATION_S, SAMPLE_INTERVAL_S
            )
        finally:
            self._terminate(proc)

        elapsed = time.monotonic() - wall_start
        log.info("Process terminated after %.2f s.", elapsed)

        # Capture any stderr output for diagnostic context.
        stderr_output = proc.stderr.read().decode(errors="replace").strip()
        if stderr_output:
            log.debug("Process stderr:\n%s", stderr_output)

        metrics = log_summary(samples, "startup_resource_usage")

        if not metrics:
            self.skipTest(
                "Process exited before any samples could be collected.  "
                "Check stderr output above for details."
            )

        log_chart_header("Tkinter app startup — resource vs threshold")
        log_perf_bar(
            "CPU mean",
            metrics["cpu_mean_pct"],
            self.MAX_CPU_MEAN_PCT,
            "%",
        )
        log_perf_bar(
            "RSS peak",
            metrics["rss_peak_mb"],
            self.MAX_RSS_PEAK_MB,
            "MB",
        )
        log_chart_footer()

        self.assertLessEqual(
            metrics["rss_peak_mb"],
            self.MAX_RSS_PEAK_MB,
            (
                f"Peak RSS {metrics['rss_peak_mb']:.1f} MB exceeds "
                f"threshold {self.MAX_RSS_PEAK_MB} MB."
            ),
        )
        self.assertLessEqual(
            metrics["cpu_mean_pct"],
            self.MAX_CPU_MEAN_PCT,
            (
                f"Mean CPU {metrics['cpu_mean_pct']:.1f}% exceeds "
                f"threshold {self.MAX_CPU_MEAN_PCT}%."
            ),
        )


# ---------------------------------------------------------------------------
# Test suite 2 – Flask web server HTTP metrics
# ---------------------------------------------------------------------------


class TestWebPerformance(unittest.TestCase):
    """Measure HTTP latency, response size, and content for the web server.

    The class manages the Flask server subprocess lifecycle via
    ``setUpClass`` / ``tearDownClass`` so the server starts once for the
    full suite and is shared across all test methods.

    Metrics recorded per test:

    ``test_index_html_metrics``
        GET /: status, latency, body size, Content-Type, tag presence
        (``<html>``, ``<head>``, ``<body>``), and ``<title>`` text.

    ``test_api_get_records_json_metrics``
        GET /api/records: status, latency, body size, Content-Type,
        valid JSON, ``records`` array present and typed correctly.

    ``test_api_put_records_latency``
        PUT /api/records: write round-trip latency and response structure.

    ``test_concurrent_get_throughput``
        10 simultaneous GET /api/records threads: total wall time, mean
        and peak per-request latency, and per-response status codes.

    ``test_server_resource_usage_under_load``
        CPU and RSS sampled while 20 sequential GETs are issued, giving
        resource cost under active request-handling rather than idle state.

    All thresholds are class attributes so they can be subclassed and
    tuned for a specific deployment target.
    """

    # ---------------------------------------------------------------
    # Thresholds — tune for your hardware and network environment.
    # ---------------------------------------------------------------

    #: Maximum acceptable round-trip time for a single GET (ms).
    MAX_GET_LATENCY_MS: float = 500.0

    #: Maximum acceptable round-trip time for a single PUT (ms).
    MAX_PUT_LATENCY_MS: float = 1000.0

    #: Maximum wall-clock time for 10 concurrent GET requests (s).
    MAX_CONCURRENT_WALL_S: float = 5.0

    #: Peak RSS limit while handling HTTP load (MB).
    MAX_RSS_PEAK_MB: float = 300.0

    # ---------------------------------------------------------------
    # Class-level server lifecycle
    # ---------------------------------------------------------------

    _proc: subprocess.Popen | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Launch the Flask server and block until it is ready."""
        log.info("=" * 60)
        log.info("CLASS SETUP  TestWebPerformance")
        log.info(
            "Launching: python -m record_management_system.web"
        )

        env = os.environ.copy()
        # Disable the reloader so the server runs as a single process,
        # making psutil PID tracking reliable.
        env["FLASK_ENV"] = "testing"

        cls._proc = subprocess.Popen(
            [sys.executable, "-m", "record_management_system.web"],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        ready = _wait_for_server(WEB_BASE_URL)
        if not ready:
            cls._terminate_server()
            raise unittest.SkipTest(
                f"Flask server did not become ready within "
                f"{SERVER_READY_TIMEOUT_S} s.  "
                "Is port 5000 already in use?"
            )

        log.info(
            "Server ready at %s  (PID %d).",
            WEB_BASE_URL,
            cls._proc.pid,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """Terminate the Flask server after all web tests have run."""
        cls._terminate_server()

    @classmethod
    def _terminate_server(cls) -> None:
        """SIGTERM the server; escalate to SIGKILL if it does not stop."""
        proc = cls._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.warning("Server did not stop cleanly; sending SIGKILL.")
            proc.kill()
            proc.wait()
        finally:
            stderr_out = (
                proc.stderr.read().decode(errors="replace").strip()
            )
            if stderr_out:
                log.debug("Server stderr:\n%s", stderr_out)
            log.info("Web server terminated.")

    # ---------------------------------------------------------------
    # Tests
    # ---------------------------------------------------------------

    def test_index_html_metrics(self) -> None:
        """GET / — measure latency, body size, and HTML structural checks.

        HTML metrics logged:

        * HTTP status code (expected 200)
        * Round-trip latency in milliseconds
        * Response body size in bytes
        * Content-Type header value
        * All HTML tag names encountered in the response
        * ``<title>`` element text content
        * Presence of ``<html>``, ``<head>``, and ``<body>`` tags
        """
        log.info("=" * 60)
        log.info("TEST  TestWebPerformance.test_index_html_metrics")

        result = _http_get(WEB_BASE_URL)
        log_http_result(result, "GET /  (HTML index page)")

        collector = _TagCollector()
        collector.feed(result.body.decode("utf-8", errors="replace"))

        log.info(
            "    HTML tags found  : %s",
            ", ".join(sorted(collector.tags)) or "(none)",
        )
        log.info(
            "    <title> text     : %s",
            collector.title_text.strip() or "(none)",
        )

        log_chart_header("GET /  HTML page — latency vs threshold")
        log_perf_bar(
            "Latency",
            result.elapsed_ms,
            self.MAX_GET_LATENCY_MS,
            "ms",
        )
        log_chart_footer()

        self.assertEqual(
            result.status_code,
            200,
            f"GET / returned HTTP {result.status_code}, expected 200.",
        )
        self.assertIn(
            "text/html",
            result.content_type.lower(),
            "Content-Type for GET / must contain 'text/html'.",
        )
        self.assertLessEqual(
            result.elapsed_ms,
            self.MAX_GET_LATENCY_MS,
            (
                f"GET / took {result.elapsed_ms:.1f} ms, "
                f"threshold {self.MAX_GET_LATENCY_MS} ms."
            ),
        )
        self.assertGreater(
            result.body_bytes,
            0,
            "GET / returned an empty response body.",
        )
        for tag in ("html", "head", "body"):
            self.assertIn(
                tag,
                collector.tags,
                f"Expected <{tag}> tag in GET / HTML response.",
            )

    def test_api_get_records_json_metrics(self) -> None:
        """GET /api/records — measure latency, size, and JSON validity.

        JSON metrics logged:

        * HTTP status code (expected 200)
        * Round-trip latency in milliseconds
        * Response body size in bytes
        * Content-Type header value
        * Number of records present in the response payload
        """
        log.info("=" * 60)
        log.info(
            "TEST  TestWebPerformance"
            ".test_api_get_records_json_metrics"
        )

        result = _http_get(f"{WEB_BASE_URL}/api/records")
        log_http_result(result, "GET /api/records  (JSON API)")

        payload = json.loads(result.body)
        record_count = len(payload.get("records", []))
        log.info("    Records in payload : %d", record_count)

        log_chart_header("GET /api/records — latency vs threshold")
        log_perf_bar(
            "Latency",
            result.elapsed_ms,
            self.MAX_GET_LATENCY_MS,
            "ms",
        )
        log_chart_footer()

        self.assertEqual(result.status_code, 200)
        self.assertIn(
            "application/json",
            result.content_type.lower(),
            "Content-Type for /api/records must be application/json.",
        )
        self.assertLessEqual(
            result.elapsed_ms,
            self.MAX_GET_LATENCY_MS,
            (
                f"GET /api/records took {result.elapsed_ms:.1f} ms, "
                f"threshold {self.MAX_GET_LATENCY_MS} ms."
            ),
        )
        self.assertIn(
            "records",
            payload,
            "Response JSON must contain a 'records' key.",
        )
        self.assertIsInstance(
            payload["records"],
            list,
            "'records' value must be a JSON array.",
        )

    def test_api_put_records_latency(self) -> None:
        """PUT /api/records — measure write round-trip latency.

        Sends an empty records list and verifies the server responds with
        HTTP 200 and echoes the same ``records`` structure back.  This
        exercises the full JSON deserialise → validate → save → serialise
        path without requiring pre-existing data.
        """
        log.info("=" * 60)
        log.info(
            "TEST  TestWebPerformance.test_api_put_records_latency"
        )

        result = _http_put(
            f"{WEB_BASE_URL}/api/records", {"records": []}
        )
        log_http_result(result, "PUT /api/records  (write round-trip)")

        log_chart_header("PUT /api/records — latency vs threshold")
        log_perf_bar(
            "Latency",
            result.elapsed_ms,
            self.MAX_PUT_LATENCY_MS,
            "ms",
        )
        log_chart_footer()

        self.assertEqual(
            result.status_code,
            200,
            f"PUT /api/records returned HTTP {result.status_code}.",
        )
        self.assertLessEqual(
            result.elapsed_ms,
            self.MAX_PUT_LATENCY_MS,
            (
                f"PUT /api/records took {result.elapsed_ms:.1f} ms, "
                f"threshold {self.MAX_PUT_LATENCY_MS} ms."
            ),
        )
        payload = json.loads(result.body)
        self.assertIn(
            "records",
            payload,
            "PUT response JSON must contain a 'records' key.",
        )

    def test_concurrent_get_throughput(self) -> None:
        """Fire 10 simultaneous GET /api/records; assert wall-clock time.

        Each request runs in its own :class:`threading.Thread`.  After all
        threads join, aggregate statistics are computed and logged:

        * Total wall-clock time for all requests to complete
        * Mean and peak per-request latency
        * Count of HTTP 200 responses
        """
        log.info("=" * 60)
        log.info(
            "TEST  TestWebPerformance.test_concurrent_get_throughput"
        )

        n_requests = 10
        results: list[HttpResult | None] = [None] * n_requests

        def worker(idx: int) -> None:
            results[idx] = _http_get(f"{WEB_BASE_URL}/api/records")

        wall_start = time.perf_counter()
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(n_requests)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall_elapsed = time.perf_counter() - wall_start

        valid = [r for r in results if r is not None]
        latencies = [r.elapsed_ms for r in valid]
        status_codes = [r.status_code for r in valid]

        log.info(
            "  [CONCURRENT] %d × GET /api/records", n_requests
        )
        log.info("    Wall time        : %.3f s", wall_elapsed)
        log.info(
            "    Latency (ms)     : mean=%.1f  peak=%.1f",
            statistics.mean(latencies),
            max(latencies),
        )
        log.info(
            "    HTTP 200 count   : %d / %d",
            status_codes.count(200),
            n_requests,
        )

        log_chart_header("10× concurrent GET — wall time & latency vs threshold")
        log_perf_bar(
            "Wall time",
            wall_elapsed * 1000,
            self.MAX_CONCURRENT_WALL_S * 1000,
            "ms",
        )
        log_perf_bar(
            "Lat mean",
            statistics.mean(latencies),
            self.MAX_GET_LATENCY_MS,
            "ms",
        )
        log_perf_bar(
            "Lat peak",
            max(latencies),
            self.MAX_GET_LATENCY_MS,
            "ms",
        )
        log_chart_footer()

        self.assertEqual(
            len(valid),
            n_requests,
            "One or more concurrent requests returned no result.",
        )
        self.assertLessEqual(
            wall_elapsed,
            self.MAX_CONCURRENT_WALL_S,
            (
                f"10 concurrent GETs took {wall_elapsed:.3f} s, "
                f"threshold {self.MAX_CONCURRENT_WALL_S} s."
            ),
        )
        for r in valid:
            self.assertEqual(
                r.status_code,
                200,
                "Concurrent GET /api/records returned "
                f"HTTP {r.status_code}.",
            )

    def test_server_resource_usage_under_load(self) -> None:
        """Sample CPU and RSS while 20 sequential GET requests are issued.

        Unlike the idle Tkinter process test, this drives real HTTP
        traffic so the resource samples reflect active request-handling
        cost.  A background thread samples the server process every
        :data:`SAMPLE_INTERVAL_S` seconds while the main thread issues
        the requests, then both threads rendezvous before assertions run.
        """
        log.info("=" * 60)
        log.info(
            "TEST  TestWebPerformance"
            ".test_server_resource_usage_under_load"
        )

        proc = self.__class__._proc
        if proc is None or proc.poll() is not None:
            self.skipTest("Server process is not running.")

        samples: List[Sample] = []
        stop_event = threading.Event()

        def sampler() -> None:
            try:
                ps = psutil.Process(proc.pid)
                ps.cpu_percent(interval=None)  # warm-up
            except psutil.NoSuchProcess:
                return
            while not stop_event.is_set():
                try:
                    mem = ps.memory_info()
                    samples.append(
                        Sample(
                            timestamp=time.monotonic(),
                            cpu_percent=ps.cpu_percent(interval=None),
                            rss_bytes=mem.rss,
                            vms_bytes=mem.vms,
                            num_threads=ps.num_threads(),
                        )
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                time.sleep(SAMPLE_INTERVAL_S)

        sample_thread = threading.Thread(target=sampler, daemon=True)
        sample_thread.start()

        for _ in range(20):
            _http_get(f"{WEB_BASE_URL}/api/records")

        stop_event.set()
        sample_thread.join(timeout=2)

        metrics = log_summary(samples, "web_server_under_load")

        if metrics:
            log_chart_header("Web server under load — resource vs threshold")
            log_perf_bar(
                "CPU mean",
                metrics["cpu_mean_pct"],
                80.0,
                "%",
            )
            log_perf_bar(
                "RSS peak",
                metrics["rss_peak_mb"],
                self.MAX_RSS_PEAK_MB,
                "MB",
            )
            log_chart_footer()

            self.assertLessEqual(
                metrics["rss_peak_mb"],
                self.MAX_RSS_PEAK_MB,
                (
                    f"Peak RSS under load "
                    f"{metrics['rss_peak_mb']:.1f} MB exceeds "
                    f"threshold {self.MAX_RSS_PEAK_MB} MB."
                ),
            )


# ---------------------------------------------------------------------------
# Test suite 3 – component micro-benchmarks
# ---------------------------------------------------------------------------


class TestComponentPerformance(unittest.TestCase):
    """In-process micro-benchmarks for core ``RecordManager`` operations.

    Each test constructs an isolated ``RecordManager`` backed by a temporary
    file so results are not affected by the contents of ``data/records.json``.
    Timing uses :func:`time.perf_counter` for sub-millisecond resolution.
    """

    # ---------------------------------------------------------------
    # Wall-clock thresholds (seconds) — tune for your hardware.
    # ---------------------------------------------------------------

    #: Maximum acceptable time to insert 100 client records.
    MAX_INSERT_100_S: float = 1.0

    #: Maximum acceptable time to search 100 records.
    MAX_SEARCH_S: float = 0.5

    #: Maximum acceptable time to perform a save + reload round-trip.
    MAX_SAVE_ROUNDTRIP_S: float = 2.0

    #: Maximum acceptable time to insert 100 flights (with dependencies).
    MAX_FLIGHT_INSERT_100_S: float = 2.0

    # ---------------------------------------------------------------
    # Set-up / tear-down
    # ---------------------------------------------------------------

    def setUp(self):
        """Create a fresh isolated manager and temporary directory."""
        from record_management_system.manager import RecordManager

        log.info("=" * 60)
        log.info(
            "TEST  TestComponentPerformance.%s", self._testMethodName
        )

        self._tmpdir = tempfile.TemporaryDirectory()
        data_file = Path(self._tmpdir.name) / "records.json"
        self.manager = RecordManager(storage_path=data_file)

    def tearDown(self):
        self._tmpdir.cleanup()

    # ---------------------------------------------------------------
    # Fixture helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _client_values(n: int) -> dict:
        """Return minimal valid client field values for record index *n*."""
        return {
            "Name": f"Perf Client {n:04d}",
            "Phone Number": f"+61 4{n:08d}",
            "City": "Sydney",
            "Country": "Australia",
        }

    @staticmethod
    def _airline_values(n: int) -> dict:
        """Return minimal valid airline field values for record index *n*."""
        return {"Company Name": f"Perf Airline {n:04d}"}

    @staticmethod
    def _flight_values(client_id: int, airline_id: int, n: int) -> dict:
        """Return valid flight field values referencing existing IDs."""
        return {
            "Client_ID": client_id,
            "Airline_ID": airline_id,
            "Date": "2026-06-01",
            "Start City": f"City {n}",
            "End City": f"City {n + 1000}",
        }

    # ---------------------------------------------------------------
    # Timing utility
    # ---------------------------------------------------------------

    def _time(self, label: str, fn, *args, **kwargs):
        """Execute *fn* and log its elapsed time.

        :returns: ``(result, elapsed_seconds)`` tuple.
        """
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        log.info("  %-52s %.4f s", label, elapsed)
        return result, elapsed

    # ---------------------------------------------------------------
    # Tests
    # ---------------------------------------------------------------

    def test_bulk_client_insert(self):
        """Insert 100 client records; assert total time < MAX_INSERT_100_S."""
        from record_management_system.records import CLIENT

        log.info("Benchmark: 100 × create_record(CLIENT)")

        def insert_100():
            for i in range(100):
                self.manager.create_record(CLIENT, self._client_values(i))

        _, elapsed = self._time("100 × create_record(CLIENT)", insert_100)

        log_chart_header("100× CLIENT insert — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_INSERT_100_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(
            elapsed,
            self.MAX_INSERT_100_S,
            (
                f"100 client inserts took {elapsed:.4f} s, "
                f"threshold is {self.MAX_INSERT_100_S} s."
            ),
        )

    def test_bulk_airline_insert(self):
        """Insert 100 airline records; assert total time < MAX_INSERT_100_S."""
        from record_management_system.records import AIRLINE

        log.info("Benchmark: 100 × create_record(AIRLINE)")

        def insert_100():
            for i in range(100):
                self.manager.create_record(AIRLINE, self._airline_values(i))

        _, elapsed = self._time("100 × create_record(AIRLINE)", insert_100)

        log_chart_header("100× AIRLINE insert — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_INSERT_100_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(elapsed, self.MAX_INSERT_100_S)

    def test_bulk_flight_insert(self):
        """Insert 100 flights after seeding one client and airline.

        Flights require referential-integrity checks on every insert, so
        this exercises a heavier code path than plain client/airline inserts.
        """
        from record_management_system.records import AIRLINE, CLIENT, FLIGHT

        self.manager.create_record(CLIENT, self._client_values(0))
        self.manager.create_record(AIRLINE, self._airline_values(0))

        log.info("Benchmark: 100 × create_record(FLIGHT)")

        def insert_100():
            for i in range(100):
                self.manager.create_record(
                    FLIGHT, self._flight_values(1, 1, i)
                )

        _, elapsed = self._time("100 × create_record(FLIGHT)", insert_100)

        log_chart_header("100× FLIGHT insert — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_FLIGHT_INSERT_100_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(
            elapsed,
            self.MAX_FLIGHT_INSERT_100_S,
            (
                f"100 flight inserts took {elapsed:.4f} s, "
                f"threshold is {self.MAX_FLIGHT_INSERT_100_S} s."
            ),
        )

    def test_search_after_bulk_insert(self):
        """Search 100 records for a specific name string.

        Verifies that linear scan performance stays below MAX_SEARCH_S even
        after a full bulk insert.
        """
        from record_management_system.records import CLIENT

        for i in range(100):
            self.manager.create_record(CLIENT, self._client_values(i))

        target = "Perf Client 0050"
        log.info("Benchmark: search_records('%s') over 100 records", target)

        results, elapsed = self._time(
            f"search_records('{target}')",
            self.manager.search_records,
            target,
        )

        log_chart_header("search_records() free-text — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_SEARCH_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(
            elapsed,
            self.MAX_SEARCH_S,
            f"Search took {elapsed:.4f} s, threshold is {self.MAX_SEARCH_S} s.",
        )
        self.assertGreaterEqual(
            len(results),
            1,
            f"Expected at least one match for '{target}', got none.",
        )

    def test_search_type_filtered(self):
        """Search with a record-type filter over a mixed dataset."""
        from record_management_system.records import AIRLINE, CLIENT

        for i in range(50):
            self.manager.create_record(CLIENT, self._client_values(i))
        for i in range(50):
            self.manager.create_record(AIRLINE, self._airline_values(i))

        log.info("Benchmark: search_records(type=CLIENT) over 100 records")

        results, elapsed = self._time(
            "search_records(type=CLIENT) over 100",
            self.manager.search_records,
            "",
            CLIENT,
        )

        log_chart_header("search_records() type-filtered — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_SEARCH_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(elapsed, self.MAX_SEARCH_S)
        self.assertEqual(len(results), 50)

    def test_save_reload_roundtrip(self):
        """Save 50 records to disk, then reload from the same path.

        Exercises the full JSON serialisation and deserialisation path.
        """
        from record_management_system.manager import RecordManager
        from record_management_system.records import CLIENT

        for i in range(50):
            self.manager.create_record(CLIENT, self._client_values(i))

        storage = self.manager.storage_path
        log.info("Benchmark: save() + from_file() round-trip with 50 records")

        def roundtrip():
            self.manager.save()
            return RecordManager.from_file(storage)

        reloaded, elapsed = self._time(
            "save() + from_file() (50 records)", roundtrip
        )

        log_chart_header("save + reload round-trip — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_SAVE_ROUNDTRIP_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(
            elapsed,
            self.MAX_SAVE_ROUNDTRIP_S,
            (
                f"Save+reload round-trip took {elapsed:.4f} s, "
                f"threshold is {self.MAX_SAVE_ROUNDTRIP_S} s."
            ),
        )
        self.assertEqual(
            len(reloaded.records),
            50,
            "Record count mismatch after reload.",
        )

    def test_list_records_performance(self):
        """List all records from a 100-record dataset."""
        from record_management_system.records import CLIENT

        for i in range(100):
            self.manager.create_record(CLIENT, self._client_values(i))

        log.info("Benchmark: list_records() over 100 records")

        results, elapsed = self._time(
            "list_records() (100 records)",
            self.manager.list_records,
        )

        log_chart_header("list_records() — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_SEARCH_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(elapsed, self.MAX_SEARCH_S)
        self.assertEqual(len(results), 100)

    def test_statistics_performance(self):
        """Compute statistics over a 150-record mixed dataset."""
        from record_management_system.records import AIRLINE, CLIENT, FLIGHT

        for i in range(50):
            self.manager.create_record(CLIENT, self._client_values(i))
        for i in range(50):
            self.manager.create_record(AIRLINE, self._airline_values(i))
        for i in range(50):
            self.manager.create_record(
                FLIGHT, self._flight_values(1, 1, i)
            )

        log.info("Benchmark: statistics() over 150 records")

        stats, elapsed = self._time(
            "statistics() (150 records)", self.manager.statistics
        )

        log_chart_header("statistics() — time vs threshold")
        log_perf_bar(
            "Elapsed",
            elapsed,
            self.MAX_SEARCH_S,
            "s",
            fmt="%.4f",
        )
        log_chart_footer()

        self.assertLessEqual(elapsed, self.MAX_SEARCH_S)
        self.assertEqual(stats["Total"], 150)


# ---------------------------------------------------------------------------
# Performance plot
# ---------------------------------------------------------------------------


def _short_group(title: str) -> str:
    """Extract a concise display name from a chart group title.

    Titles follow the pattern ``"<description> — <context>"``.  This
    function returns the description part, truncated to 20 characters.
    """
    name = title.split("—")[0].strip().rstrip(".")
    if len(name) > 20:
        name = name[:18] + "…"  # ellipsis
    return name


def show_performance_chart() -> None:
    """Render a line chart of every metric collected by :func:`log_perf_bar`.

    Each metric is normalised to a percentage of its threshold so all
    measurements share a single Y axis.  Values below 100 % are within
    bounds; a value at or above 100 % indicates a threshold violation.

    The chart is displayed in a blocking window.  If matplotlib is not
    installed the function logs a warning and returns without error.

    Call this after all tests have run (handled automatically via the
    ``conftest.py`` pytest hook and the ``__main__`` entry point).
    """
    if not _perf_data:
        return

    try:
        import matplotlib.lines as mlines
        import matplotlib.patches as mpatches
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning(
            "matplotlib not installed; skipping performance chart.  "
            "Install with:  pip install matplotlib"
        )
        print(
            "  [chart] matplotlib not installed — skipping plot.",
            file=sys.__stdout__,
            flush=True,
        )
        return

    # ---------------------------------------------------------------
    # Apply a clean plot style
    # ---------------------------------------------------------------
    for style in ("seaborn-v0_8-whitegrid", "seaborn-whitegrid"):
        try:
            plt.style.use(style)
            break
        except OSError:
            continue

    # ---------------------------------------------------------------
    # Build normalised data entries
    # ---------------------------------------------------------------
    entries = []
    for group, label, value, threshold, unit in _perf_data:
        pct = (value / threshold * 100.0) if threshold > 0 else 0.0
        entries.append({
            "x_label": f"{label}\n{_short_group(group)}",
            "pct": pct,
            "passed": pct <= 100.0,
            "raw": f"{value:.4g} {unit}",
        })

    xs = list(range(len(entries)))
    ys = [e["pct"] for e in entries]
    n_pass = sum(1 for e in entries if e["passed"])
    n_fail = len(entries) - n_pass
    y_top = max(120.0, max(ys, default=0) * 1.15)

    # ---------------------------------------------------------------
    # Figure and axes
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(max(12, len(entries) * 0.85), 7))

    # Shaded pass / fail bands
    ax.axhspan(0, 100, alpha=0.06, color="#27ae60", zorder=0)
    ax.axhspan(100, y_top, alpha=0.07, color="#e74c3c", zorder=0)

    # Threshold reference line
    ax.axhline(
        100,
        color="#e74c3c",
        linewidth=1.5,
        linestyle="--",
        alpha=0.75,
        zorder=2,
    )

    # Connecting line
    ax.plot(
        xs,
        ys,
        color="#2980b9",
        linewidth=2.0,
        alpha=0.85,
        zorder=3,
    )

    # Per-point markers, coloured by pass / fail status
    for xi, entry in zip(xs, entries):
        colour = "#27ae60" if entry["passed"] else "#e74c3c"
        ax.scatter(
            xi,
            entry["pct"],
            color=colour,
            s=90,
            zorder=5,
            edgecolors="white",
            linewidths=1.5,
        )

    # ---------------------------------------------------------------
    # Axes formatting
    # ---------------------------------------------------------------
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [e["x_label"] for e in entries],
        rotation=40,
        ha="right",
        fontsize=8.5,
    )
    ax.set_ylabel("% of threshold", fontsize=11)
    ax.set_ylim(0, y_top)
    ax.set_xlim(-0.5, max(len(entries) - 0.5, 0.5))

    # Remove top / right spines for a cleaner look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # ---------------------------------------------------------------
    # Title and legend
    # ---------------------------------------------------------------
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_str = (
        f"{n_pass} PASS" + (f"  •  {n_fail} FAIL" if n_fail else "")
    )
    ax.set_title(
        f"Performance vs Thresholds  ·  {status_str}  ·  {timestamp}",
        fontsize=13,
        fontweight="bold",
        pad=16,
    )

    legend_handles = [
        mlines.Line2D(
            [], [],
            color="#2980b9",
            linewidth=2,
            label="Metric value",
        ),
        mlines.Line2D(
            [], [],
            color="#e74c3c",
            linewidth=1.5,
            linestyle="--",
            label="Threshold (100 %)",
        ),
        mpatches.Patch(color="#27ae60", label="PASS  (≤ threshold)"),
        mpatches.Patch(color="#e74c3c", label="FAIL  (> threshold)"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=9,
        framealpha=0.85,
    )

    fig.tight_layout()
    plt.show(block=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    log.info("=" * 60)
    log.info(
        "Performance suite started at %s",
        datetime.now().isoformat(sep=" "),
    )
    log.info(
        "Suites : ProcessPerformance, WebPerformance, ComponentPerformance"
    )
    print(f"Log    : {LOG_PATH}", file=sys.__stdout__, flush=True)
    log.info("Log    : %s", LOG_PATH)
    log.info("Python : %s", sys.version)
    log.info("psutil : %s", psutil.__version__)
    log.info("=" * 60)

    # exit=False lets us continue to show_performance_chart() while
    # still preserving the correct process exit code.
    runner = unittest.main(verbosity=2, exit=False)
    show_performance_chart()
    sys.exit(0 if runner.result.wasSuccessful() else 1)
