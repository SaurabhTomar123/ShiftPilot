import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';

async function destination(page: Page, name: 'Employees' | 'Staffing' | 'Schedule') {
  const mobile = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await mobile.isVisible()) await mobile.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name, exact: true }).click();
}

test.beforeEach(async ({ page }) => { await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible(); });

test('employee form validates caps and keeps exact paise and skill levels', async ({ page }) => {
  await destination(page, 'Employees');
  await page.getByRole('button', { name: 'Add teammate', exact: true }).click();
  await page.getByLabel('Full name', { exact: true }).fill('Ananya Rao');
  await page.getByLabel('Hourly rate (INR)', { exact: true }).fill('210.01');
  await page.getByLabel('Regular weekly hours', { exact: true }).fill('70');
  await page.getByRole('button', { name: 'Save employee', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('cannot exceed the absolute weekly cap');
  await page.getByLabel('Regular weekly hours', { exact: true }).fill('40');
  await page.getByLabel('Cashier', { exact: true }).check();
  await page.getByLabel('Proficiency for Cashier', { exact: true }).selectOption('2');
  await page.getByRole('button', { name: 'Save employee', exact: true }).click();
  const row = page.getByRole('article').filter({ hasText: 'Ananya Rao' });
  await expect(row).toContainText('₹210.01/hour');
  await expect(row).toContainText('Cashier · level 2');
  await expect(page.getByRole('status')).toContainText('synthetic preview session');
});

test('stale employee edit retains inputs and reload requires an explicit action', async ({ page }) => {
  await destination(page, 'Employees');
  await page.getByRole('button', { name: 'Edit Ravi Kumar', exact: true }).click();
  await page.getByLabel('Full name', { exact: true }).fill('Ravi Updated');
  let writes = 0;
  await page.route('**/v2/employees/*', async route => {
    if (route.request().method() !== 'PATCH') return route.continue();
    writes += 1;
    expect(Object.keys(route.request().postDataJSON()).sort()).toEqual(['base_revision', 'name']);
    return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'stale_version', message: 'Employee changed in another tab.', retryable: false, details: { current_revision: 2 } } }) });
  });
  await page.getByRole('button', { name: 'Save employee', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Someone changed these values');
  await expect(page.getByLabel('Full name', { exact: true })).toHaveValue('Ravi Updated');
  expect(writes).toBe(1);
  await page.getByRole('button', { name: 'Reload latest values', exact: true }).click();
  await expect(page.getByLabel('Full name', { exact: true })).toHaveValue('Ravi Kumar');
  expect(writes).toBe(1);
});

test('overnight availability survives save and re-open', async ({ page }) => {
  await destination(page, 'Employees');
  await page.getByRole('button', { name: 'Availability for Ravi Kumar', exact: true }).click();
  const window = page.locator('.availability-window').first();
  await window.getByLabel('Weekday', { exact: true }).selectOption('6');
  await window.getByLabel('Start time', { exact: true }).fill('22:00');
  await window.getByLabel('End time', { exact: true }).fill('02:00');
  await window.getByLabel('End day', { exact: true }).selectOption('1');
  await page.getByRole('button', { name: 'Save availability', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Availability saved');
  await page.getByRole('button', { name: 'Back to team', exact: true }).first().click();
  await page.getByRole('button', { name: 'Availability for Ravi Kumar', exact: true }).click();
  await expect(page.locator('.availability-window').first().getByLabel('End day', { exact: true })).toHaveValue('1');
  await expect(page.locator('.availability-window').first().getByLabel('End time', { exact: true })).toHaveValue('02:00');
});

test('staffing validates minimum versus preferred and saves the entire filtered week', async ({ page }) => {
  await destination(page, 'Staffing');
  await expect(page.locator('.demand-intervals > div').first()).toBeVisible();
  const counts = await page.getByText(/^Showing \d+ of \d+ intervals/).textContent();
  const total = Number(counts?.match(/of (\d+)/)?.[1]);
  let writes = 0;
  page.on('request', request => { if (request.method() === 'PUT' && request.url().includes('/staffing-requirements')) { writes += 1; expect(request.postDataJSON().intervals).toHaveLength(total); } });
  await page.getByLabel(/^Minimum at/).first().fill('3');
  await page.getByLabel(/^Preferred at/).first().fill('2');
  await page.getByRole('button', { name: 'Save staffing needs', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Preferred staffing must be at least the minimum');
  expect(writes).toBe(0);
  await page.getByLabel(/^Preferred at/).first().fill('4');
  await page.getByRole('button', { name: 'Save staffing needs', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Staffing needs saved');
  expect(writes).toBe(1);
});

test('staffing opens a skill with demand when the API orders an unused skill first', async ({ page }) => {
  await page.route('**/v2/skills', async route => {
    const response = await route.fetch(); const body = await response.json();
    body.items.sort((a: { name: string }, b: { name: string }) => Number(b.name === 'Barista') - Number(a.name === 'Barista'));
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await destination(page, 'Staffing');
  await expect(page.getByLabel(/^Preferred at/).first()).toBeVisible();
});

test('type, color and navigation experiments stay usable and honor reduced motion', async ({ page }, info) => {
  await page.getByText('Appearance', { exact: true }).click();
  await page.getByLabel('Typography', { exact: true }).selectOption('editorial');
  await page.getByLabel('Color treatment', { exact: true }).selectOption('ink');
  await page.getByLabel('Sidebar transition', { exact: true }).selectOption('fold');
  await page.getByText('Appearance', { exact: true }).click();
  await expect(page.locator('.contract-app')).toHaveAttribute('data-typography', 'editorial');
  await expect(page.locator('h1')).toHaveCSS('font-family', /Fraunces/);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const opener = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await opener.isVisible()) {
    await opener.click();
    await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(opener).toBeFocused();
    await expect(page.locator('#workspace-navigation')).toHaveAttribute('inert', '');
  } else {
    await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Expand sidebar', exact: true })).toHaveAttribute('aria-expanded', 'false');
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Employees', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Team and skills', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
  }
  await destination(page, 'Employees');
  await page.getByRole('button', { name: 'Add teammate', exact: true }).click();
  await page.screenshot({ path: path.join(process.cwd(), '.impeccable/review', `management-${info.project.name}.png`), fullPage: true, animations: 'disabled' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
});

test('sidebar transitions can be interrupted without losing navigation state', async ({ page }) => {
  for (const motion of ['slide', 'dissolve', 'fold']) {
    await page.getByText('Appearance', { exact: true }).click();
    await page.getByLabel('Sidebar transition', { exact: true }).selectOption(motion);
    await page.getByText('Appearance', { exact: true }).click();
    const mobile = page.getByRole('button', { name: 'Open navigation', exact: true });
    if (await mobile.isVisible()) {
      await mobile.click(); await page.keyboard.press('Escape');
      await mobile.click();
      await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(mobile).toBeFocused();
    } else {
      await page.locator('.desktop-toggle').evaluate(button => { for (let n = 0; n < 4; n += 1) (button as HTMLButtonElement).click(); });
      await expect(page.locator('.contract-shell')).toHaveAttribute('data-collapsed', 'false');
      await expect(page.getByRole('button', { name: 'Collapse sidebar', exact: true })).toBeVisible();
    }
  }
});
