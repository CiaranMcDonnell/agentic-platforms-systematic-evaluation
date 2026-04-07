"""LangFlow flow template definitions for SDLC stages.

Each template is a Python dict representing a LangFlow flow JSON
structure with an agent node, LLM node, and tool nodes.  The
``build_flow`` function deep-copies and parameterises a template
for a specific stage execution.
"""
from __future__ import annotations

import copy
from typing import Any


def _make_base_template(stage_name: str) -> dict[str, Any]:
    """Build the base flow template structure for any SDLC stage."""
    return {
        "name": f"desmet-{stage_name}",
        "description": f"DESMET {stage_name} stage",
        "nodes": [
            {
                "id": "agent_0",
                "data": {
                    "id": "agent_0",
                    "node": {
                        "display_name": "Tool Calling Agent",
                        "template": {
                            "system_message": {"value": ""},
                            "max_iterations": {"value": 25},
                        },
                    },
                    "type": "Agent",
                },
                "position": {"x": 450, "y": 300},
            },
            {
                "id": "llm_0",
                "data": {
                    "id": "llm_0",
                    "node": {
                        "display_name": "ChatOpenAI",
                        "template": {
                            "model_name": {"value": ""},
                            "temperature": {"value": 0},
                        },
                    },
                    "type": "ChatOpenAI",
                },
                "position": {"x": 200, "y": 500},
            },
            {
                "id": "tool_exec_0",
                "data": {
                    "id": "tool_exec_0",
                    "node": {
                        "display_name": "Execute Shell",
                        "template": {
                            "name": {"value": "execute_shell"},
                            "description": {"value": "Execute a shell command in the workspace directory."},
                            "code": {"value": ""},
                        },
                    },
                    "type": "PythonFunction",
                },
                "position": {"x": 600, "y": 500},
            },
            {
                "id": "tool_read_0",
                "data": {
                    "id": "tool_read_0",
                    "node": {
                        "display_name": "Read File",
                        "template": {
                            "name": {"value": "read_file"},
                            "description": {"value": "Read the contents of a file in the workspace. Input: relative file path."},
                            "code": {"value": ""},
                        },
                    },
                    "type": "PythonFunction",
                },
                "position": {"x": 750, "y": 500},
            },
            {
                "id": "tool_write_0",
                "data": {
                    "id": "tool_write_0",
                    "node": {
                        "display_name": "Write File",
                        "template": {
                            "name": {"value": "write_file"},
                            "description": {"value": "Write content to a file in the workspace. Input: JSON with 'path' and 'content' fields."},
                            "code": {"value": ""},
                        },
                    },
                    "type": "PythonFunction",
                },
                "position": {"x": 900, "y": 500},
            },
        ],
        "edges": [
            {"source": "llm_0", "target": "agent_0"},
            {"source": "tool_exec_0", "target": "agent_0"},
            {"source": "tool_read_0", "target": "agent_0"},
            {"source": "tool_write_0", "target": "agent_0"},
        ],
    }


def _tool_code_execute(workspace: str) -> str:
    """Python code for the execute_shell tool."""
    return (
        "import subprocess\n"
        f'result = subprocess.run(input_value, shell=True, cwd="{workspace}",\n'
        '    capture_output=True, text=True, timeout=120)\n'
        "return result.stdout if result.returncode == 0 else result.stderr"
    )


def _tool_code_read(workspace: str) -> str:
    """Python code for the read_file tool."""
    return (
        "import os\n"
        f'full_path = os.path.normpath(os.path.join("{workspace}", input_value))\n'
        f'if not full_path.startswith("{workspace}"):\n'
        '    return "Error: path outside workspace"\n'
        "try:\n"
        '    with open(full_path) as f:\n'
        "        return f.read()\n"
        "except Exception as e:\n"
        '    return f"Error: {e}"'
    )


def _tool_code_write(workspace: str) -> str:
    """Python code for the write_file tool."""
    return (
        "import os, json\n"
        "data = json.loads(input_value)\n"
        f'full_path = os.path.normpath(os.path.join("{workspace}", data["path"]))\n'
        f'if not full_path.startswith("{workspace}"):\n'
        '    return "Error: path outside workspace"\n'
        "os.makedirs(os.path.dirname(full_path), exist_ok=True)\n"
        'with open(full_path, "w") as f:\n'
        '    f.write(data["content"])\n'
        'return f"Written: {data[\'path\']}"'
    )


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    stage: _make_base_template(stage)
    for stage in ("requirements", "codegen", "testing", "deploy")
}


def build_flow(
    stage_name: str,
    prompt: str,
    system_msg: str,
    workspace: str,
    model_name: str,
) -> dict[str, Any]:
    """Deep-copy a stage template and inject runtime parameters."""
    if stage_name not in STAGE_TEMPLATES:
        raise ValueError(f"Unknown stage: {stage_name!r}. Valid stages: {sorted(STAGE_TEMPLATES)}")

    flow = copy.deepcopy(STAGE_TEMPLATES[stage_name])
    flow["name"] = f"desmet-{stage_name}"

    nodes_by_id = {n["id"]: n for n in flow["nodes"]}

    nodes_by_id["agent_0"]["data"]["node"]["template"]["system_message"]["value"] = system_msg
    nodes_by_id["llm_0"]["data"]["node"]["template"]["model_name"]["value"] = model_name
    nodes_by_id["tool_exec_0"]["data"]["node"]["template"]["code"]["value"] = _tool_code_execute(workspace)
    nodes_by_id["tool_read_0"]["data"]["node"]["template"]["code"]["value"] = _tool_code_read(workspace)
    nodes_by_id["tool_write_0"]["data"]["node"]["template"]["code"]["value"] = _tool_code_write(workspace)

    return flow
