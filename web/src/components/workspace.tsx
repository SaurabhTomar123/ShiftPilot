'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowCounterClockwiseIcon, ArrowRightIcon, ArrowUpRightIcon, BellIcon,
  CalendarBlankIcon, CaretDownIcon, CaretLeftIcon, CaretRightIcon, ChartBarIcon,
  CheckIcon, ClockCounterClockwiseIcon, CompassIcon, DownloadSimpleIcon,
  FunnelIcon, GearSixIcon, ListIcon, LockSimpleIcon, MagnifyingGlassIcon,
  PlusIcon, QuestionIcon, SlidersHorizontalIcon, SparkleIcon, TrayIcon,
  UsersThreeIcon, WarningCircleIcon, XIcon,
} from '@phosphor-icons/react';
import { createDemo, makeRoster, readDemo } from '@/lib/demo';
import {
  addDays, DEMO_WEEK, DemoState, days, duration, Employee, formatDate, money,
  OutletId, outlets, Role, roleClass, roles, rosterKey, Shift, shiftHours, STORAGE_KEY, View,
} from '@/lib/types';
import { Avatar, Dialog, Empty } from './ui';
import { DraggableShift, EmptyRosterCell, RosterDragContext } from './roster-drag';

const navigation = [
  { name: 'Schedule' as View, icon: CalendarBlankIcon },
  { name: 'Team' as View, icon: UsersThreeIcon },
  { name: 'Demand' as View, icon: ChartBarIcon },
  { name: 'Requests' as View, icon: TrayIcon },
  { name: 'Rules' as View, icon: SlidersHorizontalIcon },
  { name: 'History' as View, icon: ClockCounterClockwiseIcon },
];

type EditTarget = { employeeId: string; day: number; shift?: Shift };
type Modal = 'generate' | 'publish' | 'help' | 'settings' | 'employee' | 'rule' | 'reset' | null;

export function Workspace() {
  const [data, setData] = useState<DemoState>(createDemo);
  const [loaded, setLoaded] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const [view, setView] = useState<View>('Schedule');
  const [outlet, setOutlet] = useState<OutletId>('indiranagar');
  const [week, setWeek] = useState(DEMO_WEEK);
  const [query, setQuery] = useState('');
  const [role, setRole] = useState<Role | 'All roles'>('All roles');
  const [rows, setRows] = useState(10);
  const [mobileNav, setMobileNav] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [edit, setEdit] = useState<EditTarget | null>(null);
  const [repair, setRepair] = useState<Shift | null>(null);
  const [replacement, setReplacement] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Hydrate the browser-only sandbox from external storage after server rendering.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setData(readDemo(localStorage.getItem(STORAGE_KEY))); } catch { setStorageError(true); }
    setLoaded(true);
  }, []);
  useEffect(() => {
    if (!loaded) return;
    // Report an external persistence failure; retain the usable in-memory sandbox.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch { setStorageError(true); }
  }, [data, loaded]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 6500);
    return () => clearTimeout(timer);
  }, [notice]);

  const key = rosterKey(outlet, week);
  const shifts = useMemo(() => data.rosters[key] ?? (week === DEMO_WEEK ? makeRoster(data.employees, outlet) : []), [data.rosters, data.employees, key, outlet, week]);
  const employees = data.employees.filter(e => e.outletId === outlet);
  const filtered = employees.filter(e => (role === 'All roles' || e.role === role) && `${e.name} ${e.role}`.toLowerCase().includes(query.toLowerCase()));
  const outletInfo = outlets.find(o => o.id === outlet)!;
  const scopedRequests = data.requests.filter(r => r.outletId === outlet);
  const pending = scopedRequests.filter(r => r.status === 'Pending').length;
  const versions = data.versions.filter(v => v.outletId === outlet && v.week === week);
  const latest = versions[0];
  const dirty = !latest || JSON.stringify(latest.shifts) !== JSON.stringify(shifts);
  const totalHours = shifts.filter(s => !s.absent).reduce((sum, s) => sum + duration(s.start, s.end), 0);
  const estimatedCost = shifts.filter(s => !s.absent).reduce((sum, s) => sum + duration(s.start, s.end) * (data.employees.find(e => e.id === s.employeeId)?.rate ?? 0), 0);
  const baseDemand = data.demand[key] ?? [3, 3, 3, 4, 5, 5, 4];
  const dinnerCounts = days.map((_, day) => shifts.filter(s => s.day === day && s.role === 'Kitchen' && !s.absent && s.start <= '18:00' && s.end >= '22:00').length);
  const shortages = dinnerCounts.map((n, i) => Math.max(0, baseDemand[i] - n));
  const problemDay = shortages[4] > 0 ? 4 : shortages.findIndex(n => n > 0);
  const availableReplacements = repair ? employees.filter(e => e.id !== repair.employeeId && e.role === repair.role && !shifts.some(s => s.employeeId === e.id && s.day === repair.day && !s.absent)) : [];

  function changeRoster(next: Shift[]) { setData(d => ({ ...d, rosters: { ...d.rosters, [key]: next } })); }
  function navigate(next: View) { setView(next); setMobileNav(false); setQuery(''); }
  function switchOutlet(next: OutletId) { setOutlet(next); setRows(10); setQuery(''); setRole('All roles'); setRepair(null); }
  function flash(message: string) { setNotice(message); }
  function startRepair(shift: Shift) {
    if (shift.locked) { flash('Unlock this shift before trying the absence demo.'); return; }
    setRepair(shift); setReplacement('');
  }
  function publish() {
    setData(d => ({ ...d, versions: [{ id: crypto.randomUUID(), label: `Schedule published · ${shifts.length} assignments`, at: new Date().toISOString(), outletId: outlet, week, shifts: structuredClone(shifts) }, ...d.versions] }));
    setModal(null); flash('Demo schedule published. A version has been saved in this browser.');
  }
  function download() {
    const csv = ['Employee,Day,Start,End,Role,Locked,Absent', ...shifts.map(s => [data.employees.find(e => e.id === s.employeeId)?.name, addDays(week, s.day), s.start, s.end, s.role, s.locked, !!s.absent].join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `shiftpilot-${outlet}-${week}.csv`; anchor.click(); URL.revokeObjectURL(url);
    flash('Roster exported as CSV.');
  }

  return <div className="workspace">
    <a className="skip-link" href="#main-content">Skip to schedule</a>
    {mobileNav && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`} aria-label="Main navigation">
      <a href="/" className="brand"><span className="brand-mark"><CompassIcon size={25} weight="fill" /></span>shiftpilot<span className="brand-dot">.</span></a>
      <button className="workspace-selector" onClick={() => setModal('settings')}><span className="workspace-letter">B</span><span>Brew & Co.<small>Restaurant workspace</small></span><CaretDownIcon size={14} /></button>
      <div className="nav-label">WORKSPACE</div>
      <nav>{navigation.map(item => <button key={item.name} className={`nav-item ${view === item.name ? 'active' : ''}`} onClick={() => navigate(item.name)} aria-current={view === item.name ? 'page' : undefined}><item.icon size={19} weight={view === item.name ? 'fill' : 'regular'} /><span>{item.name}</span>{item.name === 'Requests' && pending > 0 && <span className="nav-count">{pending}</span>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="demo-note"><span className="live-dot" /><strong>A little room to try things.</strong><p>This is a synthetic demo. Changes stay in your browser.</p><button onClick={() => setModal('reset')}>Reset demo <ArrowCounterClockwiseIcon size={13} /></button></div>
        <button className="nav-item" onClick={() => setModal('help')}><QuestionIcon size={19} /><span>Help & shortcuts</span><ArrowUpRightIcon size={14} /></button>
        <button className="nav-item" onClick={() => setModal('settings')}><GearSixIcon size={19} /><span>Workspace settings</span></button>
        <div className="profile"><Avatar initials="PN" color="lilac" /><span>Priya Nair<small>Demo manager</small></span><span className="online-dot" /></div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><ListIcon size={22} /></button><span className="breadcrumb-workspace">Workspace <span>/</span></span><strong>{view}</strong></div>
        <div className="topbar-actions"><span className="demo-badge"><span className="live-dot" />Synthetic browser demo</span><span className="topbar-divider" /><button className="icon-button notification-button" aria-label={`View ${pending} pending requests`} onClick={() => navigate('Requests')}><BellIcon size={20} />{pending > 0 && <i />}</button><Avatar initials="PN" color="lilac" small /></div>
      </header>

      <main id="main-content" className="main-content">
        {storageError && <div role="alert" className="storage-warning">Browser storage is unavailable. You can explore, but changes will be lost when you reload.</div>}
        <div className="page-heading"><div><h1>{view === 'Schedule' ? 'Weekly schedule' : view === 'Team' ? 'Your team' : view === 'Demand' ? 'Staffing demand' : view === 'Requests' ? 'Employee requests' : view === 'Rules' ? 'Scheduling rules' : 'Schedule history'}</h1><p>{view === 'Schedule' ? 'A little planning. A better week for everyone.' : view === 'Team' ? 'The people who make every shift work.' : view === 'Demand' ? 'Set the staffing targets your roster works toward.' : view === 'Requests' ? 'A clear place for time off, availability, and swaps.' : view === 'Rules' ? 'Your operating rules, made explicit.' : 'Every published week, with a way back.'}</p></div>
          <label className="outlet-select"><span className="outlet-pin"><CompassIcon size={17} /></span><select aria-label="Outlet" value={outlet} onChange={e => switchOutlet(e.target.value as OutletId)}>{outlets.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select><CaretDownIcon size={13} /></label>
        </div>

        {view === 'Schedule' && <>
          <section className="schedule-summary" aria-label="Demo roster summary"><div className="summary-primary"><span className="summary-icon"><CalendarBlankIcon size={22} /></span><div><strong>{shifts.length} shifts planned</strong><span>{employees.length} team members · {outletInfo.name}</span></div></div><div><span>Scheduled hours</span><strong>{totalHours}<small> hrs</small></strong></div><div><span>Estimated base cost</span><strong>{money(estimatedCost)}</strong></div><div><span>Roster status</span><strong className="status-label"><span className={`status-dot ${dirty ? 'amber' : ''}`} />{dirty ? 'Unpublished draft' : 'Published locally'}</strong></div></section>
          <div className="schedule-toolbar"><div className="week-controls"><button className="icon-button" aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))}><CaretLeftIcon size={17} /></button><strong>{formatDate(week)} – {formatDate(addDays(week, 6))}<small>{week.slice(0, 4)}</small></strong><button className="icon-button" aria-label="Next week" onClick={() => setWeek(addDays(week, 7))}><CaretRightIcon size={17} /></button><button className="button subtle small-button" onClick={() => setWeek(DEMO_WEEK)}>Demo week</button></div><div className="toolbar-actions"><button className="button" onClick={download} disabled={!shifts.length} aria-label="Export roster CSV"><DownloadSimpleIcon size={17} /><span className="optional-label">Export</span></button><button className="button" onClick={() => setModal('generate')} disabled={!loaded}><SparkleIcon size={17} />Generate week</button><button className="button primary" onClick={() => setModal('publish')} disabled={!shifts.length || !dirty}>Publish schedule<ArrowUpRightIcon size={16} /></button></div></div>
          <RosterDragContext onMove={(shiftId, target) => {
            const source = shifts.find(s => s.id === shiftId);
            const employee = employees.find(e => e.id === target.employeeId);
            if (!source || source.locked || !employee) return;
            if (source.role !== employee.role) { flash('Demo edit blocked: this employee has a different role.'); return; }
            setEdit({ employeeId: employee.id, day: target.day, shift: { ...source, employeeId: employee.id, day: target.day } });
          }}><div className="schedule-layout"><section className="roster-section" aria-label="Weekly roster">
            <div className="roster-filters"><div className="view-tabs"><span className="selected"><UsersThreeIcon size={16} />By employee</span><span className="view-subtitle">All shifts · IST</span></div><div className="filter-controls"><label className="search-field"><MagnifyingGlassIcon size={16} /><input aria-label="Search team" placeholder="Find a teammate" value={query} onChange={e => setQuery(e.target.value)} /></label><label className="role-filter"><FunnelIcon size={15} /><select aria-label="Filter role" value={role} onChange={e => setRole(e.target.value as Role | 'All roles')}><option>All roles</option>{roles.map(r => <option key={r}>{r}</option>)}</select></label></div></div>
            {!loaded ? <div className="roster-loading" aria-label="Loading roster"><div /><div /><div /><div /><div /></div> : !shifts.length ? <Empty title="A fresh week, ready to plan." description="Load a synthetic week to explore the roster, or add a shift from a teammate’s day."><button className="button primary" onClick={() => setModal('generate')}><SparkleIcon size={17} />Generate demo week</button></Empty> : !filtered.length ? <Empty title="No teammates found" description="Try a different name or role filter."><button className="button" onClick={() => { setQuery(''); setRole('All roles'); }}>Clear filters</button></Empty> : <div className="roster-scroll"><table className="roster"><thead><tr><th scope="col">Team member <span>{filtered.length}</span></th>{days.map((day, i) => <th scope="col" key={day} className={i === 4 ? 'highlight-day' : ''}><span>{day}</span><strong>{formatDate(addDays(week, i), { day: 'numeric' })}</strong>{i === 4 && <i className="day-indicator" />}</th>)}</tr></thead><tbody>{filtered.slice(0, rows).map(employee => <tr key={employee.id}><th scope="row"><div className="employee-cell"><Avatar initials={employee.initials} color={employee.color} /><div><strong>{employee.name}</strong><span>{employee.role}<b>·</b>{shiftHours(shifts, employee.id)}h</span></div></div></th>{days.map((day, index) => { const shift = shifts.find(s => s.employeeId === employee.id && s.day === index); return <td key={day} className={index === 4 ? 'highlight-day' : ''}>{shift ? <DraggableShift id={shift.id} locked={shift.locked} className={`shift ${roleClass(shift.role)} ${shift.absent ? 'absent' : ''}`} onClick={() => setEdit({ employeeId: employee.id, day: index, shift })} label={`Edit ${employee.name}, ${day}, ${shift.start} to ${shift.end}${shift.locked ? ', locked' : ''}`}><span>{shift.start} – {shift.end}{shift.locked && <LockSimpleIcon size={11} weight="fill" />}</span><small>{shift.absent ? 'Absent · needs cover' : shift.role}</small></DraggableShift> : <EmptyRosterCell employeeId={employee.id} day={index} label={`Add shift for ${employee.name} on ${day}`} onClick={() => setEdit({ employeeId: employee.id, day: index })}><span>Day off</span><PlusIcon size={14} /></EmptyRosterCell>}</td>; })}</tr>)}</tbody></table></div>}
            <div className="roster-footer"><div className="legend">{roles.map(r => <span key={r}><i className={roleClass(r)} />{r}</span>)}</div><span className="autosave"><span className="live-dot" />{storageError ? 'Session only' : 'Saved on this device'}</span></div>
            {filtered.length > 10 && <button className="show-more" onClick={() => setRows(rows === 10 ? filtered.length : 10)}>{rows === 10 ? `Show all ${filtered.length} team members` : 'Show fewer team members'}<CaretDownIcon size={13} /></button>}
          </section>
          <aside className="insights" aria-label="Schedule planning notes"><div className="insight-heading"><span className="sparkle-tile"><SparkleIcon size={18} weight="fill" /></span><h2>A second pair of eyes</h2></div><p className="insight-intro">A few things to keep this week running smoothly.</p>
            <div className="coverage-note"><span className="warning-label"><WarningCircleIcon size={15} weight="fill" />Coverage to review</span><h3>{problemDay >= 0 ? `${days[problemDay]} dinner needs a hand.` : 'Dinner coverage is in place.'}</h3><p>{problemDay >= 0 ? `${dinnerCounts[problemDay]} kitchen staff scheduled for 18:00–22:00. Your demo target is ${baseDemand[problemDay]}.` : 'The demo’s kitchen dinner targets are covered.'}</p><div className="coverage-blocks" aria-hidden="true">{Array.from({ length: baseDemand[Math.max(0, problemDay)] }, (_, i) => <i key={i} className={i < dinnerCounts[Math.max(0, problemDay)] ? 'filled' : ''} />)}</div><button onClick={() => navigate('Demand')}>Review staffing demand<ArrowRightIcon size={15} /></button></div>
            <div className="insight-row"><span className="insight-icon lavender"><LockSimpleIcon size={17} /></span><div><strong>Your decisions stay put.</strong><p>{shifts.filter(s => s.locked).length} locked shifts in this draft. Unlock a shift before editing it.</p></div></div>
            <div className="insight-row"><span className="insight-icon peach"><TrayIcon size={17} /></span><div><strong>{pending} requests to review</strong><p>Your team’s plans are part of the picture.</p><button className="text-button" onClick={() => navigate('Requests')}>Open requests<ArrowUpRightIcon size={13} /></button></div></div>
            <div className="try-scenario"><h3>Plans change.<br />Your week can adapt.</h3><p>Mark a shift absent and preview a replacement.</p><button className="button" onClick={() => { const shift = shifts.find(s => !s.locked && !s.absent && s.role === 'Kitchen'); if (shift) startRepair(shift); else flash('Generate a week with an unlocked kitchen shift first.'); }}>Try an absence<ArrowRightIcon size={15} /></button></div>
          </aside></div></RosterDragContext>
          <section className="coverage-strip" aria-label="Kitchen dinner coverage"><div><ChartBarIcon size={18} /><strong>Dinner coverage</strong><span>Kitchen · 18:00–22:00</span></div><div className="coverage-days">{days.map((day, i) => <button key={day} onClick={() => navigate('Demand')} aria-label={`${day}: ${dinnerCounts[i]} of ${baseDemand[i]} kitchen staff`}><span>{day}</span><div className="meter"><i style={{ width: `${Math.min(100, dinnerCounts[i] / baseDemand[i] * 100)}%` }} /></div><strong className={shortages[i] ? 'shortage' : ''}>{dinnerCounts[i]}/{baseDemand[i]}</strong></button>)}</div></section>
          <p className="demo-footnote">Synthetic roster preview. Hours and base cost exclude breaks and overtime. Solver validation will be provided by the backend.</p>
        </>}

        {view === 'Team' && <section className="data-surface"><div className="section-toolbar"><label className="search-field"><MagnifyingGlassIcon size={16} /><input aria-label="Search employees" placeholder="Search your team" value={query} onChange={e => setQuery(e.target.value)} /></label><button className="button primary" onClick={() => setModal('employee')}><PlusIcon size={17} />Add teammate</button></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Team member</th><th>Role</th><th>Hourly rate</th><th>Weekly limit</th><th>Draft hours</th></tr></thead><tbody>{employees.filter(e => e.name.toLowerCase().includes(query.toLowerCase())).map(e => <tr key={e.id}><td><div className="employee-cell"><Avatar initials={e.initials} color={e.color} /><strong>{e.name}</strong></div></td><td><span className={`role-badge ${roleClass(e.role)}`}>{e.role}</span></td><td>{money(e.rate)}</td><td>{e.maxHours} hours</td><td>{shiftHours(shifts, e.id)} hours</td></tr>)}</tbody></table></div><p className="surface-note">{employees.length} teammates at {outletInfo.name}. This demo shows role eligibility; detailed skills and availability await backend integration.</p></section>}

        {view === 'Demand' && <section className="data-surface"><div className="section-toolbar"><div><h2>Kitchen dinner targets</h2><p>{formatDate(week)} – {formatDate(addDays(week, 6))} · 18:00–22:00 IST</p></div><span className="neutral-badge">Manually configured</span></div><div className="demand-list">{days.map((day, i) => <div className="demand-row" key={day}><span className="date-tile"><strong>{formatDate(addDays(week, i), { day: 'numeric' })}</strong>{day}</span><div><strong>{day} dinner</strong><span>{dinnerCounts[i]} currently assigned</span></div><label>Preferred staff<input aria-label={`${day} preferred kitchen staff`} type="number" min="1" max="20" value={baseDemand[i]} onChange={e => { const next = [...baseDemand]; next[i] = Math.max(1, Math.min(20, Number(e.target.value) || 1)); setData(d => ({ ...d, demand: { ...d.demand, [key]: next } })); }} /></label><span className={`demand-status ${shortages[i] ? 'warn' : ''}`}>{shortages[i] ? `${shortages[i]} short` : 'Covered'}</span></div>)}</div><p className="surface-note">Demo targets are preferences, not mandatory minimums. Editing demand does not automatically change your roster.</p></section>}

        {view === 'Requests' && <section className="data-surface"><div className="section-toolbar"><h2>Team requests</h2><span className="neutral-badge">{pending} pending</span></div>{!scopedRequests.length && <Empty title="No requests to review" description="This outlet has no employee requests in the demo." />}{scopedRequests.map(request => <article className="request-row" key={request.id}><Avatar initials={request.employee.split(' ').map(n => n[0]).join('')} color="sand" /><div><h3>{request.employee}<span>{request.type}</span></h3><p>{request.detail}</p></div>{request.status === 'Pending' ? <div className="request-actions"><button className="button" onClick={() => setData(d => ({ ...d, requests: d.requests.map(r => r.id === request.id ? { ...r, status: 'Declined' } : r) }))}>Decline</button><button className="button primary" onClick={() => { setData(d => ({ ...d, requests: d.requests.map(r => r.id === request.id ? { ...r, status: 'Approved' } : r) })); flash('Demo request acknowledged. No roster changes were made.'); }}>Acknowledge</button></div> : <span className="neutral-badge">{request.status === 'Approved' ? 'Acknowledged' : request.status}</span>}</article>)}<p className="surface-note">Demo requests belong to Indiranagar. Acknowledging records your review locally; it does not execute a swap or grant leave.</p></section>}

        {view === 'Rules' && <section className="data-surface"><div className="section-toolbar"><div><h2>Keep the important things consistent.</h2><p>Rules shown here are configuration previews until the solver is connected.</p></div><button className="button primary" onClick={() => setModal('rule')}><PlusIcon size={17} />Add rule</button></div>{data.rules.map(rule => <div className="rule-row" key={rule.id}><span className="rule-symbol"><SlidersHorizontalIcon size={20} /></span><div><h3>{rule.name}</h3><p>{rule.description}</p></div><span className="neutral-badge">{rule.kind}</span><button className="switch" role="switch" aria-checked={rule.active} aria-label={`Enable ${rule.name}`} onClick={() => setData(d => ({ ...d, rules: d.rules.map(r => r.id === rule.id ? { ...r, active: !r.active } : r) }))}><i /></button></div>)}<p className="surface-note">No natural-language rule is executed in this UI build. Claude’s parser and compiler will provide validated rule previews.</p></section>}

        {view === 'History' && <section className="data-surface"><div className="section-toolbar"><h2>{formatDate(week)} – {formatDate(addDays(week, 6))}</h2><span className="neutral-badge">{versions.length} local versions</span></div>{!versions.length ? <Empty title="Your week’s story starts here." description="Publish a demo schedule to create its first saved version."><button className="button" onClick={() => navigate('Schedule')}>Back to schedule<ArrowRightIcon size={16} /></button></Empty> : versions.map((version, i) => <article className="history-row" key={version.id}><span className="history-symbol"><ClockCounterClockwiseIcon size={20} /></span><div><h3>Version {versions.length - i}<span>{i === 0 ? 'Latest publication' : 'Previous publication'}</span></h3><p>{version.label}</p><small>{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(version.at))} IST</small></div><button className="button" onClick={() => { changeRoster(structuredClone(version.shifts)); navigate('Schedule'); flash('Version loaded as a draft. Review and publish to save a new version.'); }}><ArrowCounterClockwiseIcon size={16} />Restore as draft</button></article>)}<p className="surface-note">Versions are synthetic browser snapshots. Production restore must revalidate current availability and constraints.</p></section>}

        <footer className="page-footer"><span>Made for the people behind every shift.</span><span>Bengaluru · Asia/Kolkata</span></footer>
      </main>
    </div>

    {notice && <div className="toast" role="status"><CheckIcon size={18} /><span>{notice}</span><button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><XIcon size={16} /></button></div>}

    {edit && <ShiftEditor target={edit} employee={data.employees.find(e => e.id === edit.employeeId)!} week={week} onClose={() => setEdit(null)} onSave={shift => { changeRoster([...shifts.filter(s => s.id !== shift.id), shift]); setEdit(null); flash('Draft updated locally. Review before publishing.'); }} onDelete={() => { if (edit.shift) changeRoster(shifts.filter(s => s.id !== edit.shift!.id)); setEdit(null); }} onAbsence={() => { if (edit.shift) startRepair(edit.shift); setEdit(null); }} />}

    {repair && <Dialog title="A change of plans. Let’s find cover." onClose={() => setRepair(null)}><p className="dialog-description">{data.employees.find(e => e.id === repair.employeeId)?.name} · {days[repair.day]}, {repair.start}–{repair.end} · {repair.role}</p><div className="inline-note"><WarningCircleIcon size={18} /><p>Demo alternatives use role and same-day availability only. Rest, skills, travel and overtime require backend validation.</p></div>{availableReplacements.length ? <div className="candidate-list">{availableReplacements.map(employee => <label className={`candidate ${replacement === employee.id ? 'chosen' : ''}`} key={employee.id}><input type="radio" name="replacement" value={employee.id} checked={replacement === employee.id} onChange={() => setReplacement(employee.id)} /><Avatar initials={employee.initials} color={employee.color} /><span><strong>{employee.name}</strong><small>{employee.role} · No shift on this day</small></span><strong>{money(employee.rate * duration(repair.start, repair.end))}<small>base shift cost</small></strong></label>)}</div> : <Empty title="No simple demo replacement" description="No same-role teammate has this day free. You can still mark the shift absent and review the resulting gap." />}<div className="dialog-actions"><button className="button" onClick={() => { changeRoster(shifts.map(s => s.id === repair.id ? { ...s, absent: true } : s)); setRepair(null); flash('Absence recorded in the demo draft. Coverage needs review.'); }}>Mark absent only</button><button className="button primary" disabled={!replacement} onClick={() => { changeRoster(shifts.map(s => s.id === repair.id ? { ...s, employeeId: replacement, absent: false } : s)); setRepair(null); flash('Replacement added to the demo draft. Publish after review.'); }}>Apply to draft<ArrowRightIcon size={16} /></button></div></Dialog>}

    {modal === 'generate' && <Dialog title="Make room for a better week." onClose={() => { if (!busy) setModal(null); }}><p className="dialog-description">Load a sample roster for {outletInfo.name}, {formatDate(week)}–{formatDate(addDays(week, 6))}.</p><div className="generation-details"><div><UsersThreeIcon size={19} /><span>{employees.length} teammates</span></div><div><LockSimpleIcon size={19} /><span>Existing locked shifts stay in place</span></div><div><CalendarBlankIcon size={19} /><span>Seven days · synthetic shift templates</span></div></div><div className="inline-note"><WarningCircleIcon size={18} /><p>This loads demo fixtures, not an optimized schedule. Unlocked draft assignments will be replaced. Backend solver integration is pending.</p></div><div className="dialog-actions"><button className="button" disabled={busy} onClick={() => setModal(null)}>Keep current draft</button><button className="button primary" disabled={busy} onClick={async () => { setBusy(true); await new Promise(resolve => setTimeout(resolve, 600)); const locked = shifts.filter(s => s.locked); const generated = makeRoster(data.employees, outlet).filter(s => !locked.some(l => l.employeeId === s.employeeId && l.day === s.day)); changeRoster([...generated, ...locked]); setBusy(false); setModal(null); flash('Sample week loaded. Review the draft before publishing.'); }}><SparkleIcon size={17} />{busy ? 'Loading sample…' : 'Load sample week'}</button></div></Dialog>}
    {modal === 'publish' && <Dialog title="Give this week the go-ahead." onClose={() => setModal(null)}><p className="dialog-description">Save a local version of the {outletInfo.name} roster for {formatDate(week)}–{formatDate(addDays(week, 6))}.</p><dl className="publish-details"><div><dt>Assignments</dt><dd>{shifts.length}</dd></div><div><dt>Scheduled hours</dt><dd>{totalHours} hrs</dd></div><div><dt>Estimated base cost</dt><dd>{money(estimatedCost)}</dd></div><div><dt>Absent shifts</dt><dd>{shifts.filter(s => s.absent).length}</dd></div></dl><div className="inline-note"><WarningCircleIcon size={18} /><p>This saves a browser snapshot only. It does not certify schedule validity or notify employees.</p></div><div className="dialog-actions"><button className="button" onClick={() => setModal(null)}>Keep reviewing</button><button className="button primary" onClick={publish}>Publish demo version<CheckIcon size={16} /></button></div></Dialog>}
    {modal === 'employee' && <EmployeeForm onClose={() => setModal(null)} onAdd={employee => { setData(d => ({ ...d, employees: [...d.employees, employee] })); setModal(null); flash('Teammate added to the local demo.'); }} outlet={outlet} />}
    {modal === 'rule' && <Dialog title="Add a scheduling preference" onClose={() => setModal(null)}><form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); setData(d => ({ ...d, rules: [...d.rules, { id: crypto.randomUUID(), name: String(form.get('name')).trim(), description: String(form.get('description')).trim(), active: true, kind: 'Preference' }] })); setModal(null); flash('Preference saved as a local configuration preview.'); }}><p className="dialog-description">Describe a preference for review. It will not be compiled or enforced in this demo.</p><label className="field">Preference name<input name="name" required maxLength={80} placeholder="Keep Friday shifts consistent" /></label><label className="field">Description<textarea name="description" required maxLength={300} placeholder="Prefer the same closing team on Fridays." /></label><div className="dialog-actions"><button className="button" type="button" onClick={() => setModal(null)}>Cancel</button><button className="button primary">Save preview</button></div></form></Dialog>}
    {modal === 'help' && <Dialog title="A quick way around" onClose={() => setModal(null)}><div className="help-list"><p><strong>Edit a shift</strong>Click any shift, or click a day off to add one. The editor is the keyboard alternative to dragging.</p><p><strong>Keep a decision</strong>Open a shift and lock it. Generation preserves the assignment.</p><p><strong>Try a repair</strong>Open an unlocked shift and choose “Report absence.” Review a replacement before applying it to the draft.</p><p><strong>Save a version</strong>Publish the demo roster. History lets you restore it as a draft.</p></div><button className="button primary" onClick={() => setModal(null)}>Got it</button></Dialog>}
    {modal === 'settings' && <Dialog title="Brew & Co. workspace" onClose={() => setModal(null)}><dl className="publish-details"><div><dt>Environment</dt><dd>Browser demo</dd></div><div><dt>Outlets</dt><dd>3 in Bengaluru</dd></div><div><dt>Timezone</dt><dd>Asia/Kolkata</dd></div><div><dt>Currency</dt><dd>Indian rupee (INR)</dd></div><div><dt>Backend connection</dt><dd>Not connected</dd></div></dl><p className="dialog-description">All changes are stored on this device. This UI does not provide production authentication or authorization.</p><button className="button" onClick={() => setModal('reset')}><ArrowCounterClockwiseIcon size={16} />Reset synthetic data</button></Dialog>}
    {modal === 'reset' && <Dialog title="Start with a fresh demo?" onClose={() => setModal(null)}><p className="dialog-description">This clears local edits, published versions, preferences and request reviews for all three demo outlets.</p><div className="dialog-actions"><button className="button" onClick={() => setModal(null)}>Keep my changes</button><button className="button primary" onClick={() => { setData(createDemo()); setWeek(DEMO_WEEK); setModal(null); flash('Demo reset to its starting data.'); }}>Reset demo</button></div></Dialog>}
  </div>;
}

function ShiftEditor({ target, employee, week, onClose, onSave, onDelete, onAbsence }: { target: EditTarget; employee: Employee; week: string; onClose: () => void; onSave: (shift: Shift) => void; onDelete: () => void; onAbsence: () => void }) {
  const [locked, setLocked] = useState(target.shift?.locked ?? false);
  const [error, setError] = useState('');
  return <Dialog title={target.shift ? 'A closer look at this shift' : 'Add a shift'} onClose={onClose}><div className="editor-person"><Avatar initials={employee.initials} color={employee.color} /><div><strong>{employee.name}</strong><span>{formatDate(addDays(week, target.day), { weekday: 'long', day: 'numeric', month: 'long' })} · IST</span></div></div><form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); const start = String(form.get('start')); const end = String(form.get('end')); const hours = duration(start, end); if (hours <= 0 || hours > 12) { setError('Choose a shift longer than 0 and no longer than 12 hours for this demo.'); return; } onSave({ id: target.shift?.id ?? crypto.randomUUID(), employeeId: employee.id, day: target.day, start, end, role: employee.role, locked, absent: target.shift?.absent }); }}>
    <div className="field-row"><label className="field">Start time<input name="start" type="time" step="1800" defaultValue={target.shift?.start ?? '10:00'} required disabled={locked} /></label><label className="field">End time<input name="end" type="time" step="1800" defaultValue={target.shift?.end ?? '18:00'} required disabled={locked} /></label></div>
    {locked && <><input type="hidden" name="start" value={target.shift?.start ?? '10:00'} /><input type="hidden" name="end" value={target.shift?.end ?? '18:00'} /></>}
    <label className="lock-option"><LockSimpleIcon size={19} /><span><strong>Lock this assignment</strong><small>Keep it in place when loading another sample.</small></span><input type="checkbox" checked={locked} onChange={e => setLocked(e.target.checked)} /></label>
    <p className="surface-note">Local preview only. Full availability, rest and overtime checks require the scheduling API.</p>{error && <p className="form-error" role="alert">{error}</p>}<div className="dialog-actions split">{target.shift ? <div className="editor-secondary"><button className="text-button danger" type="button" disabled={locked} onClick={onDelete}>Remove</button><button className="text-button" type="button" disabled={locked} onClick={onAbsence}>Report absence</button></div> : <span />}<button className="button primary">Save draft<CheckIcon size={16} /></button></div></form></Dialog>;
}

function EmployeeForm({ outlet, onAdd, onClose }: { outlet: OutletId; onAdd: (employee: Employee) => void; onClose: () => void }) {
  return <Dialog title="One more person on the team." onClose={onClose}><form onSubmit={event => { event.preventDefault(); const values = new FormData(event.currentTarget); const name = String(values.get('name')).trim(); if (!name) return; onAdd({ id: crypto.randomUUID(), name, role: String(values.get('role')) as Role, rate: Number(values.get('rate')), maxHours: Number(values.get('hours')), outletId: outlet, initials: name.split(' ').map(n => n[0]).slice(0, 2).join(''), color: 'sage' }); }}><label className="field">Full name<input name="name" required maxLength={80} placeholder="e.g. Anjali Rao" /></label><label className="field">Primary role<select name="role">{roles.map(r => <option key={r}>{r}</option>)}</select></label><div className="field-row"><label className="field">Hourly rate (₹)<input name="rate" type="number" min="1" max="10000" required defaultValue="180" /></label><label className="field">Weekly maximum (hours)<input name="hours" type="number" min="1" max="60" required defaultValue="48" /></label></div><div className="dialog-actions"><button className="button" type="button" onClick={onClose}>Cancel</button><button className="button primary">Add teammate<PlusIcon size={16} /></button></div></form></Dialog>;
}
