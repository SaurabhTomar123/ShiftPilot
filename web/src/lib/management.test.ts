import { describe, expect, it } from 'vitest';
import { availabilityProblem, decimalUnits, employeePatch, outletInstant } from './management';
import { fixture } from '../api/fixture-gateway';
import type { Schema } from '@/api/types';

describe('management input boundaries', () => {
  it('preserves paise and exact minutes without floating-point rounding', () => {
    expect(decimalUnits('210.01', 100)).toBe(21001);
    expect(decimalUnits('1.25', 60)).toBe(75);
    expect(decimalUnits('0.01', 60)).toBeNull();
    for (const input of ['-1', '', 'Infinity', '1.999', '1e3', '9007199254740992']) expect(decimalUnits(input, 100)).toBeNull();
  });
  it('omits untouched fields and explicitly clears only a changed nullable preference', () => {
    const before = fixture<Schema['EmployeeList']>('employees.list').items[0];
    const after = { ...before, preferred_weekly_minutes: null };
    const result = employeePatch({ ...before, preferred_weekly_minutes: 2400 }, after);
    expect(result).toEqual({ base_revision: before.revision, preferred_weekly_minutes: null });
  });
  it('retains overnight windows and rejects backward or out-of-range times', () => {
    const window = { weekday: 6, start_minute: 1320, end_minute: 1560, kind: 'available' as const };
    expect(availabilityProblem([window])).toBeNull();
    expect(availabilityProblem([{ ...window, end_minute: 120 }])).toBeTruthy();
    expect(availabilityProblem([{ ...window, end_minute: 2881 }])).toBeTruthy();
  });
  it('uses outlet timezone across UTC date boundaries and rejects clock-change ambiguity', () => {
    expect(outletInstant('2026-10-19', '00:30', 'Asia/Kolkata')).toBe('2026-10-18T19:00:00.000Z');
    expect(outletInstant('2026-10-19', '23:30', 'Asia/Kolkata')).toBe('2026-10-19T18:00:00.000Z');
    expect(() => outletInstant('2026-03-08', '02:30', 'America/New_York')).toThrow('clock change');
    expect(() => outletInstant('2026-11-01', '01:30', 'America/New_York')).toThrow('clock change');
  });
});
