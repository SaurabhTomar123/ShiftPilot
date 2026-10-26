import { expect, it } from 'vitest';
import { scenarioEvent, scenarioMatches, scenarioRunMatches, type ScenarioValues } from './scenario';
import records from '../api/generated/fixtures.json';
import type { Schema } from '../api/types';

const values: ScenarioValues = { type: 'absence', employee: 'person', start: '2026-10-21T00:00', end: '2026-10-22T00:00', percent: '30', skill: '', weekdays: [5], from: '18:00', until: '23:30', day: '2026-10-24', cap: '1192.50', rule: 'max_days_per_week', days: '4', latest: '21:00' };
const event = (patch: Partial<ScenarioValues>) => scenarioEvent({ ...values, ...patch }, '2026-10-19', 'Asia/Kolkata');
it('builds typed hypothetical events in outlet time without operational write fields', () => {
  expect(event({})).toEqual({ type: 'absence', payload: { employee_id: 'person', start_at: '2026-10-20T18:30:00.000Z', end_at: '2026-10-21T18:30:00.000Z' } });
  expect(event({ type: 'demand_change' })).toEqual({ type: 'demand_change', payload: { percent: 30, weekdays: [5], start_minute: 1080, end_minute: 1410 } });
  expect(event({ type: 'labour_cap' }).payload.max_cost_paise).toBe(119250);
  expect(event({ type: 'outlet_closure' }).payload.day).toBe('2026-10-24');
  expect(event({ type: 'rule' }).payload).toEqual({ rule_type: 'max_days_per_week', employee_ids: ['person'], parameters: { days: 4 } });
  expect(event({ type: 'rule', rule: 'max_shift_end_time' }).payload.parameters).toEqual({ latest_end_minute: 1260, weekdays: [5] });
});
it('rejects invalid ranges, cap precision, demand days and rule grid', () => {
  for (const patch of [{ end: values.start }, { type: 'labour_cap' as const, cap: '1.001' }, { type: 'outlet_closure' as const, day: '2026-11-01' }, { type: 'demand_change' as const, percent: '301' }, { type: 'demand_change' as const, weekdays: [] }, { type: 'rule' as const, rule: 'max_shift_end_time' as const, latest: '21:15' }]) expect(() => event(patch)).toThrow();
});
it('never confuses another scenario, outlet or generation run with a simulated plan', () => {
  const scenario = records['scenario.get'].response.body as Schema['Scenario'];
  const run = records['scenario.run.accepted'].response.body as Schema['OptimizationRun'];
  expect(scenarioMatches(scenario, scenario.outlet_id, scenario.week_start)).toBe(true);
  expect(scenarioMatches(scenario, 'other', scenario.week_start)).toBe(false);
  expect(scenarioRunMatches(run, scenario)).toBe(true);
  expect(scenarioRunMatches({ ...run, scenario_id: 'other' }, scenario)).toBe(false);
  expect(scenarioRunMatches({ ...run, kind: 'generate' }, scenario)).toBe(false);
});
