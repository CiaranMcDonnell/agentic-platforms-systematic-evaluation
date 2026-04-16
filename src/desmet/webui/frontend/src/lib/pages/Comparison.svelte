<script lang="ts">
  import VerdictBand from '../components/comparison/VerdictBand.svelte';
  import RubricMatrixPanel from '../components/comparison/RubricMatrixPanel.svelte';
  import FrameworkMetricsTable from '../components/comparison/FrameworkMetricsTable.svelte';
  import EfficiencyBreakdown from '../components/comparison/EfficiencyBreakdown.svelte';
  import StoryComparisonPanel from '../components/comparison/StoryComparisonPanel.svelte';
  import { selectedResultsRunId } from '../stores';

  let currentRunId = $state<string | null>(null);
  selectedResultsRunId.subscribe((v) => (currentRunId = v));
</script>

<div>
  <h1 style="margin-bottom: 28px;">Platform Comparison</h1>

  <!-- Verdict: rankings + completion -->
  <div style="margin-bottom: 28px;">
    <VerdictBand runId={currentRunId} />
  </div>

  <!-- Subjective DESMET scores: rubric matrix + radar -->
  <div style="margin-bottom: 28px;">
    <RubricMatrixPanel runId={currentRunId} />
  </div>

  <!-- Objective framework metrics -->
  <div style="margin-bottom: 28px;">
    <FrameworkMetricsTable runId={currentRunId} />
  </div>

  <!-- Efficiency breakdown -->
  <div style="margin-bottom: 28px;">
    <EfficiencyBreakdown runId={currentRunId} />
  </div>

  <!-- Story-level comparison with metric picker -->
  <StoryComparisonPanel runId={currentRunId} />
</div>
