import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const sample = fixtures['recommendations.replacements'];
const recommendations = sample.response.body;
const draft = fixtures['draft.create'].response.body;
const option = recommendations.recommendations[0];
const after = structuredClone(draft); after.revision += 1;
after.shifts.find((shift: { logical_shift_id: string }) => shift.logical_shift_id === option.edit.logical_shift_id).employee_id = option.employee_id;
const validation = { version_id: draft.id, expected_revision: draft.revision, shifts: after.shifts, metrics: after.metrics, validation: { hard_violations: 0, soft_violations: 0, violations: [] }, changes: [{ logical_shift_id: option.edit.logical_shift_id, kinds: ['reassigned'], before: recommendations.shift, after: after.shifts.find((shift: { logical_shift_id: string }) => shift.logical_shift_id === option.edit.logical_shift_id) }] };

async function open(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Find cover for a shift', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Find shift cover', exact: true });
  await panel.getByLabel('Shift needing cover').selectOption(sample.request.body.logical_shift_id);
  return panel;
}
async function find(page: Page) {
  const panel = await open(page); await panel.getByRole('button', { name: 'Find cover', exact: true }).click();
  await expect(panel.getByRole('heading', { name: 'Cover options for Ravi Kumar', exact: true })).toBeVisible(); return panel;
}
async function mockValidation(page: Page, hard = false) {
  await page.route('**/v2/schedule-versions/*/edits/preview', route => route.fulfill({ json: hard ? { ...validation, validation: { hard_violations: 1, soft_violations: 0, violations: [{ severity: 'hard', code: 'weekly_hours', message: 'Weekly cap changed since recommendations were read.' }] } } : validation }));
}

test('finding cover preserves engine order and explanations without schedule writes and fits the viewport', async ({ page }) => {
  const writes: string[] = []; page.on('request', r => { if (r.method() === 'POST') writes.push(new URL(r.url()).pathname); });
  const panel = await find(page);
  await expect(panel.locator('.replacement-options h4')).toHaveText(['Chitra Indiranagar', 'Aman Shah']);
  await expect(panel.getByText('₹1,192.50', { exact: true })).toBeVisible();
  await panel.getByText('Why Chitra Indiranagar can cover', { exact: true }).click();
  await expect(panel.locator('.replacement-options > li').first().getByText('Qualified for Prep', { exact: false })).toBeVisible();
  await panel.getByText('People blocked by a recorded rule (2)', { exact: true }).click();
  await expect(panel.getByText('Would break overlap, rest or travel rules', { exact: false })).toBeVisible();
  expect(writes.filter(path => !path.endsWith('/session/demo'))).toEqual(['/api/fixture/v2/recommendations/replacements']);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/replacements-${test.info().project.name}.png`, fullPage: true });
});

test('changing cover priorities clears old results and unsupported profiles never reuse Balanced', async ({ page }) => {
  const panel = await find(page); await panel.getByLabel('Cover priorities').selectOption('fairness');
  await expect(panel.getByRole('heading', { name: 'Cover options for Ravi Kumar' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Find cover', exact: true }).click();
  await expect(panel.getByText('No provider fixture is available for this request yet.', { exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' })).toHaveCount(0);
});

test('cost-restricted sessions redact detailed reasons and exact money', async ({ page }) => {
  await page.route('**/v2/session/demo', async route => { const response = await route.fetch(); const body = await response.json(); body.me.capabilities = body.me.capabilities.filter((value: string) => value !== 'view_costs'); await route.fulfill({ response, json: body }); });
  const panel = await find(page);
  await panel.getByText('Why Chitra Indiranagar can cover', { exact: true }).click();
  await expect(panel.getByText('Cost evidence requires cost access.', { exact: true }).first()).toBeVisible();
  await expect(panel).not.toContainText('₹'); await expect(panel).not.toContainText('INR');
});

test('default preview preserves its prepared draft when replacement validation is unsupported', async ({ page }) => {
  const requests: string[] = []; page.on('request', r => { if (r.method() === 'POST') requests.push(new URL(r.url()).pathname); });
  const panel = await find(page); await panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' }).click();
  await expect(panel.getByText('No replacement save has been confirmed.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Save replacement to draft' })).toHaveCount(0);
  expect(requests.filter(path => path.endsWith('/edits'))).toEqual([]);
  await panel.getByRole('button', { name: 'Open current draft for review' }).click();
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toBeVisible();
});

test('review and save use the exact returned edit and revision then require a separate proposal', async ({ page }) => {
  await mockValidation(page); let sent: unknown; let saves = 0;
  await page.route('**/v2/schedule-versions/*/edits', async route => { saves++; sent = route.request().postDataJSON(); await route.fulfill({ json: after }); });
  const panel = await find(page); await panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' }).click();
  await expect(panel.getByRole('region', { name: 'Replacement validation' })).toBeVisible(); expect(saves).toBe(0);
  await panel.getByRole('button', { name: 'Save replacement to draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toBeVisible();
  expect(saves).toBe(1); expect(sent).toEqual({ expected_revision: draft.revision, edits: [option.edit] });
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
});

test('current validation can block an otherwise recommended person', async ({ page }) => {
  await mockValidation(page, true); const panel = await find(page);
  await panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' }).click();
  await expect(panel.getByText('hard: Weekly cap changed since recommendations were read.', { exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Save replacement to draft' })).toBeDisabled();
});

test('a changed published base prevents draft creation from stale recommendations', async ({ page }) => {
  let creates = 0; page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/drafts')) creates++; });
  const panel = await find(page);
  await page.route('**/v2/outlets/*/schedules/2026-10-19', async route => { const body = structuredClone(fixtures['schedule_week.published'].response.body); body.current_version.id = '11111111-1111-4111-8111-111111111111'; await route.fulfill({ json: body }); });
  await panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' }).click();
  await expect(panel.getByText('The published week changed.', { exact: false })).toBeVisible(); expect(creates).toBe(0);
});

test('a lost save response requires reading the draft instead of replaying an edit', async ({ page }) => {
  await mockValidation(page); let saves = 0;
  await page.route('**/v2/schedule-versions/*/edits', route => { saves++; return route.abort('failed'); });
  const panel = await find(page); await panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' }).click();
  await panel.getByRole('button', { name: 'Save replacement to draft', exact: true }).click();
  await expect(panel.getByText('The save result is uncertain.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Save replacement to draft' })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' })).toBeDisabled();
  expect(saves).toBe(1);
});

test('old recommendation responses cannot replace a different week', async ({ page }) => {
  const panel = await open(page); let started!: () => void; const pending = new Promise<void>(resolve => { started = resolve; });
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/v2/recommendations/replacements', async route => { started(); await gate; await route.fulfill({ json: recommendations }).catch(() => {}); });
  await panel.getByRole('button', { name: 'Find cover', exact: true }).click(); await pending;
  await page.getByRole('button', { name: 'Next week', exact: true }).click(); release();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Find shift cover' })).toHaveCount(0);
});

test('Find cover is available in Repair Inbox and borrowing controls remain owner-only', async ({ page }) => {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Repair Inbox', exact: true }).click();
  await page.getByRole('button', { name: 'Find cover for a shift', exact: true }).click();
  await expect(page.getByLabel('Include people from other outlets')).toHaveCount(0);
  await page.getByLabel('Demo persona').selectOption('owner');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Find cover for a shift', exact: true }).click();
  await expect(page.getByLabel('Include people from other outlets')).toBeVisible();
});

test('missing fairness, empty options and locked assignments are not invented into eligible choices', async ({ page }) => {
  const response = structuredClone(recommendations); response.shift.locked = true; response.recommendations[0].fairness_delta = null;
  await page.route('**/v2/recommendations/replacements', route => route.fulfill({ json: response }));
  const panel = await find(page);
  await expect(panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' })).toBeDisabled();
  await expect(panel.locator('.replacement-options > li').first().getByText('Not reported', { exact: true })).toBeVisible();
  response.recommendations = []; response.eligible = 0;
  await panel.getByRole('button', { name: 'Find cover', exact: true }).click();
  await expect(panel.getByText('No direct cover options were returned.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' })).toHaveCount(0);
});

test('recommendations for a different shift are rejected before any draft is created', async ({ page }) => {
  const response = structuredClone(recommendations); response.shift.logical_shift_id = '11111111-1111-4111-8111-111111111111';
  await page.route('**/v2/recommendations/replacements', route => route.fulfill({ json: response }));
  const panel = await open(page); await panel.getByRole('button', { name: 'Find cover', exact: true }).click();
  await expect(panel.getByText('These recommendations do not match the selected version, shift and profile. Find cover again.', { exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Review Chitra Indiranagar in draft' })).toHaveCount(0);
});
