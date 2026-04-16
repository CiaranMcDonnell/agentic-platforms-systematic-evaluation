"""Flowise chatflow template builder.

Flowise's runtime expects each node in ``flowData.nodes`` to carry the
full React Flow node shape — ``inputAnchors``, ``inputParams``,
``outputAnchors``, ``baseClasses``, and related metadata — not just the
subset the UI exposes for editing.  Hand-synthesising that shape is
fragile and breaks on Flowise upgrades.

This module instead builds nodes from the **live node specs** exposed
by ``GET /api/v1/nodes/{name}``.  Each spec's ``inputs`` list is
classified into params vs anchors using Flowise's own
``INPUT_PARAMS_TYPE`` constant, and the React Flow structure is
synthesised mechanically.

Per-chatflow graph
------------------
* ``chatOpenRouter_0`` — LLM, bound to an openRouterApi credential ID
* ``customTool_{0,1,2}`` — execute_shell / read_file / write_file,
  referencing tool IDs created via ``POST /api/v1/tools``
* ``bufferMemory_0`` — short-term session memory
* ``toolAgent_0`` — the agent that ties model + tools + memory together
"""

from __future__ import annotations

from typing import Any

# Flowise's own classification — an input is an ``inputParam`` (i.e. a
# form field with a literal value) if its ``type`` is in this set, and
# an ``inputAnchor`` (i.e. a connection point wired to another node)
# otherwise.  Sourced from
# ``/usr/local/lib/node_modules/flowise/dist/utils/constants.js``.
_INPUT_PARAM_TYPES = frozenset(
    {
        "asyncOptions",
        "asyncMultiOptions",
        "options",
        "multiOptions",
        "datagrid",
        "string",
        "number",
        "boolean",
        "password",
        "json",
        "code",
        "date",
        "file",
        "folder",
        "tabs",
    }
)


# ── Node construction ─────────────────────────────────────────────────


def _build_node(
    node_id: str,
    spec: dict[str, Any],
    position: dict[str, int],
    input_values: dict[str, Any],
    credential_id: str | None = None,
) -> dict[str, Any]:
    """Turn a node spec from ``/api/v1/nodes/{name}`` into a React Flow node.

    ``spec`` is the JSON returned by Flowise's nodes endpoint.  This
    function classifies each entry in ``spec["inputs"]`` as either an
    ``inputParam`` or ``inputAnchor`` and assigns the handle IDs that
    Flowise's runtime uses to match edges against.
    """
    name = spec["name"]
    base_classes: list[str] = spec.get("baseClasses", [])

    input_params: list[dict[str, Any]] = []
    input_anchors: list[dict[str, Any]] = []

    # Credential is surfaced as a pseudo-param at the top of ``inputParams``
    # when the node declares one.
    cred = spec.get("credential")
    if cred:
        input_params.append(
            {
                **cred,
                "id": f"{node_id}-input-{cred['name']}-{cred['type']}",
            }
        )

    for inp in spec.get("inputs", []):
        inp_type = inp.get("type", "")
        entry = {**inp, "id": f"{node_id}-input-{inp['name']}-{inp_type}"}
        if inp_type in _INPUT_PARAM_TYPES:
            input_params.append(entry)
        else:
            input_anchors.append(entry)

    # Flowise stores actual values in ``inputs`` keyed by param/anchor name.
    # Every param/anchor must appear (even if blank) — we seed defaults
    # first, then overlay the caller-supplied values.
    inputs: dict[str, Any] = {}
    for p in input_params:
        if p.get("name") == "credential":
            continue  # credential goes on the node itself, not in ``inputs``
        inputs[p["name"]] = p.get("default", "")
    for a in input_anchors:
        inputs[a["name"]] = [] if a.get("list") else ""
    inputs.update(input_values)

    # One output anchor per node, synthesised from baseClasses.
    output_type = " | ".join(base_classes)
    output_anchors = [
        {
            "id": f"{node_id}-output-{name}-{'|'.join(base_classes)}",
            "name": name,
            "label": spec.get("label", name),
            "type": output_type,
        }
    ]

    node_data: dict[str, Any] = {
        "id": node_id,
        "label": spec.get("label", name),
        "version": spec.get("version", 1),
        "name": name,
        "type": spec.get("type", name),
        "baseClasses": base_classes,
        "category": spec.get("category", ""),
        "description": spec.get("description", ""),
        "inputParams": input_params,
        "inputAnchors": input_anchors,
        "inputs": inputs,
        "outputAnchors": output_anchors,
        "outputs": {},
        "selected": False,
    }
    if credential_id:
        node_data["credential"] = credential_id

    return {
        "id": node_id,
        "position": position,
        "type": "customNode",
        "data": node_data,
        "width": 300,
        "height": 400,
        "selected": False,
        "positionAbsolute": position,
        "dragging": False,
    }


def _build_edge(
    source_id: str,
    source_spec: dict[str, Any],
    target_id: str,
    target_anchor_name: str,
    target_anchor_type: str,
) -> dict[str, Any]:
    """Build a React Flow edge with the handle IDs Flowise's runtime expects."""
    source_name = source_spec["name"]
    source_base = "|".join(source_spec.get("baseClasses", []))
    source_handle = f"{source_id}-output-{source_name}-{source_base}"
    target_handle = f"{target_id}-input-{target_anchor_name}-{target_anchor_type}"
    return {
        "source": source_id,
        "sourceHandle": source_handle,
        "target": target_id,
        "targetHandle": target_handle,
        "type": "buttonedge",
        "id": f"{source_handle}-{target_handle}",
    }


# ── Tool JS code (baked into the tool definitions at creation time) ───


def tool_js_execute(workspace: str) -> str:
    """JS source for the ``execute_shell`` custom tool."""
    return (
        'const { execSync } = require("child_process");\n'
        "try {\n"
        f'  return execSync($input, {{ cwd: "{workspace}", timeout: 120000,'
        ' encoding: "utf-8", maxBuffer: 1024 * 1024 }});\n'
        "} catch (e) {\n"
        "  return e.stderr || e.message;\n"
        "}"
    )


def tool_js_read(workspace: str) -> str:
    """JS source for the ``read_file`` custom tool."""
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


def tool_js_write(workspace: str) -> str:
    """JS source for the ``write_file`` custom tool."""
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


_SCHEMA_SINGLE_INPUT = (
    '[{"property":"input","type":"string",'
    '"description":"%s","required":true}]'
)

TOOL_DEFS: list[dict[str, str]] = [
    {
        "name": "execute_shell",
        "description": "Execute a shell command in the workspace directory.",
        "schema_json": _SCHEMA_SINGLE_INPUT % "The shell command to execute.",
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace.",
        "schema_json": _SCHEMA_SINGLE_INPUT % "Relative file path to read.",
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file in the workspace. Input must be a JSON "
            "string with 'path' and 'content' fields."
        ),
        "schema_json": _SCHEMA_SINGLE_INPUT % (
            "JSON string: {\\\"path\\\":\\\"<rel-path>\\\",\\\"content\\\":\\\"<text>\\\"}"
        ),
    },
]


# ── Chatflow assembly ─────────────────────────────────────────────────


def build_chatflow(
    stage_name: str,
    system_msg: str,
    model_name: str,
    credential_id: str,
    tool_id_by_name: dict[str, str],
    specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Assemble a complete chatflow JSON for a stage.

    ``specs`` must contain entries for ``chatOpenRouter``, ``customTool``,
    ``bufferMemory``, and ``toolAgent`` — fetched once from
    ``GET /api/v1/nodes/{name}`` by the caller and reused across stages.
    ``tool_id_by_name`` maps each of ``execute_shell``/``read_file``/
    ``write_file`` to the tool ID returned by ``POST /api/v1/tools``.
    """
    required = {"chatOpenRouter", "customTool", "bufferMemory", "toolAgent"}
    missing = required - set(specs)
    if missing:
        raise ValueError(f"Missing node specs for Flowise chatflow: {sorted(missing)}")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # LLM (bound to credential).  Streaming is disabled so that the
    # prediction response carries full ``tokenUsage`` — streaming
    # responses in Flowise drop usage metadata.
    llm_spec = specs["chatOpenRouter"]
    llm_node = _build_node(
        "chatOpenRouter_0",
        llm_spec,
        position={"x": 200, "y": 100},
        input_values={
            "modelName": model_name,
            "temperature": 0,
            "streaming": False,
        },
        credential_id=credential_id,
    )
    nodes.append(llm_node)

    # Tools (referencing pre-registered IDs)
    tool_spec = specs["customTool"]
    tool_order = ["execute_shell", "read_file", "write_file"]
    for i, tool_name in enumerate(tool_order):
        tool_id = tool_id_by_name[tool_name]
        t_node = _build_node(
            f"customTool_{i}",
            tool_spec,
            position={"x": 200 + i * 320, "y": 500},
            input_values={"selectedTool": tool_id, "returnDirect": False},
        )
        nodes.append(t_node)

    # Memory
    memory_spec = specs["bufferMemory"]
    memory_node = _build_node(
        "bufferMemory_0",
        memory_spec,
        position={"x": 200, "y": 900},
        input_values={},
    )
    nodes.append(memory_node)

    # Agent.  Flowise resolves connected-node values at runtime by
    # substituting ``{{nodeId.data.instance}}`` references in the
    # target's ``inputs`` dict — the edges themselves are UI state,
    # not the data path.  So anchor inputs must carry reference
    # strings, not empty placeholders.
    agent_spec = specs["toolAgent"]
    tool_refs = [
        f"{{{{customTool_{i}.data.instance}}}}" for i in range(len(tool_order))
    ]
    agent_node = _build_node(
        "toolAgent_0",
        agent_spec,
        position={"x": 900, "y": 400},
        input_values={
            "systemMessage": system_msg,
            "maxIterations": 25,
            "model": "{{chatOpenRouter_0.data.instance}}",
            "memory": "{{bufferMemory_0.data.instance}}",
            "tools": tool_refs,
        },
    )
    nodes.append(agent_node)

    # Edges: LLM → agent.model, each tool → agent.tools, memory → agent.memory
    edges.append(_build_edge("chatOpenRouter_0", llm_spec, "toolAgent_0", "model", "BaseChatModel"))
    for i in range(len(tool_order)):
        edges.append(_build_edge(f"customTool_{i}", tool_spec, "toolAgent_0", "tools", "Tool"))
    edges.append(
        _build_edge("bufferMemory_0", memory_spec, "toolAgent_0", "memory", "BaseChatMemory")
    )

    return {
        "name": f"desmet-{stage_name}",
        "deployed": False,
        "isPublic": False,
        "type": "CHATFLOW",
        "nodes": nodes,
        "edges": edges,
    }
