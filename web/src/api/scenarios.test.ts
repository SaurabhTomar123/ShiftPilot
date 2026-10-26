import { expect, it } from 'vitest';
import { SchedulingClient } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import records from './generated/fixtures.json';
import type { Schema } from './types';

const sc = records['scenario.get'].response.body as Schema['Scenario'];
function setup() {
  const requests: Request[] = [];
  const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (url, init) => { const path = String(url).replace('/api/fixture', ''); const request = new Request(`http://fixture.invalid${path}`, init); requests.push(request.clone()); return fixtureResponse(path, request); } });
  return { client, requests };
}
it('creates and adds only hypothetical events and preserves operational facts', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  const before = await client.schedule(sc.outlet_id, sc.week_start);
  const created = await client.createScenario(sc.outlet_id, sc.week_start, records['scenario.create'].request.body as Schema['CreateScenarioRequest']);
  expect(created).toEqual(fixture('scenario.create'));
  await client.addScenarioEvent(created.id, records['scenario.event.add'].request.body as Schema['ScenarioEventIn']);
  expect((await client.scenario(created.id)).events).toHaveLength(2);
  expect((await client.schedule(sc.outlet_id, sc.week_start)).current_version).toEqual(before.current_version);
  expect(requests.filter(r => ['POST', 'PATCH', 'PUT'].includes(r.method)).map(r => new URL(r.url).pathname)).toEqual(['/v2/session/demo', `/v2/outlets/${sc.outlet_id}/schedules/${sc.week_start}/scenarios`, `/v2/scenarios/${sc.id}/events`]);
});
it('admits a simulation with a stable key but never fabricates a completed solver run', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  const input = { strategy: 'balanced', time_limit_seconds: 10 } as const;
  const run = await client.runScenario(sc.id, input, 'scenario-run-key');
  expect(run.kind).toBe('scenario'); expect(run.scenario_id).toBe(sc.id);
  expect(await client.runScenario(sc.id, input, 'scenario-run-key')).toEqual(run);
  await expect(client.runScenario(sc.id, { strategy: 'fairness', time_limit_seconds: 10 }, 'scenario-run-key')).rejects.toMatchObject({ status: 409 });
  await expect(client.run(run.id)).rejects.toMatchObject({ status: 501 });
  expect(requests[1].headers.get('Idempotency-Key')).toBe('scenario-run-key');
});
it('converts only to the supplied scenario draft, replays its key, and preserves proposal identity', async () => {
  const { client } = setup(); await client.signIn('manager');
  const body = records['scenario.convert'].request.body as Schema['ConvertScenarioRequest'];
  const draft = await client.convertScenario(sc.id, body, 'convert-stable-key');
  expect(draft.source).toBe('scenario'); expect(draft.status).toBe('draft');
  expect(await client.convertScenario(sc.id, body, 'convert-stable-key')).toEqual(draft);
  expect((await client.scenario(sc.id)).converted_version_id).toBe(draft.id);
  expect((await client.schedule(sc.outlet_id, sc.week_start)).current_version?.id).toBe(sc.base_version_id);
  const proposal = await client.createProposal({ draft_version_id: draft.id, expected_revision: draft.revision }, 'propose-scenario');
  expect(proposal.candidate_id).toBe(body.candidate_id); expect(proposal.base_version_id).toBe(sc.base_version_id);
});
it('discards without changing real facts and rejects writes to a closed workspace', async () => {
  const { client } = setup(); await client.signIn('manager');
  expect((await client.discardScenario(sc.id)).status).toBe('discarded');
  await expect(client.addScenarioEvent(sc.id, records['scenario.event.add'].request.body as Schema['ScenarioEventIn'])).rejects.toMatchObject({ status: 409 });
  expect((await client.schedule(sc.outlet_id, sc.week_start)).current_version?.id).toBe(sc.base_version_id);
  await client.signIn('staff'); await expect(client.scenarios(sc.outlet_id, sc.week_start)).rejects.toMatchObject({ status: 403 });
});
