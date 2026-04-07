# Agent Graph Layout Improvements

**Date:** 2026-04-07
**Component:** `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`
**Mode:** Langfuse path only (fallback path unchanged)

## Problem

When a Langfuse trace contains many observations under a single agent (e.g., 1 LLM
generation + 88 tool calls), the current layout collapses everything into a single
tall vertical column that wastes ~95% of the canvas width.

Root causes in `AgentGraph.svelte`:

1. **`flattenObservations()` (line 93)** discards the Langfuse parent/child tree and
   produces a flat sibling list.
2. **Inner cluster layout** uses `elk.direction: 'DOWN'` with no wrapping, so the
   flat list stacks into one column regardless of length.
3. **Forced sequential edges** (`obs[i] → obs[i+1]`) chain the flat list into a
   linear ribbon, preventing ELK from spreading nodes horizontally.

The Langfuse client (`langfuse_client.py:143-150`) already builds a real
parent-child tree from `parentObservationId`, so the hierarchy exists in the data —
the frontend just throws it away.

## Goals

- Use the real parent/child hierarchy from Langfuse so an LLM generation that
  invokes 88 tools is shown as a container holding 88 tool nodes.
- When a container has many leaf children, pack them into a near-widescreen
  rectangle instead of a single column.
- Preserve readability of small/structured clusters (don't apply packing where it
  would lose useful sequential information).
- Keep cross-cluster (agent → agent) transition edges, which carry the meaningful
  semantic of agent handoffs.

## Non-goals

- Fallback mode (`loadFallbackGraph`) is out of scope. It already lays out a small
  number of agent boxes sensibly with `RIGHT`-direction `layered`.
- No changes to the API, backend, or Langfuse client.
- No changes to `ObservationNode.svelte`, `AgentNode.svelte`,
  `TransitionEdge.svelte`, or `ObservationDrawer.svelte`.
- No changes to selection/click behavior, the topology badge, or keyboard
  shortcuts.

## Design

### 1. Recursive ELK tree builder

Replace the flat ELK construction (lines 146-194) with a recursive walker over the
Langfuse observation tree.

```
buildElkNode(obs, edgeIdGen) -> ElkNode
  if obs.children is empty:
    return { id, width: 200, height: obs.model ? 56 : 44 }
  else:
    childElkNodes = obs.children.map(buildElkNode)
    layoutOptions = pickLayoutOptions(obs.children)
    childEdges = buildInnerEdges(obs.children, layoutOptions)
    return { id, layoutOptions, children: childElkNodes, edges: childEdges }
```

The top-level agent containers (one per top-level child of the trace root) are
built the same way; they're just the outermost compound nodes in the ELK graph.

`allObservations` (the flat lookup map) is still populated by walking the tree
once before ELK construction, since `ObservationDrawer` and selected-state derivation
need O(1) ID → observation lookup.

### 2. Per-container layout strategy

A small helper picks ELK options based on the children:

```
pickLayoutOptions(children):
  hasCompoundChildren = children.some(c => c.children.length > 0)
  count = children.length
  if hasCompoundChildren or count <= 6:
    return LAYERED_DOWN_OPTIONS
  else:
    return RECTPACKING_OPTIONS
```

`LAYERED_DOWN_OPTIONS`:
```
elk.algorithm: layered
elk.direction: DOWN
elk.spacing.nodeNode: 20
elk.layered.spacing.nodeNodeBetweenLayers: 30
elk.padding: [top=<headerPad>,left=24,bottom=24,right=24]
```

`RECTPACKING_OPTIONS`:
```
elk.algorithm: rectpacking
elk.aspectRatio: 1.6
elk.spacing.nodeNode: 12
elk.padding: [top=<headerPad>,left=24,bottom=24,right=24]
```

`headerPad` is 48 for top-level agent containers, 32 for nested compound
observations. The threshold `6` lives as a single constant (`PACK_THRESHOLD`) at
the top of the layout section.

The root ELK graph keeps its current `layered` `RIGHT` direction so multiple agent
containers spread horizontally.

### 3. Edge strategy

Edges are built per container based on the chosen layout:

- **`layered` containers** (compound children OR ≤6 leaves): emit sequential
  `child[i] → child[i+1]` edges with the existing faint grey style
  (`stroke: #444; opacity: 0.5`). These give a clear visual flow when the chain is
  short or structured.
- **`rectpacking` containers**: no inner edges. Reading order is implied by
  packing position; per-node detail (timestamps, tokens) lives in the drawer.
- **Cross-cluster transition edges** (agent[i].lastLeaf → agent[i+1].firstLeaf):
  unchanged. Still computed at the top level and rendered as `TransitionEdge` with
  the source agent's role color.

"Last leaf" and "first leaf" of an agent are computed by a depth-first walk that
returns the first/last leaf observation (used only for the top-level cross-cluster
edges).

### 4. Svelte Flow node generation

The ELK layout output is walked recursively to produce Svelte Flow nodes:

```
emitFlowNodes(elkNode, parentId, depth, agentColor):
  if elkNode is a leaf observation:
    push observation node with parentId, position from ELK
  else:
    push group node with parentId, depth-aware style, position+size from ELK
    for each child:
      emitFlowNodes(child, elkNode.id, depth+1, agentColor)
```

ELK already returns child positions relative to their parent, which matches what
Svelte Flow expects when `parentId` is set with `extent: 'parent'`.

### 5. Visual styling for nested compound containers

Two style tiers:

**Top-level agent container (depth 0)** — unchanged:
```
border: 2px solid {roleColor}
border-radius: 12px
background: rgba(255,255,255,0.02)
box-sizing: content-box
```
Header label rendered via the existing styled `group` node label.

**Nested compound observation (depth ≥1)**:
```
border: 1px solid {obsTypeColor}
border-radius: 8px
background: rgba(255,255,255,0.015)
box-sizing: content-box
```
`obsTypeColor` matches the existing `ObservationNode` palette: `generation` blue,
`tool` green, `span` grey. Header label shows the observation name plus a compact
stat (token count for generations, latency for spans/tools).

Padding inside the container is set via ELK (`headerPad` = 32 for nested), so the
visible header doesn't overlap content.

### 6. Selection and click behavior

Unchanged in semantics: clicking an observation node toggles `selectedObsId`.
Compound observation containers are also clickable (their root container element
is the same shape as a leaf for selection purposes). The derived `selectedObservation`
lookup still uses `allObservations` which is populated from a full tree walk.

## Files touched

- `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` —
  rewrite the Langfuse-mode layout block (~lines 91-294). `flattenObservations()`
  is kept and continues to populate `allObservations` (the ID lookup map) and to
  compute first/last leaves for cross-cluster transition edges. It is no longer
  used for ELK input construction.

No other files change.

## Testing

Manual verification against real traces:

1. **Many-tool trace** (the trigger case): one agent, 1 LLM call + 88 tool calls.
   Expected: agent container is roughly 1.6:1 aspect ratio, tools packed in a grid,
   no sequential edge spaghetti, clearly visible LLM node distinguished by color.
2. **Multi-agent trace** (e.g., LangGraph planner/executor/reviewer): multiple
   agent containers spread horizontally as before, cross-cluster transition edges
   preserved, each container internally compact.
3. **Nested-hierarchy trace** (if any adapter produces a generation that owns its
   tool calls as children): generation rendered as a labeled sub-container with
   its tool children inside, distinct from the flat-siblings case.
4. **Small trace** (≤6 observations under an agent): renders identically to the
   current `layered` DOWN layout. Sequential edges still drawn.
5. **Click-to-inspect**: clicking any leaf observation opens the drawer with the
   correct observation. Clicking a nested compound container also opens its
   underlying observation.
6. **Topology badge counts**: `agents`, `tokens`, `transitions`, `observations`
   numbers match what they reported before the change.

## Risks / open questions

- **`elk.aspectRatio`**: needs to be the actual ELK option name accepted by
  `rectpacking` (`elk.aspectRatio` per ELK docs). If the bundled `elkjs` build
  rejects it, fall back to `elk.rectpacking.targetWidth`.
- **`box-sizing` and ELK width math**: the current code uses
  `box-sizing: content-box` so the border doesn't eat into the ELK-computed area.
  Nested containers must do the same. Verify visually.
- **Header label placement**: Svelte Flow renders the group node label using the
  current `data.label` field. If nested labels overlap children, increase
  `headerPad` for nested containers from 32 to 36.
