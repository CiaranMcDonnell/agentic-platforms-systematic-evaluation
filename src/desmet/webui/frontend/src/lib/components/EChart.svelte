<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import * as echarts from "echarts";
    import { fetchChartJSON } from "../api";

    let { endpoint, height = 300 }: { endpoint: string; height?: number } =
        $props();

    let container: HTMLDivElement | undefined = $state();
    let loading = $state(true);
    let errorMsg = $state("");
    let chart: echarts.ECharts | null = null;
    let resizeObserver: ResizeObserver | null = null;

    onMount(async () => {
        try {
            const data = await fetchChartJSON(endpoint);
            if (data.chart && container) {
                chart = echarts.init(container, "dark", { renderer: "canvas" });
                const option = data.chart as echarts.EChartsOption;
                chart.setOption(option);

                resizeObserver = new ResizeObserver(() => chart?.resize());
                resizeObserver.observe(container);
            }
        } catch (e) {
            console.error("Chart load error:", e);
            errorMsg = "Failed to load chart";
        }
        loading = false;
    });

    onDestroy(() => {
        resizeObserver?.disconnect();
        chart?.dispose();
    });
</script>

<div class="echart-wrap" style="height: {height}px;">
    {#if loading}
        <div class="echart-loading">Loading chart...</div>
    {:else if errorMsg}
        <div class="echart-loading" style="color: var(--red);">{errorMsg}</div>
    {/if}
    <div bind:this={container} style="width: 100%; height: 100%;"></div>
</div>

<style>
    .echart-wrap {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        width: 100%;
        min-width: 0;
        position: relative;
    }
    .echart-loading {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-2);
    }
</style>
