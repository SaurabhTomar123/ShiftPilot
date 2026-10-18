import { expect, test, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';

async function navigate(page: Page, name: string) {
  const menu = page.getByRole('button', { name: 'Open navigation' });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation').getByRole('button', { name: new RegExp(`^${name}( \\d+)?$`) }).click();
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Weekly schedule' })).toBeVisible();
  await expect(page.getByText('Saved on this device')).toBeAttached();
});

test('weekly roster, role filter and outlet/week isolation', async ({ page }) => {
  await expect(page.getByRole('table').getByText('Ravi Kumar')).toBeVisible();
  await page.getByLabel('Filter role').selectOption('Kitchen');
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(5);
  await page.getByLabel('Outlet', { exact: true }).selectOption('koramangala');
  await expect(page.getByRole('table').getByText('Akash Pai')).toBeVisible();
  await expect(page.getByRole('table').getByText('Ravi Kumar')).toHaveCount(0);
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.' })).toBeVisible();
});

test('lock, generate, publish and restore remain local and survive reload', async ({ page }) => {
  await page.getByRole('button', { name: 'Edit Ravi Kumar, Mon, 14:00 to 22:00', exact: true }).click();
  await page.getByRole('checkbox', { name: 'Lock this assignment' }).check();
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await page.getByRole('button', { name: 'Generate week', exact: true }).click();
  await page.getByRole('button', { name: 'Load sample week', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Edit Ravi Kumar, Mon, 14:00 to 22:00, locked', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Publish schedule', exact: true }).click();
  await page.getByRole('button', { name: 'Publish demo version', exact: true }).click();
  await page.reload();
  await expect(page.getByText('Published locally', { exact: true })).toBeAttached();
  await navigate(page, 'History');
  await expect(page.getByRole('heading', { name: /Version 1/ })).toBeVisible();
  await page.getByRole('button', { name: 'Restore as draft' }).click();
  await expect(page.getByRole('heading', { name: 'Weekly schedule' })).toBeVisible();
});

test('absence replacement previews a real fixture candidate and updates the draft', async ({ page }) => {
  await page.getByRole('button', { name: 'Try an absence' }).click();
  await expect(page.getByRole('dialog')).toContainText('Rest, skills, travel and overtime require backend validation');
  await page.getByRole('radio').first().check();
  await page.getByRole('button', { name: 'Apply to draft', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Replacement added');
  await expect(page.getByRole('button', { name: 'Edit Ravi Kumar, Mon, 14:00 to 22:00', exact: true })).toHaveCount(0);
});

test('team, requests and demand controls update without pretending to change a roster', async ({ page }) => {
  await navigate(page, 'Team');
  await page.getByRole('button', { name: 'Add teammate', exact: true }).click();
  await page.getByLabel('Full name', { exact: true }).fill('Anjali Rao');
  await page.getByRole('dialog').getByRole('button', { name: 'Add teammate', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Anjali Rao' })).toBeVisible();
  await navigate(page, 'Requests');
  await page.getByRole('button', { name: 'Acknowledge', exact: true }).first().click();
  await expect(page.getByRole('status')).toContainText('No roster changes');
  await navigate(page, 'Demand');
  await page.getByLabel('Fri preferred kitchen staff', { exact: true }).fill('6');
  await page.reload();
  await navigate(page, 'Demand');
  await expect(page.getByLabel('Fri preferred kitchen staff', { exact: true })).toHaveValue('6');
});

test('keyboard dialog escape and no viewport overflow', async ({ page }) => {
  await page.getByRole('button', { name: 'Generate week', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('accessibility and desktop/mobile visual capture', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.screenshot({ path: path.join(process.cwd(), '.impeccable', 'review', `${testInfo.project.name}.png`), fullPage: true, animations: 'disabled' });
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(results.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
  expect(errors).toEqual([]);
});
