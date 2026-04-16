<script lang="ts">
    import type { LangfuseTraceDetail, LangfuseObservation } from "../api";
    import { formatContent } from "../format";

    interface Props {
        traceData: LangfuseTraceDetail;
    }
    let { traceData }: Props = $props();

    interface FlatMsg {
        id: string;
        name: string;
        type: string;
        level: string;
        start_time: string | null;
        input: string | null | undefined;
        output: string | null | undefined;
        tokens: { input: number; output: number; total: number };
        model: string | null | undefined;
        duration_ms: number;
    }

    function flatten(obs: LangfuseObservation[]): FlatMsg[] {
        const out: FlatMsg[] = [];
        for (const o of obs) {
            if (o.input || o.output) {
                out.push({
                    id: o.id,
                    name: o.name || "unnamed",
                    type: o.type,
                    level: o.level,
                    start_time: o.start_time,
                    input: o.input,
                    output: o.output,
                    tokens: o.tokens,
                    model: o.model,
                    duration_ms: o.latency_ms,
                });
            }
            out.push(...flatten(o.children));
        }
        return out.sort((a, b) =>
            (a.start_time ?? "") < (b.start_time ?? "") ? -1 : 1,
        );
    }

    let msgs = $derived(flatten(traceData.observations));

    // Track which cards are expanded (all collapsed by default)
    let expanded = $state<Set<string>>(new Set());
    function toggle(id: string) {
        const next = new Set(expanded);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        expanded = next;
    }
    function expandAll() {
        expanded = new Set(msgs.map((m) => m.id));
    }
    function collapseAll() {
        expanded = new Set();
    }

    function accentColor(type: string, level: string): string {
        if (level === "ERROR") return "var(--red)";
        if (type === "generation") return "#4a9eff";
        if (type === "tool") return "var(--yellow)";
        return "var(--border)";
    }

    function typeLabel(type: string): string {
        if (type === "generation") return "LLM";
        if (type === "tool") return "TOOL";
        return type.toUpperCase();
    }
</script>

<div class="mt-wrap">
    <div class="mt-controls">
        <button class="ctrl-btn" onclick={expandAll}>Expand all</button>
        <button class="ctrl-btn" onclick={collapseAll}>Collapse all</button>
        <span class="mt-count">{msgs.length} observations</span>
    </div>

    {#each msgs as msg, i (msg.id)}
        {@const isOpen = expanded.has(msg.id)}
        {@const accent = accentColor(msg.type, msg.level)}
        <div class="mt-card" style="border-left-color:{accent}">
            <button class="mt-header" onclick={() => toggle(msg.id)}>
                <span class="mt-idx">#{i + 1}</span>
                <span class="mt-badge" style="color:{accent}"
                    >{typeLabel(msg.type)}</span
                >
                <span class="mt-name">{msg.name}</span>
                {#if msg.model}
                    <span class="mt-model">{msg.model}</span>
                {/if}
                {#if msg.tokens.total > 0}
                    <span class="mt-tok"
                        >{msg.tokens.input}↑ {msg.tokens.output}↓</span
                    >
                {/if}
                <span class="mt-dur"
                    >{(msg.duration_ms / 1000).toFixed(2)}s</span
                >
                <span class="mt-chevron">{isOpen ? "▼" : "▶"}</span>
            </button>

            {#if isOpen}
                <div class="mt-body">
                    {#if msg.input}
                        <div class="io-section">
                            <div class="io-label">INPUT</div>
                            <pre class="io-pre">{formatContent(msg.input)}</pre>
                        </div>
                    {/if}
                    {#if msg.output}
                        <div class="io-section">
                            <div class="io-label">OUTPUT</div>
                            <pre class="io-pre output">{formatContent(
                                    msg.output,
                                )}</pre>
                        </div>
                    {/if}
                </div>
            {/if}
        </div>
    {/each}

    {#if msgs.length === 0}
        <div class="mt-empty">No observations with content found.</div>
    {/if}
</div>

<style>
    .mt-wrap {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .mt-controls {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }
    .ctrl-btn {
        padding: 4px 10px;
        font-size: 11px;
        border: 1px solid var(--border);
        border-radius: 4px;
        background: var(--bg-2);
        color: var(--text-1);
        cursor: pointer;
        font-family: var(--sans);
    }
    .ctrl-btn:hover {
        border-color: var(--border-hover);
        color: var(--text-0);
    }
    .mt-count {
        font-size: 11px;
        color: var(--text-2);
        margin-left: auto;
    }

    .mt-card {
        border: 1px solid var(--border);
        border-left-width: 3px;
        border-radius: 6px;
        overflow: hidden;
        background: var(--bg-1);
    }

    .mt-header {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        padding: 8px 12px;
        background: transparent;
        border: none;
        cursor: pointer;
        font-size: 12px;
        font-family: var(--sans);
        color: var(--text-1);
        text-align: left;
    }
    .mt-header:hover {
        background: var(--bg-2);
    }

    .mt-idx {
        font-size: 10px;
        color: var(--text-2);
        font-family: var(--mono);
        width: 24px;
        flex-shrink: 0;
    }
    .mt-badge {
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.06em;
        flex-shrink: 0;
        width: 44px;
    }
    .mt-name {
        font-weight: 500;
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .mt-model {
        font-size: 10px;
        color: var(--green);
        font-family: var(--mono);
        flex-shrink: 0;
    }
    .mt-tok {
        font-size: 10px;
        color: var(--yellow);
        font-family: var(--mono);
        flex-shrink: 0;
    }
    .mt-dur {
        font-size: 10px;
        color: var(--text-2);
        font-family: var(--mono);
        flex-shrink: 0;
    }
    .mt-chevron {
        font-size: 9px;
        color: var(--text-2);
        flex-shrink: 0;
    }

    .mt-body {
        border-top: 1px solid var(--border);
    }

    .io-section {
        padding: 10px 14px;
    }
    .io-section + .io-section {
        border-top: 1px solid var(--border);
    }
    .io-label {
        font-size: 9px;
        font-weight: 600;
        letter-spacing: 0.08em;
        color: var(--text-2);
        margin-bottom: 6px;
    }
    .io-pre {
        margin: 0;
        font-size: 12px;
        font-family: var(--mono);
        white-space: pre-wrap;
        word-break: break-word;
        color: var(--text-1);
        line-height: 1.5;
        max-height: 400px;
        overflow-y: auto;
        background: var(--bg-2);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 8px 10px;
    }
    .io-pre.output {
        border-color: #4a9eff44;
    }

    .mt-empty {
        padding: 24px;
        text-align: center;
        font-size: 13px;
        color: var(--text-2);
    }
</style>
