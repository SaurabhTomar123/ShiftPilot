import { describe, expect, it, vi } from 'vitest';
import { ApiError, SchedulingClient, generateOrAttach, watchRun } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import { formatMoney, localDate, localTime, percent, runMessage } from './presentation';
import type { Scenario } from './types';

function setup(scenario: Scenario = 'optimal') {
  const requests: Request[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const path = String(input).replace('/api/fixture', '');
    const request = new Request(`http://fixture.invalid${path}`, init);
    requests.push(request.clone());
    return fixtureResponse(path, request);
  };
  return { requests, client: new SchedulingClient({ baseUrl: '/api/fixture', fetcher, fixtureScenario: scenario }) };
}

describe('contract client', () => {
  it('uses bearer auth, scoped UUIDs and approved read fixtures', async () => {
    const { client, requests } = setup();
    const me = await client.signIn('manager');
    const response = await client.schedule(me.outlet_id!, '2026-10-19');
    expect(response).toEqual(fixture('schedule_week.published'));
    expect(response.employees).toHaveLength(13);
    expect(requests[0].headers.has('Authorization')).toBe(false);
    expect(requests[1].headers.get('Authorization')).toBe('Bearer ui-fixture-manager');
    expect(requests[1].credentials).toBe('omit');
  });

  it('clears an expired session and notifies the UI without retrying', async () => {
    let expired = false;
    const unauthorized = vi.fn();
    const headers: (string | null)[] = [];
    const client = new SchedulingClient({ baseUrl: '/api/fixture', onUnauthorized: unauthorized, fetcher: async (input, init) => {
      const request = new Request(`http://fixture.invalid${String(input).replace('/api/fixture', '')}`, init);
      headers.push(request.headers.get('Authorization'));
      if (expired) return Response.json({ error: { code: 'unauthenticated', message: 'Session expired', retryable: false, details: {} } }, { status: 401 });
      return fixtureResponse(new URL(request.url).pathname, request);
    } });
    await client.signIn('manager'); expired = true;
    await expect(client.me()).rejects.toMatchObject({ status: 401 });
    await expect(client.me()).rejects.toBeInstanceOf(ApiError);
    expect(unauthorized).toHaveBeenCalledTimes(2);
    expect(headers).toEqual([null, 'Bearer ui-fixture-manager', null]);
  });

  it('does not let a late persona response replace the current credentials', async () => {
    let resolveFirst!: (response: Response) => void;
    const first = new Promise<Response>(resolve => { resolveFirst = resolve; });
    let count = 0;
    const { client: original } = setup();
    const staff = await original.signIn('staff');
    const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (input, init) => {
      if (String(input).endsWith('/session/demo') && count++ === 0) return first;
      return fixtureResponse(String(input).replace('/api/fixture', ''), new Request(`http://fixture.invalid${String(input).replace('/api/fixture', '')}`, init));
    } });
    const stale = client.signIn('manager').catch(error => error);
    await client.signIn('staff');
    resolveFirst(Response.json(fixture('session.demo.manager')));
    expect((await stale).name).toBe('AbortError');
    expect((await client.me()).user_id).toBe(staff.user_id);
  });

  it('sends the caller’s stable idempotency key and never retries a stale write', async () => {
    const { client, requests } = setup('stale');
    const me = await client.signIn('manager');
    await expect(client.generate(me.outlet_id!, '2026-10-26', { base_version_id: null, strategy: 'balanced', time_limit_seconds: 10 }, 'same-request')).rejects.toMatchObject({ status: 409, detail: { code: 'stale_version' } });
    expect(requests).toHaveLength(2);
    expect(requests[1].headers.get('Idempotency-Key')).toBe('same-request');
  });

  it('never sends fixture scenario headers to a real API', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(fixture('me.manager')));
    const client = new SchedulingClient({ baseUrl: 'https://api.example.test', fixtureScenario: 'denied', fetcher });
    await client.me();
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has('X-ShiftPilot-Scenario')).toBe(false);
  });

  it('handles non-JSON errors without leaking a server response into UI text', async () => {
    const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async () => new Response('<private internal dump>', { status: 500 }) });
    await expect(client.me()).rejects.toMatchObject({ message: 'The scheduling service returned an unreadable response.' });
  });

  it('returns denial for a manager’s foreign outlet and no invented data for an unknown week', async () => {
    const { client } = setup();
    const me = await client.signIn('manager');
    await expect(client.schedule('other-outlet', '2026-10-19')).rejects.toMatchObject({ status: 403 });
    await expect(client.schedule(me.outlet_id!, '2027-01-04')).rejects.toMatchObject({ status: 501 });
  });

  it('staff receive only their own assignments, without employee costs', async () => {
    const { client } = setup();
    const me = await client.signIn('staff');
    const week = await client.myWeek('2026-10-19');
    expect(week.shifts.every(s => s.employee_id === me.employee_id)).toBe(true);
    expect(JSON.stringify(week)).not.toContain('hourly_rate');
    await expect(client.employees(me.outlet_id!)).rejects.toMatchObject({ status: 403 });
  });
});

describe('solver status and presentation', () => {
  it.each([
    ['run.succeeded', 'Drafts ready'], ['run.time_limited_feasible', 'room to improve'],
    ['run.infeasible', 'cannot all be met'], ['run.no_solution_in_time', 'time limit'], ['run.failed', 'could not finish'],
  ])('explains %s without equating a time limit with infeasibility', (name, title) => {
    expect(runMessage(fixture(name)).title).toContain(title);
    if (name === 'run.no_solution_in_time') expect(runMessage(fixture(name)).body).toContain('does not mean');
  });

  it('polls according to provider guidance and stops at a feasible terminal result', async () => {
    const client = { run: vi.fn().mockResolvedValueOnce(fixture('run.running')).mockResolvedValueOnce(fixture('run.time_limited_feasible')) } as unknown as SchedulingClient;
    const wait = vi.fn().mockResolvedValue(undefined);
    const updates: string[] = [];
    const value = await watchRun(client, fixture('run.queued'), { signal: new AbortController().signal, wait, onUpdate: run => updates.push(run.job_state) });
    expect(updates).toEqual(['queued', 'running', 'succeeded']);
    expect(value.solver_status).toBe('FEASIBLE');
    expect(wait).toHaveBeenCalledTimes(2);
    expect(client.run).toHaveBeenCalledTimes(2);
  });

  it('cancels polling on scope changes without another fetch', async () => {
    const controller = new AbortController(); controller.abort();
    const client = { run: vi.fn() } as unknown as SchedulingClient;
    await expect(watchRun(client, fixture('run.queued'), { signal: controller.signal, onUpdate: vi.fn() })).rejects.toMatchObject({ name: 'AbortError' });
    expect(client.run).not.toHaveBeenCalled();
  });

  it('bounds polling without claiming the run failed', async () => {
    const client = { run: vi.fn().mockResolvedValue(fixture('run.running')) } as unknown as SchedulingClient;
    await expect(watchRun(client, fixture('run.queued'), { signal: new AbortController().signal, maxPolls: 2, wait: vi.fn().mockResolvedValue(undefined), onUpdate: vi.fn() })).rejects.toThrow('may still be running');
    expect(client.run).toHaveBeenCalledTimes(2);
  });

  it('preserves paise, distinguishes zero/no-demand coverage, and uses outlet-local time', () => {
    expect(formatMoney({ amount_paise: 21001, currency: 'INR' })).toBe('₹210.01');
    expect(percent(null)).toBe('Not applicable'); expect(percent(0)).toBe('0%');
    expect(localDate('2026-10-19T20:00:00Z', 'Asia/Kolkata')).toBe('2026-10-20');
    expect(localTime('2026-10-19T20:00:00Z', 'Asia/Kolkata')).toBe('01:30');
  });
});

describe('contract 2.2 admission and private caching', () => {
  it('attaches to the active run with exactly one POST', async () => {
    const { client, requests } = setup('active');
    const me = await client.signIn('manager');
    const run = await generateOrAttach(client, me.outlet_id!, '2026-10-26', { base_version_id: null, strategy: 'balanced', time_limit_seconds: 10 }, 'one-write', new AbortController().signal);
    expect(run.solver_status).toBe('OPTIMAL');
    expect(requests.filter(r => r.method === 'POST' && r.url.endsWith('/generate'))).toHaveLength(1);
    expect(requests.at(-1)?.url).toContain(`/optimization-runs/${run.id}`);
  });

  it('exposes Retry-After without retrying a rate-limited write', async () => {
    const { client, requests } = setup('rate_limited');
    const me = await client.signIn('manager');
    await expect(generateOrAttach(client, me.outlet_id!, '2026-10-26', { base_version_id: null, strategy: 'balanced', time_limit_seconds: 10 }, 'one-write', new AbortController().signal)).rejects.toMatchObject({ status: 429, retryAfter: '3' });
    expect(requests).toHaveLength(2);
  });

  it('revalidates a week and published version with ETag, reusing the body on 304', async () => {
    const { client, requests } = setup();
    const me = await client.signIn('manager');
    const week = await client.schedule(me.outlet_id!, '2026-10-19');
    expect(await client.schedule(me.outlet_id!, '2026-10-19')).toEqual(week);
    expect(requests.at(-1)?.headers.get('If-None-Match')).toBeTruthy();
    const version = await client.version(week.current_version!.id);
    expect(await client.version(version.id)).toEqual(version);
    expect(requests.at(-1)?.headers.get('If-None-Match')).toBe(`"${version.id}"`);
    await client.signIn('staff');
    await expect(client.schedule(me.outlet_id!, '2026-10-19')).rejects.toMatchObject({ status: 403 });
    expect(requests.at(-1)?.headers.has('If-None-Match')).toBe(false);
  });

  it('cannot repopulate a cache with a late response from a replaced session', async () => {
    let release!: (response: Response) => void;
    const deferred = new Promise<Response>(resolve => { release = resolve; });
    const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async () => deferred });
    const stale = client.schedule('old-outlet', '2026-10-19').catch(error => error);
    client.clearSession();
    release(Response.json(fixture('schedule_week.published'), { headers: { ETag: 'old' } }));
    expect((await stale).name).toBe('AbortError');
  });
});

describe('management forms transport and synthetic isolation', () => {
  it('creates once per key, saves changed fields, and rejects stale employee revisions', async () => {
    const { client } = setup(); const me = await client.signIn('manager');
    const original = (await client.employees(me.outlet_id!)).items[0];
    const input = { ...original, name: 'Ananya Rao' };
    const created = await client.createEmployee(input, 'create-once');
    expect(await client.createEmployee(input, 'create-once')).toEqual(created);
    const updated = await client.updateEmployee(created.id, { base_revision: created.revision, preferred_weekly_minutes: null, name: 'Ananya Nair' });
    expect(updated.revision).toBe(created.revision + 1);
    await expect(client.updateEmployee(created.id, { base_revision: created.revision, name: 'Old tab' })).rejects.toMatchObject({ status: 409 });
    expect((await client.employee(created.id)).name).toBe('Ananya Nair');
  });
  it('never shares synthetic edits with another session or sends preview session IDs to a real API', async () => {
    const { client } = setup(); const me = await client.signIn('manager');
    const employee = (await client.employees(me.outlet_id!)).items[0];
    await client.updateEmployee(employee.id, { base_revision: employee.revision, name: 'Preview only' });
    const other = setup().client; await other.signIn('manager');
    expect((await other.employee(employee.id)).name).toBe(employee.name);
    await client.signIn('manager');
    expect((await client.employee(employee.id)).name).toBe(employee.name);
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(fixture('me.manager')));
    await new SchedulingClient({ baseUrl: 'https://api.example.test', fetcher }).me();
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has('X-ShiftPilot-Preview-Session')).toBe(false);
  });
  it('preserves overnight recurring windows and versions the full staffing week', async () => {
    const { client } = setup(); const me = await client.signIn('manager');
    const employee = (await client.employees(me.outlet_id!)).items[0];
    const availability = await client.availability(employee.id);
    const windows = [{ weekday: 6, start_minute: 1320, end_minute: 1560, kind: 'available' as const }];
    const saved = await client.saveAvailability(employee.id, { base_revision: availability.revision, windows });
    expect(saved.windows).toEqual(windows);
    expect(saved.revision).toBe(availability.revision + 1);
    const staffing = await client.staffing(me.outlet_id!, '2026-10-19');
    const intervals = staffing.intervals.map((value, i) => i ? value : { ...value, preferred_required: value.preferred_required + 1 });
    const demand = await client.saveStaffing(me.outlet_id!, staffing.week_start, { base_demand_revision: staffing.demand_revision, intervals });
    expect(demand.intervals).toEqual(intervals);
    expect(demand.demand_revision).toBe(staffing.demand_revision + 1);
  });
});
