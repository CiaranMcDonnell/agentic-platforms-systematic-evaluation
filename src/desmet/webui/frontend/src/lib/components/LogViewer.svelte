<script lang="ts">
    import { tick } from "svelte";

    let { logs = [] }: { logs: string[] } = $props();
    let container: HTMLDivElement | undefined = $state();

    // Auto-scroll when logs change
    $effect(() => {
        logs.length; // track
        tick().then(() => {
            if (container) container.scrollTop = container.scrollHeight;
        });
    });

    function logClass(line: string): string {
        if (
            line.startsWith("[START]") ||
            line.startsWith("[INIT]") ||
            line.startsWith("[LOAD]") ||
            line.startsWith("[RUN]")
        )
            return "start";
        if (line.startsWith("[DONE]") || line.startsWith("[RESULTS]"))
            return "done";
        if (line.startsWith("[ERROR]")) return "error";
        if (line.startsWith("[CANCELLED]")) return "warn";
        if (line.match(/^\s{4,}step \d/)) return "progress";
        return "info";
    }
</script>

<div class="log-wrap">
    <div class="log-header">
        <span>Live Logs</span>
        <span class="mono" style="font-size: 11px; color: var(--text-2);"
            >{logs.length} lines</span
        >
    </div>
    <div class="log-body" bind:this={container}>
        {#if logs.length === 0}
            <span style="color: var(--text-2);">Waiting for logs...</span>
        {:else}
            {#each logs as line, i}
                <div class="log-line {logClass(line)}">{line}</div>
            {/each}
        {/if}
    </div>
</div>

<style>
    .log-wrap {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
    }
    .log-header {
        padding: 10px 20px;
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--bg-1);
        font-size: 12px;
        font-weight: 500;
        color: var(--text-1);
    }
    .log-body {
        background: var(--bg-0);
        padding: 16px;
        font-family: var(--mono);
        font-size: 12px;
        line-height: 1.7;
        max-height: 500px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-all;
    }
    .log-body::-webkit-scrollbar {
        width: 6px;
    }
    .log-body::-webkit-scrollbar-track {
        background: transparent;
    }
    .log-body::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 3px;
    }
    .log-line {
        padding: 1px 0;
    }
    .log-line.start {
        color: var(--text-0);
    }
    .log-line.done {
        color: var(--green);
    }
    .log-line.error {
        color: var(--red);
    }
    .log-line.warn {
        color: var(--yellow);
    }
    .log-line.info {
        color: var(--text-2);
    }
    .log-line.progress {
        color: var(--text-3, #555);
        font-size: 11px;
    }
</style>
