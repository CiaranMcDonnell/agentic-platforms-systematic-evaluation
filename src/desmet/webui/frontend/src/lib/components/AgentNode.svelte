<script lang="ts">
    import { Handle, Position } from "@xyflow/svelte";

    let {
        data,
    }: {
        data: { label: string; color: string; tokens: number; active: boolean };
    } = $props();
</script>

<div
    class="agent-node"
    class:active={data.active}
    style="--agent-color: {data.color}"
>
    <Handle type="target" position={Position.Left} />
    <div class="agent-dot"></div>
    <div class="agent-label">{data.label}</div>
    <div class="agent-tokens">{data.tokens.toLocaleString()} tok</div>
    <Handle type="source" position={Position.Right} />
</div>

<style>
    .agent-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 12px 16px;
        background: rgba(255, 255, 255, 0.06);
        border: 2px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        cursor: pointer;
        width: 120px;
        box-sizing: border-box;
        transition:
            border-color 0.2s,
            box-shadow 0.2s;
    }

    .agent-node.active {
        border-color: var(--agent-color);
        box-shadow: 0 0 16px
            color-mix(in srgb, var(--agent-color) 40%, transparent);
    }

    .agent-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--agent-color);
    }

    .agent-label {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-0);
        text-transform: capitalize;
    }

    .agent-tokens {
        font-size: 11px;
        color: var(--text-2);
    }

    :global(.svelte-flow__handle) {
        width: 6px;
        height: 6px;
        background: var(--text-3);
        border: none;
    }
</style>
