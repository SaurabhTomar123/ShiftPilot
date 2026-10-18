'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { ArrowRightIcon, CalendarBlankIcon, CaretLeftIcon, CaretRightIcon, CompassIcon, LockSimpleIcon, SparkleIcon, WarningCircleIcon } from '@phosphor-icons/react';
import manifest from '@/api/generated/manifest.json';
import { ApiError, SchedulingClient, generateOrAttach, watchRun } from '@/api/client';
import { formatMoney, localDate, localTime, percent, runMessage } from '@/api/presentation';
import type { Persona, Scenario, Schema } from '@/api/types';
import { addDays, days, formatDate } from '@/lib/types';
import { Avatar, Empty } from './ui';
import { Button } from './primitives/button';

type Session = { me: Schema['Me']; outlets: Schema['Outlet'][]; skills: Schema['Skill'][] };
type Resource<T> = { data: T; error?: never } | { error: Error; data?: never };
const skillColors = ['kitchen', 'kitchen', 'service', 'cashier', 'barista'];
const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';
const asError = (error: unknown) => error instanceof Error ? error : new Error('The scheduling service could not be reached.');

export function ContractWorkspace() {
  const [persona, setPersona] = useState<Persona>('manager');
  const [scenario, setScenario] = useState<Scenario>('optimal');
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '/api/fixture';
  const fixtureMode = baseUrl === '/api/fixture';
  return <div>
    <a className="skip-link" href="#main-content">Skip to schedule</a>
    <header className="contract-header"><Link className="brand" href="/"><CompassIcon size={25} weight="fill" />shiftpilot.</Link><div className="contract-header-controls"><span className="demo-badge"><span className="live-dot" />{fixtureMode ? 'Synthetic contract preview' : 'Connected scheduling API'}</span><label>View as<select aria-label="Demo persona" value={persona} onChange={e => setPersona(e.target.value as Persona)}><option value="manager">Manager</option><option value="owner">Owner</option><option value="staff">Employee</option></select></label></div></header>
    <SessionWorkspace key={`${persona}:${baseUrl}`} {...{ persona, scenario, baseUrl, fixtureMode, setScenario }} />
  </div>;
}

function SessionWorkspace({ persona, scenario, baseUrl, fixtureMode, setScenario }: { persona: Persona; scenario: Scenario; baseUrl: string; fixtureMode: boolean; setScenario: (scenario: Scenario) => void }) {
  const [session, setSession] = useState<Resource<Session> | null>(null);
  const [expired, setExpired] = useState(false);
  const [retry, setRetry] = useState(0);
  const [client] = useState(() => new SchedulingClient({ baseUrl, fixtureScenario: scenario, onUnauthorized: () => setExpired(true) }));
  useEffect(() => {
    const controller = new AbortController();
    client.signIn(persona, controller.signal).then(async me => {
      if (me.role === 'staff') return { me, outlets: [], skills: [] };
      const [outlets, skills] = await Promise.all([client.outlets(controller.signal), client.skills(controller.signal)]);
      return { me, outlets: outlets.items, skills: skills.items };
    }).then(data => { if (!controller.signal.aborted) setSession({ data }); }).catch(error => { if (!controller.signal.aborted && !isAbort(error)) setSession({ error: asError(error) }); });
    return () => { controller.abort(); client.clearSession(); };
  }, [client, persona, retry]);
  if (expired) return <main className="contract-content" id="main-content"><ErrorNotice error={new Error('Your session expired. Choose a persona again to start a new session.')} /><Button onClick={() => { setExpired(false); setSession(null); setRetry(r => r + 1); }}>Start a new demo session</Button></main>;
  if (!session) return <main className="contract-content" id="main-content"><h1>Getting your week ready.</h1><div className="roster-loading" role="status" aria-label="Loading session"><div /><div /><div /></div></main>;
  if (session.error) return <main className="contract-content" id="main-content"><ErrorNotice error={session.error} /><Button onClick={() => { setSession(null); setRetry(r => r + 1); }}>Try connecting again</Button></main>;
  return <div className="contract-shell"><aside className="contract-sidebar"><div><Avatar initials={session.data.me.display_name.split(' ').map(n => n[0]).slice(0, 2).join('')} color="sage" /><strong>{session.data.me.display_name}</strong><span>{session.data.me.org_name}</span></div><p><CalendarBlankIcon size={18} />{persona === 'staff' ? 'Your week' : 'Weekly schedule'}</p><Link href="/sandbox">Explore the local editing sandbox<ArrowRightIcon size={14} /></Link><small>{fixtureMode ? `Provider fixtures ${manifest.version}. No live solver or publication.` : 'Permissions and schedule facts come from the API.'}</small></aside><main className="contract-content" id="main-content">{session.data.me.role === 'staff' ? <EmployeeWeek client={client} /> : <ManagerWeek {...{ client, session: session.data, fixtureMode, scenario, setScenario }} />}</main></div>;
}

function ManagerWeek({ client, session, fixtureMode, scenario, setScenario }: { client: SchedulingClient; session: Session; fixtureMode: boolean; scenario: Scenario; setScenario: (scenario: Scenario) => void }) {
  const [outletId, setOutletId] = useState(session.me.outlet_id ?? session.outlets[0]?.id ?? '');
  const [week, setWeek] = useState('2026-10-19');
  const outlet = session.outlets.find(o => o.id === outletId);
  return <><div className="page-heading"><div><h1>Weekly schedule</h1><p>{session.me.org_name} · {fixtureMode ? 'Provider fixture data' : 'Current roster'}</p></div><label className="outlet-select"><select aria-label="Outlet" value={outletId} onChange={e => setOutletId(e.target.value)}>{session.outlets.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>
    <div className="schedule-toolbar"><div className="week-controls"><button className="icon-button" aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))}><CaretLeftIcon size={18} /></button><strong>{formatDate(week)} – {formatDate(addDays(week, 6))}<small>{week.slice(0, 4)}</small></strong><button className="icon-button" aria-label="Next week" onClick={() => setWeek(addDays(week, 7))}><CaretRightIcon size={18} /></button></div>{fixtureMode && <label className="contract-scenario">Try a demo outcome<select aria-label="Demo outcome" value={scenario} onChange={e => { client.setFixtureScenario(e.target.value as Scenario); setScenario(e.target.value as Scenario); }}><option value="optimal">Optimal draft</option><option value="feasible">Time-limited feasible</option><option value="infeasible">Impossible requirements</option><option value="timeout">No solution in time</option><option value="failed">Worker failure</option><option value="stale">Stale schedule</option><option value="denied">Access denied</option><option value="active">Existing run</option><option value="rate_limited">Rate limit</option></select></label>}</div>
    <RosterResource key={`${outletId}:${week}:${scenario}`} {...{ client, session, outletId, week, fixtureMode }} timezone={outlet?.timezone ?? session.me.timezone} />
  </>;
}

function RosterResource({ client, session, outletId, week, timezone, fixtureMode }: { client: SchedulingClient; session: Session; outletId: string; week: string; timezone: string; fixtureMode: boolean }) {
  const [resource, setResource] = useState<Resource<Schema['ScheduleWeek']> | null>(null);
  const [reload, setReload] = useState(0);
  const [run, setRun] = useState<Schema['OptimizationRun'] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Schema['ScheduleVersion'] | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [query, setQuery] = useState('');
  const operation = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    client.schedule(outletId, week, controller.signal).then(data => { if (!controller.signal.aborted) setResource({ data }); }).catch(error => { if (!controller.signal.aborted) setResource({ error: asError(error) }); });
    return () => { controller.abort(); operation.current?.abort(); };
  }, [client, outletId, week, reload]);
  if (!resource) return <div className="roster-loading" role="status" aria-label="Loading roster"><div /><div /><div /><div /></div>;
  if (resource.error) return <><ErrorNotice error={resource.error} /><Button onClick={() => { setResource(null); setReload(r => r + 1); }}>Reload this week</Button></>;
  const schedule = resource.data;
  const canGenerate = session.me.capabilities.includes('generate');
  const canSeeCosts = session.me.capabilities.includes('view_costs');
  const version = draft ?? schedule.current_version;

  async function generate() {
    operation.current?.abort();
    const controller = new AbortController(); operation.current = controller;
    setBusy(true); setError(null); setRun(null); setDraft(null);
    try {
      const initial = await generateOrAttach(client, outletId, week, { strategy: 'balanced', base_version_id: schedule.current_version?.id ?? null, time_limit_seconds: 10 }, crypto.randomUUID(), controller.signal);
      await watchRun(client, initial, { signal: controller.signal, onUpdate: setRun });
    } catch (error) { if (!controller.signal.aborted) setError(asError(error)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  async function preview(versionId: string) {
    operation.current?.abort(); const controller = new AbortController(); operation.current = controller;
    setError(null); setDraftBusy(true);
    try { const value = await client.version(versionId, controller.signal); if (!controller.signal.aborted) setDraft(value); }
    catch (error) { if (!controller.signal.aborted) setError(asError(error)); }
    finally { if (!controller.signal.aborted) setDraftBusy(false); }
  }

  return <>
    <div className="contract-version-row"><span className="neutral-badge">{draft ? 'Draft preview · not published' : schedule.current_version ? `Published version ${schedule.current_version.version_number}` : 'No published schedule'}</span>{canGenerate && <Button variant="primary" onClick={generate} disabled={busy || (fixtureMode && week !== '2026-10-26')}><SparkleIcon size={17} />{busy ? 'Generating…' : 'Generate draft'}</Button>}</div>
    {fixtureMode && week === '2026-10-19' && <p className="contract-note">This is the published fixture. Open next week to try generation and its different outcomes.</p>}
    {version && <MetricStrip metrics={version.metrics} showCosts={canSeeCosts} />}
    {error && <ErrorNotice error={error} onReload={error instanceof ApiError && error.detail.code === 'stale_version' ? () => { setResource(null); setRun(null); setDraft(null); setError(null); setReload(r => r + 1); } : undefined} />}
    {run && <RunResult {...{ run, skills: session.skills, canSeeCosts, draftBusy, preview }} />}
    {version && <>
      <div className="contract-roster-heading"><h2>{draft ? 'Proposed roster' : 'Published roster'}</h2>{draft && <Button onClick={() => setDraft(null)}>Back to published week</Button>}<label className="search-field"><input aria-label="Find a teammate" placeholder="Find a teammate" value={query} onChange={e => setQuery(e.target.value)} /></label></div>
      <ContractRoster version={version} employees={schedule.employees.filter(e => e.name.toLowerCase().includes(query.toLowerCase()))} skills={session.skills} week={week} timezone={timezone} absences={schedule.absences} />
      <div className="contract-validation"><strong>{version.validation.hard_violations} hard violations reported</strong><span>{version.validation.soft_violations} preferences to review</span><span>{version.metrics.open_shifts} open shifts</span></div>
      {version.validation.violations.length > 0 && <details className="contract-details"><summary>Review reported constraints and preferences</summary><ul>{version.validation.violations.map((issue, i) => <li key={`${issue.code}:${i}`}><span className="neutral-badge">{issue.severity}</span>{issue.message}</li>)}</ul></details>}
    </>}
    {!version && <Empty title="A fresh week, ready to plan." description="Generate a draft from this week’s employees, staffing requirements and rules. Your published roster will remain unchanged." />}
    <p className="contract-note">{fixtureMode ? 'All values are synthetic provider fixtures, not a live solve. ' : ''}Editing, repair and publication controls will be connected when their contracts are available.</p>
  </>;
}

function MetricStrip({ metrics, showCosts }: { metrics: Schema['Metrics']; showCosts: boolean }) {
  return <section className="contract-metrics" aria-label="Schedule metrics"><div><span>Preferred coverage</span><strong>{percent(metrics.coverage_ratio)}</strong></div><div><span>Assigned time</span><strong>{metrics.assigned_minutes / 60}<small> hours</small></strong></div>{showCosts && <div><span>Estimated labour cost</span><strong>{formatMoney(metrics.labour_cost)}</strong></div>}<div><span>Hard minimum shortfall</span><strong>{metrics.minimum_deficit_minutes}<small> staff-minutes</small></strong></div></section>;
}

function ContractRoster({ version, employees, skills, week, timezone, absences }: { version: Schema['ScheduleVersion']; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; week: string; timezone: string; absences: Schema['AbsenceMark'][] }) {
  const skillLabel = (id: string) => skills.find(s => s.id === id)?.name ?? 'Assigned skill';
  const skillClass = (id: string) => skillColors[Math.max(0, skills.findIndex(s => s.id === id))] ?? 'kitchen';
  const open = version.shifts.filter(s => s.employee_id === null);
  return <section className="roster-section"><div className="roster-scroll"><table className="roster contract-roster"><caption className="sr-only">Weekly roster. Times shown in {timezone}. Shift details include unpaid breaks and locks.</caption><thead><tr><th scope="col">Team member</th>{days.map((day, index) => <th scope="col" key={day}><span>{day}</span><strong>{formatDate(addDays(week, index), { day: 'numeric' })}</strong></th>)}</tr></thead><tbody>{employees.map(employee => <tr key={employee.id}><th scope="row"><div className="employee-cell"><Avatar initials={employee.name.split(' ').map(n => n[0]).slice(0, 2).join('')} color="sage" /><div><strong>{employee.name}</strong><span>{employee.scheduled_minutes / 60}h across outlets</span></div></div></th>{days.map((day, index) => { const shifts = version.shifts.filter(s => s.employee_id === employee.id && localDate(s.start_at, timezone) === addDays(week, index)); return <td key={day}>{shifts.length ? shifts.map(shift => <details className={`shift contract-shift ${skillClass(shift.skill_id)}`} key={shift.logical_shift_id}><summary>{localTime(shift.start_at, timezone)} – {localTime(shift.end_at, timezone)}{localDate(shift.end_at, timezone) !== localDate(shift.start_at, timezone) && ' (+1 day)'}{shift.locked && <LockSimpleIcon size={12} weight="fill" />}<small>{skillLabel(shift.skill_id)}</small></summary><p>{shift.break_minutes ? `${shift.break_minutes}-minute break${shift.break_start_at ? ` at ${localTime(shift.break_start_at, timezone)}` : ''}` : 'No scheduled break'}</p>{shift.locked && <p>{shift.lock_reason ?? 'Locked assignment'}</p>}{absences.some(a => a.employee_id === employee.id && a.status === 'confirmed' && Date.parse(a.start_at) < Date.parse(shift.end_at) && Date.parse(a.end_at) > Date.parse(shift.start_at)) && <p>Confirmed absence overlaps this shift.</p>}</details>) : <span className="contract-day-off">Day off</span>}</td>; })}</tr>)}</tbody></table></div>{open.length > 0 && <div className="surface-note"><strong>Unfilled assignments</strong>{open.map(shift => <p key={shift.logical_shift_id}>{skillLabel(shift.skill_id)} · {localDate(shift.start_at, timezone)} · {localTime(shift.start_at, timezone)}–{localTime(shift.end_at, timezone)}</p>)}</div>}</section>;
}

function RunResult({ run, skills, canSeeCosts, draftBusy, preview }: { run: Schema['OptimizationRun']; skills: Schema['Skill'][]; canSeeCosts: boolean; draftBusy: boolean; preview: (versionId: string) => void }) {
  const message = runMessage(run);
  return <section className={`run-result ${message.tone}`} aria-label="Optimization result"><div role="status" aria-live="polite"><h2>{message.title}</h2><p>{message.body}</p></div><p className="contract-run-id">Run {run.id} · {run.job_state}{run.solver_status && ` · ${run.solver_status}`}</p>{run.error?.trace_id && <p>Support trace: {run.error.trace_id}</p>}{run.infeasibility?.shortages.map((shortage, i) => <p key={i}>{skills.find(s => s.id === shortage.skill_id)?.name ?? 'Required skill'}: minimum {shortage.minimum_required}, at most {shortage.max_assignable} eligible.</p>)}{run.candidates.map(candidate => <article className="contract-candidate" key={candidate.id}><div><h3>{candidate.strategy.replaceAll('_', ' ')}</h3><p>{candidate.proven_optimal ? 'Proven optimal for its configured objective' : 'Feasible; optimality not proven'} · {candidate.changed_shifts} changed shifts</p><span>Preferred coverage {percent(candidate.metrics.coverage_ratio)}{canSeeCosts && ` · ${formatMoney(candidate.metrics.labour_cost)}`}</span></div><Button disabled={draftBusy} onClick={() => preview(candidate.draft_version_id)}>Preview draft<ArrowRightIcon size={14} /></Button></article>)}</section>;
}

function EmployeeWeek({ client }: { client: SchedulingClient }) {
  const [resource, setResource] = useState<Resource<Schema['MyWeek']> | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    client.myWeek('2026-10-19', controller.signal).then(data => { if (!controller.signal.aborted) setResource({ data }); }).catch(error => { if (!controller.signal.aborted) setResource({ error: asError(error) }); });
    return () => controller.abort();
  }, [client]);
  return <><div className="page-heading"><div><h1>Your week</h1><p>Your published assignments · 19–25 October 2026</p></div></div>{!resource ? <p role="status">Loading your assignments…</p> : resource.error ? <ErrorNotice error={resource.error} /> : <section className="data-surface">{resource.data.shifts.map(shift => { const outlet = resource.data.outlets.find(o => o.id === shift.outlet_id); const timezone = outlet?.timezone ?? 'Asia/Kolkata'; return <article className="employee-assignment" key={shift.logical_shift_id}><CalendarBlankIcon size={24} /><div><h2>{formatDate(localDate(shift.start_at, timezone), { weekday: 'long', day: 'numeric', month: 'long' })}</h2><p>{localTime(shift.start_at, timezone)}–{localTime(shift.end_at, timezone)} · {outlet?.name ?? 'Assigned outlet'}</p><span>{resource.data.skills.find(skill => skill.id === shift.skill_id)?.name ?? 'Assigned skill'} ? {shift.break_minutes ? `${shift.break_minutes}-minute break` : 'No scheduled break'}{shift.locked && ' · Locked assignment'}</span></div></article>; })}</section>}<p className="contract-note">Availability, leave and absence requests will appear here once the employee-request API is ready.</p></>;
}

function ErrorNotice({ error, onReload }: { error: Error; onReload?: () => void }) {
  const detail = error instanceof ApiError ? error.detail : null;
  return <section className="contract-error" role="alert"><WarningCircleIcon size={21} /><div><h2>{detail?.code === 'permission_denied' ? 'This schedule is outside your access.' : detail?.code === 'stale_version' ? 'This schedule has changed.' : 'We couldn’t load this request.'}</h2><p>{error.message}</p>{error instanceof ApiError && error.status === 429 && error.retryAfter && <p>Try again {/^\d+$/.test(error.retryAfter) ? `in ${error.retryAfter} seconds` : `after ${error.retryAfter}`}. Your request has not been retried.</p>}{detail?.trace_id && <small>Support trace: {detail.trace_id}</small>}{onReload && <Button onClick={onReload}>Reload latest schedule</Button>}</div></section>;
}
