import type { Schema } from '@/api/types';
import { decimalUnits, outletInstant, timeMinute } from './management';
import { addDays } from './types';

export type ScenarioValues = { type: Schema['ScenarioEventIn']['type']; employee: string; start: string; end: string; percent: string; skill: string; weekdays: number[]; from: string; until: string; day: string; cap: string; rule: 'max_days_per_week' | 'max_shift_end_time'; days: string; latest: string };
const whole = (value: string, min: number, max: number, label: string) => { const n = Number(value); if (!value.trim() || !Number.isInteger(n) || n < min || n > max) throw new Error(`${label} must be a whole number from ${min} to ${max}.`); return n; };
export function scenarioEvent(values: ScenarioValues, week: string, timezone: string): Schema['ScenarioEventIn'] {
  const { type } = values;
  if (type === 'absence') {
    if (!values.employee) throw new Error('Choose the person who would be absent.');
    const start_at = outletInstant(values.start.slice(0, 10), values.start.slice(11), timezone);
    const end_at = outletInstant(values.end.slice(0, 10), values.end.slice(11), timezone);
    if (Date.parse(end_at) <= Date.parse(start_at)) throw new Error('The hypothetical absence must end after it starts.');
    return { type, payload: { employee_id: values.employee, start_at, end_at } };
  }
  if (type === 'outlet_closure') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(values.day) || values.day < week || values.day >= addDays(week, 7)) throw new Error('Choose a closure day within the selected week.');
    return { type, payload: { day: values.day } };
  }
  if (type === 'labour_cap') {
    const amount = decimalUnits(values.cap, 100);
    if (amount == null || amount > 1e12) throw new Error('Enter a labour cap in rupees with at most two decimal places.');
    return { type, payload: { max_cost_paise: amount } };
  }
  if (type === 'demand_change') {
    const percent = whole(values.percent, -100, 300, 'Staffing change');
    const start_minute = timeMinute(values.from), end_minute = timeMinute(values.until);
    if (!Number.isInteger(start_minute) || !Number.isInteger(end_minute) || end_minute <= start_minute) throw new Error('The staffing window must end after it starts on the same day.');
    if (!values.weekdays.length) throw new Error('Choose at least one weekday.');
    return { type, payload: { percent, weekdays: values.weekdays, start_minute, end_minute, ...(values.skill ? { skill_id: values.skill } : {}) } };
  }
  if (!values.employee) throw new Error('Choose the person for this hypothetical rule.');
  if (values.rule === 'max_shift_end_time' && !values.weekdays.length) throw new Error('Choose at least one weekday for the finish rule.');
  const latest = timeMinute(values.latest);
  if (values.rule === 'max_shift_end_time' && (!Number.isInteger(latest) || latest < 0 || latest > 1440 || latest % 30)) throw new Error('Choose a latest finish on the half-hour grid.');
  return { type, payload: { rule_type: values.rule, employee_ids: [values.employee], parameters: values.rule === 'max_days_per_week' ? { days: whole(values.days, 1, 7, 'Maximum days') } : { latest_end_minute: latest, weekdays: values.weekdays.length ? values.weekdays : [0, 1, 2, 3, 4, 5, 6] } } };
}

export function scenarioMatches(value: Schema['Scenario'], outletId: string, week: string) { return value.outlet_id === outletId && value.week_start === week; }
export function scenarioRunMatches(run: Schema['OptimizationRun'], value: Schema['Scenario']) { return run.kind === 'scenario' && run.scenario_id === value.id && run.outlet_ids.includes(value.outlet_id) && (value.base_version_id ? run.base_version_ids.includes(value.base_version_id) : run.base_version_ids.length === 0); }
