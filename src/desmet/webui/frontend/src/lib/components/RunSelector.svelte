<script lang="ts">
    import { onMount } from "svelte";
    import { selectedResultsRunId } from "../stores";
    import { fetchResultRuns } from "../api";
    import type { ResultRun } from "../api";

    let runs = $state<ResultRun[]>([]);
    let selected = $state<string>("latest");

    selectedResultsRunId.subscribe((v) => {
        selected = v ?? "latest";
    });

    onMount(async () => {
        try {
            const res = await fetchResultRuns();
            runs = res.runs;
        } catch {
            runs = [];
        }
    });

    function onChange(e: Event) {
        const val = (e.target as HTMLSelectElement).value;
        selectedResultsRunId.set(val === "latest" ? null : val);
    }

    function formatDate(iso: string | null): string {
        if (!iso) return "";
        const d = new Date(iso);
        return (
            d.toLocaleDateString() +
            " " +
            d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        );
    }
</script>

{#if runs.length > 0}
    <div class="run-selector">
        <label for="run-select">Run:</label>
        <select id="run-select" value={selected} onchange={onChange}>
            <option value="latest">Latest</option>
            {#each runs as run}
                <option value={run.run_id}>
                    {formatDate(run.started_at)}{run.model
                        ? ` · ${run.model}`
                        : ""}{run.note ? ` — ${run.note}` : ""}
                </option>
            {/each}
        </select>
    </div>
{/if}

<style>
    .run-selector {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: var(--text-1);
    }

    label {
        font-weight: 500;
        color: var(--text-2);
    }

    select {
        background: var(--bg-1);
        color: var(--text-0);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 13px;
        cursor: pointer;
        min-width: 200px;
    }

    select:hover {
        border-color: var(--text-2);
    }
</style>
