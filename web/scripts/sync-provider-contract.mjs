import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

// Read published contract data only. Never checkout, merge or execute provider code.
const root = path.resolve(import.meta.dirname, '../..');
const ref = process.argv[2];
if (!ref || !/^[a-f0-9]{7,40}$/.test(ref)) throw new Error('Supply the reviewed provider commit hash.');
const read = file => execFileSync('git', ['show', `${ref}:${file}`], { cwd: root, maxBuffer: 16 * 1024 * 1024 });
const commit = execFileSync('git', ['rev-parse', ref], { cwd: root, encoding: 'utf8' }).trim();
const index = JSON.parse(read('contracts/v2/fixtures/index.json'));
const files = ['openapi.json', 'fixtures/index.json', ...index.fixtures.map(entry => {
  if (!/^[a-z0-9_.-]+$/.test(entry.name)) throw new Error('Unexpected fixture name.');
  return `fixtures/${entry.name}.json`;
})];
const hashes = {};
for (const file of files) {
  const bytes = read(`contracts/v2/${file}`);
  const target = path.join(root, 'web/contracts/v2', file);
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, bytes);
  hashes[file] = createHash('sha256').update(bytes).digest('hex');
}
await writeFile(path.join(root, 'web/contracts/v2/SOURCE.json'), JSON.stringify({ repository: 'https://github.com/SaurabhTomar123/ShiftPilot', commit, contractVersion: index.contract_version, sha256: hashes }, null, 2) + '\n');
console.log(`Copied ${files.length} contract data files from ${commit}. Backend files were not changed.`);
