'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { ArrowRightIcon, CalendarBlankIcon, CaretLeftIcon, CaretRightIcon, CompassIcon, LockSimpleIcon, SparkleIcon, WarningCircleIcon, CheckCircleIcon, ClockIcon, UsersThreeIcon, MapPinIcon, ListChecksIcon, CurrencyInrIcon } from '@phosphor-icons/react';
import manifest from '@/api/generated/manifest.json';
import { ApiError, SchedulingClient, generateOrAttach, watchRun } from '@/api/client';
import { formatMoney, localDate, localTime, percent, runMessage } from '@/api/presentation';
import type { Persona, Scenario, Schema } from '@/api/types';
import { addDays, days, formatDate } from '@/lib/types';
import { Avatar, Empty } from './ui';
import { AppearanceControls, WorkspaceNavigation, type SidebarMotion, type WorkspaceSection } from './workspace-navigation';
import { Button } from './primitives/button';
import { DemandScreen, TeamScreen } from './management';
import { CandidateReview, ProposalReview, strategyName } from './candidate-review';
import { DraftEditor } from './draft-editor';
import { PlanCompare } from './plan-compare';
import { Absences } from './absences';
import { ScheduleHistory } from './schedule-history';

type Session = { me: Schema['Me']; outlets: Schema['Outlet'][]; skills: Schema['Skill'][] };
type Resource<T> = { data: T; error?: never } | { error: Error; data?: never };
const skillColor = (name: string) => ({ grill: 'grill', prep: 'prep', server: 'service', cashier: 'cashier', barista: 'barista' })[name.toLowerCase()] ?? 'other';
const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';
const asError = (error: unknown) => error instanceof Error ? error : new Error('The scheduling service could not be reached.');

export function ContractWorkspace() {
  const [persona, setPersona] = useState<Persona>('manager');
  const [tone, setTone] = useState('ink');
  const [typography, setTypography] = useState('workshop');
  const [motion, setMotion] = useState<SidebarMotion>('dissolve');
  const [scenario, setScenario] = useState<Scenario>('optimal');
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '/api/fixture';
  const fixtureMode = baseUrl === '/api/fixture';
  return <div className="contract-app" data-tone={tone} data-typography={typography}>
    <a className="skip-link" href="#main-content">Skip to schedule</a>
    <header className="contract-header"><Link className="brand" href="/"><CompassIcon size={25} weight="fill" />ShiftPilot</Link><div className="contract-header-controls"><AppearanceControls {...{ tone, setTone, typography, setTypography, motion, setMotion }} /><span className="demo-badge"><span className="live-dot" />{fixtureMode ? 'Synthetic contract preview' : 'Connected scheduling API'}</span><label>View as<select aria-label="Demo persona" value={persona} onChange={e => setPersona(e.target.value as Persona)}><option value="manager">Manager</option><option value="owner">Owner</option><option value="staff">Employee</option></select></label></div></header>
    <SessionWorkspace key={`${persona}:${baseUrl}`} {...{ persona, scenario, baseUrl, fixtureMode, setScenario, motion }} />
  </div>;
}

function SessionWorkspace({ persona, scenario, baseUrl, fixtureMode, setScenario, motion }: { persona: Persona; scenario: Scenario; baseUrl: string; fixtureMode: boolean; setScenario: (scenario: Scenario) => void; motion: SidebarMotion }) {
  const [collapsed, setCollapsed] = useState(false);
  const [section, setSection] = useState<WorkspaceSection>('schedule');
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
  return <div className="contract-shell" data-collapsed={collapsed}><WorkspaceNavigation {...{ me: session.data.me, section, setSection, collapsed, setCollapsed, motion, fixtureMode, version: manifest.version }} /><main className="contract-content" id="main-content">{session.data.me.role === 'staff' ? <EmployeeWeek client={client} /> : <ManagerWeek {...{ client, session: session.data, fixtureMode, scenario, setScenario, section, setSection }} />}</main></div>;
}

function ManagerWeek({ client, session, fixtureMode, scenario, setScenario, section, setSection }: { client: SchedulingClient; session: Session; fixtureMode: boolean; scenario: Scenario; setScenario: (scenario: Scenario) => void; section: WorkspaceSection; setSection: (section: WorkspaceSection) => void }) {
  const [outletId, setOutletId] = useState(session.me.outlet_id ?? session.outlets[0]?.id ?? '');
  const [week, setWeek] = useState('2026-10-19');
  const outlet = session.outlets.find(o => o.id === outletId);
  return <><div className="page-heading"><div><h1>{section === 'absences' ? 'Repair Inbox' : section === 'team' ? 'Employees' : section === 'demand' ? 'Staffing' : section === 'history' ? 'Schedule history' : 'Weekly schedule'}</h1><p>{section === 'absences' ? 'Record time away, review repair options, and approve replacement assignments.' : section === 'team' ? 'Skills, working-hour limits and recurring availability.' : section === 'demand' ? 'Set minimum staffing and preferred coverage for your week.' : section === 'history' ? 'Compare saved versions and restore a plan for review.' : 'See who’s working, check coverage, and plan the week ahead.'}</p></div><label className="outlet-select"><MapPinIcon size={18} /><span>Outlet</span><select aria-label="Outlet" value={outletId} onChange={e => setOutletId(e.target.value)}>{session.outlets.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>
    {section !== 'team' && <div className="schedule-toolbar"><div className="week-controls"><button className="icon-button" aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))}><CaretLeftIcon size={18} /></button><strong>{formatDate(week)} – {formatDate(addDays(week, 6))}<small>{week.slice(0, 4)}</small></strong><button className="icon-button" aria-label="Next week" onClick={() => setWeek(addDays(week, 7))}><CaretRightIcon size={18} /></button></div>{fixtureMode && <label className="contract-scenario">Try a demo outcome<select aria-label="Demo outcome" value={scenario} onChange={e => { client.setFixtureScenario(e.target.value as Scenario); setScenario(e.target.value as Scenario); }}><option value="optimal">Optimal draft</option><option value="feasible">Time-limited feasible</option><option value="infeasible">Impossible requirements</option><option value="timeout">No solution in time</option><option value="failed">Worker failure</option><option value="stale">Stale schedule</option><option value="denied">Access denied</option><option value="active">Existing run</option><option value="rate_limited">Rate limit</option></select></label>}</div>}
    <nav className="management-nav" aria-label="Outlet workspace"><button aria-pressed={section === 'schedule'} onClick={() => setSection('schedule')}>Weekly roster</button><button aria-pressed={section === 'team'} onClick={() => setSection('team')}>Team and skills</button><button aria-pressed={section === 'demand'} onClick={() => setSection('demand')}>Staffing needs</button><button aria-pressed={section === 'absences'} onClick={() => setSection('absences')}>Repair Inbox</button><button aria-pressed={section === 'history'} onClick={() => setSection('history')}>History</button></nav>
    {section === 'absences' && outlet ? <Absences key={`absences:${outletId}:${week}:${scenario}`} {...{ client, outlet, week, fixtureMode }} me={session.me} skills={session.skills} /> : section === 'history' ? <ScheduleHistory key={`history:${outletId}:${week}:${scenario}`} {...{ client, outletId, week, fixtureMode }} timezone={outlet?.timezone ?? session.me.timezone} capabilities={session.me.capabilities} skills={session.skills} onSchedule={() => setSection('schedule')} /> : section === 'schedule' ? <RosterResource key={`${outletId}:${week}:${scenario}`} {...{ client, session, outletId, week, fixtureMode }} timezone={outlet?.timezone ?? session.me.timezone} onNextWeek={() => setWeek(addDays(week, 7))} /> : outlet && section === 'team' ? <TeamScreen key={`team:${outletId}`} {...{ client, outlet, skills: session.skills, capabilities: session.me.capabilities, fixtureMode }} /> : outlet && <DemandScreen key={`demand:${outletId}:${week}`} {...{ client, outlet, week, skills: session.skills, capabilities: session.me.capabilities, fixtureMode }} />}
  </>;
}

function RosterResource({ client, session, outletId, week, timezone, fixtureMode, onNextWeek }: { client: SchedulingClient; session: Session; outletId: string; week: string; timezone: string; fixtureMode: boolean; onNextWeek: () => void }) {
  const [resource, setResource] = useState<Resource<Schema['ScheduleWeek']> | null>(null);
  const [reload, setReload] = useState(0);
  const [run, setRun] = useState<Schema['OptimizationRun'] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Schema['ScheduleVersion'] | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [publication, setPublication] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draftNotice, setDraftNotice] = useState<string | null>(null);
  const createKeys = useRef(new Map<string, string>());
  const editTrigger = useRef<HTMLButtonElement>(null);
  const [query, setQuery] = useState('');
  const [selectedSkill, setSelectedSkill] = useState('all');
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
    setBusy(true); setError(null); setRun(null); setDraft(null); setEditing(false); setDraftNotice(null); setCandidateId(null); setPublication(null);
    try {
      const initial = await generateOrAttach(client, outletId, week, { strategy: 'balanced', base_version_id: schedule.current_version?.id ?? null, time_limit_seconds: 10 }, crypto.randomUUID(), controller.signal);
      await watchRun(client, initial, { signal: controller.signal, onUpdate: setRun });
    } catch (error) { if (!controller.signal.aborted) setError(asError(error)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  async function openDraft(versionId: string) {
    operation.current?.abort(); const controller = new AbortController(); operation.current = controller;
    setError(null); setDraftBusy(true);
    try { const value = await client.version(versionId, controller.signal); if (!controller.signal.aborted) { setDraft(value.status === 'draft' ? value : null); if (value.status !== 'draft') setError(new Error('This version is no longer a draft. Reload the latest week.')); } }
    catch (error) { if (!controller.signal.aborted) setError(asError(error)); }
    finally { if (!controller.signal.aborted) setDraftBusy(false); }
  }

  function reloadLatest() { operation.current?.abort(); setResource(null); setRun(null); setDraft(null); setEditing(false); setDraftNotice(null); setCandidateId(null); setError(null); setReload(r => r + 1); }
  function closeEditor() { setEditing(false); requestAnimationFrame(() => editTrigger.current?.focus()); }
  async function createEditingDraft() {
    if (draftBusy) return;
    operation.current?.abort(); const controller = new AbortController(); operation.current = controller;
    setDraftBusy(true); setError(null); setDraftNotice(null);
    const key = schedule.current_version?.id ?? 'empty';
    if (!createKeys.current.has(key)) createKeys.current.set(key, crypto.randomUUID());
    try { const value = await client.createDraft(outletId, week, { base_version_id: schedule.current_version?.id ?? null, copy_from_version_id: null }, createKeys.current.get(key)!, controller.signal); if (!controller.signal.aborted) { createKeys.current.delete(key); setDraft(value); setRun(null); setCandidateId(null); setEditing(true); } }
    catch (error) { if (!controller.signal.aborted) setError(asError(error)); }
    finally { if (!controller.signal.aborted) setDraftBusy(false); }
  }

  return <>
    {publication && <p className="save-notice" role="status">{publication}</p>}
    {draftNotice && <p className="save-notice" role="status">{draftNotice}</p>}
    <section className={`week-state ${draft ? 'draft' : schedule.current_version ? 'published' : 'unplanned'}`} aria-label="Week status">
      <div className="week-state-icon">{draft ? <ListChecksIcon size={25} /> : schedule.current_version ? <CheckCircleIcon size={25} weight="duotone" /> : <CalendarBlankIcon size={25} />}</div>
      <div className="week-state-copy"><strong>{draft ? 'Draft preview · not published' : schedule.current_version ? `Published version ${schedule.current_version.version_number}` : 'No published schedule'}</strong><p>{draft ? 'Review assignments and coverage before approving any changes.' : schedule.current_version ? 'This is the published roster. Drafts are reviewed separately.' : 'Start with a draft built from team availability, skills and staffing needs.'}</p></div>
      <div className="week-state-actions">{fixtureMode && week === '2026-10-19' && <Button onClick={onNextWeek}>Plan upcoming week<ArrowRightIcon size={16} /></Button>}{canGenerate && <Button variant="primary" onClick={generate} disabled={busy || (fixtureMode && week !== '2026-10-26')}><SparkleIcon size={18} weight="duotone" />{busy ? 'Generating…' : 'Generate draft'}</Button>}</div>
    </section>
    {fixtureMode && week === '2026-10-19' && <p className="contract-note generation-hint">Generation is available in next week’s demo. Choose “Plan upcoming week” to try it.</p>}
    {version && <>
      <div className="week-facts" aria-label="Week at a glance"><span><UsersThreeIcon size={17} />{schedule.employees.length} team members</span><span><CalendarBlankIcon size={17} />{version.shifts.length} shifts</span><span><LockSimpleIcon size={17} />{version.shifts.filter(shift => shift.locked).length} locked {version.shifts.filter(shift => shift.locked).length === 1 ? 'assignment' : 'assignments'}</span><span><ClockIcon size={17} />Times in {timezone}</span></div>
      <MetricStrip metrics={version.metrics} showCosts={canSeeCosts} />
    </>}
    {error && <ErrorNotice error={error} onReload={error instanceof ApiError && error.detail.code === 'stale_version' ? () => { setResource(null); setRun(null); setDraft(null); setError(null); setReload(r => r + 1); } : undefined} />}
    {run && <PlanCompare run={run} baseline={schedule.current_version} showCosts={canSeeCosts} />}
    {run && <RunResult {...{ run, skills: session.skills, canSeeCosts }} review={id => setCandidateId(id)} />}
    {candidateId && <CandidateReview key={candidateId} {...{ client, timezone }} candidateId={candidateId} employees={schedule.employees} skills={session.skills} canSelect={session.me.capabilities.includes('publish')} showCosts={canSeeCosts} onSelected={value => { setDraft(value); setEditing(false); setDraftNotice(null); setCandidateId(null); }} onClose={() => setCandidateId(null)} />}
    {!draft && schedule.drafts.length > 0 && <section className="existing-drafts" aria-label="Saved drafts"><h2>Saved drafts</h2>{schedule.drafts.map(value => <Button key={value.id} disabled={draftBusy} onClick={() => openDraft(value.id)}>Open draft {value.version_number} (revision {value.revision})</Button>)}</section>}
    {session.me.capabilities.includes('publish') && <div className="draft-edit-actions">{!draft && schedule.current_version && <Button disabled={draftBusy || busy} onClick={createEditingDraft}>{draftBusy ? 'Creating editing draft…' : 'Create editing draft'}</Button>}{draft && !editing && <Button ref={editTrigger} onClick={() => { setDraftNotice(null); setEditing(true); }}>Edit draft assignments</Button>}</div>}
    {draft && editing && <DraftEditor key={`${draft.id}:${draft.revision}`} {...{ client, draft, timezone, fixtureMode }} employees={schedule.employees} skills={session.skills} showCosts={canSeeCosts} onClose={closeEditor} onUpdated={(value, notice) => { setDraft(value); setDraftNotice(notice); closeEditor(); }} />}
    {draft && session.me.capabilities.includes('publish') && <div hidden={editing}><ProposalReview key={`${draft.id}:${draft.revision}`} {...{ client, draft, timezone, fixtureMode }} showCosts={canSeeCosts} onReload={reloadLatest} onPublished={result => { setPublication(`Published version ${result.published!.version_number}. ${fixtureMode ? 'This is a synthetic preview; no real schedule was changed.' : 'The scheduling service confirmed publication.'}`); reloadLatest(); }} /></div>}
    {version && <>
      <div className="contract-roster-heading"><div><h2>{draft ? 'Proposed roster' : 'Published roster'}</h2><p>Expand a shift for break times and lock details. Scroll across to see all seven days.</p></div>{draft && <Button onClick={() => { setDraft(null); setEditing(false); setCandidateId(null); }}>Back to published week</Button>}<label className="search-field"><span className="sr-only">Find a teammate</span><input aria-label="Find a teammate" placeholder="Find a teammate…" value={query} onChange={e => setQuery(e.target.value)} /></label></div>
      <div className="skill-filter" aria-label="Filter team by skill"><span>Team skills</span><button type="button" aria-pressed={selectedSkill === 'all'} onClick={() => setSelectedSkill('all')}>All skills</button>{session.skills.map(skill => <button type="button" key={skill.id} className={`role-key ${skillColor(skill.name)}`} aria-pressed={selectedSkill === skill.id} onClick={() => setSelectedSkill(selectedSkill === skill.id ? 'all' : skill.id)}><span aria-hidden="true" />{skill.name}</button>)}</div>
      <ContractRoster version={version} employees={schedule.employees.filter(e => e.name.toLowerCase().includes(query.toLowerCase()) && (selectedSkill === 'all' || e.skill_ids.includes(selectedSkill)))} skills={session.skills} week={week} timezone={timezone} absences={schedule.absences} />
      <div className="contract-validation"><strong className={version.validation.hard_violations ? 'has-violations' : ''}><CheckCircleIcon size={17} />{version.validation.hard_violations} hard violations reported</strong><span>{version.validation.soft_violations} preferences to review</span><span>{version.metrics.open_shifts} open shifts</span></div>
      <WeekReview version={version} skills={session.skills} timezone={timezone} />
    </>}
    {!version && <Empty title="A fresh week, ready to plan." description="Generate a draft from this week’s employees, staffing requirements and rules. Your published roster will remain unchanged." />}
    <p className="contract-note">{fixtureMode ? 'All values are synthetic provider fixtures, not a live solve. ' : ''}Selecting creates a draft. Proposal approval checks current facts before publishing. Assignment edits use server previews. Open Repair Inbox to record an absence and review recovery options.</p>
  </>;
}

function MetricStrip({ metrics, showCosts }: { metrics: Schema['Metrics']; showCosts: boolean }) {
  return <section className="contract-metrics" aria-label="Schedule metrics">
    <div className="metric-coverage"><span><UsersThreeIcon size={18} />Preferred coverage</span><strong>{percent(metrics.coverage_ratio)}</strong>{metrics.coverage_ratio !== null && <meter aria-label="Preferred staffing coverage" min={0} max={1} value={metrics.coverage_ratio} />}<p>Coverage against preferred staffing. Overstaffing doesn’t increase this score.</p></div>
    <div><span><ClockIcon size={18} />Assigned time</span><strong>{metrics.assigned_minutes / 60}<small> hours</small></strong><p>{metrics.overtime_minutes / 60} hours of overtime included.</p></div>
    {showCosts && <div><span><CurrencyInrIcon size={18} />Estimated labour cost</span><strong>{formatMoney(metrics.labour_cost)}</strong><p>Includes {formatMoney(metrics.overtime_cost)} in overtime. Estimate, not payroll.</p></div>}
    <div className={metrics.minimum_deficit_minutes > 0 ? 'metric-shortfall' : 'metric-minimum'}><span><ListChecksIcon size={18} />Hard minimum shortfall</span><strong>{metrics.minimum_deficit_minutes}<small> staff-minutes</small></strong><p>{metrics.minimum_deficit_minutes === 0 ? 'Required minimum staffing is covered.' : 'Required staffing is missing. Review the gaps below.'}</p></div>
  </section>;
}

function WeekReview({ version, skills, timezone }: { version: Schema['ScheduleVersion']; skills: Schema['Skill'][]; timezone: string }) {
  const gaps = version.coverage.filter(cell => cell.scheduled < cell.preferred_required).sort((a, b) => (b.minimum_required - b.scheduled) - (a.minimum_required - a.scheduled) || a.interval_start.localeCompare(b.interval_start));
  return <section className="week-review" aria-label="Schedule review">
    <div className="review-explanation"><h2>What needs a closer look?</h2><p>Minimum staffing is required. Preferred staffing is a target for a better-covered week.</p><dl><div><dt>Preferred staffing gap</dt><dd>{version.metrics.preferred_deficit_minutes.toLocaleString('en-IN')} staff-minutes</dd></div><div><dt>Employee preference match</dt><dd>{percent(version.metrics.preference_match_ratio)}</dd></div></dl><p className="review-footnote">One staff-minute means one person for one minute. These totals come from the scheduling service.</p></div>
    <div className="review-gaps"><h3>{gaps.length ? 'Staffing gaps to review' : version.coverage.length ? 'No preferred staffing gaps reported' : 'No coverage intervals reported'}</h3>{gaps.length ? <><p>Showing {Math.min(4, gaps.length)} of {gaps.length} intervals, with minimum gaps first.</p><ul>{gaps.slice(0, 4).map((cell, index) => <li key={`${cell.skill_id}:${cell.interval_start}:${index}`}><span className={`role-label ${skillColor(skills.find(skill => skill.id === cell.skill_id)?.name ?? '')}`}>{skills.find(skill => skill.id === cell.skill_id)?.name ?? 'Required skill'}</span><div><strong>{formatDate(localDate(cell.interval_start, timezone), { weekday: 'short', day: 'numeric', month: 'short' })} · {localTime(cell.interval_start, timezone)}</strong><span>{cell.scheduled} scheduled / {cell.minimum_required} minimum / {cell.preferred_required} preferred</span></div></li>)}</ul></> : <p>{version.coverage.length ? 'Every reported interval meets its preferred target.' : 'Coverage details are not available for this version.'}</p>}</div>
    {version.validation.violations.length > 0 && <details className="contract-details"><summary>Review {version.validation.violations.length} reported constraints and preferences</summary><ul>{version.validation.violations.map((issue, i) => <li key={`${issue.code}:${i}`}><span className="neutral-badge">{issue.severity}</span>{issue.message}</li>)}</ul></details>}
  </section>;
}

function ContractRoster({ version, employees, skills, week, timezone, absences }: { version: Schema['ScheduleVersion']; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; week: string; timezone: string; absences: Schema['AbsenceMark'][] }) {
  const skillLabel = (id: string) => skills.find(s => s.id === id)?.name ?? 'Assigned skill';
  const skillClass = (id: string) => skillColor(skillLabel(id));
  const employeeHours = (employee: Schema['RosterEmployee']) => version.status === 'draft'
    ? `${version.shifts.filter(shift => shift.employee_id === employee.id).reduce((minutes, shift) => minutes + (Date.parse(shift.end_at) - Date.parse(shift.start_at)) / 60000 - shift.break_minutes, 0) / 60}h in this draft`
    : `${employee.scheduled_minutes / 60}h / ${employee.regular_weekly_minutes / 60}h regular`;
  const open = version.shifts.filter(s => s.employee_id === null);
  return <section className="roster-section"><div className="roster-scroll"><table className="roster contract-roster"><caption className="sr-only">Weekly roster. Times shown in {timezone}. Shift details include template break duration and locks.</caption><thead><tr><th scope="col">Team member<small>{version.status === 'draft' ? 'Hours in this draft' : 'Hours across all outlets'}</small></th>{days.map((day, index) => <th scope="col" key={day}><span>{day}</span><strong>{formatDate(addDays(week, index), { day: 'numeric' })}</strong><small>{version.shifts.filter(shift => localDate(shift.start_at, timezone) === addDays(week, index)).length} shifts</small></th>)}</tr></thead><tbody>{employees.map(employee => <tr key={employee.id}><th scope="row"><div className="employee-cell"><Avatar initials={employee.name.split(' ').map(n => n[0]).slice(0, 2).join('')} color="sage" /><div><strong>{employee.name}</strong><span>{employeeHours(employee)}</span><small>{employee.skill_ids.map(skillLabel).join(' · ')}</small></div></div></th>{days.map((day, index) => { const shifts = version.shifts.filter(s => s.employee_id === employee.id && localDate(s.start_at, timezone) === addDays(week, index)); return <td key={day}>{shifts.length ? shifts.map(shift => <details className={`shift contract-shift ${skillClass(shift.skill_id)}`} key={shift.logical_shift_id}><summary>{localTime(shift.start_at, timezone)} – {localTime(shift.end_at, timezone)}{localDate(shift.end_at, timezone) !== localDate(shift.start_at, timezone) && ' (+1 day)'}{shift.locked && <LockSimpleIcon size={12} weight="fill" />}<small>{skillLabel(shift.skill_id)}</small><span className="shift-meta">{shift.break_minutes ? `${shift.break_minutes}m break` : 'No break'}{shift.locked && ' · Locked'}</span></summary><p>{shift.break_minutes ? `${shift.break_minutes}-minute break${shift.break_start_at ? ` at ${localTime(shift.break_start_at, timezone)}` : ''}` : 'No scheduled break'}</p>{shift.locked && <p>{shift.lock_reason ?? 'Locked assignment'}</p>}{absences.some(a => a.employee_id === employee.id && a.status === 'confirmed' && Date.parse(a.start_at) < Date.parse(shift.end_at) && Date.parse(a.end_at) > Date.parse(shift.start_at)) && <p>Confirmed absence overlaps this shift.</p>}</details>) : <span className="contract-day-off">Day off</span>}</td>; })}</tr>)}</tbody></table></div>{employees.length === 0 && <p className="roster-no-results" role="status">No teammates match these filters. Try another name or select All skills.</p>}{open.length > 0 && <div className="surface-note"><strong>Unfilled assignments</strong>{open.map(shift => <p key={shift.logical_shift_id}>{skillLabel(shift.skill_id)} · {localDate(shift.start_at, timezone)} · {localTime(shift.start_at, timezone)}–{localTime(shift.end_at, timezone)}</p>)}</div>}</section>;
}

function RunResult({ run, skills, canSeeCosts, review }: { run: Schema['OptimizationRun']; skills: Schema['Skill'][]; canSeeCosts: boolean; review: (candidateId: string) => void }) {
  const message = runMessage(run);
  return <section className={`run-result ${message.tone}`} aria-label="Optimization result"><div role="status" aria-live="polite"><h2>{message.title}</h2><p>{message.body}</p></div><p className="contract-run-id">Run {run.id} · {run.job_state}{run.solver_status && ` · ${run.solver_status}`}</p>{run.error?.trace_id && <p>Support trace: {run.error.trace_id}</p>}{run.infeasibility?.shortages.map((shortage, i) => <p key={i}>{skills.find(s => s.id === shortage.skill_id)?.name ?? 'Required skill'}: minimum {shortage.minimum_required}, at most {shortage.max_assignable} eligible.</p>)}{run.candidates.map(candidate => <article className="contract-candidate" key={candidate.id}><div><h3>{strategyName(candidate.strategy)}</h3><p>{candidate.proven_optimal ? 'Proven optimal for its configured objective' : 'Feasible; optimality not proven'} · {candidate.changed_shifts} changed shifts</p><span>Preferred coverage {percent(candidate.metrics.coverage_ratio)}{canSeeCosts && ` · ${formatMoney(candidate.metrics.labour_cost)}`}</span></div><Button onClick={() => review(candidate.id)}>Review option<ArrowRightIcon size={14} /></Button></article>)}</section>;
}

function EmployeeWeek({ client }: { client: SchedulingClient }) {
  const [resource, setResource] = useState<Resource<Schema['MyWeek']> | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    client.myWeek('2026-10-19', controller.signal).then(data => { if (!controller.signal.aborted) setResource({ data }); }).catch(error => { if (!controller.signal.aborted) setResource({ error: asError(error) }); });
    return () => controller.abort();
  }, [client]);
  return <><div className="page-heading"><div><h1>Your week</h1><p>Your published assignments · 19–25 October 2026</p></div></div>{!resource ? <p role="status">Loading your assignments…</p> : resource.error ? <ErrorNotice error={resource.error} /> : <section className="data-surface">{resource.data.shifts.map(shift => { const outlet = resource.data.outlets.find(o => o.id === shift.outlet_id); const timezone = outlet?.timezone ?? 'Asia/Kolkata'; return <article className="employee-assignment" key={shift.logical_shift_id}><CalendarBlankIcon size={24} /><div><h2>{formatDate(localDate(shift.start_at, timezone), { weekday: 'long', day: 'numeric', month: 'long' })}</h2><p>{localTime(shift.start_at, timezone)}–{localTime(shift.end_at, timezone)} · {outlet?.name ?? 'Assigned outlet'}</p><span>{resource.data.skills.find(skill => skill.id === shift.skill_id)?.name ?? 'Assigned skill'} · {shift.break_minutes ? `${shift.break_minutes}-minute break` : 'No scheduled break'}{shift.locked && ' · Locked assignment'}</span></div></article>; })}</section>}<p className="contract-note">Availability, leave and absence requests will appear here once the employee-request API is ready.</p></>;
}

function ErrorNotice({ error, onReload }: { error: Error; onReload?: () => void }) {
  const detail = error instanceof ApiError ? error.detail : null;
  return <section className="contract-error" role="alert"><WarningCircleIcon size={21} /><div><h2>{detail?.code === 'permission_denied' ? 'This schedule is outside your access.' : detail?.code === 'stale_version' ? 'This schedule has changed.' : 'We couldn’t load this request.'}</h2><p>{error.message}</p>{error instanceof ApiError && error.status === 429 && error.retryAfter && <p>Try again {/^\d+$/.test(error.retryAfter) ? `in ${error.retryAfter} seconds` : `after ${error.retryAfter}`}. Your request has not been retried.</p>}{detail?.trace_id && <small>Support trace: {detail.trace_id}</small>}{onReload && <Button onClick={onReload}>Reload latest schedule</Button>}</div></section>;
}
