# Dynamic Model Selection — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Summary

Remove hardcoded default model from config and code. Replace the static 3-model dropdown with dynamic discovery from provider APIs (OpenAI, Anthropic, OpenRouter, Google) based on which API keys are set. UI becomes a searchable grouped dropdown with localStorage-remembered last selection.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Default behavior | Dynamic discovery from provider APIs | No stale hardcoded lists |
| Provider coverage | Only providers with API keys set | Hide models the user can't use |
| Refresh strategy | TTL cache (1 hour) server-side | Balance freshness and API quota |
| UI pattern | Grouped searchable dropdown | Standard UX for 300+ OpenRouter models |
| First-run behavior | localStorage last-used + required selection | No hardcoded defaults, returning users pre-filled |

## Backend

### New module: `src/desmet/webui/model_discovery.py`

```python
def fetch_openai_models() -> list[str]: ...
def fetch_anthropic_models() -> list[str]: ...
def fetch_openrouter_models() -> list[str]: ...
def fetch_google_models() -> list[str]: ...
def get_available_models() -> dict[str, list[str]]: ...  # provider → models
```

- `httpx.Client` with 10s timeout
- TTL cache (in-process dict, 1 hour)
- Graceful per-provider fallback: any HTTP error → empty list for that provider
- Only queries providers whose API key env var is set
- Returns `{"openai": [...], "anthropic": [...], "openrouter": [...], "google": [...]}`
- Missing providers (no API key) omitted from the result

### `/api/config` endpoint changes

```python
{
    "model": llm.model,  # empty string if not configured
    "available_models": {"openai": [...], "anthropic": [...], ...},  # grouped by provider
    # remove: "allow_custom_model" (still allow via combobox free-text)
    ...
}
```

### `llm_config.py` changes

- Delete `DEFAULT_MODEL = "gpt-5.4-2026-03-05"` constant
- `get_config()` returns `LLMConfig(model="")` when no model is explicitly provided and `DESMET_MODEL` env var is unset (no crash, but empty)
- Adapters validate `cfg.model` at `initialize()` time and raise clear error if empty

### `harness/loader.py` changes

- Remove `"default_model": "gpt-5.4-2026-03-05"` fallback
- When nothing is configured, leave model empty; the runner passes the RunRequest-supplied model through

### `config/platforms.yaml` changes

- Remove `default_model: gpt-5.4-2026-03-05` line

## Frontend

### `api.ts` type changes

```typescript
export interface AppConfig {
  model: string;  // "" if not configured
  provider: string;
  api_keys_set: string[];
  // ...
  available_models: Record<string, string[]>;  // provider → list
  // remove: allow_custom_model (always allowed now via combobox)
}
```

### New component: `ModelPicker.svelte`

A lightweight searchable grouped combobox.

**Props:**
- `models: Record<string, string[]>` — provider groups
- `value: string` — bound selected model
- `placeholder?: string`

**Behavior:**
- Text input at the top acts as both filter and free-text entry (for custom models)
- Clicking the input opens a dropdown showing groups
- Typing filters visible options across all groups (case-insensitive substring)
- Each group has a header (`OpenAI`, `Anthropic`, etc.)
- Clicking an option selects it and closes the dropdown
- Pressing Enter commits the current text as a custom model
- Keyboard nav: ArrowUp/ArrowDown through visible options, Esc to close

### `NewRun.svelte` changes

- Replace the native `<select>` model dropdown with `<ModelPicker>`
- Initialize `model` state from `localStorage.getItem('desmet:last-model') || ''`
- On successful submit, save the final selected model to localStorage
- Disable the Start button when `model === ''` (replaces the current "always default" behavior)

## File Inventory

| File | Change |
|---|---|
| `src/desmet/webui/model_discovery.py` | **New** — provider API clients + TTL cache |
| `tests/test_model_discovery.py` | **New** — mock HTTP tests |
| `src/desmet/webui/api.py` | `/api/config` returns grouped `available_models`, removes hardcoded list |
| `src/desmet/llm_config.py` | Remove `DEFAULT_MODEL`, return empty model when unset |
| `src/desmet/harness/loader.py` | Remove `default_model` fallback |
| `config/platforms.yaml` | Remove `default_model` field |
| `src/desmet/webui/frontend/src/lib/api.ts` | `available_models: Record<string, string[]>` |
| `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte` | Use ModelPicker, localStorage persistence, disable submit without model |
| `src/desmet/webui/frontend/src/lib/components/ModelPicker.svelte` | **New** — searchable grouped combobox |
| `tests/test_llm_config.py` | Test `get_config()` returns empty model when unset |

## Breaking Changes

- **`DEFAULT_MODEL` removed** — callers of `get_config()` without a model argument and without `DESMET_MODEL` env var will get `LLMConfig(model="")`. Previously they got `"gpt-5.4-2026-03-05"`.
- **`allow_custom_model` field removed** from `/api/config` — combobox always allows custom text.
- **`available_models` shape change** — was `list[str]`, now `dict[str, list[str]]`. Frontend must be updated in lockstep.

## Testing

- **`test_model_discovery.py`** — mock `httpx` responses for each provider, verify parsing, TTL cache behavior, graceful fallback on 401/timeout
- **`test_llm_config.py`** — verify `get_config()` returns empty model when nothing is set, honours explicit model and env var
- **Manual:** verify frontend builds, dropdown populates from real API call (with test API key), localStorage persistence works
