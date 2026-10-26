import { expect, it } from 'vitest';
import { checkedRule, ruleIdentity, ruleImpactTime } from './rules';
import type { Schema } from '@/api/types';

const rule: Schema['RuleDefinition'] = { rule_type: 'max_days_per_week', scope_level: 'outlet', scope: { outlet_id: 'outlet' }, parameters: { days: 5 }, hard: true };
it('normalizes optional defaults without changing the supplied definition', () => {
  const input = structuredClone(rule);
  expect(checkedRule(input, false, 'outlet', [])).toEqual({ ...rule, hard: true, overrides_rule_id: null, source_text: null });
  expect(input).toEqual(rule);
});
it('limits manager scopes and person choices to the selected outlet', () => {
  for (const scope_level of ['organization', 'tag'] as const) expect(() => checkedRule({ ...rule, scope_level, scope: { tag: 'student' } }, false, 'outlet', [])).toThrow('owner');
  expect(() => checkedRule(rule, false, 'other', [])).toThrow('current outlet');
  expect(() => checkedRule({ ...rule, scope_level: 'employee', scope: { employee_id: 'outsider' } }, true, 'outlet', ['person'])).toThrow('selected outlet');
  expect(checkedRule({ ...rule, scope_level: 'tag', scope: { tag: ' student ' } }, true, 'outlet', []).scope).toEqual({ tag: 'student' });
});
it('rejects invalid day counts, soft rules and oversized notes', () => {
  for (const days of [0, 8, 1.5, NaN]) expect(() => checkedRule({ ...rule, parameters: { days } }, false, 'outlet', [])).toThrow('whole number');
  expect(() => checkedRule({ ...rule, hard: false }, false, 'outlet', [])).toThrow('required');
  expect(() => checkedRule({ ...rule, source_text: 'a'.repeat(501) }, false, 'outlet', [])).toThrow('500');
});
it('checks half-hour finish times and distinct weekdays, including midnight', () => {
  const finish = { ...rule, rule_type: 'max_shift_end_time' as const, parameters: { latest_end_minute: 1440, weekdays: [0, 4] } };
  expect(checkedRule(finish, false, 'outlet', []).parameters).toEqual(finish.parameters);
  for (const latest_end_minute of [-30, 1450, 1261]) expect(() => checkedRule({ ...finish, parameters: { ...finish.parameters, latest_end_minute } }, false, 'outlet', [])).toThrow('half-hour');
  for (const weekdays of [[], [7], [1, 1], [1.5]]) expect(() => checkedRule({ ...finish, parameters: { ...finish.parameters, weekdays } }, false, 'outlet', [])).toThrow('weekdays');
});
it('preserves exact exception references and compares field order independently', () => {
  const exception = { ...rule, overrides_rule_id: 'parent', source_text: ' Reason ' };
  expect(checkedRule(exception, false, 'outlet', [])).toMatchObject({ overrides_rule_id: 'parent', source_text: 'Reason' });
  expect(ruleIdentity({ a: 1, nested: { z: 2, b: 3 } })).toBe(ruleIdentity({ nested: { b: 3, z: 2 }, a: 1 }));
  expect(ruleIdentity([1, 2])).not.toBe(ruleIdentity([2, 1]));
});
it('retains each returned shift offset instead of assuming the selected outlet timezone', () => {
  expect(ruleImpactTime('2026-10-30T23:00:00+05:30')).toBe('2026-10-30 23:00 UTC+05:30');
  expect(ruleImpactTime('2026-10-30T23:00:00-04:00')).toBe('2026-10-30 23:00 UTC-04:00');
  expect(ruleImpactTime('2026-10-30T23:00:00Z')).toBe('2026-10-30 23:00 UTC');
});
