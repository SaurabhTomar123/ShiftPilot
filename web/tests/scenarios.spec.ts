import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const fixtures = JSON.parse(readFileSync(new URL('../src/api/generated/fixtures.json', import.meta.url), 'utf8'));
const scenario = fixtures['scenario.get'].response.body;
const candidateId = fixtures['scenario.convert'].request.body.candidate_id;
const completed = structuredClone(fixtures['scenario.run.accepted'].response.body);
completed.job_state = 'succeeded'; completed.solver_status = 'OPTIMAL'; completed.poll_after_ms = null;
const choice = structuredClone(fixtures['run.repair.widened'].response.body.candidates[0]);
choice.id = candidateId; choice.strategy = 'balanced'; choice.metrics = fixtures['scenario.convert'].response.body.metrics;
completed.candidates = [choice];

async function navigate(page: Page) {
  await page.goto('/'); await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true }); if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('button', { name: 'Scenario Lab', exact: true }).click();
  return page.getByRole('region', { name: 'Scenario Lab workspace', exact: true });
}
async function create(page: Page) {
  const lab = await navigate(page); await lab.getByRole('button', { name: 'Load Wednesday absence example', exact: true }).click();
  await lab.getByRole('button', { name: 'Create what-if', exact: true }).click();
  await expect(lab.getByRole('region', { name: 'Selected what-if' })).toBeVisible();
  return lab;
}
async function run(page: Page) {
  // Local consumer test response: the provider has not supplied a completed-scenario-run fixture.
  await page.route(`**/v2/optimization-runs/${completed.id}`, route => route.fulfill({ json: completed }));
  const lab = await create(page);
  await lab.getByRole('button', { name: 'Add Saturday evening example' }).click();
  await lab.getByRole('button', { name: 'Run what-if', exact: true }).click();
  await expect(lab.getByRole('region', { name: 'What-if comparison' })).toBeVisible();
  await lab.getByRole('radio').first().check(); return lab;
}

test('Scenario Lab entry is read-only, clearly hypothetical, accessible and fits phones', async ({ page }) => {
  const posts: string[] = []; page.on('request', request => { if (request.method() === 'POST') posts.push(request.url()); });
  const lab = await navigate(page);
  await expect(lab.getByText('What-if workspace', { exact: true })).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Create what-if' })).toBeDisabled();
  expect(posts.filter(url => !url.endsWith('/session/demo'))).toEqual([]);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/scenario-entry-${test.info().project.name}.png`, fullPage: true });
});

test('saving hypothetical events calls no operational absence, staffing, generation or publication endpoint', async ({ page }) => {
  const writes: string[] = []; page.on('request', request => { if (['POST', 'PUT', 'PATCH'].includes(request.method())) writes.push(new URL(request.url()).pathname); });
  const lab = await create(page); await lab.getByRole('button', { name: 'Add Saturday evening example', exact: true }).click();
  await expect(lab.getByText('+30% staffing', { exact: false })).toBeVisible();
  expect(writes.filter(path => !path.endsWith('/session/demo'))).toEqual([`/api/fixture/v2/outlets/${scenario.outlet_id}/schedules/${scenario.week_start}/scenarios`, `/api/fixture/v2/scenarios/${scenario.id}/events`]);
  await lab.getByRole('button', { name: 'Run what-if', exact: true }).click();
  await expect(lab.getByText('A completed scenario run and candidate detail require a connected API.', { exact: false }).first()).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Turn this into a plan' })).toHaveCount(0);
  expect(writes.filter(path => path.endsWith('/run'))).toHaveLength(1);
  await lab.getByRole('button', { name: 'Check simulation status' }).click();
  await expect(lab.getByRole('button', { name: 'Check simulation status' })).toBeEnabled();
  expect(writes.filter(path => path.endsWith('/run'))).toHaveLength(1);
});

test('typed event forms retain meaningful rule details and exact-paise cap inputs', async ({ page }) => {
  const lab = await navigate(page);
  await lab.getByLabel('What would change?').selectOption('rule');
  await lab.getByLabel('Maximum working days').fill('4');
  await lab.getByRole('button', { name: 'Add hypothetical change' }).click();
  await expect(lab.getByText('maximum 4 working days', { exact: false })).toBeVisible();
  await lab.getByLabel('What would change?').selectOption('labour_cap');
  await lab.getByLabel('Maximum weekly labour cost (INR)').fill('1192.50');
  await lab.getByRole('button', { name: 'Add hypothetical change' }).click();
  await expect(lab.getByText('Weekly cap ₹1,192.50.', { exact: false })).toBeVisible();
});

test('simulated baseline is evaluated under assumptions and conversion enters separate approval', async ({ page }) => {
  const writes: string[] = []; page.on('request', request => { if (request.method() === 'POST') writes.push(new URL(request.url()).pathname); });
  const lab = await run(page);
  await expect(lab.getByRole('heading', { name: 'The original plan under these assumptions' })).toBeVisible();
  await expect(lab.getByText('These are simulated results, not recorded published metrics.', { exact: false })).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Create proposal' })).toHaveCount(0);
  await lab.getByRole('button', { name: 'Turn this into a plan', exact: true }).click();
  await expect(lab.getByRole('region', { name: 'Scenario draft review' })).toBeVisible();
  await lab.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await expect(lab.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
  expect(writes.filter(path => path.endsWith('/approve'))).toEqual([]);
  expect(writes.filter(path => path.endsWith('/select'))).toEqual([]);
  await lab.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(lab.getByText('Publication confirmed by the server.', { exact: false })).toBeVisible();
  await page.screenshot({ path: `.impeccable/review/scenario-converted-${test.info().project.name}.png`, fullPage: true });
});

test('conversion blocked by current real facts leaves the hypothetical workspace open', async ({ page }) => {
  const lab = await run(page);
  await page.route('**/v2/scenarios/*/convert', route => route.fulfill({ status: 409, json: fixtures['scenario.convert.assumptions'].response.body }));
  await lab.getByRole('button', { name: 'Turn this into a plan', exact: true }).click();
  await expect(lab.getByText('current facts break it.', { exact: false })).toBeVisible();
  await expect(lab.getByRole('region', { name: 'Scenario draft review' })).toHaveCount(0);
  await expect(lab.getByRole('button', { name: 'Turn this into a plan', exact: true })).toBeEnabled();
});

test('lost conversion response retries only explicitly with its original key', async ({ page }) => {
  const lab = await run(page); const keys: string[] = [];
  await page.route('**/v2/scenarios/*/convert', async route => { keys.push(route.request().headers()['idempotency-key']); if (keys.length === 1) { await route.fetch(); await route.abort('failed'); } else await route.continue(); });
  await lab.getByRole('button', { name: 'Turn this into a plan', exact: true }).click();
  await expect(lab.getByRole('button', { name: 'Retry same conversion', exact: true })).toBeVisible();
  expect(keys).toHaveLength(1);
  await lab.getByRole('button', { name: 'Retry same conversion', exact: true }).click();
  await expect(lab.getByRole('region', { name: 'Scenario draft review' })).toBeVisible();
  expect(keys).toHaveLength(2); expect(keys[0]).toBeTruthy(); expect(keys[1]).toBe(keys[0]);
});

test('cost restrictions apply to simulation comparison, caps and employee evidence', async ({ page }) => {
  await page.route('**/v2/session/demo', async route => { const response = await route.fetch(); const body = await response.json(); body.me.capabilities = body.me.capabilities.filter((value: string) => value !== 'view_costs'); await route.fulfill({ response, json: body }); });
  const lab = await run(page);
  await expect(lab.getByLabel('What would change?').locator('option[value="labour_cap"]')).toHaveCount(0);
  await lab.getByRole('region', { name: 'Simulated option review' }).getByText('Why this plan?', { exact: true }).click();
  await expect(lab).not.toContainText('₹'); await expect(lab).not.toContainText('INR');
});

test('discard is explicit and closed scenarios do not offer run or conversion writes', async ({ page }) => {
  const lab = await create(page);
  await lab.getByRole('button', { name: 'Discard what-if', exact: true }).click();
  await expect(lab.getByRole('button', { name: 'Confirm discard what-if' })).toBeVisible();
  await lab.getByRole('button', { name: 'Confirm discard what-if' }).click();
  await expect(lab.getByText('Status: discarded.', { exact: false })).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Run what-if', exact: true })).toHaveCount(0);
});

test('unconfirmed create never auto-retries and requires reloading saved records', async ({ page }) => {
  let writes = 0;
  await page.route('**/v2/outlets/*/schedules/*/scenarios', route => { writes++; return route.abort('failed'); });
  const lab = await navigate(page); await lab.getByRole('button', { name: 'Load Wednesday absence example' }).click();
  await lab.getByRole('button', { name: 'Create what-if', exact: true }).click();
  await expect(lab.getByText('A scenario write was not confirmed.', { exact: false })).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Create what-if', exact: true })).toBeDisabled(); expect(writes).toBe(1);
});

test('saved results with unverified event revisions cannot be converted after resume', async ({ page }) => {
  await page.route(`**/v2/optimization-runs/${completed.id}`, route => route.fulfill({ json: completed }));
  const lab = await navigate(page);
  await lab.getByRole('button', { name: `Open ${scenario.title}`, exact: true }).click();
  await expect(lab.getByText('The event revision for these saved results is not confirmed.', { exact: false })).toBeVisible();
  await expect(lab.getByRole('button', { name: 'Turn this into a plan' })).toHaveCount(0);
});
