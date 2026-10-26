'use client';

import { useState } from 'react';
import type { Schema } from '@/api/types';
import { localDate, localTime, formatMoney } from '@/api/presentation';
import { addDays } from '@/lib/types';
import { minuteTime } from '@/lib/management';
import { scenarioEvent, type ScenarioValues } from '@/lib/scenario';
import { Button } from './primitives/button';

export const eventNames: Record<Schema['ScenarioEventIn']['type'], string> = { absence: 'Person unavailable', demand_change: 'Staffing demand change', outlet_closure: 'Outlet closure', labour_cap: 'Labour cost cap', rule: 'Scheduling rule' };
const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function ScenarioEventEditor({ week, timezone, employees, skills, showCosts, disabled, onEvent }: {
  week: string; timezone: string; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; showCosts: boolean; disabled: boolean; onEvent: (event: Schema['ScenarioEventIn']) => void;
}) {
  const [values, setValues] = useState<ScenarioValues>({ type: 'absence', employee: employees[0]?.id ?? '', start: `${addDays(week, 2)}T00:00`, end: `${addDays(week, 3)}T00:00`, percent: '30', skill: '', weekdays: [5], from: '18:00', until: '23:59', day: week, cap: '', rule: 'max_days_per_week', days: '4', latest: '21:00' });
  const [error, setError] = useState<string | null>(null);
  const patch = (value: Partial<ScenarioValues>) => { setValues(old => ({ ...old, ...value })); setError(null); };
  return <form className="scenario-event-editor" onSubmit={event => { event.preventDefault(); try { const input = scenarioEvent(values, week, timezone); setError(null); onEvent(input); } catch (value) { setError(value instanceof Error ? value.message : 'Check the hypothetical change.'); } }}><fieldset disabled={disabled}><legend>Add a hypothetical change</legend><div className="scenario-fields">
    <label>What would change?<select value={values.type} onChange={event => patch({ type: event.target.value as ScenarioValues['type'] })}>{Object.entries(eventNames).filter(([type]) => showCosts || type !== 'labour_cap').map(([type, label]) => <option key={type} value={type}>{label}</option>)}</select></label>
    {(values.type === 'absence' || values.type === 'rule') && <label>Person<select value={values.employee} onChange={event => patch({ employee: event.target.value })}><option value="">Choose a person</option>{employees.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label>}
    {values.type === 'absence' && <><label>Unavailable from<input type="datetime-local" required value={values.start} onChange={event => patch({ start: event.target.value })} /></label><label>Available again<input type="datetime-local" required value={values.end} onChange={event => patch({ end: event.target.value })} /></label></>}
    {values.type === 'outlet_closure' && <label>Closure day<input type="date" min={week} max={addDays(week, 6)} required value={values.day} onChange={event => patch({ day: event.target.value })} /></label>}
    {values.type === 'labour_cap' && <label>Maximum weekly labour cost (INR)<input inputMode="decimal" required value={values.cap} onChange={event => patch({ cap: event.target.value })} /></label>}
    {values.type === 'demand_change' && <><label>Staffing change (%)<input type="number" min={-100} max={300} step={1} required value={values.percent} onChange={event => patch({ percent: event.target.value })} /></label><label>Skill<select value={values.skill} onChange={event => patch({ skill: event.target.value })}><option value="">All skills</option>{skills.map(skill => <option key={skill.id} value={skill.id}>{skill.name}</option>)}</select></label><label>Window starts<input type="time" required value={values.from} onChange={event => patch({ from: event.target.value })} /></label><label>Window ends<input type="time" required value={values.until} onChange={event => patch({ until: event.target.value })} /></label></>}
    {values.type === 'rule' && <><label>Hypothetical rule<select value={values.rule} onChange={event => patch({ rule: event.target.value as ScenarioValues['rule'] })}><option value="max_days_per_week">Maximum days in a week</option><option value="max_shift_end_time">Latest shift finish</option></select></label>{values.rule === 'max_days_per_week' ? <label>Maximum working days<input type="number" min={1} max={7} step={1} required value={values.days} onChange={event => patch({ days: event.target.value })} /></label> : <label>Latest finish<input type="time" step={1800} required value={values.latest} onChange={event => patch({ latest: event.target.value })} /></label>}</>}
  </div>{(values.type === 'demand_change' || (values.type === 'rule' && values.rule === 'max_shift_end_time')) && <fieldset className="scenario-weekdays"><legend>Applies on</legend>{weekdays.map((day, index) => <label key={day}><input type="checkbox" checked={values.weekdays.includes(index)} onChange={event => patch({ weekdays: event.target.checked ? [...values.weekdays, index].sort() : values.weekdays.filter(value => value !== index) })} />{day}</label>)}</fieldset>}
  <p>Hypothetical only. Times use {timezone}; an absence ends at “Available again”. Demand scales minimum and preferred staffing, rounded up by the engine. Windows stay within one local day.</p>{error && <p role="alert">{error}</p>}<Button type="submit">Add hypothetical change</Button></fieldset></form>;
}

export function ScenarioEventList({ events, employees, skills, timezone, showCosts, onRemove }: {
  events: Schema['ScenarioEventIn'][]; employees: Schema['RosterEmployee'][]; skills: Schema['Skill'][]; timezone: string; showCosts: boolean; onRemove?: (index: number) => void;
}) {
  const person = (id: unknown) => employees.find(value => value.id === id)?.name ?? 'Selected person';
  const time = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value)) ? `${localDate(value, timezone)} ${localTime(value, timezone)}` : 'Not reported';
  return events.length ? <ol className="scenario-event-list">{events.map((event, index) => { const p = event.payload; return <li key={index}><div><strong>{eventNames[event.type]}</strong><p>{event.type === 'absence' ? `${person(p.employee_id)}: ${time(p.start_at)} to ${time(p.end_at)}.` : event.type === 'outlet_closure' ? `Closed on ${p.day}. Demand and shifts starting that local day are removed in this what-if.` : event.type === 'labour_cap' ? showCosts ? `Weekly cap ${formatMoney({ amount_paise: Number(p.max_cost_paise), currency: 'INR' })}. Includes overtime premium.` : 'Labour cap details require cost access.' : event.type === 'demand_change' ? `${Number(p.percent) > 0 ? '+' : ''}${p.percent}% staffing for ${skills.find(value => value.id === p.skill_id)?.name ?? 'all skills'} on ${Array.isArray(p.weekdays) ? p.weekdays.map(value => weekdays[Number(value)]).join(', ') : 'all days'}. Window: ${minuteTime(Number(p.start_minute ?? 0))} to ${Number(p.end_minute ?? 2880) >= 1440 ? 'end of day' : minuteTime(Number(p.end_minute))}.` : `${Array.isArray(p.employee_ids) ? p.employee_ids.map(person).join(', ') : 'Selected people'}: ${p.rule_type === 'max_days_per_week' ? `maximum ${Number((p.parameters as Record<string, unknown>)?.days)} working days` : `latest finish ${minuteTime(Number((p.parameters as Record<string, unknown>)?.latest_end_minute))}`}. Applies only inside this scenario.`}</p></div>{onRemove && <Button onClick={() => onRemove(index)}>Remove change {index + 1}</Button>}</li>; })}</ol> : <p>No hypothetical changes added yet.</p>;
}
