import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster' })).toBeVisible();
});

test('renders provider employees, exact money, preferences and locks', async ({ page }) => {
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(13);
  await expect(page.getByRole('table').getByText('Ravi Kumar', { exact: true })).toBeVisible();
  await expect(page.getByText('₹74,700.00', { exact: true })).toBeVisible();
  await expect(page.getByText('77.1%', { exact: true })).toBeVisible();
  await expect(page.getByText('Published version 3', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate draft' })).toBeDisabled();
});

test('generation preview stays unpublished', async ({ page }) => {
  await page.getByRole('button', { name: 'Next week' }).click();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.' })).toBeVisible();
  await page.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page.getByRole('heading', { name: 'Options ready for a closer look.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review option' })).toHaveCount(2);
  await page.getByRole('button', { name: 'Review option' }).first().click();
  await expect(page.getByRole('heading', { name: 'Review this option' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Proposed roster' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Select option and create draft' }).click();
  await expect(page.getByText('Draft preview · not published', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Proposed roster' })).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: 'Ravi Kumar' })).toContainText('27.5h in this draft');
  await expect(page.getByRole('button', { name: /Publish/ })).toHaveCount(0);
});

test('keeps feasible, timeout and infeasible results distinct', async ({ page }) => {
  await page.getByRole('button', { name: 'Next week' }).click();
  for (const [scenario, title] of [['feasible', 'A valid option, with room to improve.'], ['timeout', 'No solution found within the time limit.'], ['infeasible', 'These requirements cannot all be met.']]) {
    await page.getByLabel('Demo outcome', { exact: true }).selectOption(scenario);
    await page.getByRole('button', { name: 'Generate draft' }).click();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    if (scenario === 'timeout') {
      await expect(page.getByText('This does not mean the schedule is impossible.', { exact: false })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Review option' })).toHaveCount(0);
    }
  }
});

test('stale writes request review instead of silently retrying', async ({ page }) => {
  let writes = 0;
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/generate')) writes += 1; });
  await page.getByRole('button', { name: 'Next week' }).click();
  await page.getByLabel('Demo outcome', { exact: true }).selectOption('stale');
  await page.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page.getByRole('heading', { name: 'This schedule has changed.' })).toBeVisible();
  expect(writes).toBe(1);
  await page.getByRole('button', { name: 'Reload latest schedule' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  expect(writes).toBe(1);
});

test('persona changes clear old data and employee controls contain no costs', async ({ page }) => {
  await page.getByLabel('Demo persona', { exact: true }).selectOption('staff');
  await expect(page.getByRole('heading', { name: 'Your week', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^Saturday,? 24 October$/ })).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Generate draft' })).toHaveCount(0);
  await expect(page.getByText('Estimated labour cost', { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(localStorage).some(key => /token|session/i.test(key)))).toBe(false);
  await page.getByLabel('Demo persona', { exact: true }).selectOption('owner');
  await expect(page.getByLabel('Outlet', { exact: true }).locator('option')).toHaveCount(3);
  await page.getByLabel('Outlet', { exact: true }).selectOption({ label: 'Koramangala' });
  await expect(page.getByRole('heading', { name: 'Published roster' })).toBeVisible();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(13);
  await expect(page.getByRole('table').getByText('Ravi Kumar', { exact: true })).toHaveCount(0);
  await page.getByLabel('Outlet', { exact: true }).selectOption({ label: 'HSR Layout' });
  await expect(page.getByRole('heading', { name: 'Published roster' })).toBeVisible();
});

test('denied context clears the previous roster', async ({ page }) => {
  await page.getByLabel('Demo outcome', { exact: true }).selectOption('denied');
  await expect(page.getByRole('heading', { name: 'This schedule is outside your access.' })).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
});

test('expired sessions leave no old roster on screen', async ({ page }) => {
  await page.route('**/api/fixture/v2/outlets/*/schedules/**', route => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { code: 'unauthenticated', message: 'Session expired', retryable: false, details: {} } }) }));
  await page.getByRole('button', { name: 'Next week' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Your session expired');
  await expect(page.getByRole('table')).toHaveCount(0);
});

test('contract roster is accessible and fits desktop/mobile', async ({ page }, info) => {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.join(process.cwd(), '.impeccable/review', `${info.project.name}.png`), fullPage: true, animations: 'disabled' });
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
});

test('joins an existing run once and reports missing provider detail for the second option', async ({ page }) => {
  let writes = 0;
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/generate')) writes += 1; });
  await page.getByRole('button', { name: 'Next week' }).click();
  await page.getByLabel('Demo outcome', { exact: true }).selectOption('active');
  await page.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page.getByRole('heading', { name: 'Options ready for a closer look.' })).toBeVisible();
  expect(writes).toBe(1);
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: 'Review option' }).last().click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('A detailed provider fixture is not available');
  await expect(page.getByRole('heading', { name: 'Proposed roster' })).toHaveCount(0);
  expect(writes).toBe(1);
});

test('shows rate-limit guidance without retrying the generation write', async ({ page }) => {
  let writes = 0;
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/generate')) writes += 1; });
  await page.getByRole('button', { name: 'Next week' }).click();
  await page.getByLabel('Demo outcome', { exact: true }).selectOption('rate_limited');
  await page.getByRole('button', { name: 'Generate draft' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('in 3 seconds');
  expect(writes).toBe(1);
});

test('explains staffing metrics and filters the team by skill', async ({ page }) => {
  await expect(page.getByLabel('Week at a glance')).toContainText('13 team members');
  await expect(page.getByLabel('Week at a glance')).toContainText('60 shifts');
  await expect(page.getByRole('meter', { name: 'Preferred staffing coverage' })).toHaveAttribute('value', '0.7714');
  await expect(page.getByText('Required minimum staffing is covered.', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'What needs a closer look?' })).toBeVisible();
  const filter = page.getByRole('button', { name: 'Cashier', exact: true });
  await filter.click();
  await expect(filter).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('table').getByText('Ravi Kumar', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('table').getByText('Priya Sharma', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'All skills', exact: true }).click();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(13);
  await page.getByLabel('Find a teammate', { exact: true }).fill('no-such-person');
  await expect(page.getByRole('status')).toContainText('No teammates match these filters');
  await page.getByLabel('Find a teammate', { exact: true }).clear();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(13);
});

test('published week provides a direct route to planning next week', async ({ page }) => {
  await page.getByRole('button', { name: 'Plan upcoming week', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate draft' })).toBeEnabled();
});
