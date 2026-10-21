import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function navigate(page: Page, name: 'History' | 'Schedule') {
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name, exact: true }).click();
}
async function history(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await navigate(page, 'History'); await expect(page.getByRole('heading', { name: 'Version history', exact: true })).toBeVisible();
}
async function restore(page: Page) {
  await history(page);
  await page.getByRole('button', { name: 'Restore version 2 as draft', exact: true }).click();
  await page.getByRole('button', { name: 'Create restored draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Draft 5: review current validation', exact: true })).toBeVisible();
}

test('history and directional comparison are read-only, accessible and fit both viewports', async ({ page }) => {
  let writes = 0; page.on('request', r => { if (r.method() === 'POST' && !r.url().endsWith('/session/demo')) writes += 1; });
  await history(page);
  await expect(page.locator('.history-list')).toContainText('Recorded estimated cost');
  await page.getByRole('button', { name: 'Compare selected versions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Version 3 to Version 4', exact: true })).toBeVisible();
  const comparison = page.getByRole('region', { name: 'Assignment comparison', exact: true });
  await expect(comparison).toContainText('lock changed'); await expect(comparison).toContainText('unlocked');
  const from = await page.getByLabel('From version', { exact: true }).inputValue();
  const to = await page.getByLabel('To version', { exact: true }).inputValue();
  await page.getByLabel('From version', { exact: true }).selectOption(to);
  await page.getByLabel('To version', { exact: true }).selectOption(from);
  await page.getByRole('button', { name: 'Compare selected versions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Version 4 to Version 3', exact: true })).toBeVisible(); expect(writes).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
});

test('restore creates only a draft and publication waits for explicit proposal approval', async ({ page }) => {
  let restores = 0; page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/restore')) restores += 1; });
  await history(page);
  await page.getByRole('button', { name: 'Restore version 2 as draft', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Restore confirmation', exact: true })).toContainText('Version 3'); expect(restores).toBe(0);
  await page.getByRole('button', { name: 'Create restored draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Draft 5: review current validation', exact: true })).toBeVisible(); expect(restores).toBe(1);
  await expect(page.getByRole('status')).toContainText('Nothing has been published');
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.locator('.history-list > li').filter({ has: page.getByRole('heading', { name: 'Version 5', exact: true }) })).toContainText('Current published');
  await expect(page.getByRole('status')).toContainText('Published version 5');
});

test('current validation can block a restored draft without reviving assignments silently', async ({ page }) => {
  await page.route('**/schedule-versions/*/restore', async route => {
    const response = await route.fetch(); const value = await response.json();
    value.validation = { hard_violations: 1, soft_violations: 0, violations: [{ code: 'absent', severity: 'hard', message: 'A confirmed absence blocks this restored assignment.', employee_id: value.shifts[0].employee_id, logical_shift_ids: [value.shifts[0].logical_shift_id], facts: {} }] };
    await route.fulfill({ response, json: value });
  });
  await restore(page);
  await expect(page.getByRole('region', { name: 'Restored draft review', exact: true })).toContainText('confirmed absence');
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toBeDisabled();
  await expect(page.locator('.history-list > li').filter({ hasText: 'Current published' })).toContainText('Version 3');
});

test('a stale restore preserves the choice and waits for explicit reload', async ({ page }) => {
  await history(page); let writes = 0;
  await page.route('**/schedule-versions/*/restore', async route => { writes += 1; return route.fulfill({ status: 409, json: { error: { code: 'stale_version', message: 'The published base changed.', retryable: false, details: {} } } }); });
  await page.getByRole('button', { name: 'Restore version 2 as draft', exact: true }).click();
  await page.getByRole('button', { name: 'Create restored draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('published base changed');
  await expect(page.getByRole('heading', { name: 'Restore version 2 into a new draft', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create restored draft', exact: true })).toBeDisabled(); expect(writes).toBe(1);
  await page.getByRole('button', { name: 'Reload history', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Restore confirmation', exact: true })).toHaveCount(0); expect(writes).toBe(1);
});

test('a lost restore response is retried only explicitly with the same key and base', async ({ page }) => {
  await history(page); const actions: { key: string; body: unknown }[] = [];
  await page.route('**/schedule-versions/*/restore', async route => {
    actions.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() });
    if (actions.length > 1) return route.continue();
    await route.fetch(); return route.fulfill({ status: 503, json: { error: { code: 'internal', message: 'Restore response unavailable.', retryable: true, details: {} } } });
  });
  await page.getByRole('button', { name: 'Restore version 2 as draft', exact: true }).click();
  await page.getByRole('button', { name: 'Create restored draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Restore response unavailable'); expect(actions).toHaveLength(1);
  await page.getByRole('button', { name: 'Create restored draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Draft 5: review current validation', exact: true })).toBeVisible();
  expect(actions).toHaveLength(2); expect(actions[0]).toEqual(actions[1]);
});

test('History discovers and reopens the pending proposal from a closed schedule view', async ({ page }) => {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Create editing draft', exact: true }).click();
  await page.getByRole('button', { name: 'Close assignment editor', exact: true }).click();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await navigate(page, 'History');
  await page.getByRole('button', { name: 'Review pending proposal', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toHaveCount(0);
});

test('late comparison data cannot replace a different week', async ({ page }) => {
  await history(page); let release!: () => void; const paused = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/schedule-versions/*/compare?*', async route => { const response = await route.fetch(); await paused; await route.fulfill({ response }).catch(() => {}); });
  await page.getByRole('button', { name: 'Compare selected versions', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Comparing…', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Next week', exact: true }).click(); release();
  await expect(page.getByRole('heading', { name: 'No version history yet', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Assignment comparison', exact: true })).toHaveCount(0);
});

test('empty and denied histories do not retain the previous version list', async ({ page }) => {
  await history(page); await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No version history yet', exact: true })).toBeVisible();
  await expect(page.locator('.history-list')).toHaveCount(0);
  await page.getByRole('button', { name: 'Previous week', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Version history', exact: true })).toBeVisible();
  await page.getByLabel('Demo outcome', { exact: true }).selectOption('denied');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('only access your own outlet');
  await expect(page.locator('.history-list')).toHaveCount(0);
});

test('missing stored metrics are stated rather than replaced with recomputed estimates', async ({ page }) => {
  await page.route('**/schedules/*/versions', async route => { const response = await route.fetch(); const value = await response.json(); value.items[0].recorded_metrics = null; await route.fulfill({ response, json: value }); });
  await history(page);
  await expect(page.locator('.history-list > li').first()).toContainText('No recorded metrics');
});
