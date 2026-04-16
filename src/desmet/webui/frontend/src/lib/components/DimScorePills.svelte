<script lang="ts">
    /**
     * DimScorePills — compact colored pills for 6 rubric dimension scores.
     *
     * Each pill shows an abbreviated label (PC, TI, ER, TE, AU, TQ) and score.
     * Color encodes the score level: grey=unscored, red=0, amber=1, lime=2, green=3.
     * Tooltip shows the full dimension name and score.
     */

    const DIM_ABBR: Record<string, string> = {
        pipeline_completeness: "PC",
        tool_integration: "TI",
        error_recovery: "ER",
        time_efficiency: "TE",
        autonomy: "AU",
        trace_quality: "TQ",
    };

    const DIM_FULL: Record<string, string> = {
        pipeline_completeness: "Pipeline Completeness",
        tool_integration: "Tool Integration",
        error_recovery: "Error Recovery",
        time_efficiency: "Time Efficiency",
        autonomy: "Autonomy",
        trace_quality: "Trace Quality",
    };

    const ALL_DIMS = Object.keys(DIM_ABBR);

    interface Props {
        /** Map of dimension id → score (0–3 int or float avg, or null if unscored). */
        scores: Record<string, number | null | undefined>;
        /** Subset of dims to show. Defaults to all 6. */
        dims?: string[];
    }

    let { scores, dims = ALL_DIMS }: Props = $props();

    function pillBg(score: number | null | undefined): string {
        if (score === null || score === undefined) return "var(--bg-3)";
        if (score < 0.5) return "#ef4444";
        if (score < 1.5) return "#f59e0b";
        if (score < 2.5) return "#84cc16";
        return "#22c55e";
    }

    function pillText(score: number | null | undefined): string {
        return score === null || score === undefined ? "var(--text-2)" : "#fff";
    }

    function displayScore(score: number | null | undefined): string {
        if (score === null || score === undefined) return "—";
        // Integer scores (0/1/2/3) → no decimal; averages → 1 dp
        return Number.isInteger(score) ? String(score) : score.toFixed(1);
    }
</script>

<div class="pills">
    {#each dims as dim}
        {@const score = scores?.[dim] ?? null}
        <span
            class="pill"
            style="background:{pillBg(score)};color:{pillText(score)};"
            title="{DIM_FULL[dim] ?? dim}: {displayScore(score)}"
        >
            {DIM_ABBR[dim] ?? dim}:{displayScore(score)}
        </span>
    {/each}
</div>

<style>
    .pills {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .pill {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10px;
        font-family: var(--mono);
        font-weight: 600;
        white-space: nowrap;
        line-height: 1.6;
    }
</style>
