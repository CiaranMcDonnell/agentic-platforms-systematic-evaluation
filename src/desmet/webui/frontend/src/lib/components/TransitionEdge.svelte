<script lang="ts">
    import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/svelte";

    type TransitionData = { dots: number; sourceColor: string };
    type Props = EdgeProps & { data?: TransitionData };

    let {
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourcePosition,
        targetPosition,
        style,
        markerEnd,
        data,
    }: Props = $props();

    let pathResult = $derived(
        getBezierPath({
            sourceX,
            sourceY,
            targetX,
            targetY,
            sourcePosition,
            targetPosition,
        }),
    );

    let edgePath = $derived(pathResult[0]);
    let dots = $derived(data?.dots ?? 0);
    let dotColor = $derived(data?.sourceColor ?? "var(--text-2)");

    // Position dots evenly along the path using a hidden SVG path element
    let pathEl: SVGPathElement | undefined = $state();
    let dotPositions: { x: number; y: number }[] = $state([]);

    $effect(() => {
        if (!pathEl || dots === 0) {
            dotPositions = [];
            return;
        }
        const len = pathEl.getTotalLength();
        const positions: { x: number; y: number }[] = [];
        // Space dots evenly, with padding from endpoints
        const padding = 0.15; // 15% from each end
        const usableStart = len * padding;
        const usableEnd = len * (1 - padding);
        const usableLen = usableEnd - usableStart;

        if (dots === 1) {
            const pt = pathEl.getPointAtLength(len * 0.5);
            positions.push({ x: pt.x, y: pt.y });
        } else {
            for (let i = 0; i < dots; i++) {
                const t = usableStart + (usableLen * i) / (dots - 1);
                const pt = pathEl.getPointAtLength(t);
                positions.push({ x: pt.x, y: pt.y });
            }
        }
        dotPositions = positions;
    });
</script>

<BaseEdge path={edgePath} {style} {markerEnd} />

<!-- Hidden path element for computing dot positions -->
<path
    bind:this={pathEl}
    d={edgePath}
    fill="none"
    stroke="none"
    pointer-events="none"
/>

{#each dotPositions as pos, i}
    <circle
        cx={pos.x}
        cy={pos.y}
        r={4}
        fill={dotColor}
        opacity={0.8}
        class="transition-dot"
        style="animation-delay: {i * 50}ms"
    />
{/each}

<style>
    .transition-dot {
        animation: dot-appear 0.3s ease-out both;
    }

    @keyframes dot-appear {
        from {
            r: 0;
            opacity: 0;
        }
        to {
            r: 4;
            opacity: 0.8;
        }
    }
</style>
