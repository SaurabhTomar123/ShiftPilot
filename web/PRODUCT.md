# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js and TypeScript frontend; FastAPI, PostgreSQL and CP-SAT backend under the governing `docs/ShiftPilot_Architecture_v4.docx` (local source in the main checkout). See `docs/ARCHITECTURE_V4_ALIGNMENT.md` for current delivery order and contract gaps. Codex owns the whole UI; Claude owns backend/database implementation.

## Users

Restaurant managers create and repair weekly rosters. Owners coordinate outlets. Employees view schedules and request availability changes, leave and swaps.

## Product Purpose

A Workforce Decision & Recovery Engine: generate valid schedules, recover commitments with minimal disruption, compare trade-offs and simulate isolated what-if scenarios, with deterministic validation and human approval. Scenario Lab, impact freezes and true fairness are v4 targets awaiting API integration; they are not represented as delivered.

## Capabilities and Constraints

Schedule-first interaction. No core action requires a prompt. Authoritative validation, costs, coverage, permissions and optimization come from the backend. UI fixtures are synthetic and must be labelled. Payroll, voice, WhatsApp and generic chatbot features are out of scope. Source: `docs/Newupdate.doc` and revised scheduling roadmap.

## Evidence on Hand

Provider contract 3.3 is consumed. The UI supports candidate diffs, explicit selection, keyboard/form-based assignment previews and saves, proposal approval with four publication outcomes, and history/comparison/restoration with recorded metrics. An isolated real API/worker check generated candidates without drafts, then selected, proposed and published a 71-shift week with zero reported hard violations. Default mode remains a labelled synthetic preview. An isolated real edit check also passed lock/unlock saves and reload after a lost success response, leaving the published version unchanged. Absence management now saves facts before repair, tracks automatic runs, requires explicit lock authorization, and connects repair options to draft/proposal review. Template-based additions, drag interactions, staffing templates, staff self-service absence requests and release/tenant acceptance gates remain separate work.

## Product Principles

- Show schedules before analytics.
- Preview changes before publishing.
- Preserve locks and explain conflicts.
- Make every workflow usable without natural language.

## Accessibility & Inclusion

Keyboard alternatives to dragging, visible focus, semantic forms, reduced motion and usable narrow-screen layouts are required by the implementation roadmap.

A real history/compare/restore check created a new validated draft and reopened its pending proposal while leaving the published pointer unchanged during restore. Provider versions after 3.3 remain separate consumer integration work.
