import fixtures from './generated/fixtures.json';
import type { Fixture, Persona, Scenario, Schema } from './types';

const records = fixtures as unknown as Record<string, Fixture>;
export const fixture = <T>(name: string) => structuredClone(records[name].response.body) as T;
const respond = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const reply = (name: string) => respond(fixture(name), records[name].response.status);
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
  const indiranagar = fixture<Schema['OutletList']>('outlets.manager').items[0].id;
  if (url.pathname === '/v2/me' && method === 'GET') return reply(`me.${persona}`);
  if (url.pathname === '/v2/me/shifts' && method === 'GET') {
    if (persona !== 'staff') return denied();
    return url.searchParams.get('week_start') === '2026-10-19' ? reply('my_week.staff') : missing();
  }
  if (persona === 'staff') return denied();
  if (url.pathname === '/v2/outlets' && method === 'GET') return reply(`outlets.${persona}`);
  if (url.pathname === '/v2/skills' && method === 'GET') return reply('skills.list');
  if (url.pathname === '/v2/employees' && method === 'GET') {
    if (url.searchParams.get('outlet_id') !== indiranagar) return persona === 'manager' ? denied() : missing();
    return url.searchParams.has('cursor') ? missing() : reply('employees.list');
  }
  const schedule = /^\/v2\/outlets\/([^/]+)\/schedules\/(\d{4}-\d{2}-\d{2})(\/generate)?$/.exec(url.pathname);
  if (schedule) {
    const [, outletId, week, generate] = schedule;
    if (scenario === 'denied' || (persona === 'manager' && outletId !== me.outlet_id)) return denied();
    if (outletId !== indiranagar) return missing();
    if (!generate && method === 'GET') {
      if (week === '2026-10-19') return reply('schedule_week.published');
      if (week === '2026-10-26') return reply('schedule_week.empty');
      return missing();
    }
    if (generate && method === 'POST') {
      if (!request.headers.get('Idempotency-Key')) return respond({ error: { code: 'validation_failed', message: 'An idempotency key is required.', retryable: false, details: {} } }, 422);
      // Generate fixtures only cover the empty week and their balanced request.
      const body = await request.json().catch(() => null);
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
    const draft = fixture<Schema['ScheduleVersion']>('schedule_version.draft');
    return url.pathname.split('/').at(-1) === draft.id ? reply('schedule_version.draft') : missing();
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
