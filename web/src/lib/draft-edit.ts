import type { Schema } from '@/api/types';
import { localDate, localTime } from '../api/presentation';
import { outletInstant } from './management';

export type EditValues = { shiftId: string; mode: 'update' | 'lock' | 'unlock' | 'remove'; employeeId: string; skillId: string; startDate: string; startTime: string; endDate: string; endTime: string; reason: string };

export function valuesForShift(shift: Schema['Shift'], timezone: string): EditValues {
  return { shiftId: shift.logical_shift_id, mode: 'update', employeeId: shift.employee_id ?? '', skillId: shift.skill_id, startDate: localDate(shift.start_at, timezone), startTime: localTime(shift.start_at, timezone), endDate: localDate(shift.end_at, timezone), endTime: localTime(shift.end_at, timezone), reason: shift.lock_reason ?? '' };
}

/** Omit untouched fields, preserve logical identity, and leave break policy to the server. */
export function draftEdit(shift: Schema['Shift'], values: EditValues, timezone: string): Schema['EditRequest']['edits'][number] {
  const logical_shift_id = shift.logical_shift_id;
  if (values.mode === 'remove') return { op: 'remove', logical_shift_id };
  if (values.mode === 'lock' || values.mode === 'unlock') {
    if (values.mode === 'lock' && shift.locked) throw new Error('This assignment is already locked.');
    if (values.mode === 'unlock' && !shift.locked) throw new Error('This assignment is not locked.');
    return values.mode === 'lock' ? { op: 'lock', logical_shift_id, reason: values.reason.trim() || null } : { op: 'unlock', logical_shift_id };
  }
  if (!values.skillId) throw new Error('Choose the required skill.');
  const before = valuesForShift(shift, timezone);
  // Do not reinterpret an untouched wall time during a daylight-saving fold.
  const start = values.startDate === before.startDate && values.startTime === before.startTime ? shift.start_at : outletInstant(values.startDate, values.startTime, timezone);
  const end = values.endDate === before.endDate && values.endTime === before.endTime ? shift.end_at : outletInstant(values.endDate, values.endTime, timezone);
  if (Date.parse(end) <= Date.parse(start)) throw new Error('The assignment must end after it starts. For an overnight shift, choose the next end date.');
  if ([values.startTime, values.endTime].some(time => !/^\d{2}:(00|30)$/.test(time))) throw new Error('Use the 30-minute scheduling grid.');
  const edit: Schema['UpdateShift'] = { op: 'update', logical_shift_id };
  if (values.employeeId !== (shift.employee_id ?? '')) edit.employee_id = values.employeeId || null;
  if (values.skillId !== shift.skill_id) edit.skill_id = values.skillId;
  if (start !== shift.start_at) edit.start_at = start;
  if (end !== shift.end_at) edit.end_at = end;
  if (Object.keys(edit).length === 2) throw new Error('Change an assignment value before previewing.');
  return edit;
}
