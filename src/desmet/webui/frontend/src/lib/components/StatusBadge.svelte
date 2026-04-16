<script lang="ts">
    let { status }: { status: string } = $props();

    const classMap: Record<string, string> = {
        ready: "badge-green",
        running: "badge-green",
        implemented: "badge-green",
        "not started": "badge-yellow",
        "not built": "badge-yellow",
        "not installed": "badge-gray",
        stub: "badge-gray",
        exited: "badge-red",
        "docker not found": "badge-red",
        failed: "badge-red",
        completed: "badge-green",
        pending: "badge-blue",
        cancelled: "badge-yellow",
    };

    const dotColors: Record<string, string> = {
        "badge-green": "#3ecf8e",
        "badge-yellow": "#f5a623",
        "badge-red": "#ff4444",
        "badge-blue": "#666",
        "badge-gray": "#444",
    };

    let cls = $derived(classMap[status] || "badge-gray");
    let dotColor = $derived(dotColors[cls] || "#444");
</script>

<span class="badge {cls}">
    <svg width="6" height="6" viewBox="0 0 6 6"
        ><circle cx="3" cy="3" r="3" fill={dotColor} /></svg
    >
    {status}
</span>
