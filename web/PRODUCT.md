# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js and TypeScript frontend; FastAPI, PostgreSQL and CP-SAT backend under the governing `docs/ShiftPilot_Architecture_v4.docx` (local source in the main checkout). See `docs/ARCHITECTURE_V4_ALIGNMENT.md` for current delivery order and contract gaps. Codex owns the whole UI; Claude owns backend/database implementation.

## Users

Restaurant managers create and repair weekly rosters. Owners coordinate outlets. Employees view schedules and request availability changes, leave and swaps.

## Product Purpose

A Workforce Decision & Recovery Engine: generate valid schedules, recover commitments with minimal disruption, compare trade-offs and simulate isolated what-if scenarios, with deterministic validation and human approval. Historical fairness burden, portfolio metadata and decision traces now have consumer UI. Direct replacement recommendations now have consumer UI with draft validation and separate save/approval. Scenario Lab now has isolated event forms, bounded simulation tracking, comparisons under matching assumptions and explicit current-fact conversion into normal draft/proposal review. Completed-run fixture coverage and live isolation acceptance remain open. Run-scoped protection remains supported. Live 3.27 engine acceptance is pending.

## Capabilities and Constraints

Schedule-first interaction. No core action requires a prompt. Authoritative validation, costs, coverage, permissions and optimization come from the backend. UI fixtures are synthetic and must be labelled. Payroll, voice, WhatsApp and generic chatbot features are out of scope. Source: `docs/Newupdate.doc` and revised scheduling roadmap.

## Evidence on Hand

Frontend contract 3.27 is consumed from a commit-pinned schema/fixture snapshot, without a backend source/runtime upgrade. The UI supports candidate diffs, explicit selection, keyboard/form-based assignment previews and saves, proposal approval with four publication outcomes, and history/comparison/restoration with recorded metrics. A previous isolated real API/worker check on the reviewed 3.3 runtime generated candidates without drafts, then selected, proposed and published a 71-shift week with zero reported hard violations. Default mode remains a labelled synthetic preview. An isolated real edit check also passed lock/unlock saves and reload after a lost success response, leaving the published version unchanged. Absence management now saves facts before repair, tracks automatic runs, requires explicit lock authorization, and connects repair options to draft/proposal review. Template-based assignment additions, drag interactions, staff self-service absence requests and release/tenant acceptance gates remain separate work.

## Product Principles

- Show schedules before analytics.
- Preview changes before publishing.
- Preserve locks and explain conflicts.
- Make every workflow usable without natural language.

## Accessibility & Inclusion

Keyboard alternatives to dragging, visible focus, semantic forms, reduced motion and usable narrow-screen layouts are required by the implementation roadmap.

A real history/compare/restore check created a new validated draft and reopened its pending proposal while leaving the published pointer unchanged during restore. Run protection, impact-stage rendering and decision evidence now consume the 3.27 contract; provider runtime integration and unconsumed APIs remain separate work.

The fixed Chitra replacement story now completes validation/save and explicit proposal approval in synthetic mode. The supplied generation fairness delta is corrected. Newer P1 and SSE schema data in the snapshot do not imply corresponding UI/runtime integrations.

Staffing now separates recurring weekly templates from dated requirements. Template saves replace the full set; reviewed expansion writes dated requirements while the provider preserves manual/other retained sources. Expansion is revision-fenced and explicitly keyed; neither action generates or publishes a roster. Synthetic fixtures cover the original expansion and a separate Saturday-template save, with changed-template/manual combinations left explicit rather than fabricated.

Scheduling rules now have a typed, capability-gated workspace: preview affected people, conflicts and up to 50 shift impacts; explicitly load server-suggested exceptions for a fresh preview; then separately save or archive. Organization/tag changes are owner-only. Rules never move published assignments directly. The synthetic gateway keeps unsupported definitions explicit; successful exception and broader scope fixtures, optional parsing and live acceptance remain open.
