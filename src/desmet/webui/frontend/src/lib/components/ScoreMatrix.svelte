<script lang="ts">
  /**
   * ScoreMatrix — platform × 6-dimension rubric score grid.
   *
   * Rows = platforms (sorted by total score desc, done server-side).
   * Cols = 6 rubric dimensions (abbreviated header).
   * Cells = colored score value (null = grey "—").
   */
  import type { ScoringMatrixData } from '../api';

  const DIM_ABBR: Record<string, string> = {
    pipeline_completeness: 'PC',
    tool_integration: 'TI',
    error_recovery: 'ER',
    time_efficiency: 'TE',
    autonomy: 'AU',
    trace_quality: 'TQ',
  };

  const DIM_FULL: Record<string, string> = {
    pipeline_completeness: 'Pipeline Completeness',
    tool_integration: 'Tool Integration',
    error_recovery: 'Error Recovery',
    time_efficiency: 'Time Efficiency',
    autonomy: 'Autonomy',
    trace_quality: 'Trace Quality',
  };

  interface Props { matrixData: ScoringMatrixData; }
  let { matrixData }: Props = $props();

  function cellBg(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--bg-2)';
    if (score < 0.5)  return '#ef444430';
    if (score < 1.5)  return '#f59e0b30';
    if (score < 2.5)  return '#84cc1630';
    return '#22c55e30';
  }

  function cellBorder(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--border)';
    if (score < 0.5)  return '#ef4444';
    if (score < 1.5)  return '#f59e0b';
    if (score < 2.5)  return '#84cc16';
    return '#22c55e';
  }

  function cellColor(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--text-2)';
    if (score < 0.5)  return '#ef4444';
    if (score < 1.5)  return '#f59e0b';
    if (score < 2.5)  return '#84cc16';
    return '#22c55e';
  }

  function displayScore(score: number | null | undefined): string {
    if (score === null || score === undefined) return '—';
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
  }
</script>

<div class="matrix-wrap">
  <!-- Column headers -->
  <div class="matrix-grid" style="grid-template-columns: 160px repeat({matrixData.dimensions.length}, 1fr) 60px;">
    <div class="hdr-cell platform-hdr">Platform</div>
    {#each matrixData.dimensions as dim}
      <div class="hdr-cell dim-hdr" title={DIM_FULL[dim] ?? dim}>
        {DIM_ABBR[dim] ?? dim}
      </div>
    {/each}
    <div class="hdr-cell scored-hdr" title="Number of scored stories">Scored</div>
  </div>

  <!-- Platform rows -->
  {#each matrixData.platforms as p}
    <div class="matrix-grid" style="grid-template-columns: 160px repeat({matrixData.dimensions.length}, 1fr) 60px;">
      <!-- Platform name -->
      <div class="platform-cell">
        <span class="dot" style="background:{p.colour};"></span>
        <span class="platform-name" title={p.platform_name}>{p.platform_name}</span>
      </div>
      <!-- Dimension score cells -->
      {#each matrixData.dimensions as dim}
        {@const score = p.scores[dim] ?? null}
        <div
          class="score-cell"
          style="background:{cellBg(score)};border-color:{cellBorder(score)};color:{cellColor(score)};"
          title="{DIM_FULL[dim] ?? dim}: {displayScore(score)}"
        >
          {displayScore(score)}
        </div>
      {/each}
      <!-- Scored count -->
      <div class="scored-cell">{p.scored_count}</div>
    </div>
  {/each}
</div>

<style>
  .matrix-wrap {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 12px;
  }

  .matrix-grid {
    display: grid;
    gap: 3px;
    align-items: center;
  }

  .hdr-cell {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-2);
    text-align: center;
    padding: 4px 4px 8px;
  }
  .platform-hdr { text-align: left; }

  .platform-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 4px;
    min-width: 0;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .platform-name {
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .score-cell {
    padding: 6px 4px;
    border: 1px solid;
    border-radius: 4px;
    text-align: center;
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 600;
    cursor: default;
  }

  .scored-cell {
    text-align: center;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-2);
    padding: 6px 4px;
  }
</style>
