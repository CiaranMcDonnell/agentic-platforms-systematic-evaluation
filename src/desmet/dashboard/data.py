"""DESMET Dashboard — data helpers (stub).

This minimal stub provides platform colour and name lookups required by
charts.py.  The full data layer will be implemented separately.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    candidate = Path(__file__).resolve().parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    raise FileNotFoundError("Cannot locate project root")


REPO_ROOT = _find_repo_root()
FIGURES_DIR = REPO_ROOT / "docs" / "report" / "figures"

# ---------------------------------------------------------------------------
# Platform metadata
# ---------------------------------------------------------------------------

_PLATFORMS: dict[str, dict[str, str]] = {
    "langgraph":       {"name": "LangGraph",        "category": "multi_agent_framework"},
    "crewai":          {"name": "CrewAI",            "category": "multi_agent_framework"},
    "microsoft_autogen": {"name": "Microsoft AutoGen", "category": "multi_agent_framework"},
    "openai_agents_sdk": {"name": "OpenAI Agents SDK", "category": "agent_sdk_runtime"},
    "google_adk":      {"name": "Google ADK",        "category": "agent_sdk_runtime"},
    "semantic_kernel":  {"name": "Semantic Kernel",   "category": "agent_sdk_runtime"},
    "flowise":         {"name": "Flowise",           "category": "visual_workflow_platform"},
    "langflow":        {"name": "LangFlow",          "category": "visual_workflow_platform"},
    "dify":            {"name": "Dify",              "category": "visual_workflow_platform"},
    "n8n":             {"name": "n8n",               "category": "visual_workflow_platform"},
}

# ---------------------------------------------------------------------------
# Category colours — blues for multi-agent, greens for SDK, oranges for visual
# ---------------------------------------------------------------------------

CATEGORY_COLOURS: dict[str, list[str]] = {
    "multi_agent_framework": [
        "#1f77b4",  # steel blue
        "#4a90d9",  # medium blue
        "#7eb3e8",  # light blue
    ],
    "agent_sdk_runtime": [
        "#2ca02c",  # forest green
        "#5cc85c",  # medium green
        "#8dd68d",  # light green
    ],
    "visual_workflow_platform": [
        "#e67e22",  # burnt orange
        "#f0a04b",  # medium orange
        "#f5c27a",  # light orange
        "#f9dba9",  # pale orange
    ],
}

# Pre-compute a stable mapping from platform_id -> colour.
_COLOUR_MAP: dict[str, str] = {}
_category_indices: dict[str, int] = {}

for pid, meta in _PLATFORMS.items():
    cat = meta["category"]
    idx = _category_indices.get(cat, 0)
    colours = CATEGORY_COLOURS.get(cat, ["#999999"])
    _COLOUR_MAP[pid] = colours[idx % len(colours)]
    _category_indices[cat] = idx + 1


def get_platform_colour(platform_id: str) -> str:
    """Return the hex colour assigned to *platform_id*."""
    return _COLOUR_MAP.get(platform_id, "#999999")


def get_platform_name(platform_id: str) -> str:
    """Return the human-readable name for *platform_id*."""
    meta = _PLATFORMS.get(platform_id)
    if meta is not None:
        return meta["name"]
    return platform_id.replace("_", " ").title()
