import records from './generated/fixtures.json';
import type { Fixture, Persona, Schema } from './types';

const fixtures = records as unknown as Record<string, Fixture>;
const read = <T>(name: string) => structuredClone(fixtures[name].response.body) as T;
const response = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const missing = () => response({ error: { code: 'not_implemented', message: 'No matching scenario fixture is supplied for this request. A completed scenario run and candidate detail require a connected API.', retryable: false, details: {} } }, 501);
export const scenarioCandidateId = (fixtures['scenario.convert'].request.body as Schema['ConvertScenarioRequest']).candidate_id;
const states = new Map<string, { value: Schema['Scenario']; touched: number; runs: Map<string, string> }>();
const keyFor = (request: Request, persona: Persona) => `${persona}:${request.headers.get('X-ShiftPilot-Preview-Session')}`;
export function scenarioPreview(request: Request, persona: Persona) {
  const now = Date.now(); for (const [key, value] of states) if (now - value.touched > 1800000) states.delete(key);
  const key = keyFor(request, persona);
  if (!states.has(key)) { if (states.size >= 64) states.delete(states.keys().next().value!); states.set(key, { value: read<Schema['Scenario']>('scenario.get'), touched: now, runs: new Map() }); }
  const state = states.get(key)!; state.touched = now; return state;
}
export function recordScenarioConversion(request: Request, persona: Persona, draft: Schema['ScheduleVersion']) { const state = scenarioPreview(request, persona); state.value = { ...state.value, status: 'converted', converted_version_id: draft.id }; }

/** Provider facts only; no simulated solver result is assembled in this gateway. */
export async function scenarioFixture(url: URL, request: Request, persona: Persona): Promise<Response | null> {
  const create = /^\/v2\/outlets\/([^/]+)\/schedules\/([^/]+)\/scenarios$/.exec(url.pathname);
  const list = /^\/v2\/outlets\/([^/]+)\/scenarios$/.exec(url.pathname);
  const detail = /^\/v2\/scenarios\/([^/]+)(\/(?:events|run|discard|convert))?$/.exec(url.pathname);
  const sample = read<Schema['Scenario']>('scenario.get');
  const runId = read<Schema['OptimizationRun']>('scenario.run.accepted').id;
  if (!create && !list && !detail && url.pathname !== `/v2/optimization-runs/${runId}`) return null;
  if (request.headers.get('X-ShiftPilot-Scenario') === 'denied') return response(read('schedule_week.denied'), 403);
  if (!request.headers.get('X-ShiftPilot-Preview-Session')) return missing();
  if ((create?.[1] ?? list?.[1] ?? sample.outlet_id) !== sample.outlet_id) return missing();
  if (url.pathname === `/v2/optimization-runs/${runId}`) return missing();
  if (list && request.method === 'GET') return response({ items: url.searchParams.get('week_start') === sample.week_start ? [scenarioPreview(request, persona).value] : [] });
  if (create && request.method === 'POST') {
    const body = await request.json().catch(() => null); const input = fixtures['scenario.create'].request.body;
    if (create[2] !== sample.week_start || JSON.stringify(body) !== JSON.stringify(input)) return missing();
    const value = read<Schema['Scenario']>('scenario.create'); scenarioPreview(request, persona).value = value; return response(value, 201);
  }
  if (!detail || detail[1] !== sample.id) return missing();
  const state = scenarioPreview(request, persona);
  if (detail[2] === '/convert') return null; // The shared review gateway materializes its supplied draft.
  if (!detail[2] && request.method === 'GET') return response(state.value);
  if (state.value.status !== 'open') return response({ error: { code: 'conflict', message: `This scenario is ${state.value.status}; it can no longer change.`, retryable: false, details: {} } }, 409);
  if (detail[2] === '/events' && request.method === 'POST') {
    const body = await request.json().catch(() => null);
    if (JSON.stringify(body) !== JSON.stringify(fixtures['scenario.event.add'].request.body) || state.value.events.length !== 1) return missing();
    state.value = read('scenario.event.add'); return response(state.value, 201);
  }
  if (detail[2] === '/discard' && request.method === 'POST') { state.value = { ...state.value, status: 'discarded' }; return response(state.value); }
  if (detail[2] === '/run' && request.method === 'POST') {
    const body = await request.json().catch(() => null);
    const key = request.headers.get('Idempotency-Key');
    const fingerprint = JSON.stringify(body);
    if (key && state.runs.has(key) && state.runs.get(key) !== fingerprint) return response({ error: { code: 'idempotency_conflict', message: 'This key belongs to another scenario run request.', retryable: false, details: {} } }, 409);
    if (!key) return response({ error: { code: 'validation_failed', message: 'A stable run key is required.', retryable: false, details: {} } }, 422);
    if (body?.strategy !== 'balanced' || body?.time_limit_seconds !== 10 || state.value.events.length !== 2) return missing();
    if (state.runs.size >= 64) state.runs.delete(state.runs.keys().next().value!);
    state.runs.set(key, fingerprint);
    const run = read<Schema['OptimizationRun']>('scenario.run.accepted'); state.value = { ...state.value, latest_run_id: run.id, baseline: sample.baseline }; return response(run, 202);
  }
  return missing();
}
