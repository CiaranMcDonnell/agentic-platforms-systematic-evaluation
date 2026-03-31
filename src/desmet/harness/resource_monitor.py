"""
Resource Monitoring for DESMET Evaluation

Dataclasses and parsing utilities for container resource usage collected
via ``docker stats --format '{{json .}}'``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Size-unit parsing helpers
# ---------------------------------------------------------------------------

_SIZE_UNITS: dict[str, int] = {
    "B": 1,
    "kB": 1_000,
    "KB": 1_000,
    "MB": 1_000_000,
    "GB": 1_000_000_000,
    "KiB": 1_024,
    "MiB": 1_024 * 1_024,
    "GiB": 1_024 * 1_024 * 1_024,
}

_SIZE_RE = re.compile(r"([\d.]+)\s*([A-Za-z]+)")


def _parse_size(s: str) -> int:
    """Parse a Docker size string like ``'123.4MiB'`` into bytes (int)."""
    s = s.strip()
    m = _SIZE_RE.fullmatch(s)
    if not m:
        raise ValueError(f"Cannot parse size string: {s!r}")
    value, unit = float(m.group(1)), m.group(2)
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit {unit!r} in {s!r}")
    return int(value * _SIZE_UNITS[unit])


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResourceSample:
    """A single point-in-time resource observation for a container."""

    timestamp: datetime
    cpu_percent: float
    memory_bytes: int
    memory_limit_bytes: int
    net_rx_bytes: int
    net_tx_bytes: int


@dataclass
class ResourceSummary:
    """Aggregated resource statistics derived from a sequence of
    :class:`ResourceSample` observations."""

    samples: int
    peak_memory_bytes: int
    avg_memory_bytes: int
    avg_cpu_percent: float
    peak_cpu_percent: float
    net_rx_total_bytes: int
    net_tx_total_bytes: int
    startup_to_ready_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Serialise all fields to a plain dict, rounding floats to 4 d.p."""
        return {
            "samples": self.samples,
            "peak_memory_bytes": self.peak_memory_bytes,
            "avg_memory_bytes": self.avg_memory_bytes,
            "avg_cpu_percent": round(self.avg_cpu_percent, 4),
            "peak_cpu_percent": round(self.peak_cpu_percent, 4),
            "net_rx_total_bytes": self.net_rx_total_bytes,
            "net_tx_total_bytes": self.net_tx_total_bytes,
            "startup_to_ready_ms": round(self.startup_to_ready_ms, 4),
        }


# ---------------------------------------------------------------------------
# Docker stats JSON parsing
# ---------------------------------------------------------------------------

def _parse_docker_stats_json(raw: dict[str, str]) -> ResourceSample:
    """Parse one line of ``docker stats --format '{{json .}}'`` output.

    Expected keys (subset used here):

    * ``CPUPerc``  — e.g. ``"45.23%"``
    * ``MemUsage`` — e.g. ``"123.4MiB / 1.5GiB"``
    * ``NetIO``    — e.g. ``"1.2kB / 3.4MB"``

    Returns a :class:`ResourceSample` with ``timestamp`` set to *now* (UTC).
    """
    # CPU
    cpu_str = raw.get("CPUPerc", "0%").rstrip("%").strip()
    cpu_percent = float(cpu_str)

    # Memory: "used / limit"
    mem_parts = raw.get("MemUsage", "0B / 0B").split("/")
    memory_bytes = _parse_size(mem_parts[0].strip())
    memory_limit_bytes = _parse_size(mem_parts[1].strip())

    # Network I/O: "rx / tx"
    net_parts = raw.get("NetIO", "0B / 0B").split("/")
    net_rx_bytes = _parse_size(net_parts[0].strip())
    net_tx_bytes = _parse_size(net_parts[1].strip())

    return ResourceSample(
        timestamp=datetime.now(tz=timezone.utc),
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
        memory_limit_bytes=memory_limit_bytes,
        net_rx_bytes=net_rx_bytes,
        net_tx_bytes=net_tx_bytes,
    )


# ---------------------------------------------------------------------------
# Background resource monitor
# ---------------------------------------------------------------------------

class ResourceMonitor:
    """Polls docker stats for a container in a background thread."""

    def __init__(self, container_name: str, poll_interval: float = 2.0) -> None:
        self._container = container_name
        self._interval = poll_interval
        self._samples: list[ResourceSample] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: datetime | None = None

    def start(self) -> None:
        """Start background polling."""
        self._start_time = datetime.now(tz=timezone.utc)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> ResourceSummary:
        """Stop polling and return aggregated summary."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        return self._summarize()

    def _poll_loop(self) -> None:
        """Background loop: call docker stats --no-stream for the container."""
        while not self._stop_event.is_set():
            try:
                result = subprocess.run(
                    [
                        "docker", "stats", "--no-stream",
                        "--format", "{{json .}}",
                        self._container,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    raw = json.loads(result.stdout.strip())
                    sample = _parse_docker_stats_json(raw)
                    self._samples.append(sample)
            except subprocess.TimeoutExpired:
                log.debug("docker stats timed out for container %s", self._container)
            except json.JSONDecodeError as exc:
                log.debug("docker stats JSON parse error for %s: %s", self._container, exc)
            except OSError as exc:
                log.debug("docker stats OS error for %s: %s", self._container, exc)

            self._stop_event.wait(self._interval)

    def _summarize(self) -> ResourceSummary:
        """Aggregate samples into a ResourceSummary."""
        samples = self._samples
        n = len(samples)

        if n == 0:
            return ResourceSummary(
                samples=0,
                peak_memory_bytes=0,
                avg_memory_bytes=0,
                avg_cpu_percent=0.0,
                peak_cpu_percent=0.0,
                net_rx_total_bytes=0,
                net_tx_total_bytes=0,
                startup_to_ready_ms=0.0,
            )

        peak_memory = max(s.memory_bytes for s in samples)
        avg_memory = sum(s.memory_bytes for s in samples) // n
        avg_cpu = sum(s.cpu_percent for s in samples) / n
        peak_cpu = max(s.cpu_percent for s in samples)

        # Net delta: last minus first; if only one sample use its absolute values.
        if n > 1:
            net_rx = samples[-1].net_rx_bytes - samples[0].net_rx_bytes
            net_tx = samples[-1].net_tx_bytes - samples[0].net_tx_bytes
        else:
            net_rx = samples[0].net_rx_bytes
            net_tx = samples[0].net_tx_bytes

        # Startup-to-ready: time from _start_time to first sample with cpu_percent > 0.
        startup_ms = 0.0
        if self._start_time is not None:
            for s in samples:
                if s.cpu_percent > 0:
                    delta = s.timestamp - self._start_time
                    startup_ms = delta.total_seconds() * 1000
                    break

        return ResourceSummary(
            samples=n,
            peak_memory_bytes=peak_memory,
            avg_memory_bytes=avg_memory,
            avg_cpu_percent=avg_cpu,
            peak_cpu_percent=peak_cpu,
            net_rx_total_bytes=net_rx,
            net_tx_total_bytes=net_tx,
            startup_to_ready_ms=startup_ms,
        )
