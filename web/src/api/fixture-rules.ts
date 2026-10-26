import records from './generated/fixtures.json';
import type { Fixture, Persona, Schema } from './types';
import { ruleIdentity } from '../lib/rules';

const fixtures = records as unknown as Record<string, Fixture>;
const read = <T>(name: string) => structuredClone(fixtures[name].response.body) as T;
const response = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const failure = (code: string, message: string, status: number) => response({ error: { code, message, retryable: false, details: {} } }, status);
const states = new Map<string, { rules: Schema['SchedulingRule'][]; touched: number; replay: Map<string, { body: string; value: Schema['SchedulingRule'] }> }>();

/** Fixed provider examples only: no rule resolution, conflict analysis or impact calculation. */
export async function ruleFixture(url: URL, request: Request, persona: Persona): Promise<Response | null> {
  if (url.pathname !== '/v2/rules' && url.pathname !== '/v2/rules/preview' && !/^\/v2\/rules\/[^/]+\/archive$/.test(url.pathname)) return null;
  if (persona === 'staff' || request.headers.get('X-ShiftPilot-Scenario') === 'denied') return failure('permission_denied', 'Scheduling rules are outside your access.', 403);
  const nonce = request.headers.get('X-ShiftPilot-Preview-Session');
  if (!nonce || !/^[\w-]{1,80}$/.test(nonce)) return failure('validation_failed', 'A valid preview session is required.', 422);
  const now = Date.now(); for (const [key, value] of states) if (now - value.touched > 1800000) states.delete(key);
  const key = `${persona}:${nonce}`;
  if (!states.has(key)) { if (states.size >= 64) states.delete(states.keys().next().value!); states.set(key, { rules: read<Schema['RuleList']>('rules.list').items, touched: now, replay: new Map() }); }
  const state = states.get(key)!; state.touched = now;
  if (url.pathname === '/v2/rules' && request.method === 'GET') return response({ items: state.rules.filter(value => url.searchParams.get('include_archived') === 'true' || value.status !== 'archived') });
  const archive = /^\/v2\/rules\/([^/]+)\/archive$/.exec(url.pathname);
  if (archive && request.method === 'POST') {
    if (persona !== 'owner') return failure('permission_denied', 'Only an owner can change this tag-scoped rule.', 403);
    const supplied = read<Schema['SchedulingRule']>('rules.archive');
    if (archive[1] !== supplied.id || !state.rules.some(value => value.id === supplied.id)) return failure('not_implemented', 'No supplied archive record matches this rule.', 501);
    state.rules = state.rules.map(value => value.id === supplied.id ? supplied : value); return response(supplied);
  }
  if (request.method !== 'POST') return failure('not_implemented', 'No supplied rule example matches this operation.', 501);
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== 'object') return failure('validation_failed', 'Send a structured rule.', 422);
  if (persona !== 'owner' && ['organization', 'tag'].includes(body.scope_level)) return failure('permission_denied', 'Only an owner can set organization-wide or tag rules.', 403);
  const identity = ruleIdentity(body);
  const student = fixtures['rules.preview'].request.body;
  const conflict = fixtures['rules.preview.conflict'].request.body;
  if (url.pathname === '/v2/rules/preview') {
    if (identity === ruleIdentity(student)) return response(read('rules.preview'));
    if (identity === ruleIdentity(conflict) && state.rules.some(value => value.status === 'active')) return response(read('rules.preview.conflict'));
    return failure('not_implemented', 'No matching rule preview is supplied. Suggested exceptions and other definitions need a connected API.', 501);
  }
  const idempotencyKey = request.headers.get('Idempotency-Key');
  if (!idempotencyKey) return failure('validation_failed', 'A stable rule-save key is required.', 422);
  const replay = state.replay.get(idempotencyKey);
  if (replay) return replay.body === identity ? response(replay.value, 201) : failure('idempotency_conflict', 'This key belongs to another rule definition.', 409);
  if (identity === ruleIdentity(conflict)) return failure('conflict', 'This conflicts with Students must finish by 9 PM on weekdays. Preview and resolve it before saving.', 409);
  if (identity !== ruleIdentity(student) || state.rules.some(value => value.status === 'archived')) return failure('not_implemented', 'No matching rule-save fixture is supplied. This preview does not recreate archived rules or save exception definitions.', 501);
  const value = read<Schema['SchedulingRule']>('rules.create'); state.rules = [...state.rules.filter(rule => rule.id !== value.id), value];
  if (state.replay.size >= 64) state.replay.delete(state.replay.keys().next().value!); state.replay.set(idempotencyKey, { body: identity, value });
  return response(value, 201);
}
