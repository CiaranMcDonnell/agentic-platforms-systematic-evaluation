"""Escape helper for ADK agent instructions.

ADK's ``inject_session_state`` rewrites any ``{name}`` substring inside an
agent ``instruction`` as a session-state lookup (regex ``r'{+[^{}]*}+'``).
When ``name`` is a valid Python identifier that isn't in session state,
ADK raises ``KeyError: Context variable not found: `name`.`` — which is
exactly what killed the deploy stage on the ``google_adk`` adapter when
the executor instructions contained ``${PORT}``.

These tests exercise ``escape_adk_template`` against ADK's real
``inject_session_state`` so the guarantee is measured, not assumed.
"""
from __future__ import annotations

import asyncio

import pytest

from desmet.adapters.sdk.google_adk import escape_adk_template


@pytest.fixture
def inject():
    """Return a sync helper that runs ADK's inject_session_state with an empty state."""
    from google.adk.agents import Agent
    from google.adk.agents.readonly_context import ReadonlyContext
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.utils.instructions_utils import inject_session_state

    svc = InMemorySessionService()
    agent = Agent(name="probe", model="gemini-2.0-flash", instruction="")
    runner = Runner(app_name="probe", agent=agent, session_service=svc)

    async def _inject(template: str) -> str:
        session = await svc.create_session(app_name="probe", user_id="u")
        ctx = runner._new_invocation_context(session, new_message=None)
        return await inject_session_state(template, ReadonlyContext(ctx))

    def run(template: str) -> str:
        return asyncio.run(_inject(template))

    return run


class TestEscapeAdkTemplate:
    def test_port_literal_survives_templating(self, inject):
        """${PORT} should pass through ADK templating without raising."""
        escaped = escape_adk_template('docker-compose port mapping: "${PORT}:8000"')
        result = inject(escaped)
        assert "PORT" in result
        assert "8000" in result

    def test_bare_identifier_in_braces_does_not_raise(self, inject):
        """A bare {IDENTIFIER} must not trigger a state lookup."""
        escaped = escape_adk_template("Example: {PORT} and {API_KEY}")
        result = inject(escaped)
        assert "PORT" in result
        assert "API_KEY" in result

    def test_plain_text_is_unchanged(self):
        """Text with no braces should be byte-identical after escape."""
        text = "Write a function that validates emails."
        assert escape_adk_template(text) == text

    def test_json_like_snippet_survives(self, inject):
        """A JSON snippet inside the instruction must not raise."""
        escaped = escape_adk_template('Example: {"host": "localhost", "port": 8000}')
        result = inject(escaped)
        assert "localhost" in result

    def test_mermaid_snippet_survives(self, inject):
        """Mermaid diagrams embed {…} blocks; must not trigger state lookups."""
        snippet = (
            "classDiagram\n"
            "class User {\n"
            "  +int id\n"
            "  +string email\n"
            "}\n"
        )
        escaped = escape_adk_template(snippet)
        result = inject(escaped)
        assert "User" in result

    def test_empty_string_is_safe(self, inject):
        assert inject(escape_adk_template("")) == ""

    def test_escape_is_idempotent(self, inject):
        """Escaping twice should be safe — no double-insertion of markers."""
        once = escape_adk_template("${PORT}:8000")
        twice = escape_adk_template(once)
        assert inject(once) == inject(twice)

    def test_nested_braces_do_not_raise(self, inject):
        """Mermaid-like nested braces must survive ADK templating."""
        template = "class Foo { bar: Baz {} }\n{PORT}"
        escaped = escape_adk_template(template)
        result = inject(escaped)
        assert "Foo" in result
        assert "Baz" in result
        assert "PORT" in result

    def test_deeply_nested_braces(self, inject):
        """Multiple levels of nesting must all survive templating."""
        template = "{{ outer { inner { deepest } } }}"
        escaped = escape_adk_template(template)
        result = inject(escaped)
        assert "outer" in result
        assert "inner" in result
        assert "deepest" in result
