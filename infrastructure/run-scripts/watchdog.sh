#!/usr/bin/env bash
# Exit (waking Claude) on the first anomaly or when a model's run finishes.
# Reads the webui server log directly (the /api/runs logs endpoint is capped
# at 200 lines, so it can't be used to detect new output).
# Usage: watchdog.sh <server-log> <queue-output> <server-start-line> <queue-start-line>
SERVER_LOG="$1"
QUEUE_OUT="$2"
SERVER_START="${3:-0}"
QUEUE_START="${4:-0}"
ENV_FILE="C:/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/.env"
KEY=$(grep -E "^OPENROUTER_API_KEY=" "$ENV_FILE" | cut -d= -f2- | tr -d '"\r')
SPEND_LIMIT=60
STALL_SECS=900

# Server log lines that mean real activity (excludes our own API polling).
activity() { tail -n +"$((SERVER_START + 1))" "$SERVER_LOG" | grep -av "GET /api" | wc -l; }

last_activity=$(activity)
last_change=$(date +%s)

while true; do
  sleep 30
  server_new=$(tail -n +"$((SERVER_START + 1))" "$SERVER_LOG")
  queue_new=$(tail -n +"$((QUEUE_START + 1))" "$QUEUE_OUT")

  if echo "$server_new" | grep -aqE "_completed .*success=False|Traceback|\[error"; then
    echo "ANOMALY: stage failure or error in server log"
    echo "$server_new" | grep -aE "_completed .*success=False|Traceback|\[error" | tail -5
    echo "server line $(wc -l < "$SERVER_LOG") queue line $(wc -l < "$QUEUE_OUT")"
    exit 0
  fi

  if echo "$queue_new" | grep -qE "=== .*: run [0-9a-f]+ (completed|failed|cancelled)|Traceback|start failed"; then
    echo "QUEUE EVENT:"
    echo "$queue_new" | grep -E "=== .*: run [0-9a-f]+ (completed|failed|cancelled)|Traceback|start failed"
    echo "server line $(wc -l < "$SERVER_LOG") queue line $(wc -l < "$QUEUE_OUT")"
    exit 0
  fi

  now=$(date +%s)
  current=$(activity)
  if [ "$current" != "$last_activity" ]; then
    last_activity=$current; last_change=$now
  elif [ $((now - last_change)) -gt $STALL_SECS ]; then
    echo "ANOMALY: no server activity for $((STALL_SECS / 60)) minutes"
    tail -n +"$((SERVER_START + 1))" "$SERVER_LOG" | grep -av "GET /api" | tail -5
    echo "server line $(wc -l < "$SERVER_LOG") queue line $(wc -l < "$QUEUE_OUT")"
    exit 0
  fi

  usage=$(curl -s -H "Authorization: Bearer $KEY" https://openrouter.ai/api/v1/key \
    | grep -oE '"usage":[0-9.]+' | cut -d: -f2)
  if [ -n "$usage" ] && awk "BEGIN{exit !($usage > $SPEND_LIMIT)}"; then
    echo "ANOMALY: OpenRouter spend \$$usage exceeds \$$SPEND_LIMIT"
    exit 0
  fi
done
