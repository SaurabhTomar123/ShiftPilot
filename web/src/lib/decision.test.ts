import { expect, it } from 'vitest';
import { fairnessComparisonWarning } from './decision';
import { fixture } from '../api/fixture-gateway';
import type { Schema } from '../api/types';

it('flags an inconsistent requested-plan direction without modifying either value', () => {
  const run = fixture<Schema['OptimizationRun']>('run.succeeded');
  run.candidates[1].trace!.summary.fairness_delta = 0.02;
  const original = structuredClone(run);
  expect(fairnessComparisonWarning(run, run.candidates[1].id)).toContain('disagree on direction');
  expect(run).toEqual(original);
});

it('does not compare current engine deltas against a recorded published baseline', () => {
  const run = fixture<Schema['OptimizationRun']>('run.repair.widened');
  expect(fairnessComparisonWarning(run, run.candidates[0].id)).toBeNull();
  expect(fairnessComparisonWarning(run, 'unknown')).toBeNull();
});

it('keeps missing or consistent comparisons clear of inferred warnings', () => {
  const run = fixture<Schema['OptimizationRun']>('run.succeeded'); const candidate = run.candidates[1];
  expect(candidate.trace!.summary.fairness_delta).toBeCloseTo(candidate.metrics.fairness_burden_deviation! - run.candidates[0].metrics.fairness_burden_deviation!, 2);
  expect(fairnessComparisonWarning(run, candidate.id)).toBeNull();
  candidate.trace = null; expect(fairnessComparisonWarning(run, candidate.id)).toBeNull();
  expect(fairnessComparisonWarning(run, run.candidates[0].id)).toBeNull();
});
