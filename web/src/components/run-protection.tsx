'use client';

import { useState } from 'react';
import type { Schema } from '@/api/types';
import { localDate, localTime } from '@/api/presentation';
import { emptyProtection, hasProtection, requestedProtection, type Protection } from '@/lib/protection';
import { Button } from './primitives/button';

type Context = { base: Schema['ScheduleVersion']; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string };
const toggle = (values: string[], value: string) => values.includes(value) ? values.filter(item => item !== value) : [...values, value];
function describe(shift: Schema['Shift'], context: Context) {
  const person = shift.employee_id ? context.employees.find(e => e.id === shift.employee_id)?.name ?? `Employee ${shift.employee_id}` : 'Open shift';
  return `${person} · ${context.skills.find(s => s.id === shift.skill_id)?.name ?? 'Required skill'} · ${localDate(shift.start_at, context.timezone)} ${localTime(shift.start_at, context.timezone)} to ${localDate(shift.end_at, context.timezone)} ${localTime(shift.end_at, context.timezone)}${shift.locked ? ' · Permanent lock' : ''}`;
}

export function ProtectionControls({ value, onChange, disabled, ...context }: Context & { value: Protection; onChange: (value: Protection) => void; disabled: boolean }) {
  const [query, setQuery] = useState('');
  const selected = requestedProtection(value, context.base, context.timezone);
  const people = context.employees.filter(person => context.base.shifts.some(shift => shift.employee_id === person.id));
  const days = [...new Set(context.base.shifts.map(shift => localDate(shift.start_at, context.timezone)))].sort();
  return <details className="run-protection-controls"><summary>Protect commitments for the next run ({selected.length})</summary><p>Keep selected published assignments exactly as they are for one run. These choices do not create permanent locks. The next run starts with no protection selected.</p><p>Reviewing published version {context.base.version_number}, in {context.timezone}. The server checks current facts before accepting the request.</p><fieldset disabled={disabled}><legend>Choose what to keep unchanged</legend><div className="review-actions"><Button onClick={() => onChange({ ...emptyProtection(), shift_ids: context.base.shifts.map(shift => shift.logical_shift_id) })}>Keep this outlet’s published week</Button><Button disabled={!hasProtection(value)} onClick={() => onChange(emptyProtection())}>Clear run protections</Button></div><details><summary>Keep an employee’s published assignments</summary><div className="protection-choices">{people.map(person => <label key={person.id}><input type="checkbox" checked={value.employee_ids.includes(person.id)} onChange={() => onChange({ ...value, employee_ids: toggle(value.employee_ids, person.id) })} />Keep {person.name}’s published assignments</label>)}</div></details><details><summary>Keep a day’s published assignments</summary><div className="protection-choices">{days.map(day => <label key={day}><input type="checkbox" checked={value.days.includes(day)} onChange={() => onChange({ ...value, days: toggle(value.days, day) })} />Keep assignments on {day}</label>)}</div></details><details><summary>Pin individual published assignments</summary><label className="protection-search">Find an assignment<input aria-label="Find a published assignment to protect" value={query} onChange={e => setQuery(e.target.value)} /></label><div className="protection-shifts">{context.base.shifts.filter(shift => describe(shift, context).toLowerCase().includes(query.toLowerCase())).map(shift => <label key={shift.logical_shift_id}><input type="checkbox" checked={value.shift_ids.includes(shift.logical_shift_id)} onChange={() => onChange({ ...value, shift_ids: toggle(value.shift_ids, shift.logical_shift_id) })} />{describe(shift, context)}</label>)}</div></details></fieldset><details><summary>Review requested protection ({selected.length} {selected.length === 1 ? 'assignment' : 'assignments'})</summary><p>Overlapping employee, day and shift choices count each assignment once. Unchecking a shift does not remove protection selected through its employee or day.</p>{selected.length ? <ul>{selected.map(shift => <li key={shift.logical_shift_id}>{describe(shift, context)}</li>)}</ul> : <p>No assignments requested for protection.</p>}</details></details>;
}

export function ProtectionConflict({ ids, onRelease, disabled, ...context }: Context & { ids: string[]; onRelease: (ids: string[]) => void; disabled: boolean }) {
  const [checked, setChecked] = useState<string[]>([]);
  return <section className="protection-conflict" aria-label="Run protection conflict"><h3>Current facts conflict with protected assignments</h3><p>The server did not accept a new run. Review the affected assignments. Removing a run protection does not remove a permanent lock or change an absence.</p><fieldset disabled={disabled}><legend>Assignments you authorize to remove from this run’s protection</legend>{ids.map(id => { const shift = context.base.shifts.find(shift => shift.logical_shift_id === id); return <label key={id}><input type="checkbox" checked={checked.includes(id)} onChange={() => setChecked(values => toggle(values, id))} />{shift ? describe(shift, context) : `Assignment ${id}`}</label>; })}</fieldset><p>Other selected assignments stay protected as individual pins. Starting a new run remains a separate action.</p><Button disabled={disabled || checked.length === 0} onClick={() => onRelease(checked)}>Remove selected run protections</Button></section>;
}

export function RunProtection({ run, base, employees, skills, timezone }: { run: Schema['OptimizationRun']; base: Schema['ScheduleVersion'] | null; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string }) {
  const ids = run.frozen_logical_shift_ids;
  if (!ids) return <p>Run protection was not reported by this provider.</p>;
  const knownBase = base && run.base_version_ids.includes(base.id) ? base : null;
  return <details className="confirmed-protection"><summary>Server-confirmed run protections ({ids.length})</summary><p>These are the explicit assignments the server accepted for this run. Repair stages may additionally freeze unaffected assignments. Permanent locks are separate.</p>{ids.length === 0 ? <p>No explicit run protections were reported.</p> : <ul>{ids.map(id => { const shift = knownBase?.shifts.find(shift => shift.logical_shift_id === id); return <li key={id}>{shift && knownBase ? describe(shift, { base: knownBase, employees, skills, timezone }) : `Assignment ${id}`}</li>; })}</ul>}</details>;
}
