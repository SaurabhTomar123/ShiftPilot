# Web (Next.js chat + admin) — M2

Create the app here:

```bash
npx create-next-app@15 . --ts --tailwind --eslint --app --no-src-dir --use-npm
npx shadcn@latest init
```

Screens to build:
1. **Chat** (`/`): persona switcher (calls `POST /auth/demo-token`), outlet badge, 6 suggested prompts, streaming answer from `POST /chat/stream`, a **Show work** drawer listing each tool call (name, args, latency, ok), approval cards with Approve/Reject (`POST /actions/{id}/approve|reject`), Reset sandbox (owner).
2. **Approvals** (`/admin/approvals`): `GET /actions?status=pending|executed|rejected`.
3. **Evals** (`/admin/evals`): latest run summary, model comparison table, failures with drill-down.
4. **Audit log**, **Conversations**, **Import** (M6).

API base URL: `http://localhost:8000` (CORS already allows `http://localhost:3000`).
