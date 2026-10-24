import type { Schema } from '../api/types';

/** Flag a clear direction disagreement; never replace the engine's metrics. */
export function fairnessComparisonWarning(run: Schema['OptimizationRun'], candidateId: string): string | null {
  const candidate = run.candidates.find(value => value.id === candidateId);
  const reference = run.candidates.find(value => value.rank === 1);
  const delta = candidate?.trace?.summary;
  if (!candidate || !reference || candidate.id === reference.id || delta?.compared_to !== 'requested_plan' || delta.fairness_delta == null) return null;
  const before = reference.metrics.fairness_burden_deviation;
  const after = candidate.metrics.fairness_burden_deviation;
  if (before == null || after == null || Math.abs(after - before) <= 0.01 || Math.abs(delta.fairness_delta) <= 0.01) return null;
  return Math.sign(after - before) !== Math.sign(delta.fairness_delta) ? 'The reported fairness delta and displayed reference scores disagree on direction. Review this comparison before choosing a plan; the supplied values have been kept unchanged.' : null;
}
