# Deploy Mode Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deploy mode selector to the NewRun page so users can choose between local Docker deployment and remote server deployment.

**Architecture:** The `deploy_mode` field flows from the UI through `RunConfig` → `RunnerConfig` → `StageContext.metadata` → `DESMET_DEPLOY_MODE` env var → `_deploy_remote` tool which routes internally between local docker compose and SSH-based remote deployment.

**Tech Stack:** Svelte 5 (runes), FastAPI (Pydantic), Python subprocess

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/adapters/_tools.py` | Modify | Add local deploy routing in `_deploy_remote` |
| `src/desmet/harness/runner.py` | Modify | Add `deploy_mode` to `RunnerConfig`, set env var |
| `src/desmet/webui/api.py` | Modify | Add `deploy_mode` to `RunRequest`, pass to runner |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | Add `deploy_mode` to `RunConfig` type |
| `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte` | Modify | Add deploy target selector UI |
| `tests/test_deploy_remote.py` | Modify | Add tests for local deploy mode |

---

### Task 1: Local deploy routing in `_deploy_remote`

**Files:**
- Modify: `src/desmet/adapters/_tools.py:395-530`
- Test: `tests/test_deploy_remote.py`

- [ ] **Step 1: Write failing tests for local deploy mode**

Append to `tests/test_deploy_remote.py`:

```python
class TestLocalDeployMode:
    """Tests for deploy_mode=local routing."""

    def test_local_push_is_noop(self, tmp_path):
        with patch.dict(os.environ, {"DESMET_DEPLOY_MODE": "local"}):
            result = _deploy_remote(
                workspace=tmp_path,
                platform_id="crewai",
                story_id="US-001",
                action="push",
            )
            assert "local" in result.lower() or "available" in result.lower()

    def test_local_restart_calls_docker_compose(self, tmp_path):
        with patch.dict(os.environ, {"DESMET_DEPLOY_MODE": "local"}), \
             patch("desmet.adapters._tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="started", stderr="", returncode=0)
            result = _deploy_remote(
                workspace=tmp_path,
                platform_id="crewai",
                story_id="US-001",
                action="restart",
            )
            assert mock_run.called
            cmd_str = str(mock_run.call_args)
            assert "docker" in cmd_str or "compose" in cmd_str

    def test_local_health_check_curls_localhost(self, tmp_path):
        with patch.dict(os.environ, {"DESMET_DEPLOY_MODE": "local"}), \
             patch("desmet.adapters._tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout='{"status":"ok"}', stderr="", returncode=0)
            result = _deploy_remote(
                workspace=tmp_path,
                platform_id="crewai",
                story_id="US-001",
                action="health_check",
            )
            assert mock_run.called
            port = _deploy_port("crewai", "US-001")
            cmd_str = str(mock_run.call_args)
            assert str(port) in cmd_str
            assert "localhost" in cmd_str or "127.0.0.1" in cmd_str

    def test_local_invalid_action_returns_error(self, tmp_path):
        with patch.dict(os.environ, {"DESMET_DEPLOY_MODE": "local"}):
            result = _deploy_remote(
                workspace=tmp_path,
                platform_id="crewai",
                story_id="US-001",
                action="destroy",
            )
            assert "Error" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_deploy_remote.py::TestLocalDeployMode -v`
Expected: FAIL — local mode not implemented yet

- [ ] **Step 3: Implement local deploy routing**

In `src/desmet/adapters/_tools.py`, modify `_deploy_remote` (around line 395). Add the local mode check at the top of the function, before the existing remote logic:

After the function signature and before `host = os.environ.get("DEPLOY_HOST")`, add:

```python
    # ── Local deploy mode ──────────────────────────────────────────────
    deploy_mode = os.environ.get("DESMET_DEPLOY_MODE", "remote")
    if deploy_mode == "local":
        return _deploy_local(workspace, platform_id, story_id, action, url)
```

Then add the `_deploy_local` function before `_deploy_remote`:

```python
def _deploy_local(
    workspace: Path,
    platform_id: str,
    story_id: str,
    action: str,
    url: str = "/health",
) -> str:
    """Execute a local deploy operation via Docker Compose."""
    port = _deploy_port(platform_id, story_id)

    if action == "push":
        return "Local mode — workspace is already available, no push needed."

    if action == "restart":
        compose_project = f"{platform_id}-{story_id}".lower()
        env_file = workspace / ".env"
        existing = env_file.read_text() if env_file.exists() else ""
        lines = [
            ln for ln in existing.splitlines()
            if not ln.startswith("COMPOSE_PROJECT_NAME=")
            and not ln.startswith("PORT=")
        ]
        lines.append(f"COMPOSE_PROJECT_NAME={compose_project}")
        lines.append(f"PORT={port}")
        env_file.write_text("\n".join(lines) + "\n")

        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                return f"Error: docker compose failed: {output}"
            return output if output else "Started successfully"
        except subprocess.TimeoutExpired:
            return "Error: docker compose timed out"
        except FileNotFoundError:
            return "Error: docker command not found"
        except Exception as exc:
            return f"Error: {exc}"

    if action == "health_check":
        try:
            result = subprocess.run(
                ["curl", "-sf", f"http://localhost:{port}{url}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"Health check failed (exit {result.returncode}): {result.stderr}"
            return result.stdout if result.stdout else "OK"
        except subprocess.TimeoutExpired:
            return "Error: health check timed out"
        except FileNotFoundError:
            return "Error: curl command not found"
        except Exception as exc:
            return f"Error: {exc}"

    return f"Error: unknown action '{action}'. Valid: push, restart, health_check"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_deploy_remote.py -v`
Expected: All tests PASS (existing + new local mode tests)

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_tools.py tests/test_deploy_remote.py
git commit -m "feat: add local deploy mode routing in _deploy_remote"
```

---

### Task 2: RunnerConfig and StageContext wiring

**Files:**
- Modify: `src/desmet/harness/runner.py:66-96` (RunnerConfig) and `runner.py:468-472` (deploy stage section)

- [ ] **Step 1: Add deploy_mode to RunnerConfig**

In `src/desmet/harness/runner.py`, add to the `RunnerConfig` dataclass (after `verbose`):

```python
    deploy_mode: str = "local"  # "local" or "remote"
```

- [ ] **Step 2: Set DESMET_DEPLOY_MODE env var before deploy stage**

In the stage execution loop (around line 468), where `deploy_remote` is added to allowed tools, also set the env var. Change:

```python
                    # Grant access to deploy_remote tool for the deploy stage
                    if stage_key == "deploy" and "deploy_remote" not in stage_ctx.allowed_tools:
                        stage_ctx.allowed_tools.append("deploy_remote")
```

To:

```python
                    # Grant access to deploy_remote tool for the deploy stage
                    if stage_key == "deploy" and "deploy_remote" not in stage_ctx.allowed_tools:
                        stage_ctx.allowed_tools.append("deploy_remote")
                    if stage_key == "deploy":
                        os.environ["DESMET_DEPLOY_MODE"] = self.config.deploy_mode
```

- [ ] **Step 3: Commit**

```bash
git add src/desmet/harness/runner.py
git commit -m "feat: add deploy_mode to RunnerConfig and set env var for deploy stage"
```

---

### Task 3: Backend API — RunRequest

**Files:**
- Modify: `src/desmet/webui/api.py:244-252` (RunRequest) and `api.py:778` (config creation)

- [ ] **Step 1: Add deploy_mode to RunRequest**

In `src/desmet/webui/api.py`, add to the `RunRequest` model (after `repeats`):

```python
    deploy_mode: str = "local"
```

- [ ] **Step 2: Pass deploy_mode to RunnerConfig**

In the `start_run` function (around line 778), after `config = RunnerConfig(...)`, add:

```python
        config.deploy_mode = req.deploy_mode
```

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat: add deploy_mode to RunRequest and pass to RunnerConfig"
```

---

### Task 4: Frontend — API type and NewRun UI

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts:54-61` (RunConfig)
- Modify: `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte`

- [ ] **Step 1: Add deploy_mode to RunConfig type**

In `src/desmet/webui/frontend/src/lib/api.ts`, add to the `RunConfig` interface (after `model`):

```typescript
  deploy_mode?: string;
```

- [ ] **Step 2: Add deploy mode state and UI to NewRun.svelte**

In the `<script>` block, add after `let dryRun = $state(false);`:

```typescript
  let deployMode = $state<'local' | 'remote'>('local');
  let deployConfigured = $derived(store.config?.deploy_status === 'configured');
```

In the `submit()` function, add `deploy_mode` to the `startRun` call. Change:

```typescript
      const res = await startRun({
        platforms: selectedPlatforms,
        stories: selectedStories,
        difficulties: selectedDifficulties,
        stages: selectedStages,
        model: (model === '__custom__' ? customModel : model) || null,
        dry_run: dryRun,
      });
```

To:

```typescript
      const res = await startRun({
        platforms: selectedPlatforms,
        stories: selectedStories,
        difficulties: selectedDifficulties,
        stages: selectedStages,
        model: (model === '__custom__' ? customModel : model) || null,
        dry_run: dryRun,
        deploy_mode: deployMode,
      });
```

- [ ] **Step 3: Add the deploy target selector to the template**

Find the dry run toggle in the template (search for `dryRun`). Add the deploy mode selector right before or after it. The exact location depends on the current layout — look for the options section. Add:

```svelte
    <div class="option-group">
      <span class="option-label">Deploy Target</span>
      <div class="segmented">
        <button
          class="seg-btn"
          class:active={deployMode === 'local'}
          onclick={() => deployMode = 'local'}
        >Local (Docker)</button>
        <button
          class="seg-btn"
          class:active={deployMode === 'remote'}
          disabled={!deployConfigured}
          title={!deployConfigured ? 'Configure DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY_PATH, DEPLOY_REPO env vars to enable' : ''}
          onclick={() => deployMode = 'remote'}
        >Remote Server</button>
      </div>
    </div>
```

- [ ] **Step 4: Add styles for the segmented control**

Add to the `<style>` block at the bottom of NewRun.svelte:

```css
  .segmented {
    display: flex;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .seg-btn {
    padding: 6px 14px;
    border: none;
    background: var(--bg-secondary);
    color: var(--fg);
    cursor: pointer;
    font-size: 13px;
    transition: background 0.15s, color 0.15s;
  }
  .seg-btn:not(:last-child) {
    border-right: 1px solid var(--border);
  }
  .seg-btn.active {
    background: var(--accent);
    color: var(--bg);
    font-weight: 600;
  }
  .seg-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
```

- [ ] **Step 5: Build frontend to verify**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts src/desmet/webui/frontend/src/lib/pages/NewRun.svelte
git commit -m "feat(webui): add deploy target selector to NewRun page"
```

---

### Task 5: Full integration test

**Files:**
- Test: `tests/test_deploy_remote.py`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ --timeout=60 -q`
Expected: 632+ passed, 24 skipped, 0 failed

- [ ] **Step 2: Verify default behavior unchanged**

Run: `uv run python -c "from desmet.harness.runner import RunnerConfig; c = RunnerConfig(); print(f'deploy_mode={c.deploy_mode}')"`
Expected: `deploy_mode=local`

- [ ] **Step 3: Commit (if any final fixes needed)**

```bash
git commit -m "test: verify deploy mode integration"
```
