# Agent Graph Layout Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop flattening the Langfuse observation tree in `AgentGraph.svelte` and use a recursive ELK builder + per-container layout strategy so agents with many tool calls render as a packed grid instead of a single tall column.

**Architecture:** Replace the flat ELK construction in the Langfuse mode of `AgentGraph.svelte` with a recursive walker that mirrors the Langfuse parent/child tree. Each compound ELK node picks `layered` DOWN (small/structured) or `rectpacking` (many leaf siblings). Inner sequential edges are emitted only for `layered` containers; cross-cluster transition edges are unchanged. Svelte Flow nodes are emitted recursively with `parentId`/`extent: 'parent'` and depth-aware styling.

**Tech Stack:** Svelte 5 (frontend), `@xyflow/svelte`, `elkjs` (already bundled), TypeScript

**Spec:** `docs/superpowers/specs/2026-04-07-agent-graph-layout-design.md`

**Test strategy:** The frontend has no automated test framework. Each task ends with a manual visual check in the dev server, plus a git commit. Steps are bite-sized so a regression is easy to bisect.

---

### Task 1: Helpers — constants, leaf walkers, layout picker

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` (add helpers in the "Langfuse layout" section, just below `flattenObservations`)

- [ ] **Step 1: Add `PACK_THRESHOLD` constant and `firstLeaf`/`lastLeaf` walkers**

In `AgentGraph.svelte`, find the `flattenObservations` function (around line 93). Add the following helpers immediately after it (still inside the `<script>` block, in the "Langfuse layout" section):

```ts
  // Threshold for switching from layered DOWN to rectpacking when a container
  // has many leaf children. Tunable.
  const PACK_THRESHOLD = 6;

  function firstLeaf(obs: LangfuseObservation): LangfuseObservation {
    let cur = obs;
    while (cur.children.length > 0) cur = cur.children[0];
    return cur;
  }

  function lastLeaf(obs: LangfuseObservation): LangfuseObservation {
    let cur = obs;
    while (cur.children.length > 0) cur = cur.children[cur.children.length - 1];
    return cur;
  }
```

- [ ] **Step 2: Add `pickLayoutOptions` helper**

Immediately after the leaf walkers from Step 1, add:

```ts
  function pickLayoutOptions(
    children: LangfuseObservation[],
    headerPad: number,
  ): Record<string, string> {
    const hasCompoundChildren = children.some(c => c.children.length > 0);
    const useLayered = hasCompoundChildren || children.length <= PACK_THRESHOLD;
    if (useLayered) {
      return {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.spacing.nodeNode': '20',
        'elk.layered.spacing.nodeNodeBetweenLayers': '30',
        'elk.padding': `[top=${headerPad},left=24,bottom=24,right=24]`,
      };
    }
    return {
      'elk.algorithm': 'rectpacking',
      'elk.aspectRatio': '1.6',
      'elk.spacing.nodeNode': '12',
      'elk.padding': `[top=${headerPad},left=24,bottom=24,right=24]`,
    };
  }
```

- [ ] **Step 3: Verify the file still compiles**

Run a Vite build to catch TypeScript/Svelte errors. The behaviour is unchanged at this point — only new helpers were added, none of them are called yet.

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: build succeeds with no new errors. Pre-existing warnings are OK; the goal is just "no new errors introduced by this task".

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "refactor(webui): add layout helpers for recursive agent graph builder"
```

---

### Task 2: Recursive ELK tree builder

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` (replace the ELK construction inside `loadLangfuseGraph`, currently around lines 141–206)

- [ ] **Step 1: Add `buildElkNode` helper**

Add this helper just below `pickLayoutOptions` from Task 1 Step 2:

```ts
  type ElkNode = {
    id: string;
    width?: number;
    height?: number;
    layoutOptions?: Record<string, string>;
    children?: ElkNode[];
    edges?: { id: string; sources: string[]; targets: string[] }[];
  };

  let elkEdgeCounter = 0;
  function nextEdgeId(prefix: string): string {
    return `${prefix}-${elkEdgeCounter++}`;
  }

  function buildElkNode(
    obs: LangfuseObservation,
    depth: number,
  ): ElkNode {
    if (obs.children.length === 0) {
      return {
        id: obs.id,
        width: 200,
        height: obs.model ? 56 : 44,
      };
    }

    // Compound node: recurse into children
    const headerPad = depth === 0 ? 48 : 32;
    const layoutOptions = pickLayoutOptions(obs.children, headerPad);
    const childNodes = obs.children.map(c => buildElkNode(c, depth + 1));

    // Inner sequential edges only for layered containers (rectpacking gets none)
    const edges: { id: string; sources: string[]; targets: string[] }[] = [];
    if (layoutOptions['elk.algorithm'] === 'layered') {
      for (let i = 0; i < obs.children.length - 1; i++) {
        edges.push({
          id: nextEdgeId('inner'),
          sources: [obs.children[i].id],
          targets: [obs.children[i + 1].id],
        });
      }
    }

    return {
      id: obs.id,
      layoutOptions,
      children: childNodes,
      edges,
    };
  }
```

- [ ] **Step 2: Replace the ELK graph construction inside `loadLangfuseGraph`**

In `loadLangfuseGraph`, locate the block that currently builds `elkChildren`/`elkEdges` (the `for (const agent of agentObs) { ... }` loop and the cross-cluster edge loop). It's roughly lines 140–206 in the current file.

Replace that whole block — from `// Build ELK compound graph` down to and including the `const layout = await elk.layout(elkGraph);` line — with the following:

```ts
      // Build observation index (full DFS over each agent subtree)
      for (const agent of agentObs) {
        for (const obs of flattenObservations(agent)) {
          allObservations.set(obs.id, obs);
        }
      }

      // Build ELK compound graph recursively from the Langfuse tree
      const elk = new ELK();
      elkEdgeCounter = 0;

      const elkChildren: ElkNode[] = agentObs.map(agent => {
        const node = buildElkNode(agent, 0);
        // Force the agent-cluster id prefix so the visual style picker can
        // distinguish top-level agent containers from nested compound observations.
        node.id = `agent-${agent.name}`;
        return node;
      });

      // Cross-cluster edges: last leaf of agent[i] -> first leaf of agent[i+1]
      const crossClusterEdges: { source: string; target: string; sourceAgent: string }[] = [];
      const elkEdges: { id: string; sources: string[]; targets: string[] }[] = [];
      for (let i = 0; i < agentObs.length - 1; i++) {
        const fromLeaf = lastLeaf(agentObs[i]);
        const toLeaf = firstLeaf(agentObs[i + 1]);
        crossClusterEdges.push({
          source: fromLeaf.id,
          target: toLeaf.id,
          sourceAgent: agentObs[i].name,
        });
        elkEdges.push({
          id: nextEdgeId('cross'),
          sources: [fromLeaf.id],
          targets: [toLeaf.id],
        });
      }

      const elkGraph = {
        id: 'root',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.spacing.nodeNode': '40',
          'elk.layered.spacing.nodeNodeBetweenLayers': '60',
        },
        children: elkChildren,
        edges: elkEdges,
      };

      const layout = await elk.layout(elkGraph);
```

Note: the `node.id = 'agent-' + agent.name` line is important — without it, the agent containers would be keyed by the Langfuse observation UUID, and Step 2 of Task 4 (style picker) wouldn't be able to identify them.

But this also means observations stored in `allObservations` whose ID equals an agent's observation id would clash with `agent-<name>`. To avoid that, after the rename, the agent observation's UUID is no longer used as a node id — we only render its container under `agent-<name>`. This matches the previous behavior, where the agent observation itself was never rendered as a leaf node.

- [ ] **Step 3: Verify it compiles**

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: build succeeds with no new errors.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "refactor(webui): build agent graph ELK input recursively"
```

---

### Task 3: Recursive Svelte Flow node emission

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` (replace the ELK-layout-to-flow-nodes conversion, currently around lines 208–256)

- [ ] **Step 1: Add `emitFlowNodes` helper**

Add this helper just below `buildElkNode` from Task 2 Step 1:

```ts
  function emitFlowNodes(
    elkNode: any,
    parentId: string | undefined,
    depth: number,
    agentColor: string,
    agentName: string,
    out: Node[],
  ): void {
    const obs = allObservations.get(elkNode.id);
    const isAgentContainer = elkNode.id.startsWith('agent-');
    const hasChildren = (elkNode.children?.length ?? 0) > 0;

    if (isAgentContainer) {
      // Top-level agent cluster (depth 0)
      const agentData = agentObsForName(agentName);
      const agentTotalTokens = agentData
        ? flattenObservations(agentData).reduce((s, o) => s + o.tokens.total, 0)
        : 0;
      out.push({
        id: elkNode.id,
        type: 'group',
        position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
        style: `width: ${elkNode.width}px; height: ${elkNode.height}px; background: rgba(255,255,255,0.02); border: 2px solid ${agentColor}; border-radius: 12px; box-sizing: content-box;`,
        data: {
          label: agentName.charAt(0).toUpperCase() + agentName.slice(1),
          color: agentColor,
          tokens: agentTotalTokens,
        },
      });
      for (const child of elkNode.children ?? []) {
        emitFlowNodes(child, elkNode.id, depth + 1, agentColor, agentName, out);
      }
      return;
    }

    if (hasChildren && obs) {
      // Nested compound observation — render as a sub-container
      const obsTypeColor =
        obs.type === 'generation' ? 'var(--blue)'
        : obs.type === 'tool' ? 'var(--green)'
        : 'var(--text-2)';
      out.push({
        id: elkNode.id,
        type: 'group',
        position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
        parentId,
        extent: 'parent' as const,
        style: `width: ${elkNode.width}px; height: ${elkNode.height}px; background: rgba(255,255,255,0.015); border: 1px solid ${obsTypeColor}; border-radius: 8px; box-sizing: content-box;`,
        data: {
          label: obs.name,
          color: obsTypeColor,
          tokens: obs.tokens.total,
        },
      });
      for (const child of elkNode.children ?? []) {
        emitFlowNodes(child, elkNode.id, depth + 1, agentColor, agentName, out);
      }
      return;
    }

    // Leaf observation
    if (!obs) return;
    out.push({
      id: obs.id,
      type: 'observation',
      position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
      parentId,
      extent: 'parent' as const,
      data: {
        name: obs.name,
        obsType: obs.type,
        stat: obsStat(obs),
        model: obs.model,
        isError: obs.level === 'ERROR',
        selected: false,
      },
    });
  }
```

`agentObsForName` is a tiny lookup helper used inside `emitFlowNodes`. Add it just above `emitFlowNodes`:

```ts
  // Captured by emitFlowNodes; refreshed at the start of every loadLangfuseGraph call
  let _currentAgentObs: LangfuseObservation[] = [];
  function agentObsForName(name: string): LangfuseObservation | undefined {
    return _currentAgentObs.find(a => a.name === name);
  }
```

- [ ] **Step 2: Replace the existing flow-node conversion loop**

In `loadLangfuseGraph`, locate the block that currently turns `layout.children` into `flowNodes`. It starts at `// Convert ELK layout to Svelte Flow nodes` and runs through the `baseNodes = flowNodes;` assignment (roughly lines 208–256).

Replace that whole block with:

```ts
      // Convert ELK layout to Svelte Flow nodes (recursive)
      _currentAgentObs = agentObs;
      const flowNodes: Node[] = [];
      for (const agentLayout of layout.children ?? []) {
        const agentName = agentLayout.id.replace('agent-', '');
        const agentColor = roleColor(agentName);
        emitFlowNodes(agentLayout, undefined, 0, agentColor, agentName, flowNodes);
      }

      baseNodes = flowNodes;
```

- [ ] **Step 3: Verify it compiles**

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: build succeeds with no new errors.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "refactor(webui): emit agent graph flow nodes recursively"
```

---

### Task 4: Inner sequential edges from the recursive tree

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` (replace the inner-edge generation block, currently around lines 258–272)

- [ ] **Step 1: Add `collectInnerEdges` helper**

Add this helper just below `emitFlowNodes` from Task 3 Step 1:

```ts
  function collectInnerEdges(obs: LangfuseObservation, out: Edge[]): void {
    if (obs.children.length === 0) return;

    // Mirror the same decision the ELK builder made about this container
    const layoutOptions = pickLayoutOptions(obs.children, 0);
    const isLayered = layoutOptions['elk.algorithm'] === 'layered';

    if (isLayered) {
      for (let i = 0; i < obs.children.length - 1; i++) {
        out.push({
          id: `inner-${obs.children[i].id}-${obs.children[i + 1].id}`,
          source: obs.children[i].id,
          target: obs.children[i + 1].id,
          style: 'stroke: #444; stroke-width: 1; opacity: 0.5;',
        });
      }
    }

    for (const child of obs.children) {
      collectInnerEdges(child, out);
    }
  }
```

The `headerPad` argument to `pickLayoutOptions` doesn't affect the algorithm choice, so we pass `0` here.

- [ ] **Step 2: Replace the inner-edge construction in `loadLangfuseGraph`**

Find the block that currently builds inner edges (starts with `// Inner edges (sequential within clusters, using original flatObs order)`, around lines 261–272). Replace it with:

```ts
      // Inner sequential edges (only inside layered containers; rectpacking
      // containers get no edges to keep the grid clean)
      for (const agent of agentObs) {
        collectInnerEdges(agent, flowEdges);
      }
```

Leave the cross-cluster edge construction (`for (const ce of crossClusterEdges)` block) and the `edges = flowEdges;` assignment exactly as they are.

- [ ] **Step 3: Verify it compiles**

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: build succeeds with no new errors.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "refactor(webui): collect inner agent graph edges from tree"
```

---

### Task 5: Manual verification

**Files:** none (verification only)

This task validates the four scenarios from the spec. No code changes — just visual checks against the running webui. If any scenario fails, fix the bug, commit, and re-verify.

- [ ] **Step 1: Start the dev environment**

```bash
cd src/desmet/webui/frontend && bun run dev
```

In a separate terminal, start the FastAPI backend the way you normally would for the webui (e.g. `uv run desmet-webui` or whatever `pyproject.toml` exposes). Open the dashboard and navigate to the Scoring page → pick a story → click the **Agent Graph** tab.

- [ ] **Step 2: Many-tool trace (the trigger case)**

Pick a story whose trace has 1 agent with many tool calls (the screenshot case had ~89 observations under `agent-requirements`). Verify all of the following:

- The agent container is roughly 1.6:1 aspect ratio, NOT a tall narrow column
- Tool nodes are packed in a grid, not a single line
- No spaghetti of inner sequential edges between tool nodes
- The LLM (`generation`) node is visually distinct (blue badge) from tool nodes (green badge)
- Clicking any tool node opens the `ObservationDrawer` with the correct observation
- The topology badge still shows the correct counts (`1 agents`, total tokens, `0 transitions`, total observations)

If the agent container is still a tall column, the most likely bug is that `pickLayoutOptions` is going down the `layered` branch — add a `console.log({ count: children.length, hasCompound: children.some(c => c.children.length > 0) })` inside it to confirm.

- [ ] **Step 3: Multi-agent trace**

Pick a story whose trace has multiple agents (e.g. a LangGraph planner/executor/reviewer run). Verify:

- Multiple agent containers spread horizontally as before
- Cross-cluster transition edges (drawn via `TransitionEdge`) are still visible between agents in their role colors
- Each agent container is internally compact — small clusters use the layered DOWN look (with inner sequential edges), big clusters pack into a grid

- [ ] **Step 4: Small trace (≤6 observations under an agent)**

Pick a story whose trace has a small number of observations under each agent (or use a fresh run with 2–3 tool calls). Verify:

- Renders identically to the pre-change layout (single column, faint sequential edges between observations)
- Layout quality has not regressed for small clusters

- [ ] **Step 5: Click-to-inspect on nested compound containers**

If you have a trace where a `generation` observation has tool children of its own (i.e. truly nested, not flat siblings), verify:

- The generation renders as a labeled sub-container with its tools inside
- The sub-container has a thinner border in the generation type color (blue)
- Clicking a leaf tool inside opens the drawer correctly
- Clicking the sub-container's header area is fine (not required to do anything special — selection only fires for `observation`-type nodes, which is the existing behavior)

If your dataset has no such trace, skip this step and note it in the commit message.

- [ ] **Step 6: Topology badge and selection state**

In any trace, verify:

- Topology badge counts match what was shown before the change
- Selecting an observation highlights it (border + glow) and updates the drawer
- Pressing `Escape` clears the selection
- Pan and zoom on the canvas still work

- [ ] **Step 7: Commit verification notes (optional)**

If you fixed any bugs during verification, the fix commits already cover them. If no fixes were needed, no commit is required for this task.

If you found an issue with `elk.aspectRatio` not being honored by the bundled `elkjs`, swap `elk.aspectRatio` for `elk.rectpacking.targetWidth` (try a starting value of `800`). Commit:

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "fix(webui): use rectpacking.targetWidth where aspectRatio is unsupported"
```

---

## Self-review notes

- **Spec coverage:**
  - Section 1 (recursive tree builder) → Task 2
  - Section 2 (per-container layout strategy) → Task 1 (`pickLayoutOptions`) + Task 2 (called from `buildElkNode`)
  - Section 3 (edges) → Task 4
  - Section 4 (Svelte Flow node generation) → Task 3
  - Section 5 (visual styling for nested containers) → Task 3 Step 1 (style branches inside `emitFlowNodes`)
  - Section 6 (selection/click behavior) → unchanged; verified in Task 5 Step 6
  - Testing scenarios from the spec → Task 5
  - `elk.aspectRatio` fallback risk → noted in Task 5 Step 7
- **No placeholders:** every step shows the actual code.
- **Type consistency:** `pickLayoutOptions(children, headerPad)` is defined in Task 1 with two args; called with two args in Task 2 (`headerPad`) and in Task 4 (`0`). `buildElkNode(obs, depth)`, `emitFlowNodes(elkNode, parentId, depth, agentColor, agentName, out)`, `collectInnerEdges(obs, out)` — all signatures consistent across tasks. `firstLeaf`/`lastLeaf` defined in Task 1 and used in Task 2.
