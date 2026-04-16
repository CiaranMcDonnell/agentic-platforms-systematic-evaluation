<script lang="ts">
    import type { TimelineEvent } from "../api";

    let {
        event,
        agentColor = "#888",
        selected = false,
        onclick,
    }: {
        event: TimelineEvent;
        agentColor?: string;
        selected?: boolean;
        onclick?: () => void;
    } = $props();

    let expanded = $state(false);
    let showFull = $state(false);

    const TYPE_COLORS: Record<string, string> = {
        llm: "#4a9eff",
        tool: "#4ade80",
        agent: "#888",
        routing: "#c084fc",
    };

    const CONTENT_TRUNCATE = 500;
    const CONTENT_EXPAND_THRESHOLD = 2000;

    function formatDuration(ms: number | null): string {
        if (ms === null) return "";
        if (ms < 1000) return `${Math.round(ms)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }

    function formatTokens(n: number | null): string {
        if (n === null) return "";
        return n.toLocaleString();
    }

    let displayContent = $derived(
        !showFull && event.content.length > CONTENT_EXPAND_THRESHOLD
            ? event.content.slice(0, CONTENT_TRUNCATE) + "..."
            : event.content,
    );
</script>

<div
    class="timeline-card"
    class:selected
    class:expanded
    style="--agent-color: {agentColor}; --type-color: {TYPE_COLORS[
        event.type
    ] ?? '#888'}"
    role="button"
    tabindex="0"
    onclick={() => {
        expanded = !expanded;
        onclick?.();
    }}
    onkeydown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
            expanded = !expanded;
            onclick?.();
        }
    }}
>
    <div class="card-color-bar"></div>
    <div class="card-body">
        <div class="card-header">
            <span class="type-badge">{event.type.toUpperCase()}</span>
            <span class="raw-type">{event.raw_type}</span>
            <span class="card-stats">
                {#if event.tokens_in !== null}
                    <span class="stat-tokens"
                        >{formatTokens(event.tokens_in)}&uarr;</span
                    >
                {/if}
                {#if event.tokens_out !== null}
                    <span class="stat-tokens"
                        >{formatTokens(event.tokens_out)}&darr;</span
                    >
                {/if}
                {#if event.tool_name}
                    <span class="stat-tool">{event.tool_name}</span>
                    {#if event.tool_success === false}
                        <span class="stat-fail">FAIL</span>
                    {/if}
                {/if}
                {#if event.duration_ms !== null}
                    <span class="stat-duration"
                        >{formatDuration(event.duration_ms)}</span
                    >
                {/if}
            </span>
        </div>
        {#if event.model}
            <div class="card-model">{event.model}</div>
        {/if}
        {#if expanded}
            <div class="card-content" class:monospace={event.type === "tool"}>
                {displayContent}
                {#if !showFull && event.content.length > CONTENT_EXPAND_THRESHOLD}
                    <button
                        class="show-full-btn"
                        onclick={(e) => {
                            e.stopPropagation();
                            showFull = true;
                        }}
                    >
                        Show full ({event.content.length.toLocaleString()} chars)
                    </button>
                {/if}
            </div>
        {/if}
    </div>
</div>

<style>
    .timeline-card {
        display: flex;
        gap: 0;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.03);
        cursor: pointer;
        transition: background 0.15s;
        overflow: hidden;
    }

    .timeline-card:hover {
        background: rgba(255, 255, 255, 0.06);
    }

    .timeline-card.selected {
        background: rgba(255, 255, 255, 0.08);
        outline: 1px solid rgba(255, 255, 255, 0.15);
    }

    .card-color-bar {
        width: 3px;
        flex-shrink: 0;
        background: var(--agent-color);
    }

    .card-body {
        flex: 1;
        padding: 8px 12px;
        min-width: 0;
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
    }

    .type-badge {
        background: color-mix(in srgb, var(--type-color) 20%, transparent);
        color: var(--type-color);
        padding: 1px 6px;
        border-radius: 3px;
        font-weight: 600;
        font-size: 10px;
        letter-spacing: 0.5px;
        flex-shrink: 0;
    }

    .raw-type {
        color: #aaa;
        font-family: monospace;
        font-size: 11px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .card-stats {
        margin-left: auto;
        display: flex;
        gap: 8px;
        flex-shrink: 0;
        font-size: 11px;
        color: #888;
    }

    .stat-tokens {
        color: #4a9eff;
    }

    .stat-tool {
        color: #4ade80;
        font-family: monospace;
    }

    .stat-fail {
        color: #ff6b6b;
        font-weight: 600;
    }

    .stat-duration {
        color: #888;
    }

    .card-model {
        font-size: 11px;
        color: #666;
        padding-top: 2px;
        font-family: monospace;
    }

    .card-content {
        margin-top: 8px;
        padding: 8px;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 4px;
        font-size: 12px;
        color: #ccc;
        line-height: 1.5;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-word;
    }

    .card-content.monospace {
        font-family: monospace;
        font-size: 11px;
    }

    .show-full-btn {
        display: block;
        margin-top: 8px;
        background: rgba(74, 158, 255, 0.15);
        color: #4a9eff;
        border: none;
        padding: 4px 8px;
        border-radius: 3px;
        font-size: 11px;
        cursor: pointer;
    }

    .show-full-btn:hover {
        background: rgba(74, 158, 255, 0.25);
    }
</style>
