"""Agent execution trace models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolCall:
    """Record of a tool invocation by the agent."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    timestamp: datetime
    duration_ms: float
    success: bool
    error: str | None = None


@dataclass
class AgentMessage:
    """A message in the agent conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: datetime
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTrace:
    """Complete trace of an agent execution."""

    messages: list[AgentMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_iterations: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    total_llm_duration_ms: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None
    final_state: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    node_events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.total_tokens_input + self.total_tokens_output

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                }
                for m in self.messages
            ],
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "arguments": tc.arguments,
                    "result": str(tc.result) if tc.result is not None else None,
                    "timestamp": tc.timestamp.isoformat(),
                    "duration_ms": tc.duration_ms,
                    "success": tc.success,
                    "error": tc.error,
                }
                for tc in self.tool_calls
            ],
            "total_iterations": self.total_iterations,
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_cost_usd": self.total_cost_usd,
            "total_llm_duration_ms": self.total_llm_duration_ms,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "final_state": self.final_state,
            "errors": self.errors,
            "node_events": self.node_events,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTrace:
        """Deserialize from a dict produced by ``to_dict()``."""
        from datetime import datetime as _dt

        messages = [
            AgentMessage(
                role=m["role"],
                content=m["content"],
                timestamp=_dt.fromisoformat(m["timestamp"]),
                metadata=m.get("metadata", {}),
            )
            for m in data.get("messages", [])
        ]
        tool_calls = [
            ToolCall(
                tool_name=tc["tool_name"],
                arguments=tc["arguments"],
                result=tc.get("result"),
                timestamp=_dt.fromisoformat(tc["timestamp"]),
                duration_ms=tc["duration_ms"],
                success=tc["success"],
                error=tc.get("error"),
            )
            for tc in data.get("tool_calls", [])
        ]
        return cls(
            messages=messages,
            tool_calls=tool_calls,
            total_iterations=data.get("total_iterations", 0),
            total_tokens_input=data.get("total_tokens_input", 0),
            total_tokens_output=data.get("total_tokens_output", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            total_llm_duration_ms=data.get("total_llm_duration_ms", 0.0),
            start_time=_dt.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=_dt.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            final_state=data.get("final_state", {}),
            errors=data.get("errors", []),
            node_events=data.get("node_events", []),
            metadata=data.get("metadata", {}),
        )
