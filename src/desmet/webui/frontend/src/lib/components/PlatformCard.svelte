<script lang="ts">
    import { onDestroy } from "svelte";
    import StatusBadge from "./StatusBadge.svelte";
    import type { Platform, ImageDetail, ImageBuildMessage } from "../api";
    import { deleteImage, connectImageBuild } from "../api";
    import {
        refreshPlatformStatuses,
        refreshImageDetails,
    } from "../data.svelte";

    let {
        platform,
        imageDetail,
        onDockerAction,
        onBuildImage,
    }: {
        platform: Platform;
        imageDetail: ImageDetail | undefined;
        onDockerAction: (
            action: string,
            target: string,
        ) => Promise<{ success: boolean; message?: string }>;
        onBuildImage: (
            platformId: string,
        ) => Promise<{ success: boolean; message?: string }>;
    } = $props();

    let isDocker = $derived(platform.infra_type === "Docker");
    let isSDK = $derived(
        platform.infra_type === "Docker (isolated)" ||
            platform.infra_type === "Python SDK",
    );
    let isUp = $derived(platform.status === "ready");
    let needsBuild = $derived(platform.status === "not built");

    let expanded = $state(false);
    let actionState = $state<
        | "idle"
        | "starting"
        | "stopping"
        | "building"
        | "deleting"
        | "success"
        | "error"
    >("idle");
    let errorMsg = $state("");
    let buildLogs = $state<string[]>([]);
    let buildWs: WebSocket | null = $state(null);

    function formatSize(bytes: number): string {
        if (bytes === 0) return "";
        const gb = bytes / 1e9;
        return gb >= 1
            ? `${gb.toFixed(1)} GB`
            : `${(bytes / 1e6).toFixed(0)} MB`;
    }

    function formatAge(iso: string): string {
        if (!iso) return "";
        const diff = Date.now() - new Date(iso).getTime();
        const hours = Math.floor(diff / 3600000);
        if (hours < 1) return "just now";
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    }

    let sizeText = $derived(
        imageDetail?.exists ? formatSize(imageDetail.size_bytes) : "",
    );
    let ageText = $derived(
        imageDetail?.exists ? formatAge(imageDetail.created_at) : "",
    );
    let summaryText = $derived(
        sizeText && ageText
            ? `${sizeText}  ·  built ${ageText}`
            : sizeText
              ? sizeText
              : ageText
                ? `built ${ageText}`
                : "",
    );

    async function handleDockerAction(action: string) {
        actionState = action === "up" ? "starting" : "stopping";
        errorMsg = "";
        try {
            const res = await onDockerAction(action, platform.id);
            if (res && !res.success) {
                actionState = "error";
                errorMsg =
                    res.message ||
                    `Failed to ${action === "up" ? "start" : "stop"}`;
            } else {
                actionState = "success";
                setTimeout(() => {
                    if (actionState === "success") actionState = "idle";
                }, 3000);
            }
        } catch (err: any) {
            actionState = "error";
            errorMsg = err?.message || "Unexpected error";
        }
    }

    function handleBuildStreaming() {
        actionState = "building";
        errorMsg = "";
        buildLogs = [];

        buildWs = connectImageBuild([platform.id], (msg: ImageBuildMessage) => {
            if (msg.line) {
                buildLogs = [...buildLogs, msg.line];
            }
            if (msg.status === "built") {
                actionState = "success";
                setTimeout(() => {
                    if (actionState === "success") actionState = "idle";
                }, 3000);
                refreshPlatformStatuses();
                refreshImageDetails();
            } else if (msg.status === "failed") {
                actionState = "error";
                errorMsg = msg.error || "Build failed";
                refreshPlatformStatuses();
            }
            if (msg.done) {
                buildWs?.close();
                buildWs = null;
            }
        });
    }

    async function handleDelete() {
        if (!confirm(`Delete Docker image for ${platform.name}?`)) return;
        actionState = "deleting";
        errorMsg = "";
        try {
            const res = await deleteImage(platform.id);
            if (res.success) {
                actionState = "success";
                setTimeout(() => {
                    if (actionState === "success") actionState = "idle";
                }, 3000);
                await Promise.all([
                    refreshPlatformStatuses(),
                    refreshImageDetails(),
                ]);
            } else {
                actionState = "error";
                errorMsg = res.message || "Delete failed";
            }
        } catch (err: any) {
            actionState = "error";
            errorMsg = err?.message || "Delete failed";
        }
    }

    async function handleRebuild() {
        actionState = "deleting";
        try {
            await deleteImage(platform.id);
        } catch {
            /* continue anyway */
        }
        handleBuildStreaming();
    }

    let busy = $derived(
        ["starting", "stopping", "building", "deleting"].includes(actionState),
    );

    onDestroy(() => {
        buildWs?.close();
        buildWs = null;
    });
</script>

<div class="card" class:expanded>
    <div
        class="card-header"
        onclick={() => (expanded = !expanded)}
        role="button"
        tabindex="0"
        onkeydown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                expanded = !expanded;
            }
        }}
    >
        <div style="flex: 1; min-width: 0;">
            <div
                style="display: flex; justify-content: space-between; align-items: flex-start;"
            >
                <div>
                    <h3 style="margin: 0; font-weight: 500; font-size: 14px;">
                        {platform.name}
                    </h3>
                    <p
                        style="margin: 4px 0 0; font-size: 12px; color: var(--text-2);"
                    >
                        {platform.category}
                    </p>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <StatusBadge status={platform.status} />
                    <span class="chevron" class:open={expanded}>&#9662;</span>
                </div>
            </div>

            <div
                style="margin-top: 10px; display: flex; gap: 8px; align-items: center;"
            >
                {#if platform.implemented}
                    <span class="badge badge-green">Adapter Ready</span>
                {:else}
                    <span class="badge badge-gray">Stub</span>
                {/if}
                <span style="font-size: 11px; color: var(--text-2);"
                    >{platform.infra_type}</span
                >
                {#if summaryText}
                    <span style="font-size: 11px; color: var(--text-2);"
                        >· {summaryText}</span
                    >
                {/if}
            </div>
        </div>
    </div>

    {#if expanded}
        <div class="card-body">
            {#if isSDK && imageDetail?.exists}
                <div class="detail-row">
                    <span class="detail-label">Image</span>
                    <span class="detail-value mono">{imageDetail.tag}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Size</span>
                    <span class="detail-value"
                        >{formatSize(imageDetail.size_bytes)}</span
                    >
                </div>
                <div class="detail-row">
                    <span class="detail-label">Built</span>
                    <span class="detail-value"
                        >{new Date(
                            imageDetail.created_at,
                        ).toLocaleString()}</span
                    >
                </div>
            {/if}

            <div
                style="margin-top: 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;"
            >
                {#if isDocker}
                    {#if actionState === "starting"}
                        <button class="btn btn-outline btn-sm" disabled
                            ><span class="spinner"></span> Starting…</button
                        >
                    {:else if actionState === "stopping"}
                        <button class="btn btn-danger btn-sm" disabled
                            ><span class="spinner"></span> Stopping…</button
                        >
                    {:else if !isUp}
                        <button
                            class="btn btn-outline btn-sm"
                            onclick={() => handleDockerAction("up")}
                            >Start</button
                        >
                    {:else}
                        <button
                            class="btn btn-danger btn-sm"
                            onclick={() => handleDockerAction("down")}
                            >Stop</button
                        >
                    {/if}
                {:else if isSDK}
                    {#if actionState === "building"}
                        <button class="btn btn-outline btn-sm" disabled
                            ><span class="spinner"></span> Building…</button
                        >
                    {:else if actionState === "deleting"}
                        <button class="btn btn-outline btn-sm" disabled
                            ><span class="spinner"></span> Deleting…</button
                        >
                    {:else if needsBuild}
                        <button
                            class="btn btn-outline btn-sm"
                            onclick={handleBuildStreaming}>Build Image</button
                        >
                    {:else}
                        <button
                            class="btn btn-outline btn-sm"
                            onclick={handleRebuild}>Rebuild Image</button
                        >
                        <button
                            class="btn btn-danger btn-sm"
                            onclick={handleDelete}>Delete Image</button
                        >
                    {/if}
                {/if}

                {#if actionState === "success"}
                    <span style="font-size: 12px; color: var(--green);"
                        >&#10003; Done</span
                    >
                {/if}
            </div>

            {#if actionState === "error"}
                <div class="error-box">
                    {errorMsg}
                    <button
                        class="error-dismiss"
                        onclick={() => {
                            actionState = "idle";
                            errorMsg = "";
                        }}>dismiss</button
                    >
                </div>
            {/if}

            {#if buildLogs.length > 0}
                <div class="build-log">
                    <div
                        class="build-log-header"
                        onclick={() => (buildLogs = [])}
                    >
                        <span>Build Log ({buildLogs.length} lines)</span>
                        <span
                            style="font-size: 11px; cursor: pointer; color: var(--text-2);"
                            >clear</span
                        >
                    </div>
                    <div class="build-log-body">
                        {#each buildLogs as line}
                            <div class="log-line">{line}</div>
                        {/each}
                    </div>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .card {
        cursor: default;
    }
    .card-header {
        cursor: pointer;
    }
    .card-body {
        border-top: 1px solid var(--border);
        padding-top: 14px;
        margin-top: 14px;
    }
    .chevron {
        font-size: 12px;
        color: var(--text-2);
        transition: transform 0.2s;
        display: inline-block;
    }
    .chevron.open {
        transform: rotate(180deg);
    }

    .detail-row {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        padding: 3px 0;
    }
    .detail-label {
        color: var(--text-2);
    }
    .detail-value {
        color: var(--text-1);
    }

    .error-box {
        margin-top: 8px;
        padding: 8px 10px;
        border-radius: 6px;
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.25);
        font-size: 12px;
        color: #ef4444;
        max-width: 100%;
        max-height: 180px;
        overflow-y: auto;
        overflow-x: hidden;
        overflow-wrap: break-word;
        word-break: break-word;
        white-space: pre-wrap;
        line-height: 1.5;
    }
    .error-dismiss {
        background: none;
        border: none;
        color: #ef4444;
        text-decoration: underline;
        cursor: pointer;
        font-size: 12px;
        padding: 0;
        margin-left: 8px;
    }

    .build-log {
        margin-top: 12px;
        border: 1px solid var(--border);
        border-radius: 6px;
        overflow: hidden;
    }
    .build-log-header {
        padding: 8px 12px;
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--bg-1);
        font-size: 11px;
        font-weight: 500;
        color: var(--text-1);
    }
    .build-log-body {
        background: var(--bg-0);
        padding: 8px 12px;
        font-family: var(--mono);
        font-size: 11px;
        line-height: 1.6;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-all;
    }
    .log-line {
        color: var(--text-2);
        padding: 1px 0;
    }

    .spinner {
        display: inline-block;
        width: 12px;
        height: 12px;
        border: 2px solid currentColor;
        border-right-color: transparent;
        border-radius: 50%;
        animation: spin 0.6s linear infinite;
        vertical-align: middle;
        margin-right: 4px;
    }
</style>
