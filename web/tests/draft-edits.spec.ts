import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
const examples = JSON.parse(readFileSync(new URL('../src/api/generated/edit-examples.json', import.meta.url), 'utf8'));

async function openEditor(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Create editing draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Edit a draft assignment', exact: true })).toBeVisible();
}
async function validPreview(page: Page) {
  await openEditor(page);
  await page.getByRole('button', { name: 'Load opening-cook lock', exact: true }).click();
  await page.getByRole('button', { name: 'Preview assignment change', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Assignment change preview', exact: true }).getByRole('status')).toContainText('No hard violations');
}

test('preview is read-only and apply sends exactly the reviewed revision and edit', async ({ page }) => {
  const applied: unknown[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/edits$/.test(request.url())) applied.push(request.postDataJSON()); });
  await validPreview(page);
  expect(applied).toHaveLength(0);
  await expect(page.getByText('Editing draft 4, revision 1.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('saved to draft revision 2');
  expect(applied).toEqual([examples.openingLock]);
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Edit draft assignments', exact: true })).toBeFocused();
});

test('invalid reassignment shows the server constraint and cannot be applied', async ({ page }) => {
  let saves = 0; page.on('request', r => { if (r.method() === 'POST' && /\/edits$/.test(r.url())) saves += 1; });
  await openEditor(page);
  await page.getByRole('button', { name: 'Load conflicting reassignment', exact: true }).click();
  await page.getByRole('button', { name: 'Preview assignment change', exact: true }).click();
  const preview = page.getByRole('region', { name: 'Assignment change preview', exact: true });
  await expect(preview.getByRole('status')).toContainText('Blocked by scheduling validation');
  await expect(preview).toContainText('Ravi Kumar is not available');
  await expect(page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true })).toBeDisabled();
  expect(saves).toBe(0);
});

test('changing inputs invalidates the previous successful preview', async ({ page }) => {
  await validPreview(page);
  await expect(page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true })).toBeEnabled();
  await page.getByLabel('Lock reason', { exact: true }).fill('A different request');
  await expect(page.getByRole('region', { name: 'Assignment change preview', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true })).toHaveCount(0);
});

test('a stale save retains values and waits for explicit reload', async ({ page }) => {
  await validPreview(page); let saves = 0;
  await page.route('**/v2/schedule-versions/*/edits', async route => { saves += 1; return route.fulfill({ status: 409, json: { error: { code: 'stale_version', message: 'A newer draft revision is available.', retryable: false, details: { current_revision: 2 } } } }); });
  await page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('A newer draft revision');
  await expect(page.getByLabel('Lock reason', { exact: true })).toHaveValue('Opening cook confirmed');
  await expect(page.getByLabel('Lock reason', { exact: true })).toBeDisabled(); expect(saves).toBe(1);
  await page.getByRole('button', { name: 'Reload latest draft', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Reloaded the current draft'); expect(saves).toBe(1);
});

test('a lost save response blocks replay and reloads the committed revision', async ({ page }) => {
  await validPreview(page); let saves = 0;
  await page.route('**/v2/schedule-versions/*/edits', async route => { saves += 1; await route.fetch(); await route.fulfill({ status: 503, json: { error: { code: 'internal', message: 'The save response was lost.', retryable: true, details: {} } } }); });
  await page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('save response was lost');
  await expect(page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preview assignment change', exact: true })).toBeDisabled();
  expect(saves).toBe(1);
  await page.getByRole('button', { name: 'Reload latest draft', exact: true }).click();
  await expect(page.getByText('Draft revision 2', { exact: true })).toBeVisible(); expect(saves).toBe(1);
});

test('the edited revision is proposed and published without changing the old published week first', async ({ page }) => {
  await validPreview(page);
  await expect(page.getByText('Draft preview · not published', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true }).click();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await expect(page.getByText('Proposal status:', { exact: false })).toContainText('Revision 2');
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Published version 4');
});

test('closing without edits keeps a pending proposal available', async ({ page }) => {
  await openEditor(page);
  await page.getByRole('button', { name: 'Close assignment editor', exact: true }).click();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await page.getByRole('button', { name: 'Edit draft assignments', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Close assignment editor', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toHaveCount(0);
});

test('saving a changed revision requires a fresh proposal review', async ({ page }) => {
  const revisions: number[] = [];
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/proposals')) revisions.push(request.postDataJSON().expected_revision); });
  await openEditor(page);
  await page.getByRole('button', { name: 'Close assignment editor', exact: true }).click();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await page.getByRole('button', { name: 'Edit draft assignments', exact: true }).click();
  await page.getByRole('button', { name: 'Load opening-cook lock', exact: true }).click();
  await page.getByRole('button', { name: 'Preview assignment change', exact: true }).click();
  await page.getByRole('button', { name: 'Apply reviewed change to draft', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
  expect(revisions).toEqual([1, 2]);
});

test('create-draft can recover a lost response by replaying the same key', async ({ page }) => {
  await page.goto('/'); const keys: string[] = [];
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.route('**/schedules/*/drafts', async route => { keys.push(route.request().headers()['idempotency-key']); if (keys.length > 1) return route.continue(); await route.fetch(); return route.fulfill({ status: 503, json: { error: { code: 'internal', message: 'Draft response unavailable.', retryable: true, details: {} } } }); });
  await page.getByRole('button', { name: 'Create editing draft', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Draft response unavailable'); expect(keys).toHaveLength(1);
  await page.getByRole('button', { name: 'Create editing draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Edit a draft assignment', exact: true })).toBeVisible();
  expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1]);
});

test('the editor has a keyboard entry point and accessible phone layout', async ({ page }) => {
  await openEditor(page);
  await expect(page.getByRole('heading', { name: 'Edit a draft assignment', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Load conflicting reassignment', exact: true }).click();
  await page.getByRole('button', { name: 'Preview assignment change', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Assignment change preview', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
});

test('a preview arriving after a week change cannot replace the new roster', async ({ page }) => {
  await openEditor(page);
  await page.getByRole('button', { name: 'Load opening-cook lock', exact: true }).click();
  let release!: () => void;
  const paused = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/edits/preview', async route => { const response = await route.fetch(); await paused; await route.fulfill({ response }).catch(() => {}); });
  await page.getByRole('button', { name: 'Preview assignment change', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Checking assignment…', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Next week', exact: true }).click(); release();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Assignment change preview', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toHaveCount(0);
});
