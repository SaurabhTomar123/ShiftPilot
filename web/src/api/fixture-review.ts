import type { Persona, Schema } from './types';
import examples from './generated/edit-examples.json';

type ReadFixture = <T>(name: string) => T;
type Preview = { touched: number; draft?: Schema['ScheduleVersion']; proposal?: Schema['Proposal']; published?: Schema['ScheduleVersion']; replay: Map<string, { fingerprint: string; body: unknown; status: number }> };
const previews = new Map<string, Preview>();
const response = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } });
const error = (code: string, message: string, status: number) => response({ error: { code, message, retryable: false, details: {} } }, status);
const summary = (version: Schema['ScheduleVersion']) => Object.fromEntries(Object.entries(version).filter(([key]) => !['input_hash', 'shifts', 'metrics', 'coverage', 'validation'].includes(key))) as Schema['ScheduleVersionSummary'];
const canonical = (value: unknown): string => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);

/** Volatile synthetic flow state only. Uses provider records; never calls the real API. */
export async function reviewFixture(url: URL, request: Request, persona: Persona, fixture: ReadFixture): Promise<Response | null> {
  const nonce = request.headers.get('X-ShiftPilot-Preview-Session');
  if (!nonce) return null;
  if (request.headers.get('X-ShiftPilot-Scenario') === 'denied') return null;
  const candidate = /^\/v2\/optimization-candidates\/([^/]+)(\/select)?$/.exec(url.pathname);
  const proposalPath = /^\/v2\/proposals(?:\/([^/]+)(\/(?:approve|reject))?)?$/.exec(url.pathname);
  const versionPath = /^\/v2\/schedule-versions\/([^/]+)$/.exec(url.pathname);
  const weekPath = /^\/v2\/outlets\/([^/]+)\/schedules\/(2026-10-(?:19|26))$/.exec(url.pathname);
  const createPath = /^\/v2\/outlets\/([^/]+)\/schedules\/2026-10-19\/drafts$/.exec(url.pathname);
  const editPath = /^\/v2\/schedule-versions\/([^/]+)\/edits(\/preview)?$/.exec(url.pathname);
  const historyPath = /^\/v2\/schedules\/([^/]+)\/versions$/.exec(url.pathname);
  const comparePath = /^\/v2\/schedule-versions\/([^/]+)\/compare$/.exec(url.pathname);
  const restorePath = /^\/v2\/schedule-versions\/([^/]+)\/restore$/.exec(url.pathname);
  if (!candidate && !proposalPath && !versionPath && !weekPath && !createPath && !editPath && !historyPath && !comparePath && !restorePath) return null;
  const now = Date.now();
  for (const [key, value] of previews) if (now - value.touched > 1800000) previews.delete(key);
  const key = `${persona}:${nonce}`;
  if (!previews.has(key)) {
    if (previews.size >= 64) previews.delete(previews.keys().next().value!);
    previews.set(key, { touched: now, replay: new Map() });
  }
  const state = previews.get(key)!; state.touched = now;
  if (versionPath && request.method === 'GET') {
    if (state.draft?.id === versionPath[1]) return response(state.published ?? state.draft);
    for (const name of ['edits.apply', 'versions.restore']) { const value = fixture<Schema['ScheduleVersion']>(name); if (value.id === versionPath[1]) return response(value); }
    return null;
  }
  if (historyPath && request.method === 'GET') {
    const history = fixture<Schema['VersionHistory']>('versions.list');
    if (history.schedule_id !== historyPath[1]) {
      if (state.draft?.schedule_id !== historyPath[1]) return error('not_implemented', 'No provider history fixture is available for this schedule.', 501);
      return response({ schedule_id: historyPath[1], current_version_id: state.published?.id ?? null, items: [summary(state.published ?? state.draft)] });
    }
    if (state.draft?.schedule_id === history.schedule_id) {
      const value = state.published ?? state.draft;
      history.items = history.items.filter(v => v.id !== value.id);
      if (state.published) { history.current_version_id = value.id; history.items = history.items.map(v => v.status === 'published' ? { ...v, status: 'superseded' as const } : v); }
      history.items.unshift(summary(value)); history.items.sort((a, b) => b.version_number - a.version_number);
    }
    return response(history);
  }
  if (comparePath && request.method === 'GET') {
    const diff = fixture<Schema['VersionDiff']>('versions.compare'); const from = url.searchParams.get('with');
    if (comparePath[1] === diff.to_version_id && from === diff.from_version_id) {
      if (state.draft?.id === diff.to_version_id && state.draft.revision === 1) diff.changes = [];
      return response(diff);
    }
    if (comparePath[1] === diff.from_version_id && from === diff.to_version_id) return response({ from_version_id: diff.to_version_id, to_version_id: diff.from_version_id, changes: diff.changes.map(c => ({ ...c, before: c.after, after: c.before })), metrics_from: diff.metrics_to, metrics_to: diff.metrics_from });
    return error('not_implemented', 'The provider comparison example covers versions 3 and 4. Choose those versions in this synthetic preview.', 501);
  }
  if (proposalPath && !proposalPath[1] && request.method === 'GET') {
    return response({ items: state.proposal?.schedule_id === url.searchParams.get('schedule_id') && state.proposal.status === 'pending' ? [state.proposal] : [] });
  }
  if (weekPath) {
    const week = fixture<Schema['ScheduleWeek']>(weekPath[2] === '2026-10-19' ? 'schedule_week.published' : 'schedule_week.empty');
    const sameWeek = state.draft?.schedule_id === (week.schedule_id ?? fixture<Schema['ScheduleVersion']>('candidate.select').schedule_id);
    if (request.method !== 'GET' || !sameWeek || weekPath[1] !== week.outlet_id) return null;
    week.schedule_id = state.draft!.schedule_id;
    if (state.published) {
      week.current_version = state.published;
      // Keep synthetic row totals consistent with the provider-owned published assignments.
      const otherShifts = weekPath[2] === '2026-10-19' ? ['schedule_week.owner.koramangala', 'schedule_week.owner.hsr'].flatMap(name => fixture<Schema['ScheduleWeek']>(name).current_version?.shifts ?? []) : [];
      const shifts = [...state.published.shifts, ...otherShifts];
      week.employees = week.employees.map(employee => ({ ...employee, scheduled_minutes: shifts.filter(shift => shift.employee_id === employee.id).reduce((minutes, shift) => minutes + (Date.parse(shift.end_at) - Date.parse(shift.start_at)) / 60000 - shift.break_minutes, 0) }));
    }
    week.drafts = state.published ? [] : [summary(state.draft!)];
    return response(week);
  }
  if (editPath && request.method === 'POST') {
    if (!state.draft || editPath[1] !== state.draft.id) return error('not_found', 'Create an editing draft before changing assignments.', 404);
    if (state.published) return error('conflict', 'Published assignments must be copied into a new draft.', 409);
    const input = await request.json().catch(() => null);
    if (input?.expected_revision !== state.draft.revision) return error('stale_version', 'This draft was changed by someone else. Reload the latest draft before saving.', 409);
    if (state.draft.source !== 'manual' || state.draft.revision !== 1) return error('not_implemented', 'The provider edit examples cover revision 1 of the manual draft. Start a new demo session to repeat them.', 501);
    if (editPath[2] && canonical(input.edits) === canonical(examples.invalidReassignment.edits)) return response(fixture('edits.preview'));
    if (canonical(input.edits) !== canonical(examples.openingLock.edits)) return error('not_implemented', 'No provider validation fixture matches this edit. Try an example below, or use a connected scheduling API.', 501);
    const after = fixture<Schema['ScheduleVersion']>('edits.apply');
    if (editPath[2]) {
      const id = examples.openingLock.edits[0].logical_shift_id;
      const preview: Schema['EditPreview'] = { version_id: state.draft.id, expected_revision: 1, shifts: after.shifts, metrics: after.metrics, validation: after.validation, changes: [{ logical_shift_id: id, kinds: ['lock_changed'], before: state.draft.shifts.find(s => s.logical_shift_id === id)!, after: after.shifts.find(s => s.logical_shift_id === id)! }] };
      return response(preview);
    }
    // Match the provider: apply is revision-fenced; an old request gets stale, not a replay.
    state.draft = after; return response(after);
  }
  const lowest = fixture<Schema['CandidateDetail']>('candidate.detail.lowest_cost');
  const detail = candidate?.[1] === lowest.id ? lowest : fixture<Schema['CandidateDetail']>('candidate.detail');
  if (candidate && candidate[1] !== detail.id) return error('not_implemented', 'No provider candidate fixture matches this request.', 501);
  if (candidate && !candidate[2] && request.method === 'GET') return response({ ...detail, materialized_version_id: state.draft?.optimization_run_id === detail.run_id && state.draft.id === fixture<Schema['ScheduleVersion']>(detail.id === lowest.id ? 'candidate.select.lowest_cost' : 'candidate.select').id ? state.draft.id : null });
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
  if (restorePath) {
    const history = fixture<Schema['VersionHistory']>('versions.list');
    if (request.headers.get('X-ShiftPilot-Scenario') === 'stale' || body?.expected_base_version_id !== (state.published?.id ?? history.current_version_id)) return error('stale_version', 'The published version changed. Reload history before restoring.', 409);
    const restored = fixture<Schema['ScheduleVersion']>('versions.restore');
    if (restored.base_version_id !== body.expected_base_version_id) return error('not_implemented', 'The provider restore story is based on published version 3. Start a new preview session to repeat it.', 501);
    const source = history.items.find(v => v.version_number === 2);
    if (restorePath[1] !== source?.id) return error('not_implemented', 'The provider restore example uses version 2. Choose it in this preview.', 501);
    state.draft = restored; state.proposal = undefined; state.published = undefined;
    return remember(restored, 201);
  }
  if (createPath) {
    const base = fixture<Schema['ScheduleWeek']>('schedule_week.published');
    if (createPath[1] !== base.outlet_id) return error(persona === 'manager' ? 'permission_denied' : 'not_implemented', 'This preview only has an editing draft for Indiranagar.', persona === 'manager' ? 403 : 501);
    if (body?.base_version_id !== base.current_version!.id) return error('stale_version', 'Reload the published week before creating an editing draft.', 409);
    if (state.draft) return error('conflict', 'A draft already exists in this synthetic session. Reopen it or start another session.', 409);
    state.draft = fixture<Schema['ScheduleVersion']>('draft.create'); return remember(state.draft, 201);
  }
  if (candidate?.[2]) {
    if (state.published) return error('conflict', 'This option has already been published.', 409);
    if (state.draft && state.draft.id !== fixture<Schema['ScheduleVersion']>(detail.id === lowest.id ? 'candidate.select.lowest_cost' : 'candidate.select').id) return error('not_implemented', 'Start a new demo session to select another option after creating a draft.', 501);
    state.draft ??= fixture<Schema['ScheduleVersion']>(detail.id === lowest.id ? 'candidate.select.lowest_cost' : 'candidate.select');
    return remember(state.draft, 201);
  }
  if (proposalPath && !proposalPath[1]) {
    if (!state.draft || body?.draft_version_id !== state.draft.id) return error('not_found', 'Create or select a draft before proposing it.', 404);
    if (body.expected_revision !== state.draft.revision) return error('stale_version', 'This draft revision changed.', 409);
    if (state.proposal?.draft_revision === state.draft.revision) return error('conflict', 'A proposal has already been created for this revision in the synthetic session. Start a new demo session to repeat it.', 409);
    state.proposal = { ...fixture<Schema['Proposal']>('proposal.create'), ...(state.proposal ? { id: crypto.randomUUID() } : {}), schedule_id: state.draft.schedule_id, draft_version_id: state.draft.id, draft_revision: state.draft.revision, base_version_id: state.draft.base_version_id, candidate_id: state.draft.optimization_run_id ? (state.draft.id === fixture<Schema['ScheduleVersion']>('candidate.select.lowest_cost').id ? lowest.id : detail.id) : null, metrics_at_proposal: state.draft.metrics }; return remember(state.proposal, 201);
  }
  if (state.proposal?.status !== 'pending') return error('conflict', 'This proposal is no longer pending.', 409);
  if (proposalPath?.[2] === '/reject') { const rejected = fixture<Schema['Proposal']>('proposal.reject'); state.proposal = { ...state.proposal, status: 'rejected', decided_at: rejected.decided_at, decided_by_user_id: rejected.decided_by_user_id }; return remember(state.proposal); }
  if (proposalPath?.[2] === '/approve') {
    if (typeof body?.acknowledge_changes !== 'boolean') return error('validation_failed', 'State whether changed metrics are acknowledged.', 422);
    const outcome = request.headers.get('X-ShiftPilot-Approval-Outcome') ?? 'published';
    if (!['published', 'changed', 'stale', 'invalid'].includes(outcome)) return error('validation_failed', 'Choose a supported approval outcome.', 422);
    const name = outcome === 'changed' && body.acknowledge_changes ? 'acknowledged' : outcome;
    const decision = fixture<Schema['ProposalDecision']>(`proposal.approve.${name}`);
    decision.proposal = { ...decision.proposal, ...state.proposal, status: decision.proposal.status, decided_at: decision.proposal.decided_at, decided_by_user_id: decision.proposal.decided_by_user_id };
    if (decision.published && state.draft) {
      const recorded_metrics = name === 'acknowledged' ? decision.published.recorded_metrics : state.draft.recorded_metrics;
      decision.published = { ...decision.published, ...summary(state.draft), recorded_metrics, status: 'published', approved_by_user_id: decision.published.approved_by_user_id, published_at: decision.published.published_at };
    }
    state.proposal = decision.proposal;
    if (decision.outcome === 'published') {
      state.published = { ...state.draft!, ...decision.published! };
      if (name === 'acknowledged' && decision.published?.recorded_metrics) state.published.metrics = decision.published.recorded_metrics;
    }
    return remember(decision);
  }
  return error('not_implemented', 'This fixture operation is not available.', 501);
}
