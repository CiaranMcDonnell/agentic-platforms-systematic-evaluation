<script lang="ts">
    import type { LangfuseTraceDetail, LangfuseObservation } from "../api";

    interface Props {
        traceData: LangfuseTraceDetail;
    }
    let { traceData }: Props = $props();

    interface FlatSpan {
        id: string;
        name: string;
        type: string;
        level: string;
        start_rel_ms: number;
        duration_ms: number;
        tokens_total: number;
        model: string | null | undefined;
    }

    function parseMs(s: string | null | undefined): number {
        if (!s) return 0;
        return new Date(s).getTime();
    }

    function flatten(obs: LangfuseObservation[], originMs: number): FlatSpan[] {
        const out: FlatSpan[] = [];
        for (const o of obs) {
            out.push({
                id: o.id,
                name: o.name || "unnamed",
                type: o.type,
                level: o.level,
                start_rel_ms: Math.max(0, parseMs(o.start_time) - originMs),
                duration_ms: o.latency_ms,
                tokens_total: o.tokens.total,
                model: o.model,
            });
            out.push(...flatten(o.children, originMs));
        }
        return out;
    }

    function findOrigin(obs: LangfuseObservation[]): number {
        let min = Infinity;
        for (const o of obs) {
            const t = parseMs(o.start_time);
            if (t > 0 && t < min) min = t;
            const childMin = findOrigin(o.children);
            if (childMin < min) min = childMin;
        }
        return min === Infinity ? 0 : min;
    }

    let origin = $derived(
        findOrigin(traceData.observations) ||
            parseMs(traceData.trace.timestamp),
    );
    let totalMs = $derived(Math.max(traceData.trace.latency_ms, 1));
    let allSpans = $derived(
        flatten(traceData.observations, origin)
            .filter((s) => s.duration_ms >= 1)
            .sort((a, b) => a.start_rel_ms - b.start_rel_ms),
    );

    // Micro-span filter (percentage of total trace duration)
    type ThresholdPct = 0 | 0.5 | 1 | 5;
    let thresholdPct = $state<ThresholdPct>(1);
    let showMicro = $state(false);

    let microCutoffMs = $derived((thresholdPct / 100) * totalMs);
    let majorSpans = $derived(
        thresholdPct === 0
            ? allSpans
            : allSpans.filter((s) => s.duration_ms >= microCutoffMs),
    );
    let microSpans = $derived(
        thresholdPct === 0
            ? []
            : allSpans.filter((s) => s.duration_ms < microCutoffMs),
    );
    let visibleSpans = $derived(
        showMicro ? [...majorSpans, ...microSpans] : majorSpans,
    );

    function barColor(type: string, level: string): string {
        if (level === "ERROR") return "var(--red)";
        if (type === "generation") return "#4a9eff";
        if (type === "tool") return "var(--yellow)";
        return "#555";
    }

    function leftPct(rel: number): string {
        return ((rel / totalMs) * 100).toFixed(2) + "%";
    }
    function widthPct(dur: number): string {
        return Math.max(0.5, (dur / totalMs) * 100).toFixed(2) + "%";
    }

    // Adaptive time formatting: show ms for sub-second values, seconds above.
    function fmtTime(ms: number): string {
        if (ms < 1) return ms.toFixed(1) + "ms";
        if (ms < 1000) return Math.round(ms) + "ms";
        return (ms / 1000).toFixed(2) + "s";
    }
    function fmtTimeShort(ms: number): string {
        if (ms < 1000) return Math.round(ms) + "ms";
        if (ms < 10_000) return (ms / 1000).toFixed(2) + "s";
        return (ms / 1000).toFixed(1) + "s";
    }
</script>

<div class="tl-wrap">
    <!-- Controls: micro-span threshold -->
    <div class="tl-controls">
        <span class="ctrl-lbl">Hide spans under</span>
        <div class="threshold-chips">
            {#each [0, 0.5, 1, 5] as ThresholdPct[] as pct}
                <button
                    class="chip"
                    class:active={thresholdPct === pct}
                    onclick={() => (thresholdPct = pct)}
                    title={pct === 0
                        ? "Show every span"
                        : `Hide spans shorter than ${pct}% of trace (${fmtTime((pct / 100) * totalMs)})`}
                >
                    {pct === 0 ? "Off" : pct + "%"}
                </button>
            {/each}
        </div>
        {#if microSpans.length > 0}
            <button
                class="ctrl-btn"
                onclick={() => (showMicro = !showMicro)}
                title="Toggle the {microSpans.length} spans below the threshold"
            >
                {showMicro ? "Hide" : "Show"}
                {microSpans.length} micro span{microSpans.length === 1
                    ? ""
                    : "s"}
            </button>
        {/if}
        <span class="tl-count">
            {majorSpans.length} of {allSpans.length} spans
        </span>
    </div>

    <!-- Axis labels (adaptive units) -->
    <div class="tl-axis">
        <span>0</span>
        <span>{fmtTimeShort(totalMs / 2)}</span>
        <span>{fmtTimeShort(totalMs)}</span>
    </div>

    <!-- Timeline body (scrolls); grid + rows -->
    <div class="tl-body">
        <div class="tl-grid">
            <div class="grid-line" style="left:0%"></div>
            <div class="grid-line" style="left:25%"></div>
            <div class="grid-line" style="left:50%"></div>
            <div class="grid-line" style="left:75%"></div>
            <div class="grid-line" style="left:100%"></div>
        </div>

        <div class="tl-rows">
            {#each visibleSpans as s (s.id)}
                {@const isMicro =
                    thresholdPct > 0 && s.duration_ms < microCutoffMs}
                <div class="tl-row" class:tl-row-micro={isMicro}>
                    <div class="tl-label" title={s.name}>{s.name}</div>
                    <div class="tl-track">
                        <div
                            class="tl-bar"
                            style="left:{leftPct(
                                s.start_rel_ms,
                            )};width:{widthPct(
                                s.duration_ms,
                            )};background:{barColor(s.type, s.level)}"
                            title="{s.name} | {fmtTime(
                                s.duration_ms,
                            )}{s.tokens_total
                                ? ' | ' + s.tokens_total + ' tok'
                                : ''}{s.model ? ' | ' + s.model : ''}"
                        ></div>
                    </div>
                    <div class="tl-dur">
                        {fmtTime(s.duration_ms)}
                    </div>
                </div>
            {/each}
        </div>
    </div>

    <!-- Legend -->
    <div class="tl-legend">
        <span class="leg"
            ><span class="leg-dot" style="background:#4a9eff"></span>LLM</span
        >
        <span class="leg"
            ><span class="leg-dot" style="background:var(--yellow)"
            ></span>Tool</span
        >
        <span class="leg"
            ><span class="leg-dot" style="background:#555"></span>Chain</span
        >
        <span class="leg"
            ><span class="leg-dot" style="background:var(--red)"
            ></span>Error</span
        >
    </div>
</div>

<style>
    .tl-wrap {
        font-size: 12px;
        font-family: var(--sans);
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
    }
    .tl-body {
        position: relative;
        flex: 1;
        min-height: 0;
        overflow-y: auto;
    }

    /* ── Controls ──────────────────── */
    .tl-controls {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border);
        flex-wrap: wrap;
        flex-shrink: 0;
    }
    .ctrl-lbl {
        font-size: 11px;
        color: var(--text-2);
    }
    .threshold-chips {
        display: flex;
        gap: 4px;
    }
    .chip {
        padding: 3px 10px;
        font-size: 11px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: transparent;
        color: var(--text-2);
        cursor: pointer;
        font-family: var(--sans);
    }
    .chip:hover {
        color: var(--text-1);
    }
    .chip.active {
        background: var(--bg-2);
        color: var(--text-0);
        border-color: var(--text-2);
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
    .tl-count {
        font-size: 11px;
        color: var(--text-2);
        margin-left: auto;
    }

    .tl-axis {
        display: flex;
        justify-content: space-between;
        color: var(--text-2);
        font-size: 10px;
        font-family: var(--mono);
        margin-bottom: 4px;
        padding: 0 100px 0 140px;
        flex-shrink: 0;
    }

    .tl-grid {
        position: absolute;
        top: 0;
        left: 140px;
        right: 100px;
        bottom: 0;
        pointer-events: none;
    }

    .grid-line {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 1px;
        background: var(--border);
        opacity: 0.4;
        transform: translateX(-50%);
    }

    .tl-rows {
        display: flex;
        flex-direction: column;
        gap: 3px;
    }

    .tl-row {
        display: flex;
        align-items: center;
        gap: 8px;
        height: 22px;
    }
    .tl-row-micro {
        opacity: 0.55;
    }
    .tl-label {
        width: 132px;
        flex-shrink: 0;
        color: var(--text-1);
        font-size: 11px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: right;
        padding-right: 8px;
    }
    .tl-track {
        flex: 1;
        height: 14px;
        background: var(--bg-3);
        border-radius: 3px;
        position: relative;
        overflow: hidden;
    }
    .tl-bar {
        position: absolute;
        top: 0;
        height: 100%;
        border-radius: 3px;
        opacity: 0.8;
        transition: opacity 0.1s;
        cursor: default;
    }
    .tl-bar:hover {
        opacity: 1;
    }
    .tl-dur {
        width: 54px;
        flex-shrink: 0;
        font-family: var(--mono);
        font-size: 10px;
        color: var(--text-2);
        text-align: right;
    }

    .tl-legend {
        display: flex;
        gap: 16px;
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid var(--border);
        font-size: 11px;
        color: var(--text-2);
        flex-shrink: 0;
    }
    .leg {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .leg-dot {
        width: 10px;
        height: 10px;
        border-radius: 2px;
        flex-shrink: 0;
    }
</style>
