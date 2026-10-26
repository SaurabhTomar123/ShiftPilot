import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import openapiTS, { astToString } from 'openapi-typescript';

const root = path.resolve(import.meta.dirname, '../..');
const contract = path.join(root, 'web/contracts/v2');
const target = path.resolve(import.meta.dirname, '../src/api/generated');
const source = await readFile(path.join(contract, 'openapi.json'), 'utf8');
const indexSource = await readFile(path.join(contract, 'fixtures/index.json'), 'utf8');
const index = JSON.parse(indexSource);
const hash = createHash('sha256').update(source).update(indexSource);
const provenance = JSON.parse(await readFile(path.join(contract, 'SOURCE.json'), 'utf8'));
if (provenance.contractVersion !== index.contract_version) throw new Error('Provider version does not match its provenance.');
for (const [file, expected] of Object.entries(provenance.sha256)) {
  const actual = createHash('sha256').update(await readFile(path.join(contract, file))).digest('hex');
  if (actual !== expected) throw new Error(`Provider snapshot changed: ${file}. Re-sync from a reviewed commit.`);
}
const fixtures = {};
for (const entry of index.fixtures) {
  const content = await readFile(path.join(contract, 'fixtures', `${entry.name}.json`), 'utf8');
  hash.update(content);
  fixtures[entry.name] = JSON.parse(content);
}
const files = {
  'schema.d.ts': astToString(await openapiTS(JSON.parse(source))),
  'fixtures.json': JSON.stringify(fixtures, null, 2) + '\n',
  'edit-examples.json': JSON.stringify({ invalidReassignment: fixtures['edits.preview'].request.body, openingLock: fixtures['edits.apply'].request.body, cover: fixtures['edits.preview.cover'].request.body, coverConflict: fixtures['edits.preview.cover.conflict'].request.body }, null, 2) + '\n',
  'scenario-examples.json': JSON.stringify({ create: fixtures['scenario.create'].request.body, event: fixtures['scenario.event.add'].request.body }, null, 2) + '\n',
  'staffing-template-examples.json': JSON.stringify(fixtures['staffing_templates.put'].request.body, null, 2) + '\n',
  'manifest.json': JSON.stringify({ version: index.contract_version, providerCommit: provenance.commit, sha256: hash.digest('hex'), fixtureCount: index.fixtures.length }, null, 2) + '\n',
};
await mkdir(target, { recursive: true });
for (const [name, value] of Object.entries(files)) {
  const filename = path.join(target, name);
  if (process.argv.includes('--check')) {
    if (await readFile(filename, 'utf8').catch(() => '') !== value) throw new Error(`${name} has drifted. Run npm run contracts:generate.`);
  } else await writeFile(filename, value);
}
console.log(`${index.contract_version}: ${index.fixtures.length} fixtures ${process.argv.includes('--check') ? 'verified' : 'generated'}.`);
