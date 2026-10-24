'use client';
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import type { ReactNode } from 'react';
import type { Schema } from '@/api/types';
import { burdenNumber, formatMoney, moneyDelta, percent, signedNumber, strategyName } from '@/api/presentation';
import { FairnessBreakdown, PortfolioDetails } from './decision-evidence';
import { fairnessComparisonWarning } from '@/lib/decision';

/** Display the engine's returned portfolio and comparison basis without rescoring. */
export function PlanCompare({ run, baseline, showCosts }: {
  run: Schema['OptimizationRun']; baseline: Schema['ScheduleVersion'] | null; showCosts: boolean;
}) {
  if (!run.candidates.length) return null;
  const base = baseline && run.base_version_ids.includes(baseline.id) ? baseline : null;
  type Candidate = Schema['Candidate'];
  const reference = (candidate: Candidate) => candidate.trace?.summary.compared_to === 'base_version' ? 'Engine delta vs published base' : candidate.trace?.summary.compared_to === 'requested_plan' ? 'Engine delta vs requested plan' : 'No engine comparison reference';
  const rows: { name: string; baseline: ReactNode; value: (candidate: Candidate) => ReactNode }[] = [
    { name: 'Preferred coverage', baseline: base ? percent(base.metrics.coverage_ratio) : 'Not available', value: candidate => percent(candidate.metrics.coverage_ratio) },
    { name: 'Preferred staffing gap', baseline: base ? `${base.metrics.preferred_deficit_minutes} staff-minutes` : 'Not available', value: candidate => <>{candidate.metrics.preferred_deficit_minutes} staff-minutes{candidate.trace?.summary.preferred_gap_delta_minutes != null && <small>{signedNumber(candidate.trace.summary.preferred_gap_delta_minutes)} staff-minutes, engine delta</small>}</> },
    { name: 'Minimum shortfall', baseline: base ? `${base.metrics.minimum_deficit_minutes} staff-minutes` : 'Not available', value: candidate => `${candidate.metrics.minimum_deficit_minutes} staff-minutes` },
    ...(showCosts ? [{ name: 'Estimated labour cost', baseline: base ? formatMoney(base.metrics.labour_cost) : 'Not available', value: (candidate: Candidate) => <>{formatMoney(candidate.metrics.labour_cost)}{candidate.trace?.summary.cost_delta_paise != null && <small>{moneyDelta(candidate.trace.summary.cost_delta_paise)}, engine delta</small>}</> }] : []),
    { name: 'Assignment changes', baseline: 'Reference plan', value: candidate => candidate.changed_shifts },
    { name: 'Changed commitments', baseline: 'Reference plan', value: candidate => candidate.trace?.summary.changed_commitments ?? 'Not reported' },
    { name: 'Overtime', baseline: base ? `${base.metrics.overtime_minutes} min` : 'Not available', value: candidate => `${candidate.metrics.overtime_minutes} min` },
    { name: 'Shifts away from home outlet', baseline: 'Not reported', value: candidate => candidate.trace?.summary.cross_outlet_moves ?? 'Not reported' },
    { name: 'Open shifts', baseline: base?.metrics.open_shifts ?? 'Not available', value: candidate => candidate.metrics.open_shifts },
    { name: 'Fairness burden', baseline: burdenNumber(base?.metrics.fairness_burden_deviation), value: candidate => <>{burdenNumber(candidate.metrics.fairness_burden_deviation)}{candidate.trace?.summary.fairness_delta != null && <small>{signedNumber(candidate.trace.summary.fairness_delta)}, engine delta</small>}</> },
    { name: 'Hard violations', baseline: base?.validation.hard_violations ?? 'Not available', value: candidate => candidate.validation.hard_violations },
  ];
  return <details className="plan-compare" open={run.kind === 'repair'}><summary>Compare plans ({run.candidates.length})</summary>
    <p>Compare the returned choices before reviewing an option. {base ? `The reference column shows recorded metrics for published version ${base.version_number}.` : 'No matching published baseline was supplied.'} Engine deltas use the reference named on each option; they are not calculated from the recorded column. Current facts are checked before publication.</p>
    <p>Lower fairness burden means less historical burden imbalance. Negative preferred-gap, cost and fairness deltas mean improvement. A missing value stays unreported.</p>
    <PortfolioDetails portfolio={run.portfolio} showCosts={showCosts} />
    {run.candidates.map(candidate => { const warning = fairnessComparisonWarning(run, candidate.id); return warning ? <p className="decision-data-warning" role="alert" key={candidate.id}>{strategyName(candidate.strategy)}: {warning}</p> : null; })}
    <div className="review-table-scroll" role="region" aria-label="Plan comparison" tabIndex={0}><table><caption>Plan trade-offs. Each engine-reported delta keeps its supplied comparison reference.</caption><thead><tr><th scope="col">Measure</th><th scope="col">Recorded baseline{base ? ` v${base.version_number}` : ''}</th>{run.candidates.map(candidate => <th scope="col" key={candidate.id}>{strategyName(candidate.strategy)}<small>{reference(candidate)}</small></th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.baseline}</td>{run.candidates.map(candidate => <td key={candidate.id}>{row.value(candidate)}</td>)}</tr>)}</tbody></table></div>
    <details className="comparison-burden"><summary>Understand the fairness burden</summary><p>Overall imbalance includes the last 8 published weeks plus this week. Component points describe this week only and should not be confused with shift counts. Profiles may use different trade-offs; preferred-hours alignment is a separate measure.</p>{base && <FairnessBreakdown metrics={base.metrics} label={`Recorded baseline v${base.version_number}`} />}{run.candidates.map(candidate => <FairnessBreakdown key={candidate.id} metrics={candidate.metrics} label={strategyName(candidate.strategy)} />)}</details>
    <p>Scroll sideways to compare every plan. Open an option below to review its assignment changes and recorded reasons. Selecting it creates a draft for approval.</p>
  </details>;
}
