import fixtures from './generated/fixtures.json';
import type { Fixture, Persona, Scenario, Schema } from './types';
import { managementFixture } from './fixture-management';
import { reviewFixture } from './fixture-review';
import { absenceFixture } from './fixture-absences';

const records = fixtures as unknown as Record<string, Fixture>;
export const fixture = <T>(name: string) => structuredClone(records[name].response.body) as T;
const respond = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const reply = (name: string, request?: Request) => {
  const record = records[name].response;
  const headers = { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture', ...record.headers };
  const etag = record.headers?.ETag;
  if (etag && request?.headers.get('If-None-Match') === etag) return new Response(null, { status: 304, headers });
  return Response.json(fixture(name), { status: record.status, headers });
};
const missing = () => respond({ error: { code: 'not_implemented', message: 'No provider fixture is available for this request yet.', retryable: false, details: {} } }, 501);
const denied = () => reply('schedule_week.denied');

/** Only for synthetic contract previews. Never proxy private API requests here. */
export async function fixtureResponse(path: string, request: Request): Promise<Response> {
  const url = new URL(path, 'http://fixture.invalid');
  const method = request.method;
  const scenario = request.headers.get('X-ShiftPilot-Scenario') as Scenario | null;
  if (method === 'POST' && url.pathname === '/v2/session/demo') {
    const input: unknown = await request.json().catch(() => null);
    const persona = input && typeof input === 'object' && 'persona' in input ? input.persona : null;
    if (!['owner', 'manager', 'staff'].includes(String(persona))) return respond({ error: { code: 'validation_failed', message: 'Choose a supported demo persona.', retryable: false, details: {} } }, 422);
    const session = fixture<Schema['DemoSession']>('session.demo.manager');
    session.me = fixture<Schema['Me']>(`me.${persona}`);
    session.access_token = `ui-fixture-${persona}`;
    return respond(session, 201);
  }
  const match = /^Bearer ui-fixture-(owner|manager|staff)$/.exec(request.headers.get('Authorization') ?? '');
  if (!match) return reply('me.unauthenticated');
  const persona = match[1] as Persona;
  const me = fixture<Schema['Me']>(`me.${persona}`);
  const ownerOutlets = fixture<Schema['OutletList']>('outlets.owner').items;
  const ownerFixture = (id: string, prefix: string) => id === ownerOutlets[1]?.id ? `${prefix}.owner.koramangala` : id === ownerOutlets[2]?.id ? `${prefix}.owner.hsr` : null;
  const indiranagar = fixture<Schema['OutletList']>('outlets.manager').items[0].id;
  if (url.pathname === '/v2/me' && method === 'GET') return reply(`me.${persona}`);
  if (url.pathname === '/v2/me/shifts' && method === 'GET') {
    if (persona !== 'staff') return denied();
    return url.searchParams.get('week_start') === '2026-10-19' ? reply('my_week.staff') : missing();
  }
  if (persona === 'staff') return denied();
  if (url.pathname === '/v2/recommendations/replacements' && method === 'POST') {
    if (scenario === 'denied') return denied();
    const body = await request.json().catch(() => null);
    const sample = records['recommendations.replacements'].request?.body as Schema['ReplacementRequest'];
    if (body?.include_other_outlets && persona !== 'owner') return reply('recommendations.replacements.other_outlets.manager');
    if (body?.version_id !== sample.version_id || (body.profile ?? 'balanced') !== 'balanced' || (body.limit ?? 5) !== 5 || body.include_other_outlets) return missing();
    if (body.logical_shift_id === sample.logical_shift_id) return reply('recommendations.replacements');
    const unknown = records['recommendations.replacements.unknown_shift'].request?.body as Schema['ReplacementRequest'];
    return body.logical_shift_id === unknown.logical_shift_id ? reply('recommendations.replacements.unknown_shift') : missing();
  }
  const absence = await absenceFixture(url, request);
  if (absence) return absence;
  const review = await reviewFixture(url, request, persona, fixture);
  if (review) return review;
  const management = await managementFixture(url, request, persona, scenario, fixture);
  if (management) return management;
  if (url.pathname === '/v2/outlets' && method === 'GET') return reply(`outlets.${persona}`);
  if (url.pathname === '/v2/skills' && method === 'GET') return reply('skills.list');
  if (url.pathname === '/v2/employees' && method === 'GET') {
    if (url.searchParams.get('outlet_id') !== indiranagar) {
      if (persona === 'manager') return denied();
      const name = ownerFixture(url.searchParams.get('outlet_id') ?? '', 'employees.list');
      return name && !url.searchParams.has('cursor') ? reply(name) : missing();
    }
    return url.searchParams.has('cursor') ? missing() : reply('employees.list');
  }
  const schedule = /^\/v2\/outlets\/([^/]+)\/schedules\/(\d{4}-\d{2}-\d{2})(\/generate)?$/.exec(url.pathname);
  if (schedule) {
    const [, outletId, week, generate] = schedule;
    if (scenario === 'denied' || (persona === 'manager' && outletId !== me.outlet_id)) return denied();
    if (outletId !== indiranagar) {
      const name = ownerFixture(outletId, 'schedule_week');
      return persona === 'owner' && name && !generate && method === 'GET' && week === '2026-10-19' ? reply(name, request) : missing();
    }
    if (!generate && method === 'GET') {
      if (week === '2026-10-19') return reply('schedule_week.published', request);
      if (week === '2026-10-26') return reply('schedule_week.empty');
      return missing();
    }
    if (generate && method === 'POST') {
      if (!request.headers.get('Idempotency-Key')) return respond({ error: { code: 'validation_failed', message: 'An idempotency key is required.', retryable: false, details: {} } }, 422);
      // Generate fixtures only cover the empty week and their balanced request.
      const body = await request.json().catch(() => null);
      if (body?.freeze && ((body.freeze.shift_ids?.length ?? 0) + (body.freeze.employee_ids?.length ?? 0) + (body.freeze.days?.length ?? 0))) return missing();
      if (scenario === 'active') return reply('generate.run_in_progress');
      if (scenario === 'rate_limited') return reply('generate.rate_limited');
      if (scenario === 'stale') return reply('generate.stale_base');
      if (week !== '2026-10-26' || body?.base_version_id !== null || body?.strategy !== 'balanced') return missing();
      return reply('generate.accepted');
    }
  }
  if (method === 'GET' && url.pathname.startsWith('/v2/optimization-runs/')) {
    const queued = fixture<Schema['OptimizationRun']>('run.queued');
    if (url.pathname.split('/').at(-1) !== queued.id) return missing();
    const outcomes: Partial<Record<Scenario, string>> = { optimal: 'run.succeeded', feasible: 'run.time_limited_feasible', infeasible: 'run.infeasible', timeout: 'run.no_solution_in_time', failed: 'run.failed' };
    return reply(outcomes[scenario ?? 'optimal'] ?? 'run.succeeded');
  }
  if (method === 'GET' && url.pathname.startsWith('/v2/schedule-versions/')) {
    for (const name of ['schedule_version.draft', 'schedule_version.draft.lowest_cost', 'schedule_version.published']) {
      const version = fixture<Schema['ScheduleVersion']>(name);
      if (url.pathname.split('/').at(-1) === version.id) return reply(name, request);
    }
    return missing();
  }
  const availability = /^\/v2\/employees\/([^/]+)\/availability$/.exec(url.pathname);
  if (availability && method === 'GET') {
    for (const name of ['availability.get', 'availability.get.student']) {
      const value = fixture<Schema['Availability']>(name);
      if (value.employee_id === availability[1]) return reply(name);
    }
  }
  return missing();
}
