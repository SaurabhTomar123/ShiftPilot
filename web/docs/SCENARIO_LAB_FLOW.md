# Scenario Lab consumer delivery

25 October 2026 delivery record. Current consumer pin is 3.27; the Scenario Lab behavior and remaining fixture/event-provenance boundaries below are unchanged. Architecture v4 governs. Codex owns the UI; Claude owns API, worker, engine and database implementation.

## Contract and runtime boundary

Frontend-only snapshot **3.20.0-p4 / 128 fixtures** from provider `b6e8ef68c57381d510c93b91fe77e5e9bcbce65f`. Aggregate SHA-256: `83b59dc653bf623c7f5f760ddcfb936e791f1183b5ac61ac6072ccc6a7174b31`. `web/contracts/v2/SOURCE.json` records per-file hashes; generation verifies provider bytes before emitting client artifacts. No provider source, dependency, migration, worker or database change is included.

Scenario Lab is a manager/owner destination scoped to the selected outlet, week and session. It requires scheduling access; conversion separately requires publication access. The source architecture file still matches SHA-256 `1c22563a3953d64faaf8e48cde0ab4c7f08955320415992c8e8d41ac3fd38216`.

## Delivered flow

1. Load saved what-ifs and the published base using reads only. Creating a scenario explicitly names it and submits its ordered hypothetical events. It starts from the provider's current published version, or an empty week.
2. Typed forms support person unavailability, staffing demand percentage by skill/day/window, outlet closure within the week, an exact-paise weekly labour cap, and the provider's two supported scheduling rules. Rule forms target a person and expose working-day or latest-finish parameters. No free-form solver instruction or raw JSON input is used. Caps require cost visibility.
3. Local unsaved events can be removed. Saved events are append-only because no delete/reorder API is declared. Events never call real absence, availability, staffing or rule write endpoints. Demand scales both required and preferred staffing; rules remain hypothetical. Dates/times use the outlet timezone and ambiguous local times are rejected.
4. Run what-if admits a `kind: scenario` job with a stable key and bounded, cancellable read polling. Status failures retain the workspace and run ID. Check simulation status sends reads only. Existing runs may be attached without another solve write; identity must match the scenario, outlet and base.
5. A completed run compares candidate metrics against `Scenario.baseline` only when its run ID matches. This baseline is the original roster evaluated under the same hypothetical facts, not recorded published scores. Missing baseline values stay unavailable. Employee explanations and deltas are labelled as hypothetical; engine order and portfolio facts are retained without browser ranking. Costs are hidden in comparisons, cap details and employee evidence when permission is absent.
6. Turn this into a plan calls the scenario conversion endpoint, never normal candidate selection. It revalidates current real facts and returns a normal scenario-origin draft. The UI checks source, status, schedule and base identity. Current-fact conflicts or stale versions leave the workspace intact without success claims. No hypothetical facts are applied as operational facts.
7. A conversion response lost in transit can be checked with a read or explicitly retried with its original key/candidate. Other conversion choices remain blocked while the result is uncertain. Confirmed drafts enter the existing proposal/revalidation/approval flow; conversion does not publish.
8. Discard requires an explicit decision. Closed/expired/converted workspaces cannot add events or run again. Converted versions can be reopened for review; already published versions do not reopen as editable drafts.

Create, add-event and discard have no declared idempotency promise. An unconfirmed response blocks further workspace writes until saved records are reloaded and reviewed; no automatic retry occurs. Scope changes abort obsolete reads and polling, clear the active screen and retain the API's session privacy boundary.

## Event revision gap and conservative resume behavior

The provider stores event IDs in the run's internal configuration, but its public OptimizationRun/ScenarioBaseline does not return that set or an event revision. Events can be appended while older results still exist. The browser therefore cannot establish that a resumed/attached run evaluated the displayed events.

The UI keeps such results unavailable for comparison/conversion until a fresh run is explicitly admitted during the visit. Appending an event clears prior choices. If events differ after polling, those choices are invalidated again. This is a conservative consumer boundary, not an inferred guarantee about old results.

Provider follow-up: expose the run's ordered event IDs/revision and enforce matching-current-event semantics for conversion. In the reviewed source, conversion checks candidate scenario ownership and current real facts but does not visibly fence the candidate to the latest run/current event set. Please add old-run/changed-event/current-base acceptance examples. The UI does not treat this source inspection as a live security or solver reproduction.

## Synthetic coverage and remaining acceptance

Provider fixtures cover scenario creation, adding the Saturday demand example, listing/getting, queued admission, conversion, conversion-assumption conflict, discard and refusal of ordinary candidate selection. The preview preserves provider identities and joins a converted draft to the same synthetic proposal state, including candidate ID and base. Scenario state is bounded, expiring and scoped by persona/session.

No completed scenario run or detailed scenario candidate fixture is supplied in this pin. The preview returns an explicit unsupported error for that status read; it never substitutes the ordinary generation or repair run. Users can still create/save events, inspect records, admit the supplied job and recover its status. A complete simulated comparison in default preview awaits matching provider records.

The browser suite supplies clearly labelled local terminal-run responses to test consumer comparison/conversion behavior; conversion/draft/proposal fixtures remain provider records. Tests cover the exact scenario route, explicit approval, no operational event writes, lost response/key reuse, current-fact conflict, cost redaction, discard, unconfirmed create and resumed-event guards. These mocks are not live engine acceptance. Typed payload and response-schema tests also cover all 128 provider fixtures.

Verified for this slice: **196 unit/contract tests**, **20 new desktop/phone browser checks**, production build and lint. The full shared regression is checked before the feature push. Local screenshots are ignored under `.impeccable/review/`.

Live 3.20 API/worker/tenant/isolation acceptance remains open. Earlier real API checks describe the reviewed 3.3 runtime only. Backend integration remains a separate reviewed milestone.

## Next consumer work

- Completed 26 October: accepted the fairness correction and replacement-edit fixtures in the frontend-only 3.27 snapshot. The supplied cover story now completes validation and save. SSE/P1 schema availability does not close their UI/runtime acceptance.
- Add completed scenario run/detail/expiry/stale-base and event-revision fixtures for coherent preview and acceptance coverage.
- Continue the remaining template/import/rule and P1 demand/employee request UI against their published contracts. SSE consumption is separate; durable reads and bounded polling remain the current behavior.
