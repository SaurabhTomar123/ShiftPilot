import { expect, it } from 'vitest';
import { SchedulingClient } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import examples from './generated/staffing-template-examples.json';
import type { Schema } from './types';

function setup() {
  const requests: Request[] = [];
  const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (input, init) => { const path = String(input).replace('/api/fixture', ''); const request = new Request(`http://fixture.invalid${path}`, init); requests.push(request.clone()); return fixtureResponse(path, request); } });
  return { client, requests };
}
const initial = fixture<Schema['StaffingRequirements']>('staffing.get');

it('saves the supplied complete template without writing a dated week or roster', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  expect(await client.staffingTemplates(initial.outlet_id)).toEqual(fixture('staffing_templates.list'));
  expect(await client.saveStaffingTemplates(initial.outlet_id, examples)).toEqual(fixture('staffing_templates.put'));
  expect(await client.staffing(initial.outlet_id, initial.week_start)).toEqual(initial);
  expect(requests.filter(value => value.method === 'PUT')).toHaveLength(1);
  expect(requests.filter(value => value.method === 'POST')).toHaveLength(1);
  await expect(client.saveStaffingTemplates(initial.outlet_id, examples)).rejects.toMatchObject({ status: 409 });
});
it('expands only on explicit keyed admission and replays without incrementing demand twice', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  const body = { base_demand_revision: initial.demand_revision, use_demand_bands: false };
  const result = await client.expandStaffing(initial.outlet_id, initial.week_start, body, 'expansion-key');
  expect(result).toEqual(fixture('staffing.expand'));
  expect(await client.expandStaffing(initial.outlet_id, initial.week_start, body, 'expansion-key')).toEqual(result);
  expect(await client.staffing(initial.outlet_id, initial.week_start)).toEqual(result);
  await expect(client.expandStaffing(initial.outlet_id, initial.week_start, { ...body, use_demand_bands: true }, 'expansion-key')).rejects.toMatchObject({ status: 409, detail: { code: 'idempotency_conflict' } });
  await expect(client.expandStaffing(initial.outlet_id, initial.week_start, body, 'fresh-key')).rejects.toMatchObject({ status: 409, detail: { code: 'stale_version' } });
  expect(requests.some(value => /generate|publish|proposals/.test(value.url))).toBe(false);
});
it('refuses to fabricate expansion after a changed template or manual override', async () => {
  const { client } = setup(); await client.signIn('manager');
  await client.saveStaffingTemplates(initial.outlet_id, examples);
  await expect(client.expandStaffing(initial.outlet_id, initial.week_start, { base_demand_revision: initial.demand_revision, use_demand_bands: false }, 'changed-template')).rejects.toMatchObject({ status: 501 });
  await client.signIn('manager');
  const intervals = structuredClone(initial.intervals); intervals[0].source = 'manual';
  const saved = await client.saveStaffing(initial.outlet_id, initial.week_start, { base_demand_revision: initial.demand_revision, intervals });
  await expect(client.expandStaffing(initial.outlet_id, initial.week_start, { base_demand_revision: saved.demand_revision, use_demand_bands: false }, 'manual-override')).rejects.toMatchObject({ status: 501 });
});
it('keeps template and expansion requests scoped to the authorized outlet and persona', async () => {
  const { client } = setup(); await client.signIn('manager');
  await expect(client.staffingTemplates(crypto.randomUUID())).rejects.toMatchObject({ status: 403 });
  await client.signIn('staff'); await expect(client.staffingTemplates(initial.outlet_id)).rejects.toMatchObject({ status: 403 });
});
