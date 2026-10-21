'use client';
// Named horizontal scroll regions need a keyboard tab stop.
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import { formatMoney, localDate, localTime, percent } from '@/api/presentation';
import type { Capability, Schema } from '@/api/types';
import { formatDate } from '@/lib/types';
import { Button } from './primitives/button';
import { FormProblem } from './management';
import { ProposalReview } from './candidate-review';

type Loaded = { week: Schema['ScheduleWeek']; history: Schema['VersionHistory'] | null; proposals: Schema['Proposal'][] };

export function ScheduleHistory({ client, outletId, week, timezone, capabilities, fixtureMode, skills, onSchedule }: {
  client: SchedulingClient; outletId: string; week: string; timezone: string; capabilities: Capability[]; fixtureMode: boolean; skills: Schema['Skill'][]; onSchedule: () => void;
}) {
  const [data, setData] = useState<Loaded | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [reload, setReload] = useState(0);
  const [fromId, setFromId] = useState('');
  const [toId, setToId] = useState('');
  const [diff, setDiff] = useState<Schema['VersionDiff'] | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Schema['ScheduleVersion'] | null>(null);
  const [proposal, setProposal] = useState<Schema['Proposal'] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [notice, setNotice] = useState('');
  const active = useRef<AbortController | null>(null);
  const keys = useRef(new Map<string, string>());
  const showCosts = capabilities.includes('view_costs');
  const canPublish = capabilities.includes('publish');
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      const schedule = await client.schedule(outletId, week, controller.signal);
      const [history, pending] = schedule.schedule_id ? await Promise.all([client.versions(schedule.schedule_id, controller.signal), canPublish ? client.proposals(schedule.schedule_id, controller.signal) : Promise.resolve({ items: [] })]) : [null, { items: [] }];
      if (controller.signal.aborted) return;
      setData({ week: schedule, history, proposals: pending.items });
      const current = history?.current_version_id ?? '';
      setFromId(current);
      const candidates = history?.items.filter(v => v.id !== current && v.status !== 'discarded') ?? [];
      setToId((fixtureMode ? candidates.find(v => v.source === 'manual') : candidates[0])?.id ?? candidates[0]?.id ?? '');
    })().catch(error => { if (!controller.signal.aborted) setLoadError(asError(error)); });
    return () => { controller.abort(); active.current?.abort(); };
  }, [client, outletId, week, canPublish, fixtureMode, reload]);
  async function action(name: string, task: (signal: AbortSignal) => Promise<void>) {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(name); setError(null);
    try { await task(controller.signal); }
    catch (error) { if (!controller.signal.aborted) { setError(asError(error)); if (error instanceof ApiError && error.detail.code === 'stale_version') setStale(true); } }
    finally { if (!controller.signal.aborted) { active.current = null; setBusy(null); } }
  }
  function refresh() { active.current?.abort(); active.current = null; setBusy(null); setData(null); setLoadError(null); setError(null); setDiff(null); setDraft(null); setProposal(null); setRestoreId(null); setStale(false); setReload(n => n + 1); }
  if (loadError) return <section aria-label="Schedule history"><FormProblem error={loadError} /><Button onClick={refresh}>Reload history</Button></section>;
  if (!data) return <p role="status">Loading schedule history…</p>;
  if (!data.history) return <section className="history-empty"><h2>No version history yet</h2><p>This week has no schedule record. Generate and select an option from Schedule to start.</p><Button onClick={onSchedule}>Go to schedule</Button></section>;
  const history = data.history;
  const selected = history.items.find(v => v.id === restoreId);
  const versionName = (id: string) => `Version ${history.items.find(v => v.id === id)?.version_number ?? 'not in this list'}`;
  const person = (id: string | null) => id ? data.week.employees.find(e => e.id === id)?.name ?? `Employee ${id}` : 'Unfilled assignment';
  const role = (id: string) => skills.find(s => s.id === id)?.name ?? 'Required skill';
  const describe = (shift: Schema['Shift'] | null | undefined) => shift ? `${person(shift.employee_id)} · ${role(shift.skill_id)} · ${formatDate(localDate(shift.start_at, timezone))} ${localTime(shift.start_at, timezone)} to ${formatDate(localDate(shift.end_at, timezone))} ${localTime(shift.end_at, timezone)} · ${shift.break_minutes}m break · ${shift.locked ? 'locked' : 'unlocked'}` : 'No assignment';
  async function restore() {
    if (!selected || stale) return;
    const keyId = `${selected.id}:${history.current_version_id ?? 'empty'}`;
    if (!keys.current.has(keyId)) keys.current.set(keyId, crypto.randomUUID());
    await action('restore', async signal => {
      const value = await client.restoreVersion(selected.id, { expected_base_version_id: history.current_version_id }, keys.current.get(keyId)!, signal);
      if (signal.aborted) return;
      keys.current.delete(keyId); setDraft(value); setProposal(null); setRestoreId(null); setNotice(`Created restored draft ${value.version_number}. Nothing has been published.`);
    });
  }
  return <section className="schedule-history" aria-label="Schedule history">
    <div className="review-heading"><div><h2>Version history</h2><p>Recorded metrics show what each version cost and covered when it was saved. Comparison and restore check current facts.</p></div><Button disabled={!!busy} onClick={refresh}>Reload history</Button></div>
    {notice && <p className="save-notice" role="status">{notice}</p>}
    {history.items.length === 0 ? <p>No saved versions are available for this week.</p> : <ol className="history-list">{history.items.map(version => <li key={version.id}><div className="history-version-heading"><h3>Version {version.version_number}</h3><span className="neutral-badge">{version.id === history.current_version_id ? 'Current published' : version.status}</span><span>{version.source.replaceAll('_', ' ')} · revision {version.revision}</span></div><p>{version.reason}</p><p className="history-date">{version.published_at ? 'Published' : 'Created'} {formatDate(localDate(version.published_at ?? version.created_at, timezone), { day: 'numeric', month: 'short', year: 'numeric' })} at {localTime(version.published_at ?? version.created_at, timezone)} ({timezone})</p>{version.recorded_metrics ? <dl className="history-facts"><div><dt>Recorded preferred coverage</dt><dd>{percent(version.recorded_metrics.coverage_ratio)}</dd></div>{showCosts && <div><dt>Recorded estimated cost</dt><dd>{formatMoney(version.recorded_metrics.labour_cost)}</dd></div>}<div><dt>Recorded minimum shortfall</dt><dd>{version.recorded_metrics.minimum_deficit_minutes} staff-minutes</dd></div></dl> : <p>No recorded metrics are available for this older version.</p>}<div className="review-actions"><Button disabled={!!busy} onClick={() => { setToId(version.id); setDiff(null); }}>Compare version {version.version_number}</Button>{canPublish && version.status === 'superseded' && <Button disabled={!!busy || stale} onClick={() => { setRestoreId(version.id); setDraft(null); setProposal(null); setError(null); setNotice(''); }}>Restore version {version.version_number} as draft</Button>}</div></li>)}</ol>}
    <section className="history-compare" aria-label="Version comparison"><h2>Compare assignments</h2><p>Changes run from the first version to the second. These metrics are evaluated against current facts, rather than historical recorded values.</p><div className="history-selectors"><label>From version<select aria-label="From version" disabled={!!busy} value={fromId} onChange={e => { setFromId(e.target.value); setDiff(null); }}><option value="">Choose a version</option>{history.items.map(v => <option key={v.id} value={v.id}>Version {v.version_number} · {v.status}</option>)}</select></label><label>To version<select aria-label="To version" disabled={!!busy} value={toId} onChange={e => { setToId(e.target.value); setDiff(null); }}><option value="">Choose a version</option>{history.items.map(v => <option key={v.id} value={v.id}>Version {v.version_number} · {v.status}</option>)}</select></label><Button disabled={!!busy || !fromId || !toId || fromId === toId} onClick={() => action('compare', async signal => { setDiff(null); const value = await client.compareVersions(toId, fromId, signal); if (!signal.aborted) setDiff(value); })}>{busy === 'compare' ? 'Comparing…' : 'Compare selected versions'}</Button></div>{diff && <><h3>{versionName(diff.from_version_id)} to {versionName(diff.to_version_id)}</h3><p role="status">{diff.changes.length} changed {diff.changes.length === 1 ? 'assignment' : 'assignments'} reported. Nothing has been saved.</p><dl className="history-facts"><div><dt>Preferred coverage, from / to</dt><dd>{percent(diff.metrics_from.coverage_ratio)} / {percent(diff.metrics_to.coverage_ratio)}</dd></div>{showCosts && <div><dt>Estimated cost, from / to</dt><dd>{formatMoney(diff.metrics_from.labour_cost)} / {formatMoney(diff.metrics_to.labour_cost)}</dd></div>}</dl><div className="review-table-scroll" role="region" aria-label="Assignment comparison" tabIndex={0}><table><caption>Assignment changes in {timezone}</caption><thead><tr><th scope="col">Change</th><th scope="col">Before</th><th scope="col">After</th></tr></thead><tbody>{diff.changes.map(change => <tr key={change.logical_shift_id}><th scope="row">{change.kinds.map(kind => kind.replaceAll('_', ' ')).join(', ')}</th><td>{describe(change.before)}</td><td>{describe(change.after)}</td></tr>)}</tbody></table></div></>}</section>
    {selected && <section className="history-restore" aria-label="Restore confirmation"><h2>Restore version {selected.version_number} into a new draft</h2><p>The draft will be based on {history.current_version_id ? versionName(history.current_version_id) : 'an empty published week'}. Current availability, absences and scheduling rules will be checked. The published roster stays in place.</p><div className="review-actions"><Button variant="primary" disabled={!!busy || stale} onClick={restore}>{busy === 'restore' ? 'Creating restored draft…' : 'Create restored draft'}</Button><Button disabled={!!busy} onClick={() => setRestoreId(null)}>Cancel restore</Button></div></section>}
    {error && <FormProblem error={error} />}{stale && <p role="status">The published base changed. Reload history before restoring again.</p>}
    {data.proposals.length > 0 && !draft && <section className="history-proposals" aria-label="Pending proposals"><h2>Pending proposals</h2>{data.proposals.map(p => <div key={p.id}><p>Draft revision {p.draft_revision} · expires {formatDate(localDate(p.expires_at, timezone))} at {localTime(p.expires_at, timezone)}</p><Button disabled={!!busy} onClick={() => action('proposal', async signal => { const current = await client.proposal(p.id, signal); const value = await client.version(current.draft_version_id, signal); if (signal.aborted) return; if (value.status !== 'draft' || current.draft_revision !== value.revision) throw new Error('This draft changed after the proposal. Open its current revision from Schedule and review it again.'); setDraft(value); setProposal(current); setRestoreId(null); })}>Review pending proposal</Button></div>)}</section>}
    {draft && <section className="history-restored" aria-label="Restored draft review"><h2>Draft {draft.version_number}: review current validation</h2><p>{draft.validation.hard_violations} hard violations; {draft.validation.soft_violations} preferences to review. This draft has not been published.</p><dl className="history-facts"><div><dt>Current preferred coverage</dt><dd>{percent(draft.metrics.coverage_ratio)}</dd></div>{showCosts && <div><dt>Current estimated cost</dt><dd>{formatMoney(draft.metrics.labour_cost)}</dd></div>}</dl>{draft.validation.violations.length > 0 && <details open={draft.validation.hard_violations > 0}><summary>Review current scheduling constraints</summary><ul>{draft.validation.violations.map((v, i) => <li key={i}>{v.severity}: {v.message}</li>)}</ul></details>}<details><summary>Review draft assignments ({draft.shifts.length})</summary><ul>{draft.shifts.map(shift => <li key={shift.logical_shift_id}>{describe(shift)}</li>)}</ul></details>{canPublish && <ProposalReview key={`${draft.id}:${draft.revision}:${proposal?.id ?? 'new'}`} {...{ client, draft, timezone, fixtureMode, showCosts }} initialProposal={proposal ?? undefined} onReload={refresh} onPublished={result => { setNotice(`Published version ${result.published!.version_number}. ${fixtureMode ? 'Synthetic preview only.' : 'Confirmed by the scheduling service.'}`); refresh(); }} />}<Button onClick={onSchedule}>Go to schedule</Button></section>}
  </section>;
}

const asError = (error: unknown) => error instanceof Error ? error : new Error('The scheduling service could not be reached.');
