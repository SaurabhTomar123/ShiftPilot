import { expect, it } from 'vitest';
import { emptyProtection, hasProtection, releaseProtection, requestedProtection } from './protection';
import { fixture } from '../api/fixture-gateway';
import type { Schema } from '../api/types';

const base = fixture<Schema['ScheduleVersion']>('schedule_version.published');
const employee = base.shifts.find(shift => shift.employee_id)!.employee_id!;

it('previews the union of employee, day and individual pins without counting overlaps twice', () => {
  const person = base.shifts.filter(shift => shift.employee_id === employee);
  const spec = { ...emptyProtection(), employee_ids: [employee], shift_ids: [person[0].logical_shift_id] };
  expect(requestedProtection(spec, base, 'Asia/Kolkata').map(shift => shift.logical_shift_id)).toEqual(person.map(shift => shift.logical_shift_id));
  expect(hasProtection(spec)).toBe(true); expect(hasProtection(emptyProtection())).toBe(false);
});

it('releasing a broken employee assignment keeps the other requested assignments as individual pins', () => {
  const person = base.shifts.filter(shift => shift.employee_id === employee);
  const original = { ...emptyProtection(), employee_ids: [employee] };
  const released = releaseProtection(original, [person[0].logical_shift_id], base, 'Asia/Kolkata');
  expect(released.employee_ids).toEqual([]); expect(released.days).toEqual([]);
  expect(released.shift_ids).toEqual(person.slice(1).map(shift => shift.logical_shift_id));
  expect(original.employee_ids).toEqual([employee]);
});

it('resolves protected days using the outlet timezone and preserves open assignments', () => {
  const midnight = { ...base.shifts[0], employee_id: null, start_at: '2026-10-19T20:00:00Z', end_at: '2026-10-20T00:00:00Z' };
  const one = { ...base, shifts: [midnight] };
  expect(requestedProtection({ ...emptyProtection(), days: ['2026-10-20'] }, one, 'Asia/Kolkata')).toEqual([midnight]);
  expect(requestedProtection({ ...emptyProtection(), days: ['2026-10-19'] }, one, 'Asia/Kolkata')).toEqual([]);
});
