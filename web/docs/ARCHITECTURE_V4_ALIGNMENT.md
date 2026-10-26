# Architecture v4: UI alignment and delivery order

Revision 4, dated 21 October 2026, supersedes v3 as the target architecture. Source: the user-provided `docs/ShiftPilot_Architecture_v4.docx` in the main checkout. Source SHA-256: `1c22563a3953d64faaf8e48cde0ab4c7f08955320415992c8e8d41ac3fd38216`. Previous v3 notes remain historical. Codex owns all frontend work; Claude owns the database, engine, worker and API contracts.

The product is a **Workforce Decision & Recovery Engine**. Schedule stays the main surface. The next investment is decision quality and safe recovery, followed by Scenario Lab. Forecasting and external integrations are not the first milestone.

## Implemented foundation

| v4 area | Current consumer behavior | Remaining work |
| --- | --- | --- |
| Schedule | Published roster, manual draft edits, assignment locks, validation, candidate selection, proposals | Run-scoped pins, employee/day protection, whole-outlet shift selection and requested-scope preview delivered; engine quality acceptance pending |
| Repair Inbox | Weekly saved absences, explicit status decisions, automatic repair tracking, lock authorization, widening and returned reasons | Direct replacement ranking delivered; durable trigger inbox and more trigger types remain |
| Plan Compare | Side-by-side returned plans: coverage, minimum shortfall, cost, changed commitments, overtime, transfers, open shifts and validation | Portfolio policy, exclusion reasons, burden components and trace/taxonomy delivered; live engine acceptance pending |
| Scenario Lab | Isolated event forms, simulation status/comparison and current-fact conversion delivered | Completed-run/detail fixtures, event-revision provenance and live isolation/engine acceptance |
| Employees / Demand / History | Employee/availability, dated staffing, recurring templates with explicit expansion, history and restore remain usable | Burden summary, forecast acceptance and employee request loop |
| Scheduling rules | Typed rule definition, scope/role gates, impact/conflict preview, explicit exceptions, keyed save and archive decisions | Successful exception/broader-scope fixtures, optional parsing and live acceptance |
| Approval | Selection creates draft; explicit proposal approval revalidates current facts | New origins must enter this same flow; no parallel publication path |

Plan Compare includes recorded metrics only when the displayed baseline ID belongs to the run. Engine deltas use their own declared reference (`base_version` or `requested_plan`); the browser never subtracts historical recorded metrics to manufacture engine deltas. Historical fairness burden and this-week component points have distinct labels. Preference match remains separate. No browser-side Pareto filtering or invented recommendation is applied.

The frontend consumes OpenAPI **3.27.0-p4 / 164 fixtures**, from a byte-preserved contract-only snapshot of provider `9d176a31cd7a3786e1f9f1cfc6a3d401fa4558ea`. This includes Scenario Lab alongside replacement, portfolio, fairness, trace and protection contracts. Backend source and runtime were not upgraded by the snapshot; live 3.27 acceptance remains pending. The pin includes the replacement-save fixtures and fairness correction, now consumed. Other P1 and SSE schema data are available provider work awaiting separate UI/runtime integration, not missing backend implementation. See [decision delivery evidence](DECISION_REVIEW_FLOW.md).

## P0 delivery order and ownership

1. **Repair foundation and comparison: delivered.** Saved facts survive repair failure; matching repair-detail/select fixtures now enter the normal draft/proposal path. Requested-record status fixtures exist; preview-gateway integration remains separate.
2. **Impact protection and portfolio: delivered in the consumer.** Run-scoped controls, explicit release, impact-stage rendering, portfolio policy and supplied duplicate/guardrail/dominance/limit reasons are visible. Permanent locks remain separate. The request preview is not authoritative impact or eligibility calculation. See RUN_PROTECTION_FLOW.md and DECISION_REVIEW_FLOW.md; live engine acceptance remains open.
3. **Fairness and decision trace: delivered in the consumer.** Rolling burden imbalance is separate from weekly closing/weekend/split/overtime points. Policy 1 does not include transfer/last-minute burden. Trace uses KEPT, MOVED_TIME, REASSIGNED, CREATED, REMOVED and UNFILLED; non-selection alone is not rejection. Returned provenance, truncated evidence and cost visibility are preserved. The earlier fairness-delta inconsistency is corrected and consumed; the consistency guard remains active.
4. **Replacement recommendations: delivered in the consumer.** Find cover in Schedule and Repair Inbox shows provider-ranked direct replacements, incremental impact and rule-backed exclusions. Choosing prepares a draft and previews the returned edit; explicit save enters the existing proposal flow. The supplied Chitra validation/save/proposal story works in preview; other synthetic edits and live acceptance remain pending; see REPLACEMENT_FLOW.md. No frontend eligibility inference or direct reassignment.
5. **Scenario Lab: delivered in the consumer.** Title/baseline, typed event forms, isolated run status, simulated-baseline comparison and Turn this into a plan are integrated against the published slice. Missing completed-run/detail fixtures remain explicit preview errors. See SCENARIO_LAB_FLOW.md. Explicit server conversion rebuilds against current real facts, followed by normal draft review/approval. Switching scope cancels obsolete reads; uncertain conversion uses its stable key.

Typed scheduling rules are integrated; see RULES_FLOW.md for fresh-preview, explicit-exception and interrupted-write behavior. Recurring staffing templates and reviewed dated expansion are also integrated; see STAFFING_TEMPLATE_FLOW.md for fixture boundaries and revision semantics. Remaining P0 acceptance work does not depend on forecasting. Each contract slice needs its own fixture, consumer and live acceptance checks.

## Provider acceptance checklist for v4

The published provider work is reviewed in bounded slices. These semantics must be checked against concrete OpenAPI types and request/response/error fixtures before each remaining integration; this list is not a claim that the newer provider is missing them:

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
