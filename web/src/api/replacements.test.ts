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

it('uses the provider cover draft, preview and save records without clearing time, skill or breaks', async () => {
  const { client } = setup(); const me = await client.signIn('manager');
  const week = await client.schedule(me.outlet_id!, '2026-10-19');
  const result = await client.recommendReplacements(input); const option = result.recommendations[0];
  const draft = await client.createDraft(me.outlet_id!, '2026-10-19', { base_version_id: week.current_version!.id, copy_from_version_id: null }, 'create-cover-key', undefined, 'cover');
  expect(draft).toEqual(fixture('draft.create.cover'));
  const edit = { expected_revision: draft.revision, edits: [option.edit] };
  expect(await client.previewEdits(draft.id, edit)).toEqual(fixture('edits.preview.cover'));
  expect((await client.version(draft.id)).revision).toBe(1);
  const saved = await client.applyEdits(draft.id, edit, 'save-cover-key');
  expect(saved).toEqual(fixture('edits.apply.cover'));
  const shift = saved.shifts.find(value => value.logical_shift_id === option.edit.logical_shift_id)!;
  expect(shift.employee_id).toBe(option.employee_id);
  for (const field of ['start_at', 'end_at', 'skill_id', 'break_start_at', 'break_minutes'] as const) expect(shift[field]).toEqual(result.shift[field]);
  await expect(client.applyEdits(draft.id, edit, 'old-cover-revision')).rejects.toMatchObject({ status: 409, detail: { code: 'stale_version' } });
  expect((await client.schedule(me.outlet_id!, '2026-10-19')).current_version!.id).toBe(week.current_version!.id);
  const proposal = await client.createProposal({ draft_version_id: saved.id, expected_revision: saved.revision }, 'cover-proposal');
  expect(proposal.candidate_id).toBeNull(); expect(proposal.draft_revision).toBe(2);
  const published = await client.approveProposal(proposal.id, { acknowledge_changes: false }, 'approve-cover');
  expect(published.outcome).toBe('published');
  expect(published.published?.id).toBe(saved.id);
});

it('preserves the provider rule conflict and refuses unsupported cover edits', async () => {
  const { client } = setup(); const me = await client.signIn('manager');
  const draft = await client.createDraft(me.outlet_id!, '2026-10-19', { base_version_id: input.version_id, copy_from_version_id: null }, 'cover-conflict-draft', undefined, 'cover');
  const conflict = records['edits.preview.cover.conflict'].request.body as Schema['EditRequest'];
  const preview = await client.previewEdits(draft.id, conflict);
  expect(preview.validation.hard_violations).toBeGreaterThan(0);
  await expect(client.applyEdits(draft.id, conflict, 'invalid-cover')).rejects.toMatchObject({ status: 501 });
  await expect(client.previewEdits(draft.id, { ...conflict, edits: [{ op: 'update', logical_shift_id: input.logical_shift_id, employee_id: null }] })).rejects.toMatchObject({ status: 501 });
});

it('confines the cover-story header to the synthetic gateway', async () => {
  const client = new SchedulingClient({ baseUrl: 'https://api.invalid', fetcher: async (_url, init) => {
    expect(new Headers(init?.headers).has('X-ShiftPilot-Draft-Example')).toBe(false);
    return Response.json(fixture('draft.create.cover'), { status: 201 });
  } });
  await client.createDraft('outlet', '2026-10-19', { base_version_id: input.version_id, copy_from_version_id: null }, 'live-cover', undefined, 'cover');
});
