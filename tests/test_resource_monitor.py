"""Tests for desmet.harness.resource_monitor — data models and Docker stats parsing."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from desmet.harness.resource_monitor import (
    ResourceMonitor,
    ResourceSample,
    ResourceSummary,
    _parse_docker_stats_json,
    _parse_size,
)


# ---------------------------------------------------------------------------
# ResourceSample
# ---------------------------------------------------------------------------

def test_resource_sample_creation():
    """ResourceSample stores all fields correctly."""
    ts = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
    sample = ResourceSample(
        timestamp=ts,
        cpu_percent=12.5,
        memory_bytes=128 * 1024 * 1024,
        memory_limit_bytes=1024 * 1024 * 1024,
        net_rx_bytes=1000,
        net_tx_bytes=2000,
    )
    assert sample.timestamp == ts
    assert sample.cpu_percent == 12.5
    assert sample.memory_bytes == 128 * 1024 * 1024
    assert sample.memory_limit_bytes == 1024 * 1024 * 1024
    assert sample.net_rx_bytes == 1000
    assert sample.net_tx_bytes == 2000


# ---------------------------------------------------------------------------
# ResourceSummary
# ---------------------------------------------------------------------------

def test_resource_summary_to_dict():
    """to_dict() returns a dict with all expected keys and correct types."""
    summary = ResourceSummary(
        samples=10,
        peak_memory_bytes=256 * 1024 * 1024,
        avg_memory_bytes=128 * 1024 * 1024,
        avg_cpu_percent=23.456789,
        peak_cpu_percent=55.0,
        net_rx_total_bytes=5_000_000,
        net_tx_total_bytes=1_000_000,
        startup_to_ready_ms=1234.5678,
    )
    d = summary.to_dict()

    assert isinstance(d, dict)

    # All required keys present
    expected_keys = {
        "samples",
        "peak_memory_bytes",
        "avg_memory_bytes",
        "avg_cpu_percent",
        "peak_cpu_percent",
        "net_rx_total_bytes",
        "net_tx_total_bytes",
        "startup_to_ready_ms",
    }
    assert expected_keys == set(d.keys())

    # Integer fields
    assert d["samples"] == 10
    assert d["peak_memory_bytes"] == 256 * 1024 * 1024
    assert d["avg_memory_bytes"] == 128 * 1024 * 1024
    assert d["net_rx_total_bytes"] == 5_000_000
    assert d["net_tx_total_bytes"] == 1_000_000

    # Floats are rounded to 4 decimal places
    assert d["avg_cpu_percent"] == round(23.456789, 4)
    assert d["peak_cpu_percent"] == 55.0
    assert d["startup_to_ready_ms"] == round(1234.5678, 4)


# ---------------------------------------------------------------------------
# _parse_size helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("s,expected", [
    ("0B", 0),
    ("1B", 1),
    ("1kB", 1_000),
    ("1KB", 1_000),
    ("1MB", 1_000_000),
    ("1GB", 1_000_000_000),
    ("1KiB", 1_024),
    ("1MiB", 1_024 * 1_024),
    ("1GiB", 1_024 * 1_024 * 1_024),
    ("123.4MiB", int(123.4 * 1_024 * 1_024)),
    ("1.5GiB", int(1.5 * 1_024 * 1_024 * 1_024)),
    ("3.4MB", int(3.4 * 1_000_000)),
    ("1.2kB", int(1.2 * 1_000)),
])
def test_parse_size_valid(s, expected):
    assert _parse_size(s) == expected


def test_parse_size_with_spaces():
    """Size strings with internal spaces are accepted."""
    assert _parse_size("128 MiB") == int(128 * 1024 * 1024)


def test_parse_size_invalid_unit():
    with pytest.raises(ValueError, match="Unknown size unit"):
        _parse_size("10XB")


def test_parse_size_invalid_format():
    with pytest.raises(ValueError, match="Cannot parse size string"):
        _parse_size("not_a_size")


# ---------------------------------------------------------------------------
# _parse_docker_stats_json
# ---------------------------------------------------------------------------

def test_parse_docker_stats_json_standard():
    """Standard MiB/GiB/kB/MB values parse correctly."""
    raw = {
        "CPUPerc": "45.23%",
        "MemUsage": "123.4MiB / 1.5GiB",
        "NetIO": "1.2kB / 3.4MB",
    }
    sample = _parse_docker_stats_json(raw)

    assert abs(sample.cpu_percent - 45.23) < 0.01
    assert sample.memory_bytes == int(123.4 * 1024 * 1024)
    assert sample.memory_limit_bytes == int(1.5 * 1024 * 1024 * 1024)
    assert sample.net_rx_bytes == int(1.2 * 1000)
    assert sample.net_tx_bytes == int(3.4 * 1_000_000)


def test_parse_docker_stats_json_zero():
    """Zero values produce zeroes in every byte field (except memory limit)."""
    raw = {
        "CPUPerc": "0.00%",
        "MemUsage": "0B / 1GiB",
        "NetIO": "0B / 0B",
    }
    sample = _parse_docker_stats_json(raw)

    assert sample.cpu_percent == 0.0
    assert sample.memory_bytes == 0
    assert sample.memory_limit_bytes == int(1 * 1024 * 1024 * 1024)  # 1GiB
    assert sample.net_rx_bytes == 0
    assert sample.net_tx_bytes == 0


def test_parse_docker_stats_json_gb_memory():
    """GiB memory values and MB network values parse correctly."""
    raw = {
        "CPUPerc": "12.5%",
        "MemUsage": "2.1GiB / 4GiB",
        "NetIO": "100MB / 50MB",
    }
    sample = _parse_docker_stats_json(raw)

    assert abs(sample.cpu_percent - 12.5) < 0.01
    assert sample.memory_bytes == int(2.1 * 1024 * 1024 * 1024)
    assert sample.memory_limit_bytes == int(4 * 1024 * 1024 * 1024)
    assert sample.net_rx_bytes == int(100 * 1_000_000)
    assert sample.net_tx_bytes == int(50 * 1_000_000)


def test_parse_docker_stats_json_timestamp_is_utc():
    """Returned sample has a timezone-aware UTC timestamp."""
    raw = {"CPUPerc": "1%", "MemUsage": "10MiB / 1GiB", "NetIO": "0B / 0B"}
    sample = _parse_docker_stats_json(raw)
    assert sample.timestamp.tzinfo is not None
    assert sample.timestamp.tzinfo == timezone.utc


def test_parse_docker_stats_json_missing_keys_default_zero():
    """Missing keys fall back to zeroes without raising."""
    sample = _parse_docker_stats_json({})
    assert sample.cpu_percent == 0.0
    assert sample.memory_bytes == 0
    assert sample.net_rx_bytes == 0
    assert sample.net_tx_bytes == 0


# ---------------------------------------------------------------------------
# ResourceMonitor
# ---------------------------------------------------------------------------

_FAKE_STATS = json.dumps({
    "CPUPerc": "10.00%",
    "MemUsage": "256MiB / 1GiB",
    "NetIO": "1MB / 500kB",
})


def test_monitor_collects_samples(monkeypatch):
    """Mock subprocess.run to return fake docker stats; verify samples collected."""
    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = _FAKE_STATS

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: fake_result)

    monitor = ResourceMonitor("test-container", poll_interval=0.05)
    monitor.start()
    time.sleep(0.25)
    summary = monitor.stop()

    assert summary.samples >= 2
    assert summary.peak_memory_bytes == int(256 * 1024 * 1024)
    assert abs(summary.avg_cpu_percent - 10.0) < 0.01


def test_monitor_handles_docker_failure(monkeypatch):
    """When docker stats returns non-zero, summary has samples=0."""
    fail_result = MagicMock()
    fail_result.returncode = 1
    fail_result.stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: fail_result)

    monitor = ResourceMonitor("missing-container", poll_interval=0.05)
    monitor.start()
    time.sleep(0.2)
    summary = monitor.stop()

    assert summary.samples == 0


def test_monitor_startup_to_ready(monkeypatch):
    """First call returns 0% CPU; subsequent calls return 10% — startup_to_ready_ms > 0."""
    call_count = {"n": 0}

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        cpu = "0.00%" if call_count["n"] == 0 else "10.00%"
        call_count["n"] += 1
        result.stdout = json.dumps({
            "CPUPerc": cpu,
            "MemUsage": "128MiB / 1GiB",
            "NetIO": "0B / 0B",
        })
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)

    monitor = ResourceMonitor("test-container", poll_interval=0.05)
    monitor.start()
    time.sleep(0.3)
    summary = monitor.stop()

    assert summary.startup_to_ready_ms > 0
