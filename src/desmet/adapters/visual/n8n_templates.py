"""n8n workflow template definitions for SDLC stages.

Each template is a Python dict representing an n8n workflow JSON structure
with an AI Agent node and tool nodes.  The ``build_workflow`` function
deep-copies and parameterises a template for a specific stage execution.
"""
from __future__ import annotations

import copy
from typing import Any


def _make_base_template(stage_name: str) -> dict[str, Any]:
    """Build the base workflow template structure for any stage."""
    return {
        "name": f"desmet-{stage_name}",
        "nodes": [
            {
                "id": "trigger",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [200, 300],
                "parameters": {},
            },
            {
                "id": "agent",
                "name": "AI Agent",
                "type": "@n8n/n8n-nodes-langchain.agent",
                "typeVersion": 2,
                "position": [450, 300],
                "parameters": {
                    "promptType": "define",
                    "text": "={{$json.prompt}}",
                    "systemMessage": "",
                    "options": {},
                },
            },
            {
                "id": "llm",
                "name": "LLM Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1,
                "position": [450, 500],
                "parameters": {
                    "model": "",
                    "options": {},
                },
                "credentials": {},
            },
            {
                "id": "tool_exec",
                "name": "Execute Command",
                "type": "@n8n/n8n-nodes-langchain.toolCode",
                "typeVersion": 1,
                "position": [600, 500],
                "parameters": {
                    "name": "execute_shell",
                    "description": "Execute a shell command in the workspace directory. Use for running code, installing packages, running tests.",
                    "jsCode": "",
                },
            },
            {
                "id": "tool_read",
                "name": "Read File",
                "type": "@n8n/n8n-nodes-langchain.toolCode",
                "typeVersion": 1,
                "position": [750, 500],
                "parameters": {
                    "name": "read_file",
                    "description": "Read the contents of a file in the workspace. Input: relative file path.",
                    "jsCode": "",
                },
            },
            {
                "id": "tool_write",
                "name": "Write File",
                "type": "@n8n/n8n-nodes-langchain.toolCode",
                "typeVersion": 1,
                "position": [900, 500],
                "parameters": {
                    "name": "write_file",
                    "description": "Write content to a file in the workspace. Input: JSON with 'path' and 'content' fields.",
                    "jsCode": "",
                },
            },
        ],
        "connections": {
            "Manual Trigger": {
                "main": [[{"node": "AI Agent", "type": "main", "index": 0}]],
            },
            "LLM Model": {
                "ai_languageModel": [
                    [{"node": "AI Agent", "type": "ai_languageModel", "index": 0}],
                ],
            },
            "Execute Command": {
                "ai_tool": [
                    [{"node": "AI Agent", "type": "ai_tool", "index": 0}],
                ],
            },
            "Read File": {
                "ai_tool": [
                    [{"node": "AI Agent", "type": "ai_tool", "index": 0}],
                ],
            },
            "Write File": {
                "ai_tool": [
                    [{"node": "AI Agent", "type": "ai_tool", "index": 0}],
                ],
            },
        },
        "settings": {
            "executionOrder": "v1",
        },
    }


def _tool_js_execute(workspace: str) -> str:
    """JS code for the execute_shell tool node."""
    return (
        'const { execSync } = require("child_process");\n'
        'const cmd = $input.first().json.query || $input.first().json.command;\n'
        'try {\n'
        f'  const result = execSync(cmd, {{ cwd: "{workspace}", timeout: 120000, encoding: "utf-8", maxBuffer: 1024 * 1024 }});\n'
        '  return [{ json: { output: result } }];\n'
        '} catch (e) {\n'
        '  return [{ json: { output: e.stderr || e.message, exitCode: e.status } }];\n'
        '}'
    )


def _tool_js_read(workspace: str) -> str:
    """JS code for the read_file tool node."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        'const filePath = $input.first().json.query || $input.first().json.path;\n'
        f'const fullPath = path.resolve("{workspace}", filePath);\n'
        f'if (!fullPath.startsWith("{workspace}")) {{\n'
        '  return [{ json: { error: "Path outside workspace" } }];\n'
        '}\n'
        'try {\n'
        '  const content = fs.readFileSync(fullPath, "utf-8");\n'
        '  return [{ json: { content } }];\n'
        '} catch (e) {\n'
        '  return [{ json: { error: e.message } }];\n'
        '}'
    )


def _tool_js_write(workspace: str) -> str:
    """JS code for the write_file tool node."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        'const input = $input.first().json;\n'
        'const filePath = input.path || input.query;\n'
        'const content = input.content || "";\n'
        f'const fullPath = path.resolve("{workspace}", filePath);\n'
        f'if (!fullPath.startsWith("{workspace}")) {{\n'
        '  return [{ json: { error: "Path outside workspace" } }];\n'
        '}\n'
        'try {\n'
        '  fs.mkdirSync(path.dirname(fullPath), { recursive: true });\n'
        '  fs.writeFileSync(fullPath, content);\n'
        '  return [{ json: { success: true, path: filePath } }];\n'
        '} catch (e) {\n'
        '  return [{ json: { error: e.message } }];\n'
        '}'
    )


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    stage: _make_base_template(stage)
    for stage in ("requirements", "codegen", "testing", "deploy")
}


def build_workflow(
    stage_name: str,
    prompt: str,
    system_msg: str,
    workspace: str,
    model_name: str,
    credential_id: str,
) -> dict[str, Any]:
    """Deep-copy a stage template and inject runtime parameters."""
    if stage_name not in STAGE_TEMPLATES:
        raise ValueError(f"Unknown stage: {stage_name}")

    wf = copy.deepcopy(STAGE_TEMPLATES[stage_name])
    wf["name"] = f"desmet-{stage_name}-{credential_id[:8]}"

    nodes_by_id = {n["id"]: n for n in wf["nodes"]}

    nodes_by_id["agent"]["parameters"]["systemMessage"] = system_msg
    nodes_by_id["llm"]["parameters"]["model"] = model_name
    nodes_by_id["llm"]["credentials"] = {
        "openAiApi": {"id": credential_id, "name": "desmet-llm"},
    }
    nodes_by_id["tool_exec"]["parameters"]["jsCode"] = _tool_js_execute(workspace)
    nodes_by_id["tool_read"]["parameters"]["jsCode"] = _tool_js_read(workspace)
    nodes_by_id["tool_write"]["parameters"]["jsCode"] = _tool_js_write(workspace)
    nodes_by_id["trigger"]["parameters"] = {
        "manualTriggerData": {"prompt": prompt, "workspace": workspace},
    }

    return wf
