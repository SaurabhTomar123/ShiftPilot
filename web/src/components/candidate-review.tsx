'use client';

// Named scroll regions need a tab stop so keyboard users can scroll the tables.
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import { formatMoney, localDate, localTime, percent } from '@/api/presentation';
import type { Schema } from '@/api/types';
import { formatDate } from '@/lib/types';
import { Button } from './primitives/button';

/** One user action at a time. Aborts stale reads and never retries a write. */
function useReviewAction() {
  const active = useRef<AbortController | null>(null);
  const keys = useRef(new Map<string, string>());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => () => { active.current?.abort(); }, []);
  const keyFor = (action: string) => {
    if (!keys.current.has(action)) keys.current.set(action, crypto.randomUUID());
    return keys.current.get(action)!;
  };
  async function perform(task: (signal: AbortSignal) => Promise<void>) {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError(null);
    try { await task(controller.signal); }
    catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error : new Error('The scheduling service could not be reached.')); }
    finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); } }
  }
  return { busy, error, perform, keyFor, finish: (action: string) => keys.current.delete(action) };
}

function ReviewError({ error }: { error: Error }) {
  const details = error instanceof ApiError ? error.detail : null;
  const violations = details?.details?.violations;
  return <div className="review-error" role="alert"><strong>{details?.code === 'stale_version' ? 'This review is out of date.' : 'This action did not complete.'}</strong><p>{error.message}</p>{Array.isArray(violations) && <ul>{violations.map((v, i) => <li key={i}>{v && typeof v === 'object' && 'message' in v && typeof v.message === 'string' ? v.message : 'A scheduling constraint needs review.'}</li>)}</ul>}{details?.trace_id && <small>Support trace: {details.trace_id}</small>}<p>No automatic retry was sent. Reload current data if the draft or proposal has changed.</p></div>;
}

export function CandidateReview({ client, candidateId, employees, skills, timezone, canSelect, showCosts, onSelected, onClose }: {
  client: SchedulingClient; candidateId: string; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string;
  canSelect: boolean; showCosts: boolean; onSelected: (draft: Schema['ScheduleVersion']) => void; onClose: () => void;
}) {
  const [detail, setDetail] = useState<Schema['CandidateDetail'] | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const action = useReviewAction();
  useEffect(() => {
    const controller = new AbortController();
    client.candidate(candidateId, controller.signal).then(value => { if (!controller.signal.aborted) setDetail(value); }).catch(error => { if (!controller.signal.aborted) setLoadError(error instanceof Error ? error : new Error('Could not load this option.')); });
    return () => controller.abort();
  }, [client, candidateId]);
  const shiftRows = detail ? [...detail.diff.added.map(shift => ({ kind: 'Added', shift })), ...detail.diff.changed.map(shift => ({ kind: 'Changed', shift }))] : [];
  return <section className="option-review" aria-label="Candidate review">
    <div className="review-heading"><div><h2>Review this option</h2><p>Reviewing reads the recommendation. Selecting it creates a draft for approval.</p></div><Button onClick={onClose} disabled={action.busy}>Close option review</Button></div>
    {loadError ? <ReviewError error={loadError} /> : !detail ? <p role="status">Loading option details…</p> : <>
      <h3>{strategyName(detail.strategy)}</h3>
      <p>{detail.base_version_id ? 'Changes against the run’s published base.' : 'This option plans an empty week.'} {detail.proven_optimal ? 'Optimal for its configured objective.' : 'Feasible; optimality has not been proven.'}</p>
      <dl className="option-facts"><div><dt>Added assignments</dt><dd>{detail.diff.added.length}</dd></div><div><dt>Changed assignments</dt><dd>{detail.diff.changed.length}</dd></div><div><dt>Removed assignments</dt><dd>{detail.diff.removed.length}</dd></div><div><dt>Preferred coverage</dt><dd>{percent(detail.metrics.coverage_ratio)}</dd></div>{showCosts && <div><dt>Estimated labour cost</dt><dd>{formatMoney(detail.metrics.labour_cost)}</dd></div>}</dl>
      <p>{detail.validation.hard_violations} hard violations; {detail.validation.soft_violations} preferences to review. Selecting still leaves the week unpublished.</p>
      <details className="option-assignments"><summary>Review assignment changes ({shiftRows.length + detail.diff.removed.length})</summary><div className="review-table-scroll" tabIndex={0} role="region" aria-label="Candidate assignment changes"><table><caption>New assignment values, in {timezone}. Changed rows show the proposed values.</caption><thead><tr><th scope="col">Change</th><th scope="col">Teammate</th><th scope="col">Skill</th><th scope="col">Date and time</th><th scope="col">Break / lock</th></tr></thead><tbody>{shiftRows.map(({ kind, shift }) => <tr key={shift.logical_shift_id}><td>{kind}</td><th scope="row">{shift.employee_id ? employees.find(e => e.id === shift.employee_id)?.name ?? `Employee ${shift.employee_id}` : 'Unfilled assignment'}</th><td>{skills.find(s => s.id === shift.skill_id)?.name ?? 'Required skill'}</td><td>{formatDate(localDate(shift.start_at, timezone))} {localTime(shift.start_at, timezone)} – {formatDate(localDate(shift.end_at, timezone))} {localTime(shift.end_at, timezone)}</td><td>{shift.break_minutes}m break{shift.locked ? ', locked' : ''}</td></tr>)}{detail.diff.removed.map(id => <tr key={id}><td>Removed</td><td colSpan={4}>Logical shift {id}</td></tr>)}</tbody></table></div></details>
      {detail.validation.violations.length > 0 && <details className="option-assignments"><summary>Scheduling constraints and preferences</summary><ul>{detail.validation.violations.map((v, i) => <li key={i}>{v.severity}: {v.message}</li>)}</ul></details>}
      {action.error && <ReviewError error={action.error} />}
      <div className="review-actions">{canSelect ? <Button variant="primary" disabled={action.busy || detail.validation.hard_violations > 0} onClick={() => action.perform(async signal => { const draft = await client.selectCandidate(detail.id, action.keyFor(`select:${detail.id}`), signal); if (!signal.aborted) onSelected(draft); })}>{action.busy ? 'Creating draft…' : 'Select option and create draft'}</Button> : <p>You can review this option. A manager with publication access must select it.</p>}</div>
    </>}
  </section>;
}

export const strategyName = (strategy: Schema['Candidate']['strategy']) => ({ balanced: 'Balanced', lowest_cost: 'Lowest cost', staff_friendly: 'Hours preference alignment', max_coverage: 'Maximum coverage', least_disruption: 'Least disruption', best_coverage: 'Best coverage' })[strategy];

export function ProposalReview({ client, draft, timezone, fixtureMode, showCosts, onPublished, onReload }: {
  client: SchedulingClient; draft: Schema['ScheduleVersion']; timezone: string; fixtureMode: boolean; showCosts: boolean;
  onPublished: (decision: Schema['ProposalDecision']) => void; onReload: () => void;
}) {
  const [proposal, setProposal] = useState<Schema['Proposal'] | null>(null);
  const [decision, setDecision] = useState<Schema['ProposalDecision'] | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [demoOutcome, setDemoOutcome] = useState<'published' | 'changed' | 'stale' | 'invalid'>('published');
  const action = useReviewAction();
  const pending = proposal?.status === 'pending';
  const changed = decision?.outcome === 'changed';
  const hiddenCost = changed && !showCosts && decision.deltas?.some(delta => delta.metric === 'labour_cost');
  async function approve() {
    if (!proposal || !pending || (changed && (!acknowledged || hiddenCost))) return;
    const acceptsChanges = changed && acknowledged;
    const actionId = `approve:${proposal.id}:${acceptsChanges}`;
    await action.perform(async signal => {
      client.setFixtureApprovalOutcome(demoOutcome);
      const result = await client.approveProposal(proposal.id, { acknowledge_changes: acceptsChanges }, action.keyFor(actionId), signal);
      if (signal.aborted) return;
      action.finish(actionId); setAcknowledged(false); setDecision(result); setProposal(result.proposal);
      if (result.outcome === 'published' && result.published) onPublished(result);
    });
  }
  return <section className="proposal-review" aria-label="Proposal review">
    <div className="review-heading"><div><h2>Approve this week</h2><p>A draft stays private until its proposal is approved against current staffing facts.</p></div><span className="neutral-badge">Draft revision {draft.revision}</span></div>
    {!proposal ? <><p>Create a proposal to record the draft revision and the metrics you are reviewing.</p><Button variant="primary" disabled={action.busy || draft.validation.hard_violations > 0} onClick={() => action.perform(async signal => { const value = await client.createProposal({ draft_version_id: draft.id, expected_revision: draft.revision }, action.keyFor(`propose:${draft.id}:${draft.revision}`), signal); if (!signal.aborted) setProposal(value); })}>{action.busy ? 'Creating proposal…' : 'Create proposal'}</Button>{draft.validation.hard_violations > 0 && <p>Resolve the reported hard violations before creating a proposal.</p>}</> : <>
      <p className="proposal-state">Proposal status: <strong>{proposal.status}</strong>. Revision {proposal.draft_revision}.</p>
      <p>Expires {formatDate(localDate(proposal.expires_at, timezone))} at {localTime(proposal.expires_at, timezone)} ({timezone}). The server checks expiry when you approve.</p>
      {pending && <dl className="option-facts"><div><dt>Coverage at proposal</dt><dd>{percent(proposal.metrics_at_proposal.coverage_ratio)}</dd></div>{showCosts && <div><dt>Cost at proposal</dt><dd>{formatMoney(proposal.metrics_at_proposal.labour_cost)}</dd></div>}<div><dt>Minimum shortfall at proposal</dt><dd>{proposal.metrics_at_proposal.minimum_deficit_minutes} staff-minutes</dd></div></dl>}
      {decision && <div className={`proposal-outcome ${decision.outcome}`} role="status"><h3>{({ published: 'Published', stale: 'Stale: review the latest week', invalid: 'Invalid: scheduling rules now block this plan', changed: 'Changed: review the new metrics' })[decision.outcome]}</h3><p>{hiddenCost ? 'Estimated cost changed. A reviewer with cost access must review these changes.' : decision.message}</p>{decision.outcome === 'stale' && <p>No replacement was published by this approval. Reload the latest week before generating another option.</p>}{decision.outcome === 'invalid' && <><p>No replacement was published. Review these constraints before planning a replacement.</p><ul>{decision.violations?.map((v, i) => <li key={i}>{v.message}</li>)}</ul></>}{changed && <><p>The plan is still valid, but the following metrics moved since the proposal. Nothing has been published.</p><div className="review-table-scroll" tabIndex={0} role="region" aria-label="Changed proposal metrics"><table><caption>Metrics at proposal compared with current facts</caption><thead><tr><th scope="col">Metric</th><th scope="col">At proposal</th><th scope="col">Now</th></tr></thead><tbody>{decision.deltas?.filter(delta => showCosts || delta.metric !== 'labour_cost').map(delta => <tr key={delta.metric}><th scope="row">{deltaLabel(delta.metric)}</th><td>{deltaValue(delta.metric, delta.before)}</td><td>{deltaValue(delta.metric, delta.after)}</td></tr>)}</tbody></table></div><label className="change-acknowledgment"><input type="checkbox" checked={acknowledged} disabled={action.busy || hiddenCost} onChange={e => setAcknowledged(e.target.checked)} />I reviewed and accept these metric changes</label></>}</div>}
      {fixtureMode && pending && <label className="approval-demo">Try an approval outcome<select aria-label="Approval demo outcome" value={demoOutcome} disabled={action.busy} onChange={e => { setDemoOutcome(e.target.value as typeof demoOutcome); setAcknowledged(false); }}><option value="published">Published</option><option value="changed">Changed metrics</option><option value="stale">Stale base</option><option value="invalid">Invalid against current facts</option></select></label>}
      <div className="review-actions">{pending && <><Button variant="primary" disabled={action.busy || (changed && (!acknowledged || hiddenCost))} onClick={approve}>{action.busy ? 'Checking current facts…' : changed ? 'Accept changes and publish' : 'Approve and publish'}</Button><Button disabled={action.busy} onClick={() => action.perform(async signal => { const value = await client.rejectProposal(proposal.id, action.keyFor(`reject:${proposal.id}`), signal); if (!signal.aborted) { setProposal(value); setDecision(null); } })}>Reject proposal</Button></>}<Button disabled={action.busy} onClick={onReload}>{decision?.outcome === 'published' ? 'View published week' : 'Reload latest week'}</Button><Button disabled={action.busy} onClick={() => action.perform(async signal => { const value = await client.proposal(proposal.id, signal); if (!signal.aborted) { setProposal(value); if (value.status !== 'pending') setDecision(null); } })}>Refresh proposal status</Button></div>
    </>}
    {action.error && <ReviewError error={action.error} />}
  </section>;
}

const deltaLabel = (metric: Schema['MetricDelta']['metric']) => ({ labour_cost: 'Estimated labour cost', coverage_ratio: 'Preferred coverage', minimum_deficit_minutes: 'Hard minimum shortfall', open_shifts: 'Open shifts' })[metric];
function deltaValue(metric: Schema['MetricDelta']['metric'], value: number | null) {
  if (value === null) return 'Not applicable';
  if (metric === 'labour_cost') return formatMoney({ amount_paise: value, currency: 'INR' });
  if (metric === 'coverage_ratio') return percent(value);
  return `${value.toLocaleString('en-IN')}${metric === 'minimum_deficit_minutes' ? ' staff-minutes' : ''}`;
}
