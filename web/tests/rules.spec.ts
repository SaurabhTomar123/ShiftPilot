import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
async function rules(page: Page, owner = false) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  if (owner) { await page.getByLabel('Demo persona').selectOption('owner'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible(); }
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Rules', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Rule type', exact: true })).toBeVisible();
  return page.getByRole('region', { name: 'Scheduling rules workspace', exact: true });
}
async function student(page: Page) {
  const panel = await rules(page, true);
  await panel.getByRole('button', { name: 'Load student finish-limit example', exact: true }).click();
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await expect(panel.getByRole('heading', { name: 'Review rule impact', exact: true })).toBeVisible();
  return panel;
}

test('rules open read-only with manager scopes, accessible controls and no viewport overflow', async ({ page }) => {
  const writes: string[] = []; page.on('request', r => { if (r.method() !== 'GET' && !r.url().endsWith('/session/demo')) writes.push(r.url()); });
  const panel = await rules(page);
  expect(writes).toEqual([]);
  await expect(panel.getByRole('combobox', { name: 'Applies to', exact: true }).locator('option')).toHaveText(['Selected outlet', 'One person']);
  await expect(panel.getByText('Tag: student across outlets.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Archive rule', exact: true })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/rules-${test.info().project.name}.png`, fullPage: true });
});

test('owner preview reports server scope and requires an explicit keyed save', async ({ page }) => {
  const saved: { body: unknown; key?: string }[] = []; page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/v2/rules')) saved.push({ body: r.postDataJSON(), key: r.headers()['idempotency-key'] }); });
  const panel = await student(page);
  expect(saved).toEqual([]);
  await expect(panel.getByText('3 affected people returned.', { exact: false })).toBeVisible();
  await expect(panel.getByText('Rohit Verma', { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await panel.getByRole('button', { name: 'Save reviewed rule', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Rule saved.');
  expect(saved).toHaveLength(1); expect(saved[0].body).toEqual(fixtures['rules.create'].request.body); expect(saved[0].key).toBeTruthy();
  await expect(panel.locator('.saved-rules > li')).toHaveCount(1);
});

test('editing a definition invalidates its preview and blocks stale saves', async ({ page }) => {
  const panel = await student(page);
  await panel.getByRole('textbox', { name: 'Rule notes (optional)', exact: true }).fill('Different notes');
  await expect(panel.getByRole('region', { name: 'Rule impact preview', exact: true })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toHaveCount(0);
});

test('conflicts block saving; suggested exceptions require a fresh, supported preview', async ({ page }) => {
  const panel = await rules(page);
  await panel.getByRole('button', { name: 'Load Rohit conflict example', exact: true }).click();
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toBeDisabled();
  await panel.getByRole('button', { name: 'Use suggested exception for Rohit Verma', exact: true }).click();
  await expect(panel.getByRole('region', { name: 'Rule impact preview', exact: true })).toHaveCount(0);
  await expect(panel.getByText('This definition includes an explicit exception reference:', { exact: false })).toContainText(fixtures['rules.list'].response.body.items[0].id);
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('No matching rule preview is supplied');
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toHaveCount(0);
});

test('a supplied valid exception preview preserves the exact override on explicit save', async ({ page }) => {
  // Consumer-only variant: the provider does not supply a successful exception preview/save.
  const exception = fixtures['rules.preview.conflict'].response.body.conflicts[0].suggested_exception;
  let previews = 0; const saved: unknown[] = [];
  await page.route('**/v2/rules/preview', async route => {
    previews++; const body = route.request().postDataJSON();
    if (body.overrides_rule_id) await route.fulfill({ json: { ...fixtures['rules.preview.conflict'].response.body, rule: exception, valid: true, conflicts: [] } }); else await route.continue();
  });
  await page.route('**/v2/rules', async route => { saved.push(route.request().postDataJSON()); await route.fulfill({ status: 201, json: { ...fixtures['rules.create'].response.body, ...exception, id: 'b815d4a2-ae09-478e-bd20-a0632e34d116' } }); });
  const panel = await rules(page); await panel.getByRole('button', { name: 'Load Rohit conflict example', exact: true }).click();
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await panel.getByRole('button', { name: 'Use suggested exception for Rohit Verma', exact: true }).click();
  expect(saved).toEqual([]); expect(previews).toBe(1);
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toBeEnabled();
  await panel.getByRole('button', { name: 'Save reviewed rule', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Rule saved.'); expect(saved).toEqual([exception]); expect(previews).toBe(2);
});

test('mismatched preview definitions never authorize a save', async ({ page }) => {
  await page.route('**/v2/rules/preview', route => route.fulfill({ json: { ...fixtures['rules.preview'].response.body, rule: { ...fixtures['rules.preview'].response.body.rule, parameters: { latest_end_minute: 1200, weekdays: [0, 1, 2, 3, 4] } } } }));
  const panel = await rules(page, true); await panel.getByRole('button', { name: 'Load student finish-limit example', exact: true }).click();
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('preview does not match');
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toHaveCount(0);
});

test('cross-outlet impacts retain returned offsets and remain informational', async ({ page }) => {
  // Consumer-only impact variant, not provider/live evidence.
  await page.route('**/v2/rules/preview', route => route.fulfill({ json: { ...fixtures['rules.preview'].response.body, impact: [{ employee_id: 'person', name: 'Person in another outlet', logical_shift_id: 'shift', start_at: '2026-10-30T18:00:00-04:00', end_at: '2026-10-30T23:00:00-04:00', message: 'Finish exceeds the proposed limit.' }] } }));
  const panel = await student(page);
  await expect(panel.getByText('2026-10-30 23:00 UTC-04:00', { exact: true })).toBeVisible();
  await expect(panel.getByText('Up to 50 impacts are returned.', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

test('lost save responses lock edits and retry only explicitly with the original key', async ({ page }) => {
  const keys: string[] = [];
  await page.route('**/v2/rules', async route => { keys.push(route.request().headers()['idempotency-key']); if (keys.length === 1) { await route.fetch(); await route.abort('failed'); } else await route.continue(); });
  const panel = await student(page); await panel.getByRole('button', { name: 'Save reviewed rule', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Retry same rule save', exact: true })).toBeVisible();
  await expect(panel.getByRole('combobox', { name: 'Rule type', exact: true })).toBeDisabled();
  await expect(panel.getByRole('button', { name: 'Archive rule', exact: true })).toBeDisabled(); expect(keys).toHaveLength(1);
  await panel.getByRole('button', { name: 'Check rule save', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('does not prove this request completed'); expect(keys).toHaveLength(1);
  await panel.getByRole('button', { name: 'Retry same rule save', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Rule saved.'); expect(keys).toHaveLength(2); expect(keys[1]).toBe(keys[0]);
});

test('late server conflicts invalidate the old preview without retrying a write', async ({ page }) => {
  let writes = 0;
  await page.route('**/v2/rules', route => { writes++; return route.fulfill({ status: 409, json: { error: { code: 'conflict', message: 'Current facts now conflict. Preview again.', retryable: false, details: {} } } }); });
  const panel = await student(page); await panel.getByRole('button', { name: 'Save reviewed rule', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('Current facts now conflict');
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toHaveCount(0); expect(writes).toBe(1);
});

test('archiving requires a separate decision and supports inspecting archived records', async ({ page }) => {
  let writes = 0; page.on('request', r => { if (r.url().endsWith('/archive')) writes++; });
  const panel = await rules(page, true); await panel.getByRole('button', { name: 'Archive rule', exact: true }).click();
  expect(writes).toBe(0); await panel.getByRole('button', { name: 'Keep rule', exact: true }).click(); expect(writes).toBe(0);
  await panel.getByRole('button', { name: 'Archive rule', exact: true }).click(); await panel.getByRole('button', { name: 'Confirm archive rule', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Rule archived.'); expect(writes).toBe(1);
  await expect(panel.locator('.saved-rules > li')).toHaveCount(0); await panel.getByLabel('Include archived rules').check();
  await expect(panel.locator('.saved-rules > li')).toContainText('archived');
});

test('unconfirmed archive results require a read before any further writes', async ({ page }) => {
  let writes = 0;
  await page.route('**/v2/rules/*/archive', async route => { writes++; await route.fetch(); await route.abort('failed'); });
  const panel = await rules(page, true); await panel.getByRole('button', { name: 'Archive rule', exact: true }).click(); await panel.getByRole('button', { name: 'Confirm archive rule', exact: true }).click();
  await expect(panel.getByText('The archive result is not confirmed.', { exact: false })).toBeVisible();
  await expect(panel.getByRole('combobox', { name: 'Rule type', exact: true })).toBeDisabled(); expect(writes).toBe(1);
  await panel.getByRole('button', { name: 'Reload saved rules', exact: true }).click();
  await expect(panel.locator('.saved-rules > li')).toContainText('archived');
  await expect(panel.getByRole('combobox', { name: 'Rule type', exact: true })).toBeEnabled(); expect(writes).toBe(1);
});

test('a late preview cannot authorize a rule in a newly selected outlet', async ({ page }) => {
  const panel = await rules(page, true);
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void; const pending = new Promise<void>(resolve => { started = resolve; });
  await page.route('**/v2/rules/preview', async route => { started(); await gate; await route.fulfill({ json: fixtures['rules.preview'].response.body }).catch(() => {}); });
  await panel.getByRole('button', { name: 'Load student finish-limit example', exact: true }).click();
  await panel.getByRole('button', { name: 'Preview rule impact', exact: true }).click(); await pending;
  await page.getByLabel('Outlet', { exact: true }).selectOption(fixtures['outlets.owner'].response.body.items[1].id); release();
  await expect(panel.getByRole('combobox', { name: 'Rule type', exact: true })).toHaveValue('max_days_per_week');
  await expect(panel.getByRole('button', { name: 'Save reviewed rule', exact: true })).toHaveCount(0);
});
