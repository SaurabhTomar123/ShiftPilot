import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const repair = fixtures['candidate.detail.repair'].response.body;

async function generate(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Review option', exact: true })).toHaveCount(2);
}
async function repairReview(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Repair Inbox', exact: true }).click();
  await page.getByRole('button', { name: 'Review repair', exact: true }).click();
  await page.getByRole('button', { name: 'Start or check repair for this week', exact: true }).click();
  await page.getByRole('button', { name: 'Review repair option', exact: true }).click();
  const region = page.getByRole('region', { name: 'Candidate review', exact: true });
  await region.getByText('Why this plan?', { exact: true }).click();
  return region;
}

test('portfolio comparison shows engine policy and its declared delta reference without writes', async ({ page }) => {
  const writes: string[] = []; page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()); });
  await generate(page); const before = writes.length;
  await page.getByText('Compare plans (2)', { exact: true }).click();
  await page.getByText('How these options were chosen', { exact: true }).click();
  await expect(page.locator('.portfolio-details')).toContainText('Employee fairness: Same assignments as Balanced');
  await expect(page.locator('.portfolio-details')).toContainText('Maximum coverage: Outside the reported safeguards: cost');
  const table = page.getByRole('region', { name: 'Plan comparison', exact: true });
  await expect(table).toContainText('Engine delta vs requested plan'); await expect(table).toContainText('7.83');
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  await expect(table).toContainText('-0.14');
  expect(writes).toHaveLength(before);
});

test('fairness components are weekly burden points and not preference scores', async ({ page }) => {
  await generate(page); await page.getByRole('button', { name: 'Review option', exact: true }).first().click();
  const region = page.getByRole('region', { name: 'Candidate review', exact: true });
  await region.getByText('This plan: fairness burden', { exact: true }).click();
  await expect(region.locator('.fairness-breakdown')).toContainText('Policy 1');
  await expect(region.locator('.fairness-breakdown')).toContainText('this week only');
  await expect(region.locator('.fairness-breakdown')).toContainText('Transfer and last-minute burden are not included');
  await region.getByText('Why this plan?', { exact: true }).click();
  await expect(region.locator('.decision-facts > div').filter({ has: page.getByText('Created', { exact: true }) }).locator('dd')).toHaveText('60');
  expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('repair trace distinguishes eligible alternatives from blocked ones and publishes only after approval', async ({ page }) => {
  let approvals = 0; page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/approve')) approvals += 1; });
  const region = await repairReview(page);
  const taxonomy = region.getByRole('region', { name: 'Decision change taxonomy', exact: true });
  await expect(taxonomy).toContainText('Reassigned'); await expect(taxonomy).toContainText('Ravi Kumar'); await expect(taxonomy).toContainText('2026-10-21');
  await region.locator('.employee-evidence > summary').click();
  await expect(region).toContainText('Eligible, not selected'); await expect(region).toContainText('Blocked by a recorded constraint');
  await expect(region).toContainText('No additional rejection reason is inferred');
  expect(approvals).toBe(0);
  await region.getByRole('button', { name: 'Select option and create draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Repair draft .* has not been published/ })).toBeVisible();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click(); expect(approvals).toBe(0);
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Repair publication confirmed'); expect(approvals).toBe(1);
});

test('cost-restricted views redact cost facts in summary and detailed reasoning', async ({ page }) => {
  await page.route('**/session/demo', async route => { const response = await route.fetch(); const body = await response.json(); body.me.capabilities = body.me.capabilities.filter((capability: string) => capability !== 'view_costs'); await route.fulfill({ response, json: body }); });
  const region = await repairReview(page); await region.locator('.employee-evidence > summary').click();
  await expect(region).not.toContainText('INR 1,350'); await expect(region).not.toContainText('Estimated cost change');
  await expect(region).toContainText('Cost evidence requires cost access');
  const inboxEvidence = page.locator('.repair-option .decision-evidence'); await inboxEvidence.locator(':scope > summary').click(); await inboxEvidence.locator('.employee-evidence > summary').click();
  await expect(inboxEvidence).not.toContainText('INR 1,350');
});

test('missing legacy trace and burden values remain explicitly unreported', async ({ page }) => {
  await page.route('**/optimization-candidates/*', async route => { const response = await route.fetch(); const body = await response.json(); body.trace = null; body.trace_changes = []; body.explanations = []; body.metrics.fairness_burden_deviation = null; body.metrics.fairness_components = null; await route.fulfill({ response, json: body }); });
  await generate(page); await page.getByRole('button', { name: 'Review option', exact: true }).first().click();
  const region = page.getByRole('region', { name: 'Candidate review', exact: true });
  await region.getByText('Why this plan?', { exact: true }).click(); await expect(region).toContainText('A decision trace was not recorded');
  await region.getByText('This plan: fairness burden', { exact: true }).click(); await expect(region.locator('.fairness-breakdown')).toContainText('Not reported');
  await expect(region.locator('.decision-facts')).toHaveCount(0);
});

test('provenance and truncated evidence use returned facts without inventing explanations', async ({ page }) => {
  await page.route('**/optimization-candidates/*', async route => { const response = await route.fetch(); const body = await response.json(); body.trace.explanations_truncated = true; body.explanations[0].alternatives[0].status = 'rejected'; body.explanations[0].alternatives[0].reasons = [{ code: 'rules', ok: false, message: 'Closing rule blocks this assignment', facts: { rule_ids: ['00000000-0000-4000-8000-000000000001'], absence_ids: ['00000000-0000-4000-8000-000000000002'] } }]; await route.fulfill({ response, json: body }); });
  const region = await repairReview(page); await expect(region).toContainText('limited to 30 shifts');
  await region.locator('.employee-evidence > summary').click(); await region.getByText('Constraint sources', { exact: true }).click();
  await expect(region).toContainText('Rule 00000000-0000-4000-8000-000000000001');
  await expect(region).toContainText('Absence 00000000-0000-4000-8000-000000000002');
  await expect(region).toContainText('Closing rule blocks this assignment');
  expect(repair.trace.counts.REASSIGNED).toBe(1);
});

test('decision profiles are explicit inputs and never fabricate a different profile in the preview', async ({ page }) => {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await page.getByLabel('Decision profile', { exact: true }).selectOption('fairness');
  let requested = ''; page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/generate')) requested = request.postDataJSON().strategy; });
  await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('No provider fixture'); expect(requested).toBe('fairness');
  await expect(page.getByRole('button', { name: 'Review option', exact: true })).toHaveCount(0);
});
