import { expect, it } from 'vitest';
import { SchedulingClient } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import records from './generated/fixtures.json';
import type { Schema } from './types';

const input = records['recommendations.replacements'].request.body as Schema['ReplacementRequest'];
function setup() {
  const requests: Request[] = [];
  const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (url, init) => {
    const path = String(url).replace('/api/fixture', ''); const request = new Request(`http://fixture.invalid${path}`, init);
    requests.push(request.clone()); return fixtureResponse(path, request);
  } });
  return { client, requests };
}
it('reads replacement facts without a mutation key, selection, draft or publication', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  expect(await client.recommendReplacements(input)).toEqual(fixture('recommendations.replacements'));
  expect(requests).toHaveLength(2);
  expect(requests[1].headers.get('Idempotency-Key')).toBeNull();
  expect(await requests[1].json()).toEqual(input);
});
it('does not fabricate cover for unsupported profiles, shifts, versions or owner widening', async () => {
  const { client } = setup(); await client.signIn('manager');
  for (const patch of [{ profile: 'fairness' as const }, { version_id: crypto.randomUUID() }, { logical_shift_id: crypto.randomUUID() }]) {
    await expect(client.recommendReplacements({ ...input, ...patch })).rejects.toMatchObject({ status: 501 });
  }
  await expect(client.recommendReplacements({ ...input, include_other_outlets: true })).rejects.toMatchObject({ status: 403 });
  await client.signIn('owner');
  await expect(client.recommendReplacements({ ...input, include_other_outlets: true })).rejects.toMatchObject({ status: 501 });
});
it('preserves unknown-shift validation and staff access denial', async () => {
  const { client } = setup(); await client.signIn('manager');
  await expect(client.recommendReplacements(records['recommendations.replacements.unknown_shift'].request.body as Schema['ReplacementRequest'])).rejects.toMatchObject({ status: 422, detail: { details: { fields: [{ path: ['logical_shift_id'], message: 'That shift is not in this version.' }] } } });
  await client.signIn('staff');
  await expect(client.recommendReplacements(input)).rejects.toMatchObject({ status: 403 });
});
it('does not retry failed recommendation POSTs or send preview headers to a live origin', async () => {
  let count = 0;
  const client = new SchedulingClient({ baseUrl: 'https://api.invalid', fixtureScenario: 'optimal', fetcher: async (_url, init) => {
    count++; expect(new Headers(init?.headers).has('X-ShiftPilot-Preview-Session')).toBe(false);
    return Response.json({ error: { code: 'internal', message: 'Unavailable', retryable: true, details: {} } }, { status: 500 });
  } });
  await expect(client.recommendReplacements(input)).rejects.toMatchObject({ status: 500 }); expect(count).toBe(1);
});
