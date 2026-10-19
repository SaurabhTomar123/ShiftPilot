'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import examples from '@/api/generated/edit-examples.json';
import { formatMoney, localDate, localTime, percent } from '@/api/presentation';
import type { Schema } from '@/api/types';
import { draftEdit, valuesForShift, type EditValues } from '@/lib/draft-edit';
import { formatDate } from '@/lib/types';
import { Button } from './primitives/button';
import { FormProblem } from './management';

type Reviewed = { request: Schema['EditRequest']; result: Schema['EditPreview'] };

export function DraftEditor({ client, draft, employees, skills, timezone, fixtureMode, showCosts, onClose, onUpdated }: {
  client: SchedulingClient; draft: Schema['ScheduleVersion']; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string; fixtureMode: boolean; showCosts: boolean;
  onClose: () => void; onUpdated: (value: Schema['ScheduleVersion'], notice: string) => void;
}) {
  const sorted = [...draft.shifts].sort((a, b) => a.start_at.localeCompare(b.start_at) || a.logical_shift_id.localeCompare(b.logical_shift_id));
  const [values, setValues] = useState<EditValues | null>(() => sorted[0] ? valuesForShift(sorted[0], timezone) : null);
  const [reviewed, setReviewed] = useState<Reviewed | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState<'preview' | 'save' | 'reload' | null>(null);
  const [needsReload, setNeedsReload] = useState(false);
  const active = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const shift = draft.shifts.find(s => s.logical_shift_id === values?.shiftId);
  useEffect(() => { heading.current?.focus(); return () => active.current?.abort(); }, []);
  function change(patch: Partial<EditValues>) { setValues(old => old && { ...old, ...patch }); setReviewed(null); setError(null); }
  function choose(id: string) { const target = draft.shifts.find(s => s.logical_shift_id === id); if (target) { setValues(valuesForShift(target, timezone)); setReviewed(null); setError(null); } }
  async function perform(kind: NonNullable<typeof busy>, task: (signal: AbortSignal) => Promise<void>) {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(kind); setError(null);
    try { await task(controller.signal); }
    catch (error) {
      if (!controller.signal.aborted) {
        setError(error instanceof Error ? error : new Error('The scheduling service could not be reached.'));
        if (kind === 'save' || (error instanceof ApiError && ['stale_version', 'conflict'].includes(error.detail.code))) { setNeedsReload(true); setReviewed(null); }
      }
    } finally { if (!controller.signal.aborted) { active.current = null; setBusy(null); } }
  }
  async function preview(event: React.FormEvent) {
    event.preventDefault(); if (!values || !shift || needsReload) return;
    let request: Schema['EditRequest'];
    try { request = { expected_revision: draft.revision, edits: [draftEdit(shift, values, timezone)] }; }
    catch (error) { setError(error instanceof Error ? error : new Error('Check the edit values.')); return; }
    await perform('preview', async signal => {
      const result = await client.previewEdits(draft.id, request, signal);
      if (signal.aborted) return;
      if (result.version_id !== draft.id || result.expected_revision !== draft.revision) throw new Error('The preview does not match this draft revision. Reload the draft.');
      setReviewed({ request, result });
    });
  }
  async function save() {
    if (!reviewed || reviewed.result.validation.hard_violations || needsReload) return;
    await perform('save', async signal => {
      const value = await client.applyEdits(draft.id, reviewed.request, crypto.randomUUID(), signal);
      if (!signal.aborted) onUpdated(value, `Assignment changes saved to draft revision ${value.revision}. Nothing has been published.`);
    });
  }
  function example(name: keyof typeof examples) {
    const edit = examples[name].edits[0];
    const target = draft.shifts.find(s => s.logical_shift_id === edit.logical_shift_id);
    if (!target) { setError(new Error('This example belongs to the editing draft copied from the 19 October published week.')); return; }
    setValues({ ...valuesForShift(target, timezone), mode: edit.op as EditValues['mode'], ...('employee_id' in edit ? { employeeId: edit.employee_id } : {}), ...('reason' in edit ? { reason: edit.reason } : {}) }); setReviewed(null); setError(null);
  }
  const person = (id: string | null) => id ? employees.find(e => e.id === id)?.name ?? `Employee ${id}` : 'Unfilled assignment';
  const role = (id: string) => skills.find(s => s.id === id)?.name ?? 'Required skill';
  const describe = (value: Schema['Shift'] | null | undefined) => value ? `${person(value.employee_id)}, ${role(value.skill_id)}, ${formatDate(localDate(value.start_at, timezone))} ${localTime(value.start_at, timezone)} to ${formatDate(localDate(value.end_at, timezone))} ${localTime(value.end_at, timezone)}; ${value.break_minutes}m break; ${value.locked ? 'locked' : 'unlocked'}` : 'No assignment';
  return <section className="draft-editor" aria-label="Draft assignment editor">
    <div className="review-heading"><div><h2 tabIndex={-1} ref={heading}>Edit a draft assignment</h2><p>Times in {timezone}. Preview checks coverage, cost and scheduling rules before you save.</p></div><Button disabled={busy === 'save'} onClick={onClose}>Close assignment editor</Button></div>
    <p>Editing draft {draft.version_number}, revision {draft.revision}. The published week stays in place.</p>
    {fixtureMode && <div className="edit-examples"><strong>Try a provider example</strong><p>The preview has two fixed edit examples. Other changes need a connected scheduling API.</p><Button disabled={!!busy || needsReload} onClick={() => example('openingLock')}>Load opening-cook lock</Button><Button disabled={!!busy || needsReload} onClick={() => example('invalidReassignment')}>Load conflicting reassignment</Button></div>}
    {!values || !shift ? <p>This draft has no assignments to edit. Generate and select an option to start planning.</p> : <form onSubmit={preview}>
      <fieldset disabled={!!busy || needsReload}><legend className="sr-only">Assignment changes</legend>
        <div className="assignment-fields"><label className="assignment-picker">Assignment<select aria-label="Assignment" value={values.shiftId} onChange={e => choose(e.target.value)}>{sorted.map(s => <option key={s.logical_shift_id} value={s.logical_shift_id}>{formatDate(localDate(s.start_at, timezone))} {localTime(s.start_at, timezone)} · {person(s.employee_id)} · {role(s.skill_id)}{s.locked ? ' · Locked' : ''}</option>)}</select></label>
          <label>Change type<select aria-label="Change type" value={values.mode} onChange={e => change({ mode: e.target.value as EditValues['mode'] })}><option value="update">Assignment, role or time</option><option value="lock" disabled={shift.locked}>Lock assignment</option><option value="unlock" disabled={!shift.locked}>Unlock assignment</option><option value="remove">Remove assignment</option></select></label>
          {values.mode === 'update' && <><label>Assigned teammate<select aria-label="Assigned teammate" value={values.employeeId} onChange={e => change({ employeeId: e.target.value })}><option value="">Leave unfilled</option>{employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><label>Required skill<select aria-label="Required skill" value={values.skillId} onChange={e => change({ skillId: e.target.value })}>{skills.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Start date<input type="date" required value={values.startDate} onChange={e => change({ startDate: e.target.value })} /></label><label>Start time<input type="time" step={1800} required value={values.startTime} onChange={e => change({ startTime: e.target.value })} /></label><label>End date<input type="date" required value={values.endDate} onChange={e => change({ endDate: e.target.value })} /></label><label>End time<input type="time" step={1800} required value={values.endTime} onChange={e => change({ endTime: e.target.value })} /></label><p className="assignment-picker">Fixed template break: {shift.break_minutes} minutes. The service moves the break with a changed start and checks whether it still fits.</p></>}
          {values.mode === 'lock' && <label className="assignment-picker">Lock reason<input maxLength={200} value={values.reason} onChange={e => change({ reason: e.target.value })} /></label>}
          {values.mode === 'remove' && <p className="assignment-picker">This removes the assignment from the draft. Preview the staffing impact before applying the removal.</p>}
        </div><Button type="submit" disabled={!!busy || needsReload}>{busy === 'preview' ? 'Checking assignment…' : 'Preview assignment change'}</Button>
      </fieldset>
    </form>}
    {error && <FormProblem error={error} />}
    {needsReload && <p className="edit-reload-notice" role="status">Saving is paused. The draft may have changed, or the save may have completed without a response. Reload its current values before another save. Your inputs remain here until you reload.</p>}
    <div className="review-actions"><Button disabled={!!busy} onClick={() => perform('reload', async signal => { const value = await client.version(draft.id, signal); if (signal.aborted) return; if (value.status !== 'draft') throw new Error(`This version is now ${value.status}. Close the editor and reload the latest week.`); onUpdated(value, 'Reloaded the current draft. Review its assignments before making another change.'); })}>{busy === 'reload' ? 'Reloading…' : 'Reload latest draft'}</Button></div>
    {reviewed && <section className="edit-preview" aria-label="Assignment change preview"><h3>Review before saving</h3><p role="status">{reviewed.result.validation.hard_violations ? 'Blocked by scheduling validation.' : 'No hard violations reported.'} Nothing has been saved.</p><dl className="edit-change-list">{reviewed.result.changes.map(item => <div key={item.logical_shift_id}><dt>{item.kinds.map(kind => kind.replaceAll('_', ' ')).join(', ')}</dt><dd><strong>Before:</strong> {describe(item.before)}<br /><strong>After:</strong> {describe(item.after)}</dd></div>)}</dl>
      <dl className="edit-metrics"><div><dt>Preferred coverage</dt><dd>{percent(draft.metrics.coverage_ratio)} → {percent(reviewed.result.metrics.coverage_ratio)}</dd></div>{showCosts && <div><dt>Estimated labour cost</dt><dd>{formatMoney(draft.metrics.labour_cost)} → {formatMoney(reviewed.result.metrics.labour_cost)}</dd></div>}<div><dt>Hard minimum shortfall</dt><dd>{draft.metrics.minimum_deficit_minutes} → {reviewed.result.metrics.minimum_deficit_minutes} staff-minutes</dd></div></dl>
      <p>{reviewed.result.validation.hard_violations} hard violations; {reviewed.result.validation.soft_violations} preferences to review.</p>{reviewed.result.validation.hard_violations > 0 && <ul>{reviewed.result.validation.violations.filter(v => v.severity === 'hard').map((v, i) => <li key={i}><strong>Required:</strong> {v.message}</li>)}</ul>}{reviewed.result.validation.soft_violations > 0 && <details className="edit-soft-issues"><summary>Review scheduling preferences ({reviewed.result.validation.soft_violations})</summary><ul>{reviewed.result.validation.violations.filter(v => v.severity === 'soft').map((v, i) => <li key={i}>{v.message}</li>)}</ul></details>}
      <Button variant="primary" disabled={!!busy || needsReload || reviewed.result.validation.hard_violations > 0 || !reviewed.result.changes.length} onClick={save}>{busy === 'save' ? 'Saving assignment…' : 'Apply reviewed change to draft'}</Button>
    </section>}
  </section>;
}
