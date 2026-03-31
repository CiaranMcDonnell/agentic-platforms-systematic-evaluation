"""
Resource Monitoring for DESMET Evaluation

Dataclasses and parsing utilities for container resource usage collected
via ``docker stats --format '{{json .}}'``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

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
