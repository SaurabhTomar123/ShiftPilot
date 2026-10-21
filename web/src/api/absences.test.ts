import { expect, it } from 'vitest';
import { SchedulingClient, watchRun } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import records from './generated/fixtures.json';
import type { Schema } from './types';
import { runMessage } from './presentation';

function setup() {
  const requests: Request[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const path = String(input).replace('/api/fixture', ''); const request = new Request(`http://fixture.invalid${path}`, init);
    requests.push(request.clone()); return fixtureResponse(path, request);
  };
  return { client: new SchedulingClient({ baseUrl: '/api/fixture', fetcher }), requests };
}

it('does not present expired candidate results as ready solver options', () => {
  const expired = fixture<Schema['OptimizationRun']>('run.candidates_expired');
  expect(expired.candidates_expired).toBe(true);
  expect(runMessage(expired).title).toContain('expired');
  expect(runMessage(expired).body).toContain('start a new run');
});

it('records an absence once, then reads its repair without generation or publication', async () => {
  const { client, requests } = setup(); await client.signIn('manager');
  const result = await client.reportAbsence(records['absence.report'].request.body as Schema['ReportAbsenceRequest'], 'stable-absence');
  expect(result).toEqual(fixture('absence.report'));
  const signal = new AbortController().signal;
  const run = await watchRun(client, await client.run(result.repair_run_ids![0]), { signal, onUpdate: () => {} });
  expect(run.kind).toBe('repair'); expect(run.candidates.length).toBeGreaterThan(0);
  expect(requests.filter(r => r.method === 'POST')).toHaveLength(2);
  expect(requests[1].headers.get('Idempotency-Key')).toBe('stable-absence');
});

it('does not substitute unrelated preview facts for dates, status decisions or repair options', async () => {
  const { client } = setup(); await client.signIn('manager');
  await expect(client.reportAbsence({ ...records['absence.report'].request.body as Schema['ReportAbsenceRequest'], end_at: '2026-10-25T00:00:00+05:30' }, 'other')).rejects.toMatchObject({ status: 501 });
  const list = fixture<Schema['AbsenceList']>('absences.list');
  await expect(client.updateAbsence(list.items.find(item => item.status === 'requested')!.id, { status: 'confirmed' })).rejects.toMatchObject({ status: 501 });
  const run = fixture<Schema['OptimizationRun']>('run.repair.widened');
  await expect(client.candidate(run.candidates[0].id)).rejects.toMatchObject({ status: 501 });
});

it('scopes absence reads by outlet and overlapping interval', async () => {
  const { client } = setup(); const me = await client.signIn('manager');
  const current = await client.absences(me.outlet_id!, '2026-10-19T00:00:00+05:30', '2026-10-26T00:00:00+05:30'); expect(current.items).toHaveLength(2);
  expect((await client.absences(me.outlet_id!, '2026-10-26T00:00:00+05:30', '2026-11-02T00:00:00+05:30')).items).toHaveLength(0);
  await expect(client.absences(crypto.randomUUID(), '2026-10-19T00:00:00Z', '2026-10-26T00:00:00Z')).rejects.toMatchObject({ status: 501 });
});

it('leaving one screen does not abort another screen sharing its pending schedule read', async () => {
  let release!: () => void;
  let scheduleReads = 0;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (input, init) => {
    const path = String(input).replace('/api/fixture', '');
    if (path.includes('/schedules/')) { scheduleReads += 1; await gate; init?.signal?.throwIfAborted(); }
    return fixtureResponse(path, new Request(`http://fixture.invalid${path}`, init));
  } });
  const me = await client.signIn('manager');
  const departing = new AbortController(); const arriving = new AbortController();
  const oldRead = client.schedule(me.outlet_id!, '2026-10-19', departing.signal);
  const oldResult = expect(oldRead).rejects.toMatchObject({ name: 'AbortError' });
  departing.abort();
  const newRead = client.schedule(me.outlet_id!, '2026-10-19', arriving.signal);
  release();
  await oldResult; expect((await newRead).current_version).not.toBeNull(); expect(scheduleReads).toBe(1);
});

it('sends exact freeze inputs and never returns unprotected success for unsupported preview requests', async () => {
  const { client, requests } = setup(); const me = await client.signIn('manager');
  const body: Schema['RepairRequest'] = { ...records['repair.freeze_conflict'].request.body, allow_cross_outlet: false };
  await expect(client.repair(me.outlet_id!, '2026-10-19', body, 'freeze-conflict')).rejects.toMatchObject({ status: 409, detail: { details: { frozen_logical_shift_ids: body.freeze!.shift_ids } } });
  expect(await requests.at(-1)!.json()).toEqual(body);
  expect(requests.at(-1)!.headers.get('Idempotency-Key')).toBe('freeze-conflict');
  await expect(client.repair(me.outlet_id!, '2026-10-19', { ...body, freeze: { employee_ids: [crypto.randomUUID()] } }, 'unknown-freeze')).rejects.toMatchObject({ status: 501 });
  await expect(client.generate(me.outlet_id!, '2026-10-26', { base_version_id: null, strategy: 'balanced', time_limit_seconds: 10, freeze: { days: ['2026-10-26'] } }, 'empty-freeze')).rejects.toMatchObject({ status: 501 });
  expect(requests.filter(request => request.method === 'POST')).toHaveLength(4);
});
