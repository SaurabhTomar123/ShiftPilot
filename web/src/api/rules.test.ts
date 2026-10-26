import { expect, it } from 'vitest';
import { SchedulingClient } from './client';
import { fixture, fixtureResponse } from './fixture-gateway';
import examples from './generated/rule-examples.json';
import type { Schema } from './types';

function setup() {
  const requests: Request[] = [];
  const client = new SchedulingClient({ baseUrl: '/api/fixture', fetcher: async (input, init) => { const path = String(input).replace('/api/fixture', ''); const request = new Request(`http://fixture.invalid${path}`, init); requests.push(request.clone()); return fixtureResponse(path, request); } });
  return { client, requests };
}
const student = examples.student as Schema['RuleDefinition'];
const conflict = examples.conflict as Schema['RuleDefinition'];
it('previews without changing the catalog or sending an idempotency key', async () => {
  const { client, requests } = setup(); await client.signIn('owner');
  const initial = await client.rules(true);
  expect(await client.previewRule(student)).toEqual(fixture('rules.preview'));
  expect(await client.rules(true)).toEqual(initial);
  expect(requests.find(value => value.url.endsWith('/preview'))?.headers.get('Idempotency-Key')).toBeNull();
});
it('saves the supplied record with stable replay, never duplicates it or invokes roster writes', async () => {
  const { client, requests } = setup(); await client.signIn('owner');
  const saved = await client.createRule(student, 'save-rule');
  expect(saved).toEqual(fixture('rules.create'));
  expect(await client.createRule(student, 'save-rule')).toEqual(saved);
  expect((await client.rules(true)).items).toEqual([saved]);
  await expect(client.createRule({ ...student, source_text: 'changed' }, 'save-rule')).rejects.toMatchObject({ status: 409 });
  expect(requests.some(value => /generate|publish|proposals|schedule-versions/.test(value.url))).toBe(false);
});
it('keeps conflict previews unsavable and refuses to fabricate a suggested exception preview', async () => {
  const { client } = setup(); await client.signIn('manager');
  const preview = await client.previewRule(conflict);
  expect(preview.valid).toBe(false); expect(preview.conflicts).toHaveLength(1);
  await expect(client.createRule(conflict, 'conflicting')).rejects.toMatchObject({ status: 409 });
  await expect(client.previewRule(preview.conflicts[0].suggested_exception!)).rejects.toMatchObject({ status: 501 });
  expect((await client.rules(true)).items).toEqual(fixture<Schema['RuleList']>('rules.list').items);
});
it('archives only explicitly, filters archived records and does not invent recreation', async () => {
  const { client, requests } = setup(); await client.signIn('owner');
  const id = fixture<Schema['SchedulingRule']>('rules.archive').id;
  expect(await client.archiveRule(id)).toEqual(fixture('rules.archive'));
  expect((await client.rules(false)).items).toEqual([]);
  expect((await client.rules(true)).items[0].status).toBe('archived');
  expect(requests.find(value => value.url.endsWith('/archive'))?.headers.get('Idempotency-Key')).toBeNull();
  await expect(client.createRule(student, 'fresh')).rejects.toMatchObject({ status: 501 });
});
it('denies owner scopes to managers and every rules operation to staff', async () => {
  const { client } = setup(); await client.signIn('manager');
  await expect(client.previewRule(student)).rejects.toMatchObject({ status: 403 });
  await expect(client.archiveRule(fixture<Schema['SchedulingRule']>('rules.archive').id)).rejects.toMatchObject({ status: 403 });
  await client.signIn('staff'); await expect(client.rules(true)).rejects.toMatchObject({ status: 403 });
  await expect(client.previewRule(conflict)).rejects.toMatchObject({ status: 403 });
});
