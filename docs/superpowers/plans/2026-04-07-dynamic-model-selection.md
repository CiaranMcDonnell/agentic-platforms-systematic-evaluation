# Dynamic Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded default model with dynamic discovery from provider APIs (OpenAI, Anthropic, OpenRouter, Google) and a searchable grouped dropdown UI.

**Architecture:** New `model_discovery.py` module queries provider APIs for their model lists (with 1-hour TTL cache, based on which API keys are set). `/api/config` returns these grouped by provider. A new `ModelPicker.svelte` component replaces the native `<select>` with a searchable combobox that supports both picking and free-text custom entry. `DEFAULT_MODEL` is removed; adapters validate the model at `initialize()` time.

**Tech Stack:** httpx (sync HTTP in backend), Svelte 5 runes, localStorage for persistence

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/webui/model_discovery.py` | Create | Provider API clients + TTL cache |
| `src/desmet/llm_config.py` | Modify | Remove `DEFAULT_MODEL`, return empty model when unset |
| `src/desmet/harness/context.py` | Modify | Use `""` instead of `DEFAULT_MODEL` for default field value |
| `src/desmet/webui/api.py` | Modify | `/api/config` returns grouped `available_models` |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | Change `available_models` type to `Record<string, string[]>` |
| `src/desmet/webui/frontend/src/lib/components/ModelPicker.svelte` | Create | Searchable grouped combobox |
| `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte` | Modify | Use ModelPicker, localStorage persistence, disable submit without model |
| `tests/test_model_discovery.py` | Create | Mock HTTP tests for providers + cache |
| `tests/test_llm_config.py` | Create | Test get_config() behavior with/without model |

---

### Task 1: model_discovery module

**Files:**
- Create: `src/desmet/webui/model_discovery.py`
- Create: `tests/test_model_discovery.py`

- [ ] **Step 1: Write failing tests for model_discovery**

Create `tests/test_model_discovery.py`:

```python
"""Tests for the model discovery module."""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest


class TestFetchOpenAI:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_openai_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-5.4-2026-03-05", "object": "model"},
                {"id": "gpt-5-turbo", "object": "model"},
                {"id": "dall-e-3", "object": "model"},
            ],
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             patch("httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_openai_models()
            assert "gpt-5.4-2026-03-05" in result
            assert "gpt-5-turbo" in result
            mock_get.assert_called_once()
            call_headers = mock_get.call_args[1].get("headers", {})
            assert call_headers.get("Authorization") == "Bearer sk-test"

    def test_returns_empty_on_error(self):
        from desmet.webui.model_discovery import fetch_openai_models

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             patch("httpx.get", side_effect=Exception("network down")):
            result = fetch_openai_models()
            assert result == []

    def test_returns_empty_without_api_key(self):
        from desmet.webui.model_discovery import fetch_openai_models

        with patch.dict(os.environ, {}, clear=True):
            result = fetch_openai_models()
            assert result == []


class TestFetchAnthropic:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_anthropic_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "claude-opus-4-6"},
                {"id": "claude-sonnet-4-6"},
            ],
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}), \
             patch("httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_anthropic_models()
            assert "claude-opus-4-6" in result
            assert "claude-sonnet-4-6" in result
            call_headers = mock_get.call_args[1].get("headers", {})
            assert call_headers.get("x-api-key") == "sk-ant"


class TestFetchOpenRouter:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_openrouter_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "anthropic/claude-opus-4-6"},
                {"id": "openai/gpt-5.4"},
                {"id": "meta-llama/llama-3.1-70b"},
            ],
        }
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or"}), \
             patch("httpx.get", return_value=mock_resp):
            result = fetch_openrouter_models()
            assert "anthropic/claude-opus-4-6" in result
            assert "openai/gpt-5.4" in result


class TestFetchGoogle:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_google_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "models/gemini-2.0-pro"},
                {"name": "models/gemini-2.0-flash"},
            ],
        }
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "sk-goog"}), \
             patch("httpx.get", return_value=mock_resp):
            result = fetch_google_models()
            assert "gemini-2.0-pro" in result
            assert "gemini-2.0-flash" in result


class TestGetAvailableModels:
    def test_returns_only_configured_providers(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()  # reset for test
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", return_value=["gpt-5.4"]), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            result = model_discovery.get_available_models()
            assert "openai" in result
            assert result["openai"] == ["gpt-5.4"]
            # Providers without keys are omitted
            assert "anthropic" not in result
            assert "openrouter" not in result
            assert "google" not in result

    def test_cache_prevents_duplicate_calls(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()
        call_count = {"n": 0}

        def fake_fetch():
            call_count["n"] += 1
            return ["gpt-5.4"]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", side_effect=fake_fetch), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            model_discovery.get_available_models()
            model_discovery.get_available_models()
            model_discovery.get_available_models()
            assert call_count["n"] == 1  # fetched once, then cached

    def test_cache_expires_after_ttl(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", return_value=["gpt-5.4"]), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            model_discovery.get_available_models()
            # Expire the cache by rewinding the stored timestamp
            model_discovery._CACHE["timestamp"] = time.time() - (model_discovery._CACHE_TTL_SECONDS + 10)
            model_discovery.get_available_models()
            assert model_discovery._CACHE["timestamp"] > time.time() - model_discovery._CACHE_TTL_SECONDS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_model_discovery.py -v`
Expected: FAIL — `model_discovery` module not found

- [ ] **Step 3: Implement model_discovery**

Create `src/desmet/webui/model_discovery.py`:

```python
"""Dynamic model discovery from provider APIs.

Queries OpenAI, Anthropic, OpenRouter, and Google for their available
models, grouped by provider.  Only providers with a configured API key
are queried.  Results are cached in-process with a 1-hour TTL.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600  # 1 hour
_CACHE: dict[str, Any] = {
    "timestamp": 0.0,
    "data": {},
}
_HTTP_TIMEOUT = 10.0


def _clear_cache() -> None:
    """Reset the in-process cache (used by tests)."""
    _CACHE["timestamp"] = 0.0
    _CACHE["data"] = {}


# ── Per-provider fetchers ─────────────────────────────────────────────


def fetch_openai_models() -> list[str]:
    """Fetch available OpenAI models. Returns empty list on error or no key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("OpenAI models fetch returned %s", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("OpenAI models fetch failed: %s", e)
        return []


def fetch_anthropic_models() -> list[str]:
    """Fetch available Anthropic models. Returns empty list on error or no key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("Anthropic models fetch returned %s", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("Anthropic models fetch failed: %s", e)
        return []


def fetch_openrouter_models() -> list[str]:
    """Fetch available OpenRouter models. Returns empty list on error or no key."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("OpenRouter models fetch returned %s", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("OpenRouter models fetch failed: %s", e)
        return []


def fetch_google_models() -> list[str]:
    """Fetch available Google models. Returns empty list on error or no key.

    The Google API returns names like ``models/gemini-2.0-pro`` — strip
    the ``models/`` prefix.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("Google models fetch returned %s", resp.status_code)
            return []
        models = resp.json().get("models", [])
        ids: list[str] = []
        for m in models:
            name = m.get("name", "")
            if name.startswith("models/"):
                ids.append(name[len("models/"):])
            elif name:
                ids.append(name)
        return sorted(ids)
    except Exception as e:
        logger.warning("Google models fetch failed: %s", e)
        return []


# ── Aggregated fetch with cache ───────────────────────────────────────


def get_available_models() -> dict[str, list[str]]:
    """Return available models grouped by provider.

    Only providers whose API key env var is set are included in the
    result dict.  Results are cached in-process for ``_CACHE_TTL_SECONDS``.
    """
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return _CACHE["data"]

    result: dict[str, list[str]] = {}
    if os.environ.get("OPENAI_API_KEY"):
        models = fetch_openai_models()
        if models:
            result["openai"] = models
    if os.environ.get("ANTHROPIC_API_KEY"):
        models = fetch_anthropic_models()
        if models:
            result["anthropic"] = models
    if os.environ.get("OPENROUTER_API_KEY"):
        models = fetch_openrouter_models()
        if models:
            result["openrouter"] = models
    if os.environ.get("GOOGLE_API_KEY"):
        models = fetch_google_models()
        if models:
            result["google"] = models

    _CACHE["timestamp"] = now
    _CACHE["data"] = result
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_model_discovery.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/webui/model_discovery.py tests/test_model_discovery.py
git commit -m "feat: add model_discovery module with provider API clients and TTL cache"
```

---

### Task 2: Remove DEFAULT_MODEL from llm_config

**Files:**
- Modify: `src/desmet/llm_config.py:29-30, 132-137`
- Modify: `src/desmet/harness/context.py:12, 55`
- Create: `tests/test_llm_config.py`

- [ ] **Step 1: Write failing tests for llm_config**

Create `tests/test_llm_config.py`:

```python
"""Tests for llm_config default behavior."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestGetConfig:
    def test_empty_model_when_nothing_set(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            assert cfg.model == ""

    def test_uses_explicit_model_argument(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config(model="my-custom-model")
            assert cfg.model == "my-custom-model"

    def test_uses_desmet_model_env_var(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_MODEL": "env-model"}, clear=True):
            cfg = get_config()
            assert cfg.model == "env-model"

    def test_explicit_overrides_env(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_MODEL": "env-model"}, clear=True):
            cfg = get_config(model="explicit-model")
            assert cfg.model == "explicit-model"

    def test_no_default_model_constant(self):
        """DEFAULT_MODEL should no longer exist in llm_config."""
        import desmet.llm_config as llm_config
        assert not hasattr(llm_config, "DEFAULT_MODEL")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm_config.py -v`
Expected: FAIL — `test_empty_model_when_nothing_set` fails because it returns `gpt-5.4-2026-03-05`; `test_no_default_model_constant` fails because the constant exists.

- [ ] **Step 3: Modify llm_config.py to remove DEFAULT_MODEL**

In `src/desmet/llm_config.py`, delete the line:
```python
DEFAULT_MODEL = "gpt-5.4-2026-03-05"
```

Also delete the matching documentation line 20:
```
    DEFAULT_MODEL          – legacy fallback (prefer DESMET_MODEL)
```

Change `get_config()` (around line 132) from:
```python
    resolved_model = (
        model
        or os.getenv("DESMET_MODEL")
        or os.getenv("DEFAULT_MODEL")
        or DEFAULT_MODEL
    )
```

To:
```python
    resolved_model = (
        model
        or os.getenv("DESMET_MODEL")
        or os.getenv("DEFAULT_MODEL")
        or ""
    )
```

- [ ] **Step 4: Update harness/context.py to not import DEFAULT_MODEL**

In `src/desmet/harness/context.py`, change line 12:
```python
from desmet.llm_config import DEFAULT_MODEL, DEFAULT_TEMPERATURE
```

To:
```python
from desmet.llm_config import DEFAULT_TEMPERATURE
```

And change line 55:
```python
    model: str = DEFAULT_MODEL
```

To:
```python
    model: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm_config.py tests/test_metrics.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/desmet/llm_config.py src/desmet/harness/context.py tests/test_llm_config.py
git commit -m "refactor(llm): remove DEFAULT_MODEL, return empty model when unset"
```

---

### Task 3: Remove default_model from platforms.yaml and update loader docstring

**Files:**
- Modify: `config/platforms.yaml:145-147`
- Modify: `src/desmet/harness/loader.py:37-42`

- [ ] **Step 1: Remove default_model from platforms.yaml**

In `config/platforms.yaml`, delete lines 145-147:
```yaml
  # The canonical default lives in src/desmet/llm_config.py.
  # Override at runtime with DESMET_MODEL or DEFAULT_MODEL env vars.
  default_model: gpt-5.4-2026-03-05
```

- [ ] **Step 2: Update loader.py docstring**

In `src/desmet/harness/loader.py`, update the docstring around line 37-42 to remove the `default_model` reference. Change:
```python
        {
            "time_budgets": {"basic": 600, "intermediate": 1200, "advanced": 2400},
            "iteration_limits": {"basic": 25, "intermediate": 40, "advanced": 60},
            "default_model": "gpt-5.4-2026-03-05",
        }
```

To:
```python
        {
            "time_budgets": {"basic": 600, "intermediate": 1200, "advanced": 2400},
            "iteration_limits": {"basic": 25, "intermediate": 40, "advanced": 60},
        }
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ --timeout=60 -q`
Expected: All tests PASS (or only pre-existing skips)

- [ ] **Step 4: Commit**

```bash
git add config/platforms.yaml src/desmet/harness/loader.py
git commit -m "refactor: remove default_model from platforms.yaml"
```

---

### Task 4: Update /api/config endpoint

**Files:**
- Modify: `src/desmet/webui/api.py:334-355`

- [ ] **Step 1: Update the get_config endpoint**

In `src/desmet/webui/api.py`, modify the `get_config` function (around line 334-355). Change the `available_models` field from a hardcoded list to a call to `model_discovery.get_available_models()`. Also remove the `allow_custom_model` field since the new picker always allows free-text.

Find:
```python
    return {
        "model": cfg.model,
        "provider": llm.provider.value,
        "api_keys_set": cfg.api_keys_set,
        "langfuse_status": cfg.langfuse_status,
        "deploy_status": cfg.deploy_status,
        "temperature": llm.temperature,
        "available_models": [
            "gpt-5.4-2026-03-05",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
        ],
        "allow_custom_model": True,
        "valid_stages": ["requirements", "codegen", "testing", "deploy", "all"],
        "difficulty_levels": ["basic", "intermediate", "advanced"],
        "langsmith_available": None,
    }
```

Replace with:
```python
    from desmet.webui.model_discovery import get_available_models

    return {
        "model": cfg.model,
        "provider": llm.provider.value,
        "api_keys_set": cfg.api_keys_set,
        "langfuse_status": cfg.langfuse_status,
        "deploy_status": cfg.deploy_status,
        "temperature": llm.temperature,
        "available_models": get_available_models(),
        "valid_stages": ["requirements", "codegen", "testing", "deploy", "all"],
        "difficulty_levels": ["basic", "intermediate", "advanced"],
        "langsmith_available": None,
    }
```

- [ ] **Step 2: Verify endpoint returns grouped dict**

Run: `uv run python -c "
from unittest.mock import patch
import os
from desmet.webui.model_discovery import _clear_cache
_clear_cache()
with patch.dict(os.environ, {}, clear=True):
    from desmet.webui.model_discovery import get_available_models
    print(get_available_models())
"`
Expected: `{}` (empty dict when no API keys are set — proves the hardcoded list is gone)

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat(api): /api/config returns grouped models from model_discovery"
```

---

### Task 5: Frontend API type update

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts:28-40`

- [ ] **Step 1: Update AppConfig type**

In `src/desmet/webui/frontend/src/lib/api.ts`, find the `AppConfig` interface:

```typescript
export interface AppConfig {
  model: string;
  provider: string;
  api_keys_set: string[];
  langfuse_status: string;
  deploy_status: string;
  temperature: number;
  available_models: string[];
  allow_custom_model?: boolean;
  valid_stages: string[];
  difficulty_levels: string[];
  langsmith_available?: boolean;
}
```

Replace with:

```typescript
export interface AppConfig {
  model: string;
  provider: string;
  api_keys_set: string[];
  langfuse_status: string;
  deploy_status: string;
  temperature: number;
  available_models: Record<string, string[]>;
  valid_stages: string[];
  difficulty_levels: string[];
  langsmith_available?: boolean;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts
git commit -m "feat(webui): update AppConfig type for grouped available_models"
```

---

### Task 6: ModelPicker component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/ModelPicker.svelte`

- [ ] **Step 1: Create ModelPicker.svelte**

Create `src/desmet/webui/frontend/src/lib/components/ModelPicker.svelte`:

```svelte
<script lang="ts">
  interface Props {
    models: Record<string, string[]>;
    value: string;
    placeholder?: string;
  }

  let { models, value = $bindable(''), placeholder = 'Type or select a model...' }: Props = $props();

  let inputValue = $state(value);
  let isOpen = $state(false);
  let container: HTMLDivElement;

  // Sync external value changes into input
  $effect(() => {
    inputValue = value;
  });

  // Filtered groups based on case-insensitive substring search
  let filteredGroups = $derived.by(() => {
    const q = inputValue.toLowerCase().trim();
    const result: Record<string, string[]> = {};
    for (const [provider, list] of Object.entries(models)) {
      const matches = q
        ? list.filter(m => m.toLowerCase().includes(q))
        : list;
      if (matches.length) {
        result[provider] = matches;
      }
    }
    return result;
  });

  let hasAnyMatches = $derived(
    Object.values(filteredGroups).some(list => list.length > 0)
  );

  function handleInput(e: Event) {
    inputValue = (e.target as HTMLInputElement).value;
    isOpen = true;
  }

  function handleFocus() {
    isOpen = true;
  }

  function handleBlur(e: FocusEvent) {
    // Delay close so option clicks register first
    setTimeout(() => {
      if (container && !container.contains(document.activeElement)) {
        isOpen = false;
        // Commit current input as the value (supports custom models)
        value = inputValue;
      }
    }, 150);
  }

  function selectOption(option: string) {
    value = option;
    inputValue = option;
    isOpen = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      isOpen = false;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      value = inputValue;
      isOpen = false;
    }
  }

  const providerLabels: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    openrouter: 'OpenRouter',
    google: 'Google',
  };
</script>

<div class="model-picker" bind:this={container}>
  <input
    type="text"
    class="input picker-input"
    {placeholder}
    value={inputValue}
    oninput={handleInput}
    onfocus={handleFocus}
    onblur={handleBlur}
    onkeydown={handleKeydown}
  />
  {#if isOpen}
    <div class="dropdown">
      {#if !Object.keys(models).length}
        <div class="empty-msg">
          No providers configured. Set an API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, or GOOGLE_API_KEY) to see available models.
        </div>
      {:else if !hasAnyMatches}
        <div class="empty-msg">
          No models match "{inputValue}". Press Enter to use this as a custom model.
        </div>
      {:else}
        {#each Object.entries(filteredGroups) as [provider, list]}
          <div class="group">
            <div class="group-header">{providerLabels[provider] || provider}</div>
            {#each list as model}
              <button
                class="option {value === model ? 'selected' : ''}"
                onmousedown={() => selectOption(model)}
                type="button"
              >
                {model}
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .model-picker {
    position: relative;
    width: 100%;
    max-width: 420px;
  }
  .picker-input {
    width: 100%;
    font-family: var(--mono, monospace);
    font-size: 13px;
  }
  .dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    max-height: 320px;
    overflow-y: auto;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    z-index: 100;
    padding: 4px 0;
  }
  .group {
    padding: 4px 0;
  }
  .group:not(:last-child) {
    border-bottom: 1px solid var(--border);
  }
  .group-header {
    padding: 6px 12px 4px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    font-weight: 600;
  }
  .option {
    display: block;
    width: 100%;
    padding: 6px 12px;
    border: none;
    background: transparent;
    color: var(--text-1);
    font-family: var(--mono, monospace);
    font-size: 12.5px;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s ease;
  }
  .option:hover {
    background: rgba(212, 168, 83, 0.1);
    color: var(--text-0);
  }
  .option.selected {
    background: rgba(212, 168, 83, 0.2);
    color: var(--text-0);
    font-weight: 500;
  }
  .empty-msg {
    padding: 12px 14px;
    font-size: 12px;
    color: var(--text-2);
    line-height: 1.5;
  }
</style>
```

- [ ] **Step 2: Build frontend to verify**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/ModelPicker.svelte
git commit -m "feat(webui): add ModelPicker searchable grouped combobox"
```

---

### Task 7: Integrate ModelPicker into NewRun page

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte`

- [ ] **Step 1: Import ModelPicker and add localStorage logic**

In `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte`, add the import near the top of the `<script>` block (after `import StatusBadge`):

```typescript
  import ModelPicker from '../components/ModelPicker.svelte';
```

Replace the existing model state initialization. Find:
```typescript
  let model = $state('');
  let customModel = $state('');
```

Replace with:
```typescript
  const LAST_MODEL_KEY = 'desmet:last-model';
  let model = $state<string>(
    typeof localStorage !== 'undefined' ? (localStorage.getItem(LAST_MODEL_KEY) ?? '') : ''
  );
```

(The `customModel` field is no longer needed because the ModelPicker handles free-text directly.)

- [ ] **Step 2: Save model to localStorage on submit**

In the `submit()` function, find the line:
```typescript
      const res = await startRun({
```

Before it, add:
```typescript
      if (typeof localStorage !== 'undefined' && model) {
        localStorage.setItem(LAST_MODEL_KEY, model);
      }
```

And in the startRun call, replace:
```typescript
        model: (model === '__custom__' ? customModel : model) || null,
```

With:
```typescript
        model: model || null,
```

- [ ] **Step 3: Replace the model dropdown in the template**

Find the model filter group:
```svelte
    <div class="filter-group" style="flex: 1; min-width: 200px;">
      <span class="filter-label">Model</span>
      <select class="input" style="max-width: 320px;" bind:value={model}>
        <option value="">Default ({store.config?.model})</option>
        {#each store.config?.available_models || [] as m}<option value={m}>{m}</option>{/each}
        <option value="__custom__">Custom model</option>
      </select>
    </div>
```

Replace with:
```svelte
    <div class="filter-group" style="flex: 1; min-width: 200px;">
      <span class="filter-label">Model</span>
      <ModelPicker
        models={store.config?.available_models || {}}
        bind:value={model}
      />
    </div>
```

- [ ] **Step 4: Remove the custom model input block**

Find and delete the entire `{#if model === '__custom__'}` block (around lines 148-165):

```svelte
  {#if model === '__custom__'}
    <div class="card" style="padding: 14px 20px;">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <input
          id="custom-model"
          class="input"
          type="text"
          style="max-width: 360px;"
          placeholder="e.g. claude-opus-4-6 or openai/gpt-5.4"
          bind:value={customModel}
        />
        <div style="font-size: 12.5px; color: var(--text-2); line-height: 1.5;">
          Native: <code style="font-size: 12px;">claude-opus-4-6</code>, <code style="font-size: 12px;">gpt-5.4-2026-03-05</code>
          · OpenRouter: <code style="font-size: 12px;">vendor/model</code> — <a href="https://openrouter.ai/models" target="_blank" rel="noopener" style="color: var(--accent);">browse models</a>
        </div>
      </div>
    </div>
  {/if}
```

Delete the whole block — ModelPicker handles free-text entry inline.

- [ ] **Step 5: Disable Start button when no model selected**

Find the Start button:
```svelte
    <button
      class="btn btn-primary"
      style="padding: 10px 28px; font-size: 14px; border-radius: 8px; flex-shrink: 0;"
      disabled={!selectedPlatforms.length || submitting}
      onclick={submit}
    >
      {submitting ? 'Starting...' : 'Start Benchmark Run'}
    </button>
```

Change the `disabled` attribute to also require a model:
```svelte
      disabled={!selectedPlatforms.length || !model || submitting}
```

- [ ] **Step 6: Build frontend to verify**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 7: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/NewRun.svelte
git commit -m "feat(webui): use ModelPicker with localStorage persistence on NewRun"
```

---

### Task 8: Full integration test

**Files:**
- Test: all

- [ ] **Step 1: Run full Python test suite**

Run: `uv run pytest tests/ --timeout=60 -q`
Expected: All tests pass or pre-existing skips only. No new failures.

- [ ] **Step 2: Verify backend config endpoint manually**

Start the webui: `uv run desmet`

In another terminal: `curl http://127.0.0.1:8042/api/config | python -c "import json, sys; d = json.load(sys.stdin); print('available_models type:', type(d['available_models']).__name__); print('model:', repr(d['model']))"`

Expected:
- `available_models type: dict` (was `list`)
- `model: ''` or the value of `DESMET_MODEL` if set

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git commit -m "test: verify dynamic model selection integration"
```
