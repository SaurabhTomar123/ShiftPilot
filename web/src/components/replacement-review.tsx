'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import { localDate, localTime, signedNumber, strategyName } from '@/api/presentation';
import type { Schema } from '@/api/types';
import { formatMoney } from '@/api/presentation';
import { Facts } from './decision-evidence';
import { Button } from './primitives/button';
import { FormProblem } from './management';

type Reviewed = { draft: Schema['ScheduleVersion']; request: Schema['EditRequest']; preview: Schema['EditPreview']; name: string };

export function ReplacementReview({ client, version, outletId, week, employees, skills, timezone, showCosts, owner, fixtureMode, initialShiftId, onClose, onReady }: {
  client: SchedulingClient; version: Schema['ScheduleVersion']; outletId: string; week: string;
  employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string; showCosts: boolean; owner: boolean; fixtureMode: boolean; initialShiftId?: string;
  onClose: () => void; onReady: (draft: Schema['ScheduleVersion']) => void;
}) {
  const [shiftId, setShiftId] = useState(initialShiftId ?? version.shifts[0]?.logical_shift_id ?? '');
  const [profile, setProfile] = useState<Schema['ReplacementRequest']['profile']>('balanced');
  const [otherOutlets, setOtherOutlets] = useState(false);
  const [result, setResult] = useState<Schema['ReplacementRecommendations'] | null>(null);
  const [reviewed, setReviewed] = useState<Reviewed | null>(null);
  const [prepared, setPrepared] = useState<Schema['ScheduleVersion'] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const active = useRef<AbortController | null>(null);
  const createKey = useRef(crypto.randomUUID());
  const heading = useRef<HTMLHeadingElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); return () => active.current?.abort(); }, []);
  const person = (id: string | null) => employees.find(value => value.id === id)?.name ?? (id ? 'Assigned teammate' : 'Open shift');
  const describe = (shift: Schema['Shift']) => `${skills.find(value => value.id === shift.skill_id)?.name ?? 'Required skill'}: ${localDate(shift.start_at, timezone)} ${localTime(shift.start_at, timezone)} to ${localDate(shift.end_at, timezone)} ${localTime(shift.end_at, timezone)}`;
  function reset() { setResult(null); setReviewed(null); setError(null); }
  async function perform(kind: string, task: (signal: AbortSignal) => Promise<void>) {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(kind); setError(null);
    try { await task(controller.signal); }
    catch (value) { if (!controller.signal.aborted) { setError(value instanceof Error ? value : new Error('The scheduling service could not be reached.')); if (kind === 'save') { setUncertain(true); setReviewed(null); } } }
    finally { if (!controller.signal.aborted) { active.current = null; setBusy(null); } }
  }
  async function find(event: React.FormEvent) {
    event.preventDefault(); reset();
    await perform('find', async signal => {
      const value = await client.recommendReplacements({ version_id: version.id, logical_shift_id: shiftId, profile, include_other_outlets: otherOutlets, limit: 5 }, signal);
      if (signal.aborted) return;
      if (value.version_id !== version.id || value.shift.logical_shift_id !== shiftId || value.profile !== profile || value.version_status !== version.status) throw new Error('These recommendations do not match the selected version, shift and profile. Find cover again.');
      setResult(value); requestAnimationFrame(() => resultHeading.current?.focus());
    });
  }
  async function choose(option: Schema['Recommendation']) {
    if (!result || uncertain) return;
    await perform('prepare', async signal => {
      setReviewed(null);
      if (result.shift.locked) throw new Error('This assignment is locked. Review and unlock it in the draft editor before finding cover again.');
      if (option.edit.op !== 'update' || option.edit.logical_shift_id !== result.shift.logical_shift_id || option.edit.employee_id !== option.employee_id) throw new Error('The returned replacement edit does not match this person and shift. Request fresh recommendations.');
      let target = prepared;
      if (!target && version.status === 'published') {
        const current = await client.schedule(outletId, week, signal);
        if (current.current_version?.id !== version.id) throw new Error('The published week changed. Close Find cover and reload the latest week before choosing someone.');
        target = await client.createDraft(outletId, week, { base_version_id: version.id, copy_from_version_id: null }, createKey.current, signal);
      } else if (!target) {
        target = await client.version(version.id, signal);
        if (target.revision !== version.revision) throw new Error('The draft revision changed. Close Find cover and reload it before choosing someone.');
      }
      if (signal.aborted) return;
      setPrepared(target);
      const before = target.shifts.find(value => value.logical_shift_id === result.shift.logical_shift_id);
      if (target.status !== 'draft' || target.schedule_id !== version.schedule_id || !before || before.locked || before.employee_id !== result.vacating_employee_id || before.start_at !== result.shift.start_at || before.end_at !== result.shift.end_at || before.skill_id !== result.shift.skill_id) throw new Error('The prepared draft no longer matches this recommendation. Open the draft and review its current assignments.');
      const request: Schema['EditRequest'] = { expected_revision: target.revision, edits: [option.edit] };
      const preview = await client.previewEdits(target.id, request, signal);
      if (signal.aborted) return;
      if (preview.version_id !== target.id || preview.expected_revision !== target.revision) throw new Error('Validation belongs to another draft revision. Open the draft and review current facts.');
      setReviewed({ draft: target, request, preview, name: option.name });
    });
  }
  return <section className="replacement-review" aria-label="Find shift cover">
    <div className="review-heading"><div><h2 ref={heading} tabIndex={-1}>Find cover for one shift</h2><p>Check a direct replacement while every other assignment stays in place. Rearranging several shifts needs a repair run.</p></div><Button disabled={!!busy} onClick={onClose}>Close Find cover</Button></div>
    <p>Times in {timezone}. Finding cover reads current facts; it does not save an absence, reassign anyone or publish.</p>
    {fixtureMode && <p className="contract-note">The supplied example is Ravi Kumar’s Prep shift on 21 October, using Balanced at Indiranagar. Recommendations are available; validating and saving their replacement edits needs a connected API.</p>}
    <form onSubmit={find}><fieldset disabled={!!busy || !!prepared || uncertain} className="replacement-inputs"><legend>Choose the assignment and priorities</legend>
      <label>Shift needing cover<select aria-label="Shift needing cover" value={shiftId} onChange={event => { setShiftId(event.target.value); reset(); }}>{version.shifts.map(shift => <option key={shift.logical_shift_id} value={shift.logical_shift_id}>{person(shift.employee_id)}: {describe(shift)}{shift.locked ? ' (Locked)' : ''}</option>)}</select></label>
      <label>Cover priorities<select value={profile} onChange={event => { setProfile(event.target.value as typeof profile); reset(); }}>{(['balanced', 'stability', 'lowest_cost', 'fairness', 'max_coverage', 'staff_friendly'] as const).map(value => <option key={value} value={value}>{strategyName(value)}</option>)}</select></label>
      {owner && <label className="replacement-consent"><input type="checkbox" checked={otherOutlets} onChange={event => { setOtherOutlets(event.target.checked); reset(); }} />Include people from other outlets</label>}
      <Button type="submit" variant="primary" disabled={!shiftId}>{busy === 'find' ? 'Checking cover…' : 'Find cover'}</Button>
    </fieldset></form>
    {error && <FormProblem error={error} />}
    {prepared && <div className="surface-note"><p>Draft {prepared.version_number} is prepared. {uncertain ? 'The save result is uncertain. Read the current draft before another change.' : 'Preparing a draft does not apply the replacement. Review validation before saving.'} Closing this panel keeps the draft.</p><Button disabled={!!busy} onClick={() => perform('reload', async signal => { const value = await client.version(prepared.id, signal); if (!signal.aborted) { if (value.status !== 'draft') throw new Error('This is no longer a draft. Close Find cover and reload the latest week.'); onReady(value); } })}>Open current draft for review</Button></div>}
    {result && <div className="replacement-results"><h3 ref={resultHeading} tabIndex={-1}>Cover options for {person(result.vacating_employee_id)}</h3><p>{describe(result.shift)}</p><p>Negative fairness change means a fairer burden distribution. Cost includes labour and overtime premium against leaving the shift open.</p><p>Engine policy {result.policy_version}, {strategyName(result.profile)}. {result.eligible} eligible of {result.considered} qualified people checked; showing {result.recommendations.length}. Engine order is preserved. Blocked people are listed separately, up to 10.</p>
      {result.shift.locked && <p role="alert">This shift is locked. Recommendations do not authorize unlocking; use the draft editor to review the lock first.</p>}
      {!result.recommendations.length && <p role="status">No direct cover options were returned. Review availability or start a repair to consider moving other shifts.</p>}
      <ol className="replacement-options">{result.recommendations.map(option => <li key={option.employee_id}><article><div className="replacement-option-heading"><h4>{option.name}</h4><span>Engine rank {option.rank}</span></div><p>{option.disruption_class === 'cross_outlet' ? 'From another outlet' : option.disruption_class === 'overtime' ? 'Adds overtime' : 'Direct replacement'}</p><dl className="decision-facts">{showCosts && <div><dt>Cost versus leaving unfilled</dt><dd>{formatMoney(option.incremental_cost)}</dd></div>}<div><dt>Added overtime</dt><dd>{option.overtime_minutes_added} min</dd></div><div><dt>Fairness burden change</dt><dd>{option.fairness_delta == null ? 'Not reported' : signedNumber(option.fairness_delta)}</dd></div><div><dt>Weekly hours after</dt><dd>{option.weekly_minutes_after / 60} h</dd></div><div><dt>Preferred window</dt><dd>{option.within_preferred_window == null ? 'Not specified' : option.within_preferred_window ? 'Within preference' : 'Outside preference'}</dd></div></dl><details><summary>Why {option.name} can cover</summary><Facts items={option.reasons} showCosts={showCosts} /></details><Button disabled={!!busy || uncertain || result.shift.locked} onClick={() => choose(option)}>Review {option.name} in draft</Button></article></li>)}</ol>
      {!!result.rejected.length && <details className="replacement-blocked"><summary>People blocked by a recorded rule ({result.rejected.length})</summary>{result.rejected.map(person => <div key={person.employee_id}><h4>{person.name}</h4><Facts items={person.reasons} showCosts={showCosts} /></div>)}</details>}
    </div>}
    {reviewed && <section className="edit-preview" aria-label="Replacement validation"><h3>Review {reviewed.name} before saving</h3><p>Draft revision {reviewed.request.expected_revision}. {reviewed.preview.validation.hard_violations} hard violations; {reviewed.preview.validation.soft_violations} preferences. Nothing has been reassigned.</p><p>Proposed change: {person(result!.vacating_employee_id)} to {reviewed.name}, {describe(result!.shift)}.</p><ul>{reviewed.preview.validation.violations.map((item, index) => <li key={index}>{item.severity}: {item.message}</li>)}</ul><p>Preferred staffing gap: {reviewed.preview.metrics.preferred_deficit_minutes} staff-minutes.{showCosts && ` Estimated draft cost: ${formatMoney(reviewed.preview.metrics.labour_cost)}.`}</p><Button variant="primary" disabled={!!busy || uncertain || reviewed.preview.validation.hard_violations > 0 || !reviewed.preview.changes.length} onClick={() => perform('save', async signal => { const value = await client.applyEdits(reviewed.draft.id, reviewed.request, crypto.randomUUID(), signal); if (!signal.aborted) { if (value.id !== reviewed.draft.id || value.status !== 'draft' || value.revision <= reviewed.request.expected_revision) throw new Error('The save response does not confirm this draft revision. Open the current draft before continuing.'); onReady(value); } })}>{busy === 'save' ? 'Saving replacement…' : 'Save replacement to draft'}</Button><p>Saving changes only the draft. A separate proposal and approval are required to publish.</p></section>}
    {error instanceof ApiError && error.status === 501 && <p>The preview has no matching example for this request. No replacement save has been confirmed.</p>}
  </section>;
}
