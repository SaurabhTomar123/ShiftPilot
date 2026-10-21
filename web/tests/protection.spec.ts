import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const week = fixtures['schedule_week.published'].response.body;
const base = week.current_version;
const conflict = fixtures['repair.freeze_conflict'];
const target = base.shifts.find((shift: { logical_shift_id: string }) => shift.logical_shift_id === conflict.request.body.freeze.shift_ids[0]);
const employee = week.employees.find((person: { id: string }) => person.id === target.employee_id);
const theirs = base.shifts.filter((shift: { employee_id: string }) => shift.employee_id === employee.id).map((shift: { logical_shift_id: string }) => shift.logical_shift_id);

async function start(page: Page, inbox = false) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  if (inbox) {
    const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Repair Inbox', exact: true }).click();
    await page.getByRole('button', { name: 'Review repair', exact: true }).click();
  }
  await page.locator('.run-protection-controls > summary').click();
}

async function keepPerson(page: Page) {
  await page.getByText('Keep an employee’s published assignments', { exact: true }).click();
  await page.getByRole('checkbox', { name: `Keep ${employee.name}’s published assignments`, exact: true }).check();
}

test('protection choices are read-only, accessible, and reset on week changes', async ({ page }) => {
  const writes: string[] = []; page.on('request', request => { if (request.method() !== 'GET' && !request.url().endsWith('/session/demo')) writes.push(request.url()); });
  await start(page); await keepPerson(page);
  await page.getByText('Keep a day’s published assignments', { exact: true }).click();
  await page.getByRole('checkbox', { name: 'Keep assignments on 2026-10-21', exact: true }).check();
  await page.getByRole('button', { name: 'Keep this outlet’s published week', exact: true }).click();
  await expect(page.locator('.run-protection-controls > summary')).toHaveText(`Protect commitments for the next run (${base.shifts.length})`);
  expect(writes).toEqual([]);
  expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Next week', exact: true }).click(); await expect(page.locator('.run-protection-controls')).toHaveCount(0);
  await page.getByRole('button', { name: 'Previous week', exact: true }).click(); await expect(page.locator('.run-protection-controls > summary')).toHaveText('Protect commitments for the next run (0)');
  expect(writes).toEqual([]);
});

test('a provider freeze conflict requires explicit release and a separate repair request', async ({ page }) => {
  const writes: { body: Record<string, unknown>; key?: string }[] = [];
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/repair')) writes.push({ body: request.postDataJSON(), key: request.headers()['idempotency-key'] }); });
  await start(page, true);
  await page.getByText('Pin individual published assignments', { exact: true }).click();
  await page.locator('.protection-shifts').getByRole('checkbox', { name: new RegExp(`${employee.name}.*2026-10-21.*10:00`) }).check();
  const repair = page.getByRole('button', { name: 'Start or check repair for this week', exact: true }); await repair.click();
  const warning = page.getByRole('region', { name: 'Run protection conflict', exact: true });
  await expect(warning).toBeVisible(); expect(writes).toHaveLength(1); expect(writes[0].body.freeze).toEqual(conflict.request.body.freeze);
  const release = warning.getByRole('button', { name: 'Remove selected run protections', exact: true }); await expect(release).toBeDisabled();
  await warning.getByRole('checkbox').check(); await release.click(); expect(writes).toHaveLength(1);
  await expect(warning).toHaveCount(0); await expect(page.locator('.run-protection-controls > summary')).toHaveText('Protect commitments for the next run (0)');
  await repair.click(); await expect(page.getByRole('region', { name: 'Repair result', exact: true })).toBeVisible();
  expect(writes).toHaveLength(2); expect(writes[1].body.freeze).toBeUndefined(); expect(writes[1].key).not.toBe(writes[0].key);
  await expect(page.locator('.repair-stages')).toContainText('Only directly affected assignments');
  await expect(page.locator('.repair-stages')).toContainText('Why scope widened: impact left 240 staff-minutes');
});

test('releasing a conflict inside an employee freeze preserves their other assignments', async ({ page }) => {
  const requests: Record<string, unknown>[] = [];
  await page.route('**/schedules/*/repair', async route => { requests.push(route.request().postDataJSON()); await route.fulfill({ status: 409, json: conflict.response.body }); });
  await start(page, true); await keepPerson(page);
  const repair = page.getByRole('button', { name: 'Start or check repair for this week', exact: true }); await repair.click();
  const warning = page.getByRole('region', { name: 'Run protection conflict', exact: true });
  await warning.getByRole('checkbox').check(); await warning.getByRole('button', { name: 'Remove selected run protections', exact: true }).click();
  expect(requests).toHaveLength(1);
  await expect(page.locator('.run-protection-controls > summary')).toHaveText(`Protect commitments for the next run (${theirs.length - 1})`);
  await repair.click(); await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].freeze).toEqual({ shift_ids: theirs.filter((id: string) => id !== target.logical_shift_id), employee_ids: [], days: [] });
  expect(requests[1].unlock_logical_shift_ids).toEqual([]);
});

test('generation sends one run-scoped freeze and shows the server-confirmed set', async ({ page }) => {
  let input: Record<string, unknown> | null = null; let writes = 0;
  await page.route('**/schedules/*/generate', async route => {
    input = route.request().postDataJSON(); writes += 1;
    // A terminal contract-shaped mock: this verifies transport and confirmation,
    // without fabricating a solver result for protected generation.
    await route.fulfill({ status: 202, json: { ...fixtures['generate.accepted'].response.body, job_state: 'cancelled', solver_status: null, poll_after_ms: null, base_version_ids: [base.id], frozen_logical_shift_ids: theirs } });
  });
  await start(page); await keepPerson(page); await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await expect(page.locator('.confirmed-protection > summary')).toHaveText(`Server-confirmed run protections (${theirs.length})`);
  expect(writes).toBe(1); expect(input).toMatchObject({ base_version_id: base.id, freeze: { shift_ids: [], employee_ids: [employee.id], days: [] } });
  await expect(page.locator('.run-protection-controls > summary')).toHaveText('Protect commitments for the next run (0)');
  await page.locator('.confirmed-protection > summary').click(); await expect(page.locator('.confirmed-protection')).toContainText(employee.name);
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
});

test('attaching to an existing run discloses a different confirmed protection set', async ({ page }) => {
  let writes = 0;
  await page.route('**/schedules/*/generate', async route => { writes += 1; await route.fulfill({ status: 409, json: fixtures['generate.run_in_progress'].response.body }); });
  await page.route('**/optimization-runs/*', async route => route.fulfill({ status: 200, json: { ...fixtures['generate.accepted'].response.body, job_state: 'cancelled', poll_after_ms: null, base_version_ids: [base.id], frozen_logical_shift_ids: [] } }));
  await start(page); await keepPerson(page); await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await expect(page.getByText(/This run has a different protection set from your request/)).toBeVisible();
  await expect(page.locator('.confirmed-protection > summary')).toHaveText('Server-confirmed run protections (0)'); expect(writes).toBe(1);
});

test('a changed published base requires reviewing protections again before repair', async ({ page }) => {
  let changed = false; let writes = 0;
  await page.route('**/outlets/*/schedules/2026-10-19', async route => { const headers = route.request().headers(); delete headers['if-none-match']; const response = await route.fetch({ headers }); const value = await response.json(); if (changed) value.current_version = { ...value.current_version, id: '00000000-0000-4000-8000-000000000004', version_number: 4 }; await route.fulfill({ response, json: value }); });
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/repair')) writes += 1; });
  await start(page, true); await keepPerson(page); changed = true;
  await page.getByRole('button', { name: 'Start or check repair for this week', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Reload records and review protections'); expect(writes).toBe(0);
  await page.getByRole('button', { name: 'Reload records', exact: true }).click();
  await expect(page.locator('.run-protection-controls > summary')).toHaveText('Protect commitments for the next run (0)');
  await expect(page.getByText(/The published base changed. Run protections were cleared/)).toBeVisible(); expect(writes).toBe(0);
});

test('a later explicit repair intent gets a fresh key after an accepted run', async ({ page }) => {
  const keys: string[] = [];
  const returned = { ...fixtures['repair.accepted'].response.body, job_state: 'cancelled', poll_after_ms: null, frozen_logical_shift_ids: theirs };
  await page.route('**/schedules/*/repair', async route => { keys.push(route.request().headers()['idempotency-key']); await route.fulfill({ status: 202, json: returned }); });
  await page.route('**/optimization-runs/*', async route => route.fulfill({ status: 200, json: returned }));
  await start(page, true); await keepPerson(page);
  const repair = page.getByRole('button', { name: 'Start or check repair for this week', exact: true });
  await repair.click(); await expect(page.locator('.confirmed-protection > summary')).toHaveText(`Server-confirmed run protections (${theirs.length})`);
  await page.getByRole('checkbox', { name: `Keep ${employee.name}’s published assignments`, exact: true }).check();
  await repair.click(); await expect.poll(() => keys.length).toBe(2);
  expect(keys[0]).toBeTruthy(); expect(keys[1]).not.toBe(keys[0]);
});

test('an uncertain repair response preserves the request key for an explicit retry', async ({ page }) => {
  const writes: { key?: string; body: unknown }[] = [];
  const returned = { ...fixtures['repair.accepted'].response.body, job_state: 'cancelled', poll_after_ms: null, frozen_logical_shift_ids: theirs };
  await page.route('**/schedules/*/repair', async route => {
    writes.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() });
    await route.fulfill(writes.length === 1 ? { status: 503, json: { error: { code: 'internal', message: 'Repair response unavailable', retryable: true, details: {} } } } : { status: 202, json: returned });
  });
  await page.route('**/optimization-runs/*', async route => route.fulfill({ status: 200, json: returned }));
  await start(page, true); await keepPerson(page);
  const repair = page.getByRole('button', { name: 'Start or check repair for this week', exact: true }); await repair.click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Repair response unavailable'); expect(writes).toHaveLength(1);
  await expect(page.getByRole('checkbox', { name: `Keep ${employee.name}’s published assignments`, exact: true })).toBeChecked();
  await repair.click(); await expect(page.locator('.confirmed-protection > summary')).toHaveText(`Server-confirmed run protections (${theirs.length})`);
  expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]);
});
