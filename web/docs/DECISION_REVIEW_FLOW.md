# Portfolio, fairness and decision review

Delivered 24 October 2026 against architecture v4. Codex owns this consumer UI; database, engine and API implementation remain Claude's scope.

## Contract and runtime boundary

Frontend pin: **3.18.0-p4 / 115 fixtures**, provider commit `5d93779f6a51a823db9b3d376f68e9feaa22fe96`, aggregate SHA-256 `ceca5f12379c3c4d8fea346a3f5c6867edff1dc787bd0e8099f2c57519a9906e`. Source bytes and per-file hashes are recorded in `web/contracts/v2/SOURCE.json`. No provider implementation, migration, worker or dependency was merged or executed. Previous live API evidence refers to the earlier reviewed 3.3 runtime; live 3.18 solver/tenant/release acceptance remains pending.

## Review behavior

- The decision profile is an explicit generation input: Balanced, Stability, Lowest cost, Employee fairness, Maximum coverage or Hours preference alignment. Stability needs a published base. The fixed preview only supports its supplied Balanced solve and explains unsupported profiles rather than relabelling the result.
- Plan Compare keeps engine order. Its portfolio disclosure shows the considered profiles, policy and supplied duplicate, guardrail, dominated or limit reasons. The browser does not rank, deduplicate, score or recommend plans.
- Recorded published metrics have their own column only for a matching base ID. Each engine delta names its reference: published base, requested plan or no reported reference. The browser does not derive engine deltas by subtracting frozen historical scores.
- Fairness burden covers the last eight published weeks plus this week, normalized by regular capacity. Lower imbalance is fairer. Weekly closing/weekend/split/overtime component points are distinct from historical imbalance and employee preferences. Policy 1 excludes transfer and last-minute burden. Missing legacy values stay unreported.
- Why this plan shows KEPT, MOVED_TIME, REASSIGNED, CREATED, REMOVED and UNFILLED counts, returned assignment changes, employee facts, alternative-person facts and supplied rule/absence references. An eligible alternative is not described as rejected. Truncated explanations disclose the provider's 30-shift bound.
- Cost permissions apply to headline metrics, deltas, portfolio reasons and incremental-cost facts inside both repair summary and candidate detail. Returned messages render as escaped text.

## Repair selection and approval

The preview now consumes the matching repair detail/select records. Selecting the repair option creates a repair-origin draft with the correct candidate ID and published base. Proposal creation preserves that identity; only explicit approval publishes within the synthetic session. Reviewing facts, selecting a profile or opening a disclosure does not publish.

Requested-absence confirm/reject/cancel fixtures are present in this pin but are not yet integrated into the preview gateway. Unsupported mutations remain errors. The real client uses the declared status endpoints without a fixture fallback.

## Provider follow-up: inconsistent supplied fairness delta

In `run.succeeded.json`, Balanced has fairness burden **7.97** and Lowest cost has **7.83**, while the Lowest cost trace reports `compared_to: requested_plan` and `fairness_delta: +0.02`. The displayed scores imply a decrease; the returned delta implies an increase. The same inconsistency was observed in upstream 3.26 during review.

The UI preserves all supplied values and warns that their directions disagree. It does not replace the delta with -0.14, recompute fairness or manufacture a correction. The consistency check is limited to a declared requested-plan reference with known scores and material, opposing directions; recorded published baselines are excluded. Claude should verify the fixture's reference/scores/delta and publish matching values. This is fixture evidence, not a claim that a live solver reproduced the defect.

## Verification and next work

Contract generation/hash checks, AJV response validation, TypeScript/build, lint and unit tests cover this slice. Browser coverage includes desktop/phone layouts and accessibility, read-only disclosures, profile input, missing legacy evidence, provenance, cost redaction and repair selection through explicit approval. The full regression run passed 152 desktop/phone cases; 172 unit/contract tests passed. Local visual captures are ignored under `.impeccable/review/`.

Next UI work: review the newer published replacement contract and add Find cover, then review Scenario Lab's isolated events/run/compare/current-fact conversion flow. Upstream 3.26 already includes those provider contracts and further P1 surfaces; their consumer integration and live acceptance are separate milestones. Do not merge unreviewed backend implementation as part of a UI snapshot update.
