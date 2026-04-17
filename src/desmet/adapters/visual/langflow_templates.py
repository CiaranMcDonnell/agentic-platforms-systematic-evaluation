"""LangFlow flow template builder.

LangFlow's runtime consumes a React Flow graph where every node
carries its full component spec — template fields, outputs,
base_classes, tool_mode, conditional_paths, etc.  The catalog
returned by ``GET /api/v1/all`` already provides exactly the
``data.node`` part of that shape, so we use it as-is and only
override the template field values we care about.

Topology
--------
::

    ChatInput ──▶ Agent ──▶ ChatOutput
                    ▲
    OpenRouterComponent (model_output) ──┤
    PythonCodeStructuredTool (x3) ──────┤

Each ``PythonCodeStructuredTool`` carries the DESMET workspace tool
code (shell / read / write) with the function name selected.
"""

from __future__ import annotations

import ast
import copy
import json
import uuid
from typing import Any


# ── Node ID helpers ───────────────────────────────────────────────────


def _node_id(component_name: str) -> str:
    """LangFlow node ids look like ``ComponentName-<5 alnum chars>``."""
    suffix = uuid.uuid4().hex[:5]
    return f"{component_name}-{suffix}"


# ── Node construction ─────────────────────────────────────────────────


def _build_node(
    component_name: str,
    spec: dict[str, Any],
    template_overrides: dict[str, Any],
    position: dict[str, float],
    node_id: str,
    field_flag_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap a catalog component spec in the React Flow envelope.

    ``spec`` is the value from ``GET /api/v1/all[category][component_name]``.
    ``template_overrides`` maps field names → new ``value`` (the field
    definition is preserved; only the ``value`` slot is replaced).
    ``field_flag_overrides`` maps field name → dict of *other* field-spec
    keys to override — e.g. turning off ``load_from_db`` on a secret
    input so the literal ``value`` is used instead of being looked up in
    Global Variables.
    """
    node_spec = copy.deepcopy(spec)

    # Override template field values in-place.
    for field_name, new_value in template_overrides.items():
        if field_name in node_spec["template"]:
            node_spec["template"][field_name]["value"] = new_value

    if field_flag_overrides:
        for field_name, flags in field_flag_overrides.items():
            if field_name in node_spec["template"]:
                node_spec["template"][field_name].update(flags)

    return {
        "id": node_id,
        "position": position,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": component_name,
            "node": node_spec,
        },
    }


def _build_edge(
    source_id: str,
    source_spec: dict[str, Any],
    source_output_name: str,
    target_id: str,
    target_spec: dict[str, Any],
    target_field_name: str,
) -> dict[str, Any]:
    """Build a LangFlow edge with its structured handle objects.

    Handles are not strings — they're small dicts carrying the source
    output name and data type alongside the target field metadata.
    """
    # Locate the source output to get its declared types.
    src_outputs = source_spec.get("outputs") or []
    src_output = next((o for o in src_outputs if o.get("name") == source_output_name), None)
    if src_output is None:
        raise ValueError(
            f"Source component has no output named {source_output_name!r}: "
            f"{[o.get('name') for o in src_outputs]}"
        )
    output_types = src_output.get("types", [])

    # Locate the target field to get its input types.
    target_field = target_spec["template"].get(target_field_name)
    if target_field is None:
        raise ValueError(f"Target component has no template field {target_field_name!r}")
    target_input_types = target_field.get("input_types", [])
    target_type = target_field.get("type", "str")
    source_data_type = source_spec.get("display_name") or source_spec.get("type") or ""

    return {
        "source": source_id,
        "target": target_id,
        "data": {
            "sourceHandle": {
                "dataType": source_data_type,
                "id": source_id,
                "name": source_output_name,
                "output_types": output_types,
            },
            "targetHandle": {
                "fieldName": target_field_name,
                "id": target_id,
                "inputTypes": target_input_types,
                "type": target_type,
            },
        },
    }


# ── Python tool code ──────────────────────────────────────────────────
#
# Each PythonCodeStructuredTool node carries a complete module body in
# its ``tool_code`` template field and the name of the function that
# should be surfaced as the tool in ``tool_function``.  The code runs
# in-process on the LangFlow server, so we can use ``subprocess`` and
# plain file I/O against the mounted workspace.


def tool_code_execute(workspace: str) -> tuple[str, str]:
    """Return (code, function_name) for the ``execute_shell`` tool."""
    code = (
        "import subprocess\n"
        "\n"
        "def execute_shell(command: str) -> str:\n"
        '    """Run a shell command in the workspace directory."""\n'
        "    try:\n"
        "        out = subprocess.run(\n"
        "            command, shell=True,\n"
        f'            cwd="{workspace}",\n'
        "            capture_output=True, text=True, timeout=120,\n"
        "        )\n"
        "        return out.stdout if out.returncode == 0 else out.stderr\n"
        "    except Exception as e:\n"
        '        return f"Error: {e}"\n'
    )
    return code, "execute_shell"


def tool_code_read(workspace: str) -> tuple[str, str]:
    """Return (code, function_name) for the ``read_file`` tool."""
    code = (
        "import os\n"
        "\n"
        "def read_file(path: str) -> str:\n"
        '    """Read the contents of a file relative to the workspace."""\n'
        f'    full = os.path.normpath(os.path.join("{workspace}", path))\n'
        f'    if not full.startswith("{workspace}"):\n'
        '        return "Error: path outside workspace"\n'
        "    try:\n"
        "        with open(full, encoding=\"utf-8\") as fh:\n"
        "            return fh.read()\n"
        "    except Exception as e:\n"
        '        return f"Error: {e}"\n'
    )
    return code, "read_file"


def tool_code_write(workspace: str) -> tuple[str, str]:
    """Return (code, function_name) for the ``write_file`` tool."""
    code = (
        "import os\n"
        "\n"
        "def write_file(path: str, content: str) -> str:\n"
        '    """Write content to a file relative to the workspace."""\n'
        f'    full = os.path.normpath(os.path.join("{workspace}", path))\n'
        f'    if not full.startswith("{workspace}"):\n'
        '        return "Error: path outside workspace"\n'
        "    try:\n"
        "        os.makedirs(os.path.dirname(full), exist_ok=True)\n"
        "        with open(full, \"w\", encoding=\"utf-8\") as fh:\n"
        "            fh.write(content)\n"
        '        return f"Written: {path}"\n'
        "    except Exception as e:\n"
        '        return f"Error: {e}"\n'
    )
    return code, "write_file"


TOOL_BUILDERS = [
    ("execute_shell", "Execute a shell command in the workspace.", tool_code_execute),
    ("read_file", "Read a file from the workspace.", tool_code_read),
    ("write_file", "Write content to a file in the workspace.", tool_code_write),
]


# ── Tool code parsing (mirrors LangFlow's internal _parse_code) ───────
#
# ``PythonCodeStructuredTool`` expects the UI-side ``update_build_config``
# to have populated three things before the component runs:
#   * ``_classes``     — JSON list of class definitions (empty for us)
#   * ``_functions``   — JSON list of function + arg metadata
#   * per-arg template fields keyed ``{funcName}|{argName}``
#
# We build the flow programmatically, so none of those exist.  This
# helper re-implements the minimum subset of LangFlow's parser so the
# component can construct its tool schema at runtime.


def _parse_tool_code(code: str) -> tuple[list[dict], list[dict]]:
    """Return ``(classes, functions)`` in LangFlow's expected JSON shape."""
    tree = ast.parse(code)
    lines = code.split("\n")
    classes: list[dict] = []
    functions: list[dict] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls_lines = lines[node.lineno - 1 : node.end_lineno]
            classes.append({"name": node.name, "code": cls_lines})
            continue
        if not isinstance(node, ast.FunctionDef):
            continue
        args: list[dict] = []
        for arg in node.args.args:
            annotation: str | None = None
            if arg.annotation is not None:
                annotation = ast.unparse(arg.annotation)
            args.append({"name": arg.arg, "annotation": annotation})
        functions.append({"name": node.name, "args": args})
    return classes, functions


def _per_arg_template_fields(
    tool_code: str,
) -> tuple[list[dict], dict[str, dict], dict[str, dict[str, Any]]]:
    """Parse the tool code and synthesise the per-arg template fields.

    Returns ``(classes, named_functions, extra_fields)``.

    LangFlow's UI builds a ``{func}|{arg}`` MessageTextInput for every
    argument so the structured-tool schema knows the arg name, type,
    and description at runtime.  ``_functions`` is stored as a dict
    keyed by function name (not a list), since ``_find_arg`` does
    ``named_functions[func_name]`` at build time.
    """
    classes, functions = _parse_tool_code(tool_code)
    named_functions: dict[str, dict] = {f["name"]: f for f in functions}
    extra_fields: dict[str, dict[str, Any]] = {}
    for fn in functions:
        for arg in fn["args"]:
            field_name = f"{fn['name']}|{arg['name']}"
            extra_fields[field_name] = {
                "type": "str",
                "_input_type": "MessageTextInput",
                "name": field_name,
                "display_name": f"{arg['name']}: Description",
                "info": f"Enter the description for {arg['name']}",
                "value": f"Argument '{arg['name']}' for {fn['name']}",
                "placeholder": "",
                "required": True,
                "show": True,
                "multiline": False,
                "list": False,
                "dynamic": True,
                "advanced": False,
                "input_types": ["Message"],
            }
    return classes, named_functions, extra_fields


# ── Flow assembly ─────────────────────────────────────────────────────


def build_flow(
    stage_name: str,
    system_msg: str,
    model_name: str,
    api_key: str,
    workspace: str,
    catalog: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Assemble a LangFlow flow JSON for a DESMET stage.

    ``catalog`` is the full response from ``GET /api/v1/all`` — the
    builder pulls ``OpenRouterComponent``, ``PythonCodeStructuredTool``,
    ``Agent``, ``ChatInput``, and ``ChatOutput`` specs out of it.
    """
    chat_in_spec = catalog["input_output"]["ChatInput"]
    chat_out_spec = catalog["input_output"]["ChatOutput"]
    llm_spec = catalog["openrouter"]["OpenRouterComponent"]
    tool_spec = catalog["tools"]["PythonCodeStructuredTool"]
    agent_spec = catalog["models_and_agents"]["Agent"]

    # Generate unique node ids.
    chat_in_id = _node_id("ChatInput")
    chat_out_id = _node_id("ChatOutput")
    llm_id = _node_id("OpenRouterComponent")
    agent_id = _node_id("Agent")
    tool_ids: list[str] = []

    nodes: list[dict[str, Any]] = []

    # Chat input (carries no pre-set text; Agent receives the prompt
    # via ``input_value`` wired from ChatInput).
    nodes.append(
        _build_node(
            "ChatInput",
            chat_in_spec,
            template_overrides={},
            position={"x": -400, "y": 0},
            node_id=chat_in_id,
        )
    )

    # OpenRouter chat model.
    # ``api_key`` has ``load_from_db: true`` by default, which makes
    # LangFlow interpret the value as a Global Variable name and look
    # it up (that's how the UI secret picker works).  We want the
    # literal key, so disable the lookup for this field.
    nodes.append(
        _build_node(
            "OpenRouterComponent",
            llm_spec,
            template_overrides={
                "api_key": api_key,
                "model_name": model_name,
                "temperature": 0.0,
                "stream": False,
            },
            field_flag_overrides={
                "api_key": {"load_from_db": False},
            },
            position={"x": 200, "y": 400},
            node_id=llm_id,
        )
    )

    # Workspace tools.  The UI normally runs ``update_build_config``
    # to populate ``_classes`` / ``_functions`` / per-arg fields when
    # the user types code into ``tool_code``.  Building the flow via
    # the API skips that step, so we replicate it here from the same
    # ``tool_code`` string the agent will see.
    for idx, (tool_name, tool_desc, builder) in enumerate(TOOL_BUILDERS):
        code, fn_name = builder(workspace)
        classes, named_functions, extra_fields = _per_arg_template_fields(code)
        tid = _node_id("PythonCodeStructuredTool")
        tool_ids.append(tid)

        tool_node = _build_node(
            "PythonCodeStructuredTool",
            tool_spec,
            template_overrides={
                "tool_name": tool_name,
                "tool_description": tool_desc,
                "tool_code": code,
                "tool_function": fn_name,
                "return_direct": False,
                "global_variables": [],
                "_classes": json.dumps(classes),
                "_functions": json.dumps(named_functions),
            },
            position={"x": 600 + idx * 350, "y": 400},
            node_id=tid,
        )
        # Splice in the per-arg dynamic fields that update_build_config
        # would normally add.
        for fname, fspec in extra_fields.items():
            tool_node["data"]["node"]["template"][fname] = fspec
        nodes.append(tool_node)

    # Agent.
    nodes.append(
        _build_node(
            "Agent",
            agent_spec,
            template_overrides={
                "system_prompt": system_msg,
                "max_iterations": 25,
            },
            position={"x": 600, "y": 0},
            node_id=agent_id,
        )
    )

    # Chat output.
    nodes.append(
        _build_node(
            "ChatOutput",
            chat_out_spec,
            template_overrides={},
            position={"x": 1200, "y": 0},
            node_id=chat_out_id,
        )
    )

    # Edges.
    edges: list[dict[str, Any]] = [
        _build_edge(
            chat_in_id, chat_in_spec, "message",
            agent_id, agent_spec, "input_value",
        ),
        _build_edge(
            llm_id, llm_spec, "model_output",
            agent_id, agent_spec, "model",
        ),
        _build_edge(
            agent_id, agent_spec, "response",
            chat_out_id, chat_out_spec, "input_value",
        ),
    ]
    for tid in tool_ids:
        edges.append(
            _build_edge(tid, tool_spec, "result_tool", agent_id, agent_spec, "tools")
        )

    return {
        "name": f"desmet-{stage_name}",
        "description": f"DESMET {stage_name} stage",
        "data": {
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }
