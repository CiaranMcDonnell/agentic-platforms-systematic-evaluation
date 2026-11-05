"""Queue one evaluation run per model through the DESMET webui API, sequentially."""

import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8042"
MODELS = sys.argv[1:] or ["anthropic/claude-sonnet-5.5", "openai/gpt-5.6-terra", "z-ai/glm-5.3"]
PLATFORMS = [
    "langgraph",
    "crewai",
    "microsoft_agent_framework",
    "openai_agents_sdk",
    "google_adk",
]


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


for _ in range(60):
    try:
        call("/api/runs")
        break
    except Exception:
        time.sleep(2)
else:
    sys.exit("webui never came up")

for model in MODELS:
    resp = call(
        "/api/runs/start",
        {
            "platforms": PLATFORMS,
            "stories": os.environ.get("STORIES", "US-001").split(","),
            "model": model,
            "repeats": int(os.environ.get("REPEATS", "3")),
            "deploy_mode": os.environ.get("DEPLOY_MODE", "remote"),
        },
    )
    # A run already in flight for this model (e.g. watcher restarted): follow it.
    run_id = resp.get("run_id") or resp.get("active_run_id")
    if not run_id:
        sys.exit(f"start failed for {model}: {resp}")
    print(f"=== {model}: run {run_id} started", flush=True)

    seen = 0
    while True:
        time.sleep(20)
        st = call(f"/api/runs/{run_id}")
        logs = st["logs"]
        # logs is the last 200 lines; print only new ones
        new = logs[seen:] if seen <= len(logs) else logs
        for line in new:
            print(f"[{model}] {line}", flush=True)
        seen = len(logs)
        if st["status"] not in ("pending", "running"):
            print(f"=== {model}: run {run_id} {st['status']} error={st['error']}", flush=True)
            break
