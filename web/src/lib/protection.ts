import type { Schema } from '../api/types';
import { localDate } from '../api/presentation';

export type Protection = Required<Schema['FreezeSpec']>;
export const emptyProtection = (): Protection => ({ shift_ids: [], employee_ids: [], days: [] });
export const hasProtection = (value: Protection) => value.shift_ids.length + value.employee_ids.length + value.days.length > 0;

/** A display preview of the request's union. The server resolves and validates it. */
export function requestedProtection(value: Protection, base: Schema['ScheduleVersion'], timezone: string) {
  return base.shifts.filter(shift => value.shift_ids.includes(shift.logical_shift_id) || (shift.employee_id !== null && value.employee_ids.includes(shift.employee_id)) || value.days.includes(localDate(shift.start_at, timezone)));
}

/** An explicit release preserves other selected assignments as individual pins. */
export function releaseProtection(value: Protection, ids: string[], base: Schema['ScheduleVersion'], timezone: string): Protection {
  return { ...emptyProtection(), shift_ids: requestedProtection(value, base, timezone).filter(shift => !ids.includes(shift.logical_shift_id)).map(shift => shift.logical_shift_id) };
}
