"""Unit tests for the LangSmith webUI client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestCheckStatus:
    @pytest.mark.asyncio
    async def test_returns_unavailable_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from desmet.webui.langsmith_client import check_status
        result = await check_status()
        assert result == {"available": False, "project": None}

    @pytest.mark.asyncio
    async def test_returns_available_on_200(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
        from desmet.webui.langsmith_client import check_status
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            result = await check_status()

        assert result["available"] is True

    @pytest.mark.asyncio
    async def test_returns_unavailable_on_exception(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
        from desmet.webui.langsmith_client import check_status

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value = mock_client
            result = await check_status()

        assert result["available"] is False


class TestFetchRunTree:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from desmet.webui.langsmith_client import fetch_run_tree
        result = await fetch_run_tree("some-run-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
        from desmet.webui.langsmith_client import fetch_run_tree

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value = mock_client
            result = await fetch_run_tree("some-run-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_assembles_tree_from_flat_children(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
        from desmet.webui.langsmith_client import fetch_run_tree

        root_resp = MagicMock()
        root_resp.raise_for_status = MagicMock()
        root_resp.json = MagicMock(return_value={
            "id": "root-1", "name": "desmet-langgraph-requirements",
            "run_type": "chain", "start_time": "2026-01-01T00:00:00Z",
            "end_time": "2026-01-01T00:01:00Z",
            "total_tokens": 500, "error": None, "tags": [],
            "inputs": None, "outputs": "done", "extra": {"total_tokens": 500},
        })

        child_resp = MagicMock()
        child_resp.raise_for_status = MagicMock()
        child_resp.json = MagicMock(return_value={"runs": [
            {
                "id": "child-1", "name": "planner_node",
                "run_type": "chain", "parent_run_id": "root-1",
                "start_time": "2026-01-01T00:00:01Z",
                "end_time": "2026-01-01T00:00:10Z",
                "inputs": None, "outputs": None,
                "extra": {"total_tokens": 100}, "error": None,
            }
        ]})

        call_count = 0
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return root_resp
            return child_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = mock_get
            mock_client_cls.return_value = mock_client
            result = await fetch_run_tree("root-1")

        assert result is not None
        assert result["run"]["id"] == "root-1"
        assert len(result["children"]) == 1
        assert result["children"][0]["name"] == "planner_node"
