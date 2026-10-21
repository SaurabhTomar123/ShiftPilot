# Protect commitments for one run

Architecture v4 sections 13 and 15; frontend contract **3.15.0-p4**, provider commit `03d747cc0cc4b67fccaed8489abbb0d53cd741b4`.

Schedule and Repair Inbox expose protection controls only when a published base exists. A manager can select logical shift IDs, employees or outlet-local days. The whole-outlet shortcut selects every logical shift ID in that outlet's displayed published version; no unsupported outlet-freeze field is invented. Open assignments can also be protected.

Selections are a local request preview. Their union counts each assignment once, using the outlet timezone and the shift's local start day. Choosing employee/day protection continues to cover a shift even if its individual checkbox is unchecked. The controls explain this explicitly. Only the server resolves eligibility, conflicts and the actual freeze set.

Generate and explicit repair send the chosen `freeze` with their reviewed published base. Empty choices omit the field. Repair reloads the current published version before writing; if protection was reviewed against a different version, it refuses the write and asks for a record reload. A changed base clears the old choices. Week/outlet/persona changes unmount their scope.

An admitted/attached run clears the next-run input. `frozen_logical_shift_ids` displays the server-confirmed explicit set, with assignment names/times when its baseline is known. A different set, including an existing active run's set, gets a visible notice. Missing provider fields are reported as missing, not asserted to mean zero. Automatic impact-stage freezes are distinguished from explicit protections.

`409 conflict` with `details.frozen_logical_shift_ids` keeps the request visible. The manager checks the specific assignments they authorize to remove, then explicitly removes those run protections. The remaining selected assignments are preserved as individual pins, even when an employee/day originally selected them. This sends no write. Starting the revised run is a separate action with its revised payload. Accepted repair requests retire their key so a later explicit intent can start a new run. Uncertain responses retain the same key and unchanged inputs for an explicit retry, with no automatic write retry. Permanent lock authorization remains independent; releasing a run protection never unlocks a shift or cancels an absence.

Repair stages display the provider's `impact`, `released` and `widened_because` values. The UI does not compute or claim to reproduce the Impact Analyzer. Expired candidate results have explicit recovery copy rather than a misleading ready message.

## Synthetic and runtime boundaries

The snapshot provides a matching individual-pin conflict fixture. Other protected solver requests have no successful fixture and return an explicit unsupported result; the gateway never substitutes an unprotected success. Browser tests additionally use declared-shape mocks for transport, stale-base and existing-run branches. These are not solver acceptance evidence.

The attempted broad backend merge was rejected by automatic approval review because it would introduce unreviewed backend files and dependencies. The safer delivery copies contract data under `web/` only. No backend source, migrations, databases, API or worker services were changed. Live 3.15 pin-preservation and impact-quality verification remains pending provider runtime integration; earlier live 3.3 checks do not establish it.

## Verification ? 21 October 2026

The production build (including TypeScript), lint, 161 unit/contract tests and all 108 pinned fixture/hash checks pass. The full desktop/phone suite passed 134 cases (3.5 minutes). After the accepted-request key lifecycle correction, the final build and all 48 affected absence/protection/proposal cases passed (1.5 minutes), including four added accepted/uncertain-response cases. Together these runs verify all 138 distinct browser cases. Tests cover union preview, local-day semantics, explicit conflict release, preservation of other pins, stale-base reload, existing-run mismatch, one-run reset, scope cancellation, unchanged request replay after an uncertain response, and a fresh key for a later accepted request. Expanded controls pass axe and viewport checks. Desktop and phone protection/conflict captures were inspected.

No live 3.15 engine, migration, pin-preservation, Impact Analyzer quality or cross-tenant release acceptance is claimed by these frontend checks.
