"""Tests for the Langfuse REST proxy client."""

from __future__ import annotations

import httpx
import pytest

from desmet.webui import langfuse_client as lc


def _configure(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse.test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")


def _install_transport(monkeypatch, handler):
    """Route every ``httpx.AsyncClient`` the module creates through *handler*."""
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(lc.httpx, "AsyncClient", factory)


def _obs(i: int, parent: str | None = None) -> dict:
    return {
        "id": f"obs-{i}",
        "name": f"step-{i}",
        "type": "SPAN",
        "startTime": f"2026-10-27T10:00:{i % 60:02d}.000Z",
        "endTime": f"2026-10-27T10:00:{i % 60:02d}.500Z",
        "parentObservationId": parent,
    }


@pytest.mark.asyncio
async def test_fetch_trace_pages_through_all_observations(monkeypatch):
    """A trace with more observations than one page must be fetched completely.

    Langfuse caps a single observations request at 100 items. The client has
    to follow ``meta.totalPages`` or the span tree arrives with its parents
    missing and every orphan looks like a separate root.
    """
    _configure(monkeypatch)
    # 250 observations: obs-0 is the root, everything else hangs off it.
    all_obs = [_obs(0)] + [_obs(i, parent="obs-0") for i in range(1, 250)]
    page_size = 100
    pages_requested: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/public/traces/trace-1":
            return httpx.Response(200, json={"id": "trace-1", "name": "t", "usage": {}})
        if request.url.path == "/api/public/observations":
            page = int(request.url.params.get("page", "1"))
            pages_requested.append(page)
            # Newest-first like the real API.
            ordered = list(reversed(all_obs))
            chunk = ordered[(page - 1) * page_size : page * page_size]
            return httpx.Response(
                200,
                json={
                    "data": chunk,
                    "meta": {
                        "page": page,
                        "limit": page_size,
                        "totalItems": len(all_obs),
                        "totalPages": 3,
                    },
                },
            )
        return httpx.Response(404)

    _install_transport(monkeypatch, handler)

    result = await lc.fetch_trace("trace-1")

    assert result is not None
    assert sorted(pages_requested) == [1, 2, 3]
    roots = result["observations"]
    assert [r["id"] for r in roots] == ["obs-0"]
    assert len(roots[0]["children"]) == 249


@pytest.mark.asyncio
async def test_fetch_trace_keeps_native_observation_type(monkeypatch):
    """Framework-native types (CHAIN, AGENT) are passed through lower-cased.

    The canonical execution model decides what a chain or agent span means;
    the client must not collapse them into ``span``.
    """
    _configure(monkeypatch)
    obs = [
        {**_obs(0), "type": "AGENT"},
        {**_obs(1, parent="obs-0"), "type": "CHAIN"},
        {**_obs(2, parent="obs-0"), "type": "GENERATION"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/api/public/traces/"):
            return httpx.Response(200, json={"id": "trace-1", "usage": {}})
        return httpx.Response(
            200,
            json={"data": obs, "meta": {"page": 1, "limit": 100, "totalItems": 3, "totalPages": 1}},
        )

    _install_transport(monkeypatch, handler)

    result = await lc.fetch_trace("trace-1")

    assert result is not None
    root = result["observations"][0]
    assert root["type"] == "agent"
    assert sorted(c["type"] for c in root["children"]) == ["chain", "generation"]
