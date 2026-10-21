# V4 foundation: Repair Inbox and plan comparison

21 October 2026. Architecture source: user-provided `docs/ShiftPilot_Architecture_v4.docx`. Revision 4 supersedes Revision 3. See [alignment, ownership and next delivery order](ARCHITECTURE_V4_ALIGNMENT.md).

This delivery contains frontend changes only. The accepted provider pin remains **3.3.0-p4 / 83 fixtures**. Remote backend OpenAPI 3.14 was inspected for v4 readiness; no v4 scenario/freeze/replacement routes or fairness/portfolio/decision-trace types were declared at inspection time. Newer v3 capabilities remain separate integration work.

## Delivered

- Repair Inbox is a real manager/owner destination with outlet/week-scoped absence records and reporting. Confirm/reject/cancel require a separate decision. Successful absence facts survive repair failures.
- Automatic repair IDs are tracked independently, with bounded GET polling and explicit read-only recovery. Explicit repair reloads its published base, permits individual locked-assignment releases, and exposes cross-outlet consent only to an owner.
- Widening stages, disruption, validation and returned employee/alternative facts are displayed. No unselected employee is assigned an invented rejection reason.
- Plan Compare appears in both generation and repair results. It shows returned plans side by side, including preferred coverage, hard-minimum shortfall, capability-gated cost, assignment changes, overtime, transfers, open shifts and validation. Deltas refer explicitly to a matching recorded baseline; an unmatched baseline produces no fabricated delta. Fairness burden remains unreported until a real provider metric exists.
- Real repair candidates enter the existing detail → select → draft → proposal → explicit approval workflow. No absence or repair-status request publishes a schedule.
- Shared GET cancellation is now per caller: leaving one screen aborts that screen's wait without poisoning another screen's in-flight read. Session replacement still cancels/clears shared queries. A delayed-navigation regression test covers the live failure discovered during this delivery.
- The v4 roadmap prioritizes impact/freeze and portfolio semantics, historical burden and trace, replacements, then isolated Scenario Lab and conversion. Forecasting and workforce collaboration follow as P1.

## Preview boundaries

The provider fixtures contain a confirmed sick absence, a different requested leave record and a repair-summary story. They do not provide matching requested-record status mutations or repair candidate detail/select fixtures. The preview returns an explicit unsupported result for these requests rather than substituting a generation candidate or a different absence. Only the supplied reporting inputs succeed. No fixture record or provider source was hand-edited.

Default preview stays synthetic. Scenario creation, run-scoped freezes, true fairness, Pareto portfolio selection, recommendations and decision traces are not claimed as implemented. Those require the concrete provider handoff defined in ARCHITECTURE_V4_ALIGNMENT.md. Staff self-service absence UI is also pending.

## Isolated real API evidence

The verified Codex-only container `shiftpilot-codex-pg`, labelled `shiftpilot.owner=codex-ui`, uses database `shiftpilot_codex` on port 5435. The reviewed API runs on port 8011. A worker was started from the UI worktree against that same isolated database; existing unidentified workers and Claude's database on 5434 were not stopped or changed.

A browser-only Playwright bridge forwarded requests to the actual API and stripped preview headers. This verifies browser/API behavior, not deployed CORS or normal live-mode configuration. Default UI configuration was not changed.

For the already valid published week of **26 October**, the check selected an assigned, unlocked Ravi shift and reported a confirmed sick absence covering its actual start/end, with reason `Isolated Codex UI absence and repair verification`. The absence remains in the synthetic database. The automatic repair completed; browser candidate detail returned 200, selection 201, proposal creation 201 and explicit approval 200. The published pointer moved from version 1 to version **3** (version 2 was a pre-existing manual draft). Final validation reports **zero hard violations**, and the absence remains confirmed. No operational user data was used. The older week of 19 October was not republished by this check.

Desktop and phone captures were inspected. Plan Compare uses a named, focusable horizontal scroll region on narrow screens; explanatory copy distinguishes recorded baselines and missing burden metrics.

Verification passed: type checks, lint, production build, 131 unit/contract tests, and all 83 provider fixture checks. The full desktop/phone suite passed all 122 cases (4.7 minutes). After the final CSS-only removal of nested vertical scrolling, the final production build and all 32 affected absence/comparison/proposal cases passed again (1.5 minutes). The phone comparison was manually checked at 324px content width: 631px content/client height, with 740px horizontal content, confirming horizontal-only overflow. Captures were inspected. Tests cover explicit writes, saved-fact persistence on polling failure, lock consent, current-base reads, status confirmation, missing fixtures, cost visibility, unreported fairness, invalid ranges, delayed navigation, accessibility and viewport fit. No backend fairness, freeze, dominance, scenario-isolation or tenant-release acceptance is inferred from these UI checks.
