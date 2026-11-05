"""Adapters must tag every recorded message with the agent that produced it.

Without the tag the local trace cannot be turned into agent turns, so the
execution model degrades to one anonymous turn per stage (see
``build_from_stage_file``). These tests cover the platforms whose native
events carry the agent but whose adapters used to drop it.
"""

from __future__ import annotations

from types import SimpleNamespace

from desmet.adapters._shared.observation import ObservationCollector, ObservationRequirements
from desmet.harness.trace import AgentTrace


def _collector(trace: AgentTrace) -> ObservationCollector:
    return ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False, messages=False, iterations=False
        ),
    )


# ── CrewAI ──────────────────────────────────────────────────────────────


class TestCrewAITagging:
    def test_event_agent_role_reads_direct_field(self):
        from desmet.adapters.multiagent.crewai import _event_agent_role

        assert _event_agent_role(SimpleNamespace(agent_role="Technical Lead")) == "Technical Lead"

    def test_event_agent_role_falls_back_to_from_agent(self):
        from desmet.adapters.multiagent.crewai import _event_agent_role

        event = SimpleNamespace(agent_role=None, from_agent=SimpleNamespace(role="QA Engineer"))
        assert _event_agent_role(event) == "QA Engineer"

    def test_event_agent_role_is_none_when_absent(self):
        from desmet.adapters.multiagent.crewai import _event_agent_role

        assert _event_agent_role(SimpleNamespace()) is None

    def test_llm_response_message_carries_agent_role(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter

        adapter = CrewAIAdapter(config={"model": "test-model"})
        trace = AgentTrace()
        adapter._current_collector = _collector(trace)

        adapter._record_llm_response_message(
            SimpleNamespace(response="I will write the tests", agent_role="QA Engineer")
        )

        assert trace.messages[-1].role == "assistant"
        assert trace.messages[-1].metadata["agent_role"] == "QA Engineer"

    def test_llm_response_message_without_role_still_recorded(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter

        adapter = CrewAIAdapter(config={"model": "test-model"})
        trace = AgentTrace()
        adapter._current_collector = _collector(trace)

        adapter._record_llm_response_message(SimpleNamespace(response="done"))

        assert trace.messages[-1].content == "done"
        assert "agent_role" not in trace.messages[-1].metadata


# ── OpenAI Agents SDK ───────────────────────────────────────────────────


class TestOpenAIAgentsTagging:
    def test_item_metadata_uses_owning_agent_name(self):
        from desmet.adapters.sdk.openai_agents import _item_metadata

        item = SimpleNamespace(agent=SimpleNamespace(name="desmet_codegen_executor"))
        assert _item_metadata(item) == {"agent": "desmet_codegen_executor"}

    def test_item_metadata_is_empty_without_agent(self):
        from desmet.adapters.sdk.openai_agents import _item_metadata

        assert _item_metadata(SimpleNamespace()) == {}
        assert _item_metadata(SimpleNamespace(agent=None)) == {}

    def test_extract_trace_tags_messages_with_agent(self):
        """Source-level guard: the extraction loop must attach the item's agent."""
        import inspect

        from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter

        src = inspect.getsource(OpenAIAgentsAdapter._extract_trace)
        assert "_item_metadata(item)" in src


# ── Google ADK ──────────────────────────────────────────────────────────


class TestGoogleADKTagging:
    def test_function_call_summary_lists_calls(self):
        from desmet.adapters.sdk.google_adk import _event_function_call_text

        event = SimpleNamespace(
            get_function_calls=lambda: [
                SimpleNamespace(name="write_file", args={"path": "a.py", "content": "x" * 500}),
                SimpleNamespace(name="list_directory", args={}),
            ]
        )
        text = _event_function_call_text(event)
        assert text is not None
        assert text.startswith("write_file(")
        assert "list_directory()" in text
        assert len(text) < 400

    def test_function_call_summary_is_none_without_calls(self):
        from desmet.adapters.sdk.google_adk import _event_function_call_text

        assert _event_function_call_text(SimpleNamespace(get_function_calls=lambda: [])) is None
        assert _event_function_call_text(SimpleNamespace()) is None

    def test_run_loop_records_function_call_events_with_author(self):
        """Source-level guard: tool-only events must still produce a tagged message."""
        import inspect

        from desmet.adapters.sdk.google_adk import GoogleADKAdapter

        src = inspect.getsource(GoogleADKAdapter)
        assert "_event_function_call_text(event)" in src
