"""Flowise chatflow template definitions for SDLC stages.

Each template is a Python dict representing a Flowise chatflow JSON
structure with an agent node, LLM node, and tool nodes.  The
``build_chatflow`` function deep-copies and parameterises a template
for a specific stage execution.

Node layout per chatflow
------------------------
- ``agent_0``      — Tool Agent (toolAgent / AgentFlow)
- ``llm_0``        — ChatOpenAI model
- ``tool_exec_0``  — execute_shell custom tool
- ``tool_read_0``  — read_file custom tool
- ``tool_write_0`` — write_file custom tool

Edges wire the LLM and all three tools into the agent's inputs.
"""
from __future__ import annotations

import copy
from typing import Any


def _make_base_template(stage_name: str) -> dict[str, Any]:
    """Build the base chatflow template structure for any SDLC stage."""
    return {
        "name": f"desmet-{stage_name}",
        "deployed": False,
        "isPublic": False,
        "type": "CHATFLOW",
        "nodes": [
            {
                "id": "agent_0",
                "data": {
                    "id": "agent_0",
                    "label": "Tool Agent",
                    "name": "toolAgent",
                    "type": "AgentFlow",
                    "category": "Agents",
                    "inputs": {
                        "systemMessage": "",
                        "maxIterations": "25",
                    },
                },
                "position": {"x": 450, "y": 300},
                "type": "customNode",
            },
            {
                "id": "llm_0",
                "data": {
                    "id": "llm_0",
                    "label": "ChatOpenAI",
                    "name": "chatOpenAI",
                    "type": "ChatOpenAI",
                    "category": "Chat Models",
                    "inputs": {
                        "modelName": "",
                        "temperature": "0",
                    },
                },
                "position": {"x": 200, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_exec_0",
                "data": {
                    "id": "tool_exec_0",
                    "label": "Execute Shell",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "execute_shell",
                        "toolDesc": "Execute a shell command in the workspace directory.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 600, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_read_0",
                "data": {
                    "id": "tool_read_0",
                    "label": "Read File",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "read_file",
                        "toolDesc": "Read the contents of a file in the workspace. Input: relative file path.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 750, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_write_0",
                "data": {
                    "id": "tool_write_0",
                    "label": "Write File",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "write_file",
                        "toolDesc": "Write content to a file in the workspace. Input: JSON with 'path' and 'content' fields.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 900, "y": 500},
                "type": "customNode",
            },
        ],
        "edges": [
            {"source": "llm_0", "target": "agent_0", "sourceHandle": "llm_0-output-chatOpenAI-ChatOpenAI", "targetHandle": "agent_0-input-model-ChatModel"},
            {"source": "tool_exec_0", "target": "agent_0", "sourceHandle": "tool_exec_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
            {"source": "tool_read_0", "target": "agent_0", "sourceHandle": "tool_read_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
            {"source": "tool_write_0", "target": "agent_0", "sourceHandle": "tool_write_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
        ],
    }


def _tool_js_execute(workspace: str) -> str:
    """JS code for the execute_shell custom tool."""
    return (
        'const { execSync } = require("child_process");\n'
        "try {\n"
        f'  const result = execSync($input, {{ cwd: "{workspace}", timeout: 120000,'
        ' encoding: "utf-8", maxBuffer: 1024 * 1024 }});\n'
        "  return result;\n"
        "} catch (e) {\n"
        "  return e.stderr || e.message;\n"
        "}"
    )


def _tool_js_read(workspace: str) -> str:
    """JS code for the read_file custom tool."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        f'const fullPath = path.resolve("{workspace}", $input);\n'
        f'if (!fullPath.startsWith("{workspace}")) return "Error: path outside workspace";\n'
        "try {\n"
        '  return fs.readFileSync(fullPath, "utf-8");\n'
        "} catch (e) {\n"
        '  return "Error: " + e.message;\n'
        "}"
    )


def _tool_js_write(workspace: str) -> str:
    """JS code for the write_file custom tool."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        "const input = JSON.parse($input);\n"
        f'const fullPath = path.resolve("{workspace}", input.path);\n'
        f'if (!fullPath.startsWith("{workspace}")) return "Error: path outside workspace";\n'
        "try {\n"
        "  fs.mkdirSync(path.dirname(fullPath), { recursive: true });\n"
        "  fs.writeFileSync(fullPath, input.content);\n"
        '  return "Written: " + input.path;\n'
        "} catch (e) {\n"
        '  return "Error: " + e.message;\n'
        "}"
    )


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    stage: _make_base_template(stage)
    for stage in ("requirements", "codegen", "testing", "deploy")
}


def build_chatflow(
    stage_name: str,
    prompt: str,
    system_msg: str,
    workspace: str,
    model_name: str,
) -> dict[str, Any]:
    """Deep-copy a stage template and inject runtime parameters."""
    if stage_name not in STAGE_TEMPLATES:
        raise ValueError(f"Unknown stage: {stage_name!r}. Valid stages: {sorted(STAGE_TEMPLATES)}")

    cf = copy.deepcopy(STAGE_TEMPLATES[stage_name])
    cf["name"] = f"desmet-{stage_name}"

    nodes_by_id = {n["id"]: n for n in cf["nodes"]}

    nodes_by_id["agent_0"]["data"]["inputs"]["systemMessage"] = system_msg
    nodes_by_id["llm_0"]["data"]["inputs"]["modelName"] = model_name
    nodes_by_id["tool_exec_0"]["data"]["inputs"]["toolFunc"] = _tool_js_execute(workspace)
    nodes_by_id["tool_read_0"]["data"]["inputs"]["toolFunc"] = _tool_js_read(workspace)
    nodes_by_id["tool_write_0"]["data"]["inputs"]["toolFunc"] = _tool_js_write(workspace)

    return cf
