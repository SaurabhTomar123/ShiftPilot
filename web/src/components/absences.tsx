'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient, watchRun } from '@/api/client';
import { formatMoney, localDate, localTime, runMessage } from '@/api/presentation';
import type { Schema } from '@/api/types';
import { outletInstant } from '@/lib/management';
import { addDays } from '@/lib/types';
import { Button } from './primitives/button';
import { DecisionEvidence } from './decision-evidence';
import { PlanCompare } from './plan-compare';
import { ProtectionControls, ProtectionConflict, RunProtection } from './run-protection';
import { emptyProtection, hasProtection, releaseProtection, requestedProtection } from '@/lib/protection';
import { FormProblem } from './management';
import { CandidateReview, ProposalReview, strategyName } from './candidate-review';

const asError = (value: unknown) => value instanceof Error ? value : new Error('The service could not be reached.');
const stageNames = { impact: 'Only directly affected assignments', same_day: 'Same day, home team', adjacent_shifts: 'Include the day either side', other_outlets: 'Borrow from other outlets', overtime: 'Allow contracted overtime' };

export function Absences({ client, outlet, week, me, skills, fixtureMode }: {
  client: SchedulingClient; outlet: Schema['Outlet']; week: string; me: Schema['Me']; skills: Schema['Skill'][]; fixtureMode: boolean;
}) {
  const [data, setData] = useState<{ schedule: Schema['ScheduleWeek']; items: Schema['AbsenceMark'][] } | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [report, setReport] = useState<Schema['AbsenceReport'] | null>(null);
  const [runs, setRuns] = useState<Schema['OptimizationRun'][]>([]);
  const [runErrors, setRunErrors] = useState<Record<string, string>>({});
  const [employee, setEmployee] = useState('');
  const [start, setStart] = useState(`${addDays(week, 2)}T00:00`);
  const [end, setEnd] = useState(`${addDays(week, 3)}T00:00`);
  const [kind, setKind] = useState<Schema['ReportAbsenceRequest']['kind']>('sick');
  const [status, setStatus] = useState<'confirmed' | 'requested'>('confirmed');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [decision, setDecision] = useState<{ id: string; status: Schema['UpdateAbsenceRequest']['status'] } | null>(null);
  const [locks, setLocks] = useState<string[]>([]);
  const [authorized, setAuthorized] = useState<string[]>([]);
  const [protection, setProtection] = useState(emptyProtection);
  const [protectionConflicts, setProtectionConflicts] = useState<string[]>([]);
  const [protectionNotice, setProtectionNotice] = useState('');
  const reviewedBase = useRef<string | null>(null);
  const [crossOutlet, setCrossOutlet] = useState(false);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Schema['ScheduleVersion'] | null>(null);
  const [notice, setNotice] = useState('');
  const savedNotice = useRef<HTMLParagraphElement>(null);
  const life = useRef<AbortController | null>(null);
  const active = useRef(false);
  const keys = useRef(new Map<string, string>());
  const showCosts = me.capabilities.includes('view_costs');
  const canPublish = me.capabilities.includes('publish');
  const range = (value: { start_at: string; end_at: string }) => `${localDate(value.start_at, outlet.timezone)} ${localTime(value.start_at, outlet.timezone)} to ${localDate(value.end_at, outlet.timezone)} ${localTime(value.end_at, outlet.timezone)}`;
  const name = (id: string | null) => id ? data?.schedule.employees.find(e => e.id === id)?.name ?? `Employee ${id}` : 'Open shift';
  const lockDescription = (id: string) => {
    const shift = report?.affected.find(shift => shift.logical_shift_id === id) ?? data?.schedule.current_version?.shifts.find(shift => shift.logical_shift_id === id);
    return shift ? `${skills.find(skill => skill.id === shift.skill_id)?.name ?? 'Assignment'}: ${range(shift)}` : `Assignment ${id}`;
  };
  const keyFor = (body: unknown) => { const identity = JSON.stringify(body); if (!keys.current.has(identity)) keys.current.set(identity, crypto.randomUUID()); return keys.current.get(identity)!; };
  async function load(signal: AbortSignal) {
    const [schedule, list] = await Promise.all([client.schedule(outlet.id, week, signal), client.absences(outlet.id, outletInstant(week, '00:00', outlet.timezone), outletInstant(addDays(week, 7), '00:00', outlet.timezone), signal)]);
    if (!signal.aborted) {
      if (reviewedBase.current && reviewedBase.current !== schedule.current_version?.id) { setProtection(emptyProtection()); setProtectionConflicts([]); setProtectionNotice('The published base changed. Run protections were cleared; review the latest assignments before another request.'); }
      reviewedBase.current = schedule.current_version?.id ?? null;
      setData({ schedule, items: list.items }); setEmployee(previous => previous || schedule.employees[0]?.id || ''); setLoadError(null); }
  }
  useEffect(() => {
    const controller = new AbortController(); life.current = controller;
    load(controller.signal).catch(error => { if (!controller.signal.aborted) setLoadError(asError(error)); });
    return () => controller.abort();
    // The parent remounts this screen when its outlet, week or scenario changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, outlet.id, week, outlet.timezone]);
  async function action(task: (signal: AbortSignal) => Promise<void>) {
    if (active.current || !life.current) return;
    active.current = true; setBusy(true); setError(null);
    const signal = life.current.signal;
    try { await task(signal); } catch (error) {
      if (!signal.aborted) {
        setError(asError(error));
        if (error instanceof ApiError && Array.isArray(error.detail.details?.frozen_logical_shift_ids)) setProtectionConflicts(error.detail.details.frozen_logical_shift_ids.filter((id): id is string => typeof id === 'string'));
        if (error instanceof ApiError && Array.isArray(error.detail.details?.locked_logical_shift_ids)) { setLocks(error.detail.details.locked_logical_shift_ids.filter((id): id is string => typeof id === 'string')); setAuthorized([]); }
      }
    } finally { if (!signal.aborted) { active.current = false; setBusy(false); } }
  }
  async function track(id: string, signal: AbortSignal) {
    setRunErrors(previous => { const next = { ...previous }; delete next[id]; return next; });
    try {
      const initial = await client.run(id, signal);
      await watchRun(client, initial, { signal, onUpdate: value => setRuns(previous => [...previous.filter(r => r.id !== value.id), value]) });
    } catch (error) { if (!signal.aborted) setRunErrors(previous => ({ ...previous, [id]: asError(error).message })); }
  }
  async function saved(value: Schema['AbsenceReport'], signal: AbortSignal) {
    if (signal.aborted) return;
    setProtection(emptyProtection()); setProtectionConflicts([]); setProtectionNotice(''); setReport(value); setLocks(value.lock_conflicts); setAuthorized([]); setCandidateId(null); setDraft(null); setRuns([]); setRunErrors({}); setDecision(null);
    setNotice(`Absence saved as ${value.absence.status}. Repair results do not undo this record.`);
    requestAnimationFrame(() => { if (!signal.aborted) savedNotice.current?.focus(); });
    // Tracking failures are independent of the already confirmed write.
    await Promise.all((value.repair_run_ids ?? []).map(id => track(id, signal)));
    try { await load(signal); } catch (error) { if (!signal.aborted) setLoadError(asError(error)); }
  }
  if (!data) return loadError ? <><p role="alert">Could not load absences: {(error ?? loadError).message}</p><Button onClick={() => action(load)}>Reload absences</Button></> : <p role="status">Loading absences and the published week…</p>;
  return <section className="absence-screen" aria-label="Absence management">
    <div className="absence-intro"><h2>Cover the gap, keep the record</h2><p>Save the absence first. Confirmed absences start repairs for affected published schedules. Review an option and approve a proposal before any replacement reaches the team.</p><p>Dates and times use {outlet.timezone}. The end time is excluded.</p></div>
    {fixtureMode && <p className="contract-note">Synthetic preview: reporting supports the supplied Ravi sick-day example on 21 October and leave request on 23 October. Other mutations need the live API. Repair details and draft selection use the supplied example; other status changes remain limited in this preview.</p>}
    <div className="absence-layout"><form className="absence-form" onSubmit={event => { event.preventDefault(); action(async signal => {
      const input: Schema['ReportAbsenceRequest'] = { employee_id: employee, start_at: outletInstant(start.slice(0, 10), start.slice(11), outlet.timezone), end_at: outletInstant(end.slice(0, 10), end.slice(11), outlet.timezone), kind, status, reason: reason.trim() || null };
      if (Date.parse(input.end_at) <= Date.parse(input.start_at)) throw new Error('End must be after the start.');
      const value = await client.reportAbsence(input, keyFor(input), signal); await saved(value, signal);
    }); }}><h2>Report an absence</h2><label>Employee<select aria-label="Absent employee" required value={employee} disabled={busy} onChange={e => setEmployee(e.target.value)}>{data.schedule.employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><label>Starts<input aria-label="Absence starts" type="datetime-local" required value={start} disabled={busy} onChange={e => setStart(e.target.value)} /></label><label>Ends<input aria-label="Absence ends" type="datetime-local" required value={end} disabled={busy} onChange={e => setEnd(e.target.value)} /></label><label>Type<select aria-label="Absence type" value={kind} disabled={busy} onChange={e => setKind(e.target.value as typeof kind)}><option value="sick">Sick</option><option value="leave">Leave</option><option value="other">Other</option></select></label><label>Record as<select aria-label="Absence status" value={status} disabled={busy} onChange={e => setStatus(e.target.value as typeof status)}><option value="confirmed">Confirmed absence</option><option value="requested">Request awaiting confirmation</option></select></label><label>Reason (optional)<textarea aria-label="Absence reason" maxLength={500} value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label><p>{status === 'confirmed' ? 'This immediately affects scheduling constraints. Repair does not publish automatically.' : 'A request does not invalidate assignments until a manager confirms it.'}</p><Button type="submit" variant="primary" disabled={busy || !employee}>{busy ? 'Saving or checking repairs…' : 'Save absence'}</Button></form>
    <section className="absence-records" aria-label="Saved absences"><div className="review-heading"><h2>This week’s absences</h2><Button disabled={busy} onClick={() => action(load)}>Reload records</Button></div>{data.items.length === 0 && <p>No absences overlap this week.</p>}<ul>{data.items.map(item => <li key={item.id}><h3>{name(item.employee_id)} <span className="neutral-badge">{item.status}</span></h3><p>{item.kind} · {range(item)}</p>{['requested', 'confirmed'].includes(item.status) && <div className="review-actions">{item.status === 'requested' && <><Button disabled={busy} onClick={() => setDecision({ id: item.id, status: 'confirmed' })}>Confirm absence</Button><Button disabled={busy} onClick={() => setDecision({ id: item.id, status: 'rejected' })}>Reject request</Button></>}<Button disabled={busy} onClick={() => setDecision({ id: item.id, status: 'cancelled' })}>Cancel absence</Button>{item.status === 'confirmed' && <Button disabled={busy} onClick={() => { setProtection(emptyProtection()); setProtectionConflicts([]); setProtectionNotice(''); setReport({ absence: item, affected: [], lock_conflicts: [], repair_suggested: true, repair_run_ids: [] }); setLocks([]); setAuthorized([]); setRuns([]); setRunErrors({}); setCandidateId(null); setDraft(null); setNotice('Selected saved absence. Start or attach to its repair for this published week.'); }}>Review repair</Button>}</div>}</li>)}</ul></section></div>
    {decision && <section className="absence-decision" aria-label="Confirm absence change"><h2>Set this absence to {decision.status}?</h2><p>{name(data.items.find(item => item.id === decision.id)?.employee_id ?? null)}. {decision.status === 'confirmed' ? 'This records a confirmed absence and starts eligible repairs.' : 'This changes the absence record. It does not restore or publish a roster.'}</p><Button disabled={busy} variant="primary" onClick={() => action(async signal => saved(await client.updateAbsence(decision.id, { status: decision.status }, signal), signal))}>Save as {decision.status}</Button><Button disabled={busy} onClick={() => setDecision(null)}>Keep current status</Button></section>}
    {notice && <p className="save-notice" role="status" tabIndex={-1} ref={savedNotice}>{notice}</p>}{error && <FormProblem error={error} />}{loadError && <p role="alert">Saved records could not be refreshed: {loadError.message}. Reload records before another decision.</p>}
    {report && <section className="absence-repair" aria-label="Absence repair"><h2>{name(report.absence.employee_id)}: {report.absence.status}</h2><p>{range(report.absence)}</p>{report.affected.length > 0 && <details><summary>Affected published assignments ({report.affected.length})</summary><ul>{report.affected.map(shift => <li key={`${shift.version_id}:${shift.logical_shift_id}`}>{range(shift)} · {shift.outlet_id === outlet.id ? outlet.name : `Outlet ${shift.outlet_id}`} · {shift.locked ? 'Locked' : 'Unlocked'}</li>)}</ul></details>}
      {report.absence.status === 'confirmed' && <>{data.schedule.current_version && <ProtectionControls base={data.schedule.current_version} employees={data.schedule.employees} {...{ skills }} timezone={outlet.timezone} value={protection} disabled={busy} onChange={value => { setProtection(value); setProtectionConflicts([]); setProtectionNotice(''); setError(null); }} />}{protectionConflicts.length > 0 && data.schedule.current_version && <ProtectionConflict key={protectionConflicts.join()} base={data.schedule.current_version} employees={data.schedule.employees} {...{ skills }} timezone={outlet.timezone} ids={protectionConflicts} disabled={busy} onRelease={ids => { setProtection(releaseProtection(protection, ids, data.schedule.current_version!, outlet.timezone)); setProtectionConflicts([]); setError(null); }} />}{protectionNotice && <p className="save-notice">{protectionNotice}</p>}<p>Repair uses this week’s latest published base. An existing repair for this absence can be returned. The absence remains saved if repair fails.</p>{locks.length > 0 && <fieldset><legend>Permission to change locked assignments</legend><p>Select each assignment you authorize this repair to change.</p>{locks.map(id => <label key={id}><input type="checkbox" checked={authorized.includes(id)} disabled={busy} onChange={e => setAuthorized(values => e.target.checked ? [...values, id] : values.filter(value => value !== id))} />{lockDescription(id)}</label>)}</fieldset>}{me.role === 'owner' && <label className="absence-consent"><input type="checkbox" checked={crossOutlet} disabled={busy} onChange={e => setCrossOutlet(e.target.checked)} />Allow this repair to borrow staff from other outlets</label>}<Button disabled={busy || locks.some(id => !authorized.includes(id))} onClick={() => action(async signal => {
        const current = await client.schedule(outlet.id, week, signal);
        if (!current.current_version) throw new Error('There is no published version to repair for this week.');
        if (hasProtection(protection) && current.current_version.id !== data.schedule.current_version?.id) throw new Error('The published week changed. Reload records and review protections before starting a repair.');
        const input: Schema['RepairRequest'] = { absence_id: report.absence.id, base_version_id: current.current_version.id, unlock_logical_shift_ids: authorized, allow_cross_outlet: me.role === 'owner' && crossOutlet, time_limit_seconds: 3, ...(hasProtection(protection) ? { freeze: protection } : {}) };
        const run = await client.repair(outlet.id, week, input, keyFor(input), signal);
        if (signal.aborted) return;
        keys.current.delete(JSON.stringify(input));
        const requested = requestedProtection(protection, current.current_version, outlet.timezone).map(shift => shift.logical_shift_id).sort();
        const confirmed = [...(run.frozen_logical_shift_ids ?? [])].sort();
        setProtectionNotice(JSON.stringify(requested) === JSON.stringify(confirmed) ? 'Review the server-confirmed protections below. The next run starts with no protection selected.' : 'This run has a different protection set from your request. An existing run may have been returned. Review its server-confirmed protections before selecting an option.');
        setProtection(emptyProtection()); setProtectionConflicts([]);
        setCandidateId(null); setDraft(null); setRuns(previous => [...previous.filter(r => r.id !== run.id), run]); await track(run.id, signal);
      })}>Start or check repair for this week</Button></>}
      {Object.entries(runErrors).map(([id, message]) => <div key={id} role="alert"><p>Absence is saved. Repair status could not be confirmed: {message}</p><p>Run {id}</p><Button disabled={busy} onClick={() => action(signal => track(id, signal))}>Check repair status</Button></div>)}
      {runs.map(run => <section className="repair-run" key={run.id} aria-label="Repair result"><h3>{runMessage(run).title}</h3><p>{runMessage(run).body}</p><p>Run {run.id} · {run.job_state}{run.solver_status ? ` · ${run.solver_status}` : ''}</p>{run.error && <p role="alert">{run.error.message}</p>}{run.infeasibility && <p role="alert">Minimum staffing could not be met. Review staffing and availability before trying another repair.</p>}<RunProtection run={run} base={data.schedule.current_version} employees={data.schedule.employees} skills={skills} timezone={outlet.timezone} /><PlanCompare run={run} baseline={data.schedule.current_version} showCosts={showCosts} /><ol className="repair-stages">{run.repair_stages?.map(stage => <li key={stage.stage}><strong>{stageNames[stage.stage]}</strong><span>{stage.result.replaceAll('_', ' ')}{stage.reason ? `: ${stage.reason.replaceAll('_', ' ')}` : ''}</span><p>{stage.released}</p>{stage.widened_because && <p>Why scope widened: {stage.widened_because}</p>}<p>{stage.free_shifts} changeable shifts; {stage.pool} eligible people.{stage.minimum_shortfall_minutes != null ? ` Minimum shortfall: ${stage.minimum_shortfall_minutes} staff-minutes.` : ''}</p></li>)}</ol>{run.candidates.map(candidate => <article className="repair-option" key={candidate.id}><h4>{strategyName(candidate.strategy)}</h4><p>{candidate.changed_shifts} changed shifts; {candidate.validation.hard_violations} hard violations.{showCosts ? ` Estimated cost ${formatMoney(candidate.metrics.labour_cost)}.` : ''}</p>{candidate.disruption && <p>{candidate.disruption.added_shifts} added shifts · {candidate.disruption.cross_outlet_moves} cross-outlet moves · {candidate.disruption.open_shifts} open shifts</p>}<DecisionEvidence trace={candidate.trace} explanations={candidate.explanations} employees={data.schedule.employees} showCosts={showCosts} assignments={report.affected} skills={skills} timezone={outlet.timezone} />{run.outlet_ids.includes(outlet.id) ? <Button disabled={busy} onClick={() => { setCandidateId(candidate.id); setDraft(null); }}>Review repair option</Button> : <p>Open the affected outlet’s schedule to review this option.</p>}</article>)}</section>)}
    </section>}
    {candidateId && <CandidateReview key={candidateId} {...{ client, skills, showCosts }} candidateId={candidateId} employees={data.schedule.employees} timezone={outlet.timezone} canSelect={canPublish} onSelected={value => { setDraft(value); setCandidateId(null); }} onClose={() => setCandidateId(null)} />}
    {draft && <section aria-label="Repair draft review"><h2>Repair draft {draft.version_number} has not been published</h2><ProposalReview {...{ client, draft, fixtureMode, showCosts }} timezone={outlet.timezone} onReload={() => action(load)} onPublished={() => { setNotice('Repair publication confirmed by the server.'); setDraft(null); action(load); }} /></section>}
  </section>;
}
