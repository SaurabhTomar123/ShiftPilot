import { describe, expect, it } from 'vitest';
import { draftEdit, valuesForShift } from './draft-edit';
import { fixture } from '../api/fixture-gateway';
import type { Schema } from '../api/types';

const shift = fixture<Schema['ScheduleVersion']>('draft.create').shifts[0];
const zone = 'Asia/Kolkata';
describe('assignment edit requests', () => {
  it('omits untouched values and sends explicit null to unassign', () => {
    const values = valuesForShift(shift, zone);
    expect(() => draftEdit(shift, values, zone)).toThrow('Change an assignment');
    expect(draftEdit(shift, { ...values, employeeId: '' }, zone)).toEqual({ op: 'update', logical_shift_id: shift.logical_shift_id, employee_id: null });
  });
  it('resolves overnight outlet dates to instants without changing break policy', () => {
    const values = { ...valuesForShift(shift, zone), startTime: '22:00', endDate: '2026-10-20', endTime: '02:00' };
    expect(draftEdit(shift, values, zone)).toEqual({ op: 'update', logical_shift_id: shift.logical_shift_id, start_at: '2026-10-19T16:30:00.000Z', end_at: '2026-10-19T20:30:00.000Z' });
  });
  it('requires an end after start and the scheduling grid', () => {
    const values = valuesForShift(shift, zone);
    expect(() => draftEdit(shift, { ...values, endTime: '09:00' }, zone)).toThrow('end after');
    expect(() => draftEdit(shift, { ...values, endTime: '18:15' }, zone)).toThrow('30-minute');
  });
  it('represents remove and explicit lock changes without assignment or break mutations', () => {
    const values = valuesForShift(shift, zone);
    expect(draftEdit(shift, { ...values, mode: 'remove' }, zone)).toEqual({ op: 'remove', logical_shift_id: shift.logical_shift_id });
    expect(draftEdit(shift, { ...values, mode: 'lock', reason: ' Opening cook confirmed ' }, zone)).toEqual({ op: 'lock', logical_shift_id: shift.logical_shift_id, reason: 'Opening cook confirmed' });
    expect(() => draftEdit(shift, { ...values, mode: 'unlock' }, zone)).toThrow('not locked');
  });
  it('preserves an unchanged ambiguous clock instant while rejecting new ambiguous times', () => {
    const folded = { ...shift, start_at: '2026-11-01T01:30:00-04:00', end_at: '2026-11-01T04:00:00-05:00' };
    const values = valuesForShift(folded, 'America/New_York');
    expect(draftEdit(folded, { ...values, employeeId: '' }, 'America/New_York')).not.toHaveProperty('start_at');
    expect(() => draftEdit(folded, { ...values, startTime: '01:00' }, 'America/New_York')).toThrow('skipped or repeated');
  });
});
