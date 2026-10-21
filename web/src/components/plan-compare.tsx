'use client';
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import type { ReactNode } from 'react';
import type { Schema } from '@/api/types';
import { formatMoney, percent } from '@/api/presentation';
import { strategyName } from './candidate-review';

/** Compare returned plans; portfolio selection and fairness belong to the engine. */
export function PlanCompare({ run, baseline, showCosts }: {
  run: Schema['OptimizationRun']; baseline: Schema['ScheduleVersion'] | null; showCosts: boolean;
}) {
  if (!run.candidates.length) return null;
  const base = baseline && run.base_version_ids.includes(baseline.id) ? baseline : null;
  const delta = (value: number, before: number, unit: string) => `${value > before ? '+' : ''}${Number((value - before).toFixed(1))} ${unit}`;
  const coverage = (metrics: Schema['Metrics']) => <>{percent(metrics.coverage_ratio)}{base && metrics.coverage_ratio !== null && base.metrics.coverage_ratio !== null && <small>{delta(metrics.coverage_ratio * 100, base.metrics.coverage_ratio * 100, 'percentage points')}</small>}</>;
  const cost = (metrics: Schema['Metrics']) => <>{formatMoney(metrics.labour_cost)}{base && <small>{metrics.labour_cost.amount_paise >= base.metrics.labour_cost.amount_paise ? '+' : '−'}{formatMoney({ ...metrics.labour_cost, amount_paise: Math.abs(metrics.labour_cost.amount_paise - base.metrics.labour_cost.amount_paise) })}</small>}</>;
  const rows: { name: string; baseline: ReactNode; value: (candidate: Schema['OptimizationRun']['candidates'][number]) => ReactNode }[] = [
    { name: 'Preferred coverage', baseline: base ? percent(base.metrics.coverage_ratio) : 'Not available', value: candidate => coverage(candidate.metrics) },
    { name: 'Minimum shortfall', baseline: base ? `${base.metrics.minimum_deficit_minutes} staff-minutes` : 'Not available', value: candidate => `${candidate.metrics.minimum_deficit_minutes} staff-minutes` },
    ...(showCosts ? [{ name: 'Estimated labour cost', baseline: base ? formatMoney(base.metrics.labour_cost) : 'Not available', value: (candidate: Schema['OptimizationRun']['candidates'][number]) => cost(candidate.metrics) }] : []),
    { name: 'Assignment changes', baseline: 'Reference plan', value: candidate => candidate.changed_shifts },
    { name: 'Overtime', baseline: base ? `${base.metrics.overtime_minutes} min` : 'Not available', value: candidate => <>{candidate.metrics.overtime_minutes} min{base && <small>{delta(candidate.metrics.overtime_minutes, base.metrics.overtime_minutes, 'min')}</small>}</> },
    { name: 'Cross-outlet moves', baseline: 'Not reported', value: candidate => candidate.disruption?.cross_outlet_moves ?? 'Not reported' },
    { name: 'Open shifts', baseline: base?.metrics.open_shifts ?? 'Not available', value: candidate => candidate.metrics.open_shifts },
    { name: 'Fairness burden', baseline: 'Not reported', value: () => 'Not reported' },
    { name: 'Hard violations', baseline: base?.validation.hard_violations ?? 'Not available', value: candidate => candidate.validation.hard_violations },
  ];
  return <details className="plan-compare" open={run.kind === 'repair'}><summary>Compare plans ({run.candidates.length})</summary><p>Compare the returned choices before reviewing an option. {base ? `Deltas use the recorded metrics of published version ${base.version_number}; current facts are checked again before publication.` : 'No matching published baseline was supplied, so no baseline deltas are shown.'}</p><p>Fairness burden was not reported for these plans. Employee preference match measures a different thing.</p><div className="review-table-scroll" role="region" aria-label="Plan comparison" tabIndex={0}><table><caption>Plan trade-offs. Positive cost or overtime deltas mean an increase; positive coverage deltas mean higher preferred coverage.</caption><thead><tr><th scope="col">Measure</th><th scope="col">Recorded baseline{base ? ` v${base.version_number}` : ''}</th>{run.candidates.map(candidate => <th scope="col" key={candidate.id}>{strategyName(candidate.strategy)}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.baseline}</td>{run.candidates.map(candidate => <td key={candidate.id}>{row.value(candidate)}</td>)}</tr>)}</tbody></table></div><p>Scroll sideways to compare every plan. Open an option below to review its assignment changes and returned reasons. Selecting it creates a draft for approval.</p></details>;
}
