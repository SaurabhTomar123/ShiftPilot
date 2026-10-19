import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function draft(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await page.getByRole('button', { name: 'Review option', exact: true }).first().click();
  await page.getByRole('button', { name: 'Select option and create draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toBeVisible();
}
async function propose(page: Page) {
  await draft(page);
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
}

test('review is read-only; selection and proposal creation carry explicit writes', async ({ page }) => {
  const writes: { path: string; key: string | undefined; body: unknown }[] = [];
  page.on('request', req => { if (req.method() === 'POST') writes.push({ path: new URL(req.url()).pathname, key: req.headers()['idempotency-key'], body: req.postDataJSON() }); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  await page.getByRole('button', { name: 'Review option', exact: true }).first().click();
  await expect(page.getByText('60', { exact: true }).first()).toBeVisible();
  expect(writes.filter(w => w.path.endsWith('/select'))).toHaveLength(0);
  await expect(page.getByRole('button', { name: 'Create proposal', exact: true })).toHaveCount(0);
  await page.getByText('Review assignment changes (60)', { exact: true }).click();
  await expect(page.getByRole('region', { name: 'Candidate assignment changes' }).getByRole('table')).toBeVisible();
  await page.getByRole('button', { name: 'Select option and create draft', exact: true }).click();
  await page.getByRole('button', { name: 'Create proposal', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toBeVisible();
  const select = writes.filter(w => w.path.endsWith('/select'));
  const proposals = writes.filter(w => w.path.endsWith('/proposals'));
  expect(select).toHaveLength(1); expect(select[0].key).toBeTruthy();
  expect(proposals).toHaveLength(1); expect(proposals[0].key).toBeTruthy();
  expect(proposals[0].body).toMatchObject({ expected_revision: 1 });
  expect(writes.filter(w => w.path.endsWith('/approve'))).toHaveLength(0);
});

test('publication waits for a server outcome and reloads the confirmed roster', async ({ page }) => {
  await propose(page);
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Published version 1');
  await expect(page.getByRole('status')).toContainText('synthetic preview');
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toHaveCount(0);
});

test('changed metrics require acknowledgment and a separate idempotent approval', async ({ page }) => {
  const approvals: { key: string | undefined; body: unknown }[] = [];
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/approve')) approvals.push({ key: req.headers()['idempotency-key'], body: req.postDataJSON() }); });
  await propose(page);
  await page.getByLabel('Approval demo outcome', { exact: true }).selectOption('changed');
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Changed: review the new metrics', exact: true })).toBeVisible();
  const table = page.getByRole('region', { name: 'Changed proposal metrics', exact: true });
  await expect(table).toContainText('74,700.00'); await expect(table).toContainText('78,435.00');
  const publish = page.getByRole('button', { name: 'Accept changes and publish', exact: true });
  await expect(publish).toBeDisabled(); expect(approvals).toHaveLength(1);
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toHaveCount(0);
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel('I reviewed and accept these metric changes', { exact: true }).check();
  await publish.click();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  expect(approvals).toHaveLength(2);
  expect(approvals.map(a => a.body)).toEqual([{ acknowledge_changes: false }, { acknowledge_changes: true }]);
  expect(approvals[0].key).toBeTruthy(); expect(approvals[1].key).not.toBe(approvals[0].key);
});

for (const outcome of ['stale', 'invalid'] as const) test(`${outcome} approval reports its reason and leaves the week unpublished`, async ({ page }) => {
  let writes = 0;
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/approve')) writes += 1; });
  await propose(page);
  await page.getByLabel('Approval demo outcome', { exact: true }).selectOption(outcome);
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('heading', { name: outcome === 'stale' ? 'Stale: review the latest week' : 'Invalid: scheduling rules now block this plan', exact: true })).toBeVisible();
  if (outcome === 'invalid') await expect(page.getByRole('region', { name: 'Proposal review' })).toContainText('confirmed absence');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
  expect(writes).toBe(1);
  await page.getByRole('button', { name: 'Reload latest week', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'A fresh week, ready to plan.', exact: true })).toBeVisible();
});

test('an uncertain approval can be retried explicitly with the same key', async ({ page }) => {
  await propose(page); const keys: string[] = []; let attempts = 0;
  await page.route('**/v2/proposals/*/approve', async route => {
    keys.push(route.request().headers()['idempotency-key']);
    if (++attempts === 1) {
      // The server commits; the caller loses the success response.
      await route.fetch();
      return route.fulfill({ status: 503, json: { error: { code: 'internal', message: 'Approval response unavailable.', retryable: true, details: {} } } });
    }
    return route.continue();
  });
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Approval response unavailable');
  expect(attempts).toBe(1);
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Approve and publish', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1]);
});

test('rejecting a proposal does not publish a schedule', async ({ page }) => {
  await propose(page);
  await page.getByRole('button', { name: 'Reject proposal', exact: true }).click();
  await expect(page.getByText('rejected', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve and publish', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toHaveCount(0);
});

test('a late candidate read cannot replace the newly selected week', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next week', exact: true }).click();
  await page.getByRole('button', { name: 'Generate draft', exact: true }).click();
  let release!: () => void;
  const paused = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/v2/optimization-candidates/*', async route => {
    const response = await route.fetch(); await paused;
    await route.fulfill({ response }).catch(() => {});
  });
  await page.getByRole('button', { name: 'Review option', exact: true }).first().click();
  await expect(page.getByRole('region', { name: 'Candidate review', exact: true }).getByRole('status')).toContainText('Loading option details');
  await page.getByRole('button', { name: 'Previous week', exact: true }).click(); release();
  await expect(page.getByRole('heading', { name: 'Published roster', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Candidate review', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Proposed roster', exact: true })).toHaveCount(0);
});
