import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const reported = fixtures['absence.report'].response.body;
const repair = fixtures['run.repair.widened'].response.body;

async function open(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Repair Inbox', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'This week’s absences', exact: true })).toBeVisible();
  await page.getByLabel('Absent employee', { exact: true }).selectOption(reported.absence.employee_id);
}

test('absence screen is read-only on entry, accessible, and fits the viewport', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && !request.url().endsWith('/session/demo')) writes.push(request.url()); });
  await open(page);
  await expect(page.getByRole('region', { name: 'Saved absences', exact: true })).toContainText('requested');
  expect(writes).toEqual([]);
  expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('saving a confirmed absence tracks its repair without starting generation or publication', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && !request.url().endsWith('/session/demo')) writes.push(request.url()); });
  await open(page);
  await page.getByRole('button', { name: 'Save absence', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Absence saved as confirmed');
  await expect(page.getByRole('region', { name: 'Repair result', exact: true })).toContainText('Least disruption');
  await expect(page.getByRole('region', { name: 'Absence repair', exact: true })).toContainText('Include the day either side');
  const comparison = page.getByRole('region', { name: 'Plan comparison', exact: true });
  await expect(comparison).toContainText('Recorded baseline v3');
  await expect(comparison.getByRole('row', { name: /^Fairness burden/ })).toContainText(String(repair.candidates[0].metrics.fairness_burden_deviation));
  await expect(comparison).toContainText('Assignment changes');
  expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([]);
  expect(writes).toHaveLength(1); expect(writes[0]).toMatch(/\/absences$/);
  await page.getByRole('button', { name: 'Review repair option', exact: true }).first().click();
  await expect(page.getByRole('region', { name: 'Candidate review', exact: true })).toContainText('Review this option');
  await expect(page.getByRole('button', { name: 'Select option and create draft', exact: true })).toBeVisible();
  expect(writes).toHaveLength(1);
});

test('plan comparison respects cost visibility and never substitutes preference match for fairness', async ({ page }) => {
  await page.route('**/session/demo', async route => {
    const response = await route.fetch(); const session = await response.json();
    session.me.capabilities = session.me.capabilities.filter((capability: string) => capability !== 'view_costs');
    await route.fulfill({ response, json: session });
  });
  await open(page); await page.getByRole('button', { name: 'Save absence', exact: true }).click();
  const comparison = page.getByRole('region', { name: 'Plan comparison', exact: true });
  await expect(comparison).toBeVisible();
  await expect(comparison).not.toContainText('Estimated labour cost');
  await expect(comparison).not.toContainText('₹');
  await expect(comparison.getByRole('row', { name: /Fairness burden/ })).not.toContainText('%');
});

test('repair polling failure preserves the saved absence and retries only the status read', async ({ page }) => {
  let reads = 0; let reports = 0;
  await page.route('**/optimization-runs/**', async route => {
    reads += 1;
    if (reads === 1) await route.fulfill({ status: 503, json: { error: { code: 'internal', message: 'Worker status unavailable', retryable: true, details: {} } } });
    else await route.continue();
  });
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/absences')) reports += 1; });
  await open(page); await page.getByRole('button', { name: 'Save absence', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Absence is saved');
  await expect(page.getByRole('status')).toContainText('Absence saved as confirmed');
  await page.getByRole('button', { name: 'Check repair status', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Repair result', exact: true })).toBeVisible();
  expect(reports).toBe(1); expect(reads).toBe(2);
});

test('status changes require a separate decision and unsupported preview writes stay unconfirmed', async ({ page }) => {
  let updates = 0; page.on('request', r => { if (r.method() === 'PATCH') updates += 1; });
  await open(page);
  await page.getByRole('button', { name: 'Confirm absence', exact: true }).click();
  expect(updates).toBe(0);
  await page.getByRole('button', { name: 'Keep current status', exact: true }).click();
  expect(updates).toBe(0);
  await page.getByRole('button', { name: 'Reject request', exact: true }).click();
  await page.getByRole('button', { name: 'Save as rejected', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('not supported by this preview');
  await expect(page.getByRole('region', { name: 'Saved absences', exact: true })).toContainText('requested');
  expect(updates).toBe(1);
});

test('locked repair needs explicit permission and uses the latest published base', async ({ page }) => {
  const requests: Record<string, unknown>[] = [];
  await page.route('**/schedules/*/repair', async route => {
    requests.push(route.request().postDataJSON());
    if (requests.length === 1) await route.fulfill({ status: 409, json: fixtures['repair.locked'].response.body });
    else await route.fulfill({ status: 202, json: fixtures['repair.accepted'].response.body });
  });
  await open(page); await page.getByRole('button', { name: 'Review repair', exact: true }).click();
  const start = page.getByRole('button', { name: 'Start or check repair for this week', exact: true });
  await start.click();
  const permission = page.getByRole('group', { name: 'Permission to change locked assignments', exact: true });
  await expect(permission).toBeVisible(); await expect(start).toBeDisabled();
  expect(requests[0].unlock_logical_shift_ids).toEqual([]);
  await permission.getByRole('checkbox').check(); await start.click();
  await expect(page.getByRole('region', { name: 'Repair result', exact: true })).toBeVisible();
  expect(requests[1].unlock_logical_shift_ids).toEqual(reported.affected.map((shift: { logical_shift_id: string }) => shift.logical_shift_id));
  expect(requests[1].base_version_id).toBe(repair.base_version_ids[0]);
  expect(requests[1].allow_cross_outlet).toBe(false);
  await expect(page.getByLabel('Allow this repair to borrow staff from other outlets')).toHaveCount(0);
});

test('invalid time range never sends an absence write', async ({ page }) => {
  let reports = 0; page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/absences')) reports += 1; });
  await open(page); await page.getByLabel('Absence ends', { exact: true }).fill('2026-10-20T00:00');
  await page.getByRole('button', { name: 'Save absence', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('End must be after'); expect(reports).toBe(0);
});

test('switching to Absences during the initial schedule read keeps the shared read usable', async ({ page }) => {
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  let reads = 0;
  await page.route('**/outlets/*/schedules/2026-10-19', async route => { reads += 1; await gate; await route.continue(); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Weekly schedule', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Repair Inbox', exact: true }).click();
  release();
  await expect(page.getByRole('heading', { name: 'This week’s absences', exact: true })).toBeVisible();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  expect(reads).toBe(1);
});
