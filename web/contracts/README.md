# Frontend provider contract snapshot

`v2/` contains data copied byte-for-byte from Claude's published contract at the commit recorded in `v2/SOURCE.json`. The UI owns its generated TypeScript client artifacts; the provider owns these schema/fixture contents. Do not hand-edit the snapshot or generated files.

This keeps frontend contract consumption independent of a backend source merge. The repository-root `contracts/v2` still describes the backend checked out in this branch; it is not the current frontend pin. No provider Python, migration, worker, deployment or configuration file is imported or executed by this workflow.

After reviewing a new provider contract:

```powershell
git fetch origin
node scripts/sync-provider-contract.mjs <reviewed-provider-commit>
npm run contracts:generate
npm run contracts:check
```

Run the commands from `web/`. Sync reads Git blobs for OpenAPI, the fixture index and the indexed fixture JSON only. `SOURCE.json` records the full commit and SHA-256 of each copied file. Generation/check verifies those hashes and the declared version before generating client types and the fixture registry. AJV validates every indexed response against the pinned OpenAPI schema.

The pin does not upgrade a running API. A live deployment must provide the accepted contract version for the corresponding features. The local backend/runtime remains a separate integration and acceptance step.
