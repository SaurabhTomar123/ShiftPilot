import type { Persona, Schema } from './types';

type ReadFixture = <T>(name: string) => T;
type Preview = { touched: number; draft?: Schema['ScheduleVersion']; proposal?: Schema['Proposal']; published?: Schema['ScheduleVersion']; replay: Map<string, { fingerprint: string; body: unknown; status: number }> };
const previews = new Map<string, Preview>();
const response = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const error = (code: string, message: string, status: number) => response({ error: { code, message, retryable: false, details: {} } }, status);

/** Volatile synthetic flow state only. Uses provider records; never calls the real API. */
export async function reviewFixture(url: URL, request: Request, persona: Persona, fixture: ReadFixture): Promise<Response | null> {
  const nonce = request.headers.get('X-ShiftPilot-Preview-Session');
  if (!nonce) return null;
  const candidate = /^\/v2\/optimization-candidates\/([^/]+)(\/select)?$/.exec(url.pathname);
  const proposalPath = /^\/v2\/proposals(?:\/([^/]+)(\/(?:approve|reject))?)?$/.exec(url.pathname);
  const versionPath = /^\/v2\/schedule-versions\/([^/]+)$/.exec(url.pathname);
  const weekPath = /^\/v2\/outlets\/([^/]+)\/schedules\/2026-10-26$/.exec(url.pathname);
  if (!candidate && !proposalPath && !versionPath && !weekPath) return null;
  const now = Date.now();
  for (const [key, value] of previews) if (now - value.touched > 1800000) previews.delete(key);
  const key = `${persona}:${nonce}`;
  if (!previews.has(key)) {
    if (previews.size >= 64) previews.delete(previews.keys().next().value!);
    previews.set(key, { touched: now, replay: new Map() });
  }
  const state = previews.get(key)!; state.touched = now;
  if (versionPath) return request.method === 'GET' && state.draft?.id === versionPath[1] ? response(state.published ?? state.draft) : null;
  if (weekPath) {
    const week = fixture<Schema['ScheduleWeek']>('schedule_week.empty');
    if (request.method !== 'GET' || !state.published || weekPath[1] !== week.outlet_id) return null;
    week.schedule_id = state.published.schedule_id; week.current_version = state.published;
    return response(week);
  }
  const detail = fixture<Schema['CandidateDetail']>('candidate.detail');
  if (candidate && candidate[1] !== detail.id) return error('not_implemented', 'A detailed provider fixture is not available for this option. Review the Balanced option in this preview.', 501);
  if (candidate && !candidate[2] && request.method === 'GET') return response({ ...detail, materialized_version_id: state.draft?.id ?? null });
  if (proposalPath?.[1] && proposalPath[1] !== state.proposal?.id) return error('not_found', 'No proposal exists in this synthetic session.', 404);
  if (proposalPath?.[1] && !proposalPath[2] && request.method === 'GET') return response(state.proposal);
  if (request.method !== 'POST') return error('not_implemented', 'This fixture operation is not available.', 501);
  const idempotencyKey = request.headers.get('Idempotency-Key');
  if (!idempotencyKey) return error('validation_failed', 'An idempotency key is required.', 422);
  const body = await request.json().catch(() => null);
  const fingerprint = `${url.pathname}:${JSON.stringify(body)}`;
  const replay = state.replay.get(idempotencyKey);
  if (replay) return replay.fingerprint === fingerprint ? response(replay.body, replay.status) : error('idempotency_conflict', 'This key belongs to another action.', 409);
  const remember = (value: unknown, status = 200) => {
    if (state.replay.size >= 64) state.replay.delete(state.replay.keys().next().value!);
    state.replay.set(idempotencyKey, { fingerprint, body: structuredClone(value), status }); return response(value, status);
  };
  if (candidate?.[2]) {
    if (state.published) return error('conflict', 'This option has already been published.', 409);
    state.draft ??= fixture<Schema['ScheduleVersion']>('candidate.select');
    return remember(state.draft, 201);
  }
  if (proposalPath && !proposalPath[1]) {
    if (!state.draft || body?.draft_version_id !== state.draft.id) return error('not_found', 'Select the Balanced option before proposing its draft.', 404);
    if (body.expected_revision !== state.draft.revision) return error('stale_version', 'This draft revision changed.', 409);
    if (state.proposal) return error('conflict', 'A proposal has already been created in this synthetic session. Start a new demo session to repeat the flow.', 409);
    state.proposal = fixture<Schema['Proposal']>('proposal.create'); return remember(state.proposal, 201);
  }
  if (state.proposal?.status !== 'pending') return error('conflict', 'This proposal is no longer pending.', 409);
  if (proposalPath?.[2] === '/reject') { state.proposal = fixture<Schema['Proposal']>('proposal.reject'); return remember(state.proposal); }
  if (proposalPath?.[2] === '/approve') {
    if (typeof body?.acknowledge_changes !== 'boolean') return error('validation_failed', 'State whether changed metrics are acknowledged.', 422);
    const outcome = request.headers.get('X-ShiftPilot-Approval-Outcome') ?? 'published';
    if (!['published', 'changed', 'stale', 'invalid'].includes(outcome)) return error('validation_failed', 'Choose a supported approval outcome.', 422);
    const name = outcome === 'changed' && body.acknowledge_changes ? 'acknowledged' : outcome;
    const decision = fixture<Schema['ProposalDecision']>(`proposal.approve.${name}`);
    state.proposal = decision.proposal;
    if (decision.outcome === 'published') {
      state.published = { ...state.draft!, ...decision.published! };
    }
    return remember(decision);
  }
  return error('not_implemented', 'This fixture operation is not available.', 501);
}
