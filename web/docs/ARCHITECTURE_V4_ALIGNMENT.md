# Architecture v4: UI alignment and delivery order

Revision 4, dated 21 October 2026, supersedes v3 as the target architecture. Source: the user-provided `docs/ShiftPilot_Architecture_v4.docx` in the main checkout. Source SHA-256: `1c22563a3953d64faaf8e48cde0ab4c7f08955320415992c8e8d41ac3fd38216`. Previous v3 notes remain historical. Codex owns all frontend work; Claude owns the database, engine, worker and API contracts.

The product is a **Workforce Decision & Recovery Engine**. Schedule stays the main surface. The next investment is decision quality and safe recovery, followed by Scenario Lab. Forecasting and external integrations are not the first milestone.

## Implemented foundation

| v4 area | Current consumer behavior | Remaining work |
| --- | --- | --- |
| Schedule | Published roster, manual draft edits, assignment locks, validation, candidate selection, proposals | Run-scoped pins, employee/day protection, whole-outlet shift selection and requested-scope preview delivered; engine quality acceptance pending |
| Repair Inbox | Weekly saved absences, explicit status decisions, automatic repair tracking, lock authorization, widening and returned reasons | Durable trigger inbox and recommendation ranking; more trigger types |
| Plan Compare | Side-by-side returned plans: coverage, minimum shortfall, cost, changed commitments, overtime, transfers, open shifts and validation | Engine portfolio/dominance metadata, burden metrics, full trace and taxonomy |
| Scenario Lab | Design and safety contract specified below; no operational form masquerading as simulation | Isolated scenario create/events/run/compare/convert APIs and fixtures |
| Employees / Demand / History | Existing employee/availability, manual staffing, history and restore workflows remain usable | Burden summary, forecast acceptance and employee request loop |
| Approval | Selection creates draft; explicit proposal approval revalidates current facts | New origins must enter this same flow; no parallel publication path |

Plan Compare uses **recorded** metrics only when the displayed baseline ID belongs to the run. It labels this reference explicitly. No matching baseline means no computed baseline deltas. Fairness burden is shown as not reported; preference match and target-hours alignment are never relabelled as fairness. No browser-side Pareto filtering or invented recommendation is applied.

The current frontend consumes OpenAPI **3.15.0-p4**, 108 fixtures, from a byte-preserved contract-only snapshot of provider `03d747c`. It declares `FreezeSpec`, generate/repair freeze inputs, server-confirmed protection IDs and an `impact` repair stage. No dedicated freeze endpoint is required. Scenario/replacement routes and fairness/portfolio/decision-trace schemas remain unavailable in this pin. Backend source and the running API were not upgraded by the snapshot; live 3.15 acceptance is pending. Newer v3 APIs exist; this is not a claim that those integrations are missing from Claude's implementation. The architecture's endpoint examples are target designs, not an already accepted executable contract.

## P0 delivery order and ownership

1. **Repair foundation and comparison — this delivery.** Codex builds the operational inbox and comparative UI on the reviewed contract, preserves saved facts on failure, and uses the normal proposal path. Claude supplies matching repair-detail/select and status-transition fixtures for complete synthetic coverage.
2. **Impact protection and portfolio.** Run-scoped controls, explicit release and impact-stage rendering are delivered against 3.15; see RUN_PROTECTION_FLOW.md. The request preview is not an authoritative impact or eligibility calculation. Portfolio/guardrail metadata and richer impact provenance remain pending. Claude supplies impact scope, frozen assignments, release/conflict records, explicit pin inputs, guardrails and portfolio metadata. Codex builds shift/employee/day/outlet protection controls, an impact preview and up to three engine-selected alternatives. Persisted shift locks and run-scoped freezes must be visually distinct. A hard fact conflicting with a pin requires explicit authorization.
3. **Fairness and decision trace.** Claude implements the rolling historical burden model and returns baseline/candidate/delta plus component contributions and policy revision. Codex displays fairness burden, closing/weekend/split/overtime/transfer/last-minute changes and provenance. Trace uses KEPT, MOVED_TIME, REASSIGNED, CREATED, REMOVED and OPEN/UNFILLED. Non-selection alone is never a rejection reason. Bounded counterfactual results must be labelled.
4. **Replacement recommendations.** Claude returns feasible replacements, ranking/profile, incremental impact and rule-backed exclusion reasons. Codex adds Find cover to affected assignments and routes a selected result through a draft/proposal. No frontend eligibility inference or direct reassignment.
5. **Scenario Lab.** Claude implements overlay-only storage, run admission, comparison, expiry and current-fact conversion. Codex builds scenario title/baseline, event editor, isolated run status, baseline comparison and Turn this into a plan. Conversion is an explicit server action followed by normal draft review and approval. Switching scope cancels obsolete reads; a lost conversion response is recovered using its stable key.

Steps 2–5 can be implemented in UI as soon as their individual contracts are accepted. They do not require forecasting to be completed first.

## Required provider handoff for v4

These are required semantics, not invented field names to send today. Claude should publish concrete OpenAPI types and request/response/error fixtures before integration:

- Run identity, snapshot/base/fact/policy revisions, impact scope, freeze set, conflicting protections, authorized releases and stage provenance.
- Portfolio strategy, assignment-diff identity, deduplication/dominance result, guardrails, recommendation rationale and valid plan limit. Do not rename an existing profile into a fairness strategy without a real fairness solve.
- Baseline and candidate metric vectors with clear units/direction, burden components, current versus recorded evaluation basis, and visibility/redaction rules.
- Typed trace/change taxonomy and constraint IDs, with bounded alternative facts and explanation provenance.
- Scenario lifecycle, supported event types/scopes, isolated overlay payloads, run/comparison reads, stale/expired handling and conversion result. Conversion must rebuild against current real facts; it must not commit hypothetical absences or demand as real facts.
- Replacement eligibility/ranking and its materialization into the existing proposal workflow.
- Permission, stale-base, hard-invalid, locked/frozen conflict, infeasible, timeout, worker failure, idempotent replay and cross-tenant denial examples for each mutation.

## P1 and P2

After P0, Codex builds employee absence status, eligible open shifts, consented swaps/giveaways, availability-change requests and notifications against Claude's request contracts. Accepted requests become normal proposals. Demand adds imported observations, advisory forecast confidence, explicit labour-model mapping, proposal acceptance and preserved manual overrides. SSE supplements durable GET status and falls back to bounded polling.

P2 integrations, service accounts, quotas, entitlements and metering stay outside solver correctness. Payroll, HRIS and autonomous publication remain out of scope.

## Acceptance boundaries

- A confirmed absence persists when repair fails. Repair admission is independent of batch generation.
- Protected assignments stay fixed unless the relevant release is explicitly authorized; facts and safety constraints cannot be relaxed.
- Engine-selected plans obey guardrails and are deduplicated/non-dominated by the provider. UI shows the supplied facts and uncertainty.
- Fairness uses historical burden, not protected attributes or a renamed preference metric.
- Creating, running or discarding a scenario cannot write operational absences, availability, rules, staffing requirements or published schedules. This requires backend isolation tests as well as UI request assertions.
- Conversion, repair, manual edits and employee requests all enter the same current-fact validation and publication transaction.
- Cross-tenant, deployment, full v4 engine and release acceptance remain open until verified; this frontend slice does not close them.
