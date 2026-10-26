import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const initial = fixtures['staffing.get'].response.body;
const templates = fixtures['staffing_templates.list'].response.body;
async function staffing(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Staffing', exact: true }).click();
  await expect(page.getByLabel(/^Minimum at/).first()).toBeVisible();
  await page.getByText('Weekly staffing template', { exact: true }).click();
  const panel = page.getByRole('region', { name: 'Weekly staffing template editor', exact: true });
  await expect(panel.getByLabel(/^Template start/).first()).toBeVisible(); return panel;
}

test('opening the template is read-only, accessible and fits the phone viewport', async ({ page }) => {
  const writes: string[] = []; page.on('request', request => { if (['PUT', 'POST', 'PATCH'].includes(request.method())) writes.push(request.url()); });
  const panel = await staffing(page);
  await expect(panel.getByRole('button', { name: 'Save weekly template', exact: true })).toBeDisabled();
  expect(writes.filter(url => !url.endsWith('/session/demo'))).toEqual([]);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/staffing-template-${test.info().project.name}.png`, fullPage: true });
});

test('saving Saturday staffing sends the entire template and leaves the dated week unchanged', async ({ page }) => {
  const saved: unknown[] = []; page.on('request', request => { if (request.method() === 'PUT') saved.push(request.postDataJSON()); });
  const panel = await staffing(page);
  await panel.getByRole('button', { name: 'Load Saturday Grill example', exact: true }).click();
  await panel.getByRole('button', { name: 'Save weekly template', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Dated requirements are unchanged');
  expect(saved).toEqual([fixtures['staffing_templates.put'].request.body]);
  await expect(page.getByText('Revision 3.', { exact: false }).last()).toBeVisible();
  await panel.getByLabel('Template weekday').selectOption('0');
  await panel.getByRole('button', { name: 'Reload weekly template', exact: true }).click();
  await expect(panel.getByText('Template revision 2.', { exact: true })).toBeVisible();
});

test('overlapping and invalid-count blocks never reach the save endpoint', async ({ page }) => {
  let writes = 0; page.on('request', request => { if (request.method() === 'PUT') writes++; });
  const panel = await staffing(page);
  await panel.getByLabel('Template skill').selectOption(templates.items[0].skill_id);
  await panel.getByRole('button', { name: 'Add template block', exact: true }).click();
  await panel.getByRole('button', { name: 'Save weekly template', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('must not overlap'); expect(writes).toBe(0);
  await panel.getByRole('button', { name: 'Remove block 2 from weekly template', exact: true }).click();
  await panel.getByLabel('Template minimum 1', { exact: true }).fill('3');
  await panel.getByLabel('Template preferred 1', { exact: true }).fill('2');
  await panel.getByRole('button', { name: 'Save weekly template', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('preferred staffing must be at least'); expect(writes).toBe(0);
});

test('expansion review is not a write; explicit expansion sends the reviewed demand revision and updates dated requirements', async ({ page }) => {
  const writes: { url: string; body: unknown; key: string | undefined }[] = [];
  page.on('request', request => { if (request.method() === 'POST' && !request.url().endsWith('/session/demo')) writes.push({ url: request.url(), body: request.postDataJSON(), key: request.headers()['idempotency-key'] }); });
  const panel = await staffing(page); await panel.getByRole('button', { name: 'Review expansion request', exact: true }).click();
  await expect(panel.getByText('This is a request summary, not a generated-interval preview.', { exact: false })).toBeVisible(); expect(writes).toEqual([]);
  await panel.getByRole('button', { name: 'Expand saved template into this week', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Expansion confirmed');
  expect(writes).toHaveLength(1); expect(writes[0].body).toEqual({ base_demand_revision: 3, use_demand_bands: false }); expect(writes[0].key).toBeTruthy();
  expect(writes[0].url).toContain('/staffing-requirements/expand?week_start=2026-10-19');
  await expect(page.getByText('Revision 4.', { exact: false }).last()).toBeVisible();
});

test('unsaved dated edits block expansion until the user explicitly reloads them', async ({ page }) => {
  const panel = await staffing(page); await page.getByLabel(/^Minimum at/).first().fill('2');
  await expect(panel.getByRole('button', { name: 'Review expansion request', exact: true })).toBeDisabled();
  await expect(panel.getByText('Dated staffing has unsaved changes.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Reload dated staffing', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Review expansion request', exact: true })).toBeEnabled();
});

test('unsupported template saves preserve inputs and require a deliberate reload', async ({ page }) => {
  const panel = await staffing(page); await panel.getByLabel('Template minimum 1', { exact: true }).fill('0');
  await panel.getByRole('button', { name: 'Save weekly template', exact: true }).click();
  await expect(panel.getByText('The template save or revision was not confirmed.', { exact: false })).toBeVisible();
  await expect(panel.getByLabel('Template minimum 1', { exact: true })).toHaveValue('0');
  await expect(panel.getByRole('button', { name: 'Save weekly template', exact: true })).toBeDisabled();
  await panel.getByRole('button', { name: 'Reload weekly template', exact: true }).click();
  await expect(panel.getByText('Weekly template reloaded.', { exact: false })).toBeVisible();
});

test('a lost expansion response locks dated writes and retries only explicitly with the original key', async ({ page }) => {
  const keys: string[] = [];
  await page.route('**/staffing-requirements/expand?*', async route => { keys.push(route.request().headers()['idempotency-key']); if (keys.length === 1) { await route.fetch(); await route.abort('failed'); } else await route.continue(); });
  const panel = await staffing(page); await panel.getByRole('button', { name: 'Review expansion request', exact: true }).click();
  await panel.getByRole('button', { name: 'Expand saved template into this week', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Retry same expansion', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save staffing needs', exact: true })).toBeDisabled();
  expect(keys).toHaveLength(1);
  await panel.getByRole('button', { name: 'Check dated staffing', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('does not prove this expansion completed'); expect(keys).toHaveLength(1);
  await panel.getByRole('button', { name: 'Retry same expansion', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Expansion confirmed');
  expect(keys).toHaveLength(2); expect(keys[1]).toBe(keys[0]);
  await expect(page.getByRole('button', { name: 'Save staffing needs', exact: true })).toBeEnabled();
});

test('a changed template revision stops expansion before its POST', async ({ page }) => {
  let writes = 0; page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/expand')) writes++; });
  const panel = await staffing(page); await panel.getByRole('button', { name: 'Review expansion request', exact: true }).click();
  await page.route('**/staffing-templates', route => route.fulfill({ json: { ...templates, revision: 2 } }));
  await panel.getByRole('button', { name: 'Expand saved template into this week', exact: true }).click();
  await expect(panel.getByText('The saved weekly template changed.', { exact: false })).toBeVisible(); expect(writes).toBe(0);
});

test('manual intervals returned by the server remain visible after expansion', async ({ page }) => {
  // Consumer-only fixture variant: the provider expansion example does not contain manual overrides.
  const dated = structuredClone(initial); dated.intervals[0].source = 'manual'; dated.intervals[0].minimum_required = 2; dated.intervals[0].preferred_required = 2;
  await page.route('**/staffing-requirements?*', route => route.fulfill({ json: dated }));
  const expanded = structuredClone(dated); expanded.demand_revision += 1;
  await page.route('**/staffing-requirements/expand?*', route => route.fulfill({ json: expanded }));
  const panel = await staffing(page); await panel.getByRole('button', { name: 'Review expansion request', exact: true }).click();
  await expect(panel.getByText('1 current manual intervals.', { exact: false })).toBeVisible();
  await panel.getByRole('button', { name: 'Expand saved template into this week', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Expansion confirmed');
  await expect(page.locator('.demand-intervals > div').first()).toContainText('manual');
  await expect(page.getByLabel(/^Minimum at/).first()).toHaveValue('2');
});

test('late template reads cannot replace a different outlet', async ({ page }) => {
  await page.goto('/'); await page.getByLabel('Demo persona').selectOption('owner');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; }); let started!: () => void; const pending = new Promise<void>(resolve => { started = resolve; });
  await page.route('**/staffing-templates', async route => { started(); await gate; await route.fulfill({ json: templates }).catch(() => {}); });
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Staffing', exact: true }).click(); await pending;
  const outletId = fixtures['outlets.owner'].response.body.items[1].id;
  await page.getByLabel('Outlet', { exact: true }).selectOption(outletId); release();
  await page.getByText('Weekly staffing template', { exact: true }).click();
  await expect(page.getByText('The template response belongs to another outlet.', { exact: true })).toBeVisible();
  await expect(page.getByLabel(/^Template start/)).toHaveCount(0);
});

test('read-only scheduling access cannot edit or expand staffing templates', async ({ page }) => {
  await page.route('**/v2/session/demo', async route => { const response = await route.fetch(); const body = await response.json(); body.me.capabilities = body.me.capabilities.filter((value: string) => value !== 'edit_demand'); await route.fulfill({ response, json: body }); });
  const panel = await staffing(page);
  await expect(panel.getByLabel(/^Template minimum/).first()).toBeDisabled();
  await expect(panel.getByRole('button', { name: 'Save weekly template', exact: true })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Review expansion request', exact: true })).toBeDisabled();
});

test('the changed-template example never receives the original template expansion result', async ({ page }) => {
  const panel = await staffing(page);
  await panel.getByRole('button', { name: 'Load Saturday Grill example', exact: true }).click();
  await panel.getByRole('button', { name: 'Save weekly template', exact: true }).click();
  await expect(panel.getByRole('status')).toContainText('Weekly template saved');
  await panel.getByRole('button', { name: 'Review expansion request', exact: true }).click();
  await panel.getByRole('button', { name: 'Expand saved template into this week', exact: true }).click();
  await expect(panel.getByText('Expansion fixtures cover the original weekly template', { exact: false })).toBeVisible();
  await expect(page.getByText('Revision 3.', { exact: false }).last()).toBeVisible();
  await expect(panel.getByText('Expansion confirmed', { exact: false })).toHaveCount(0);
});
