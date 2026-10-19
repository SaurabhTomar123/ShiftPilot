# UI alignment with architecture v3

Governing source: `ShiftPilot System Architecture v3.docx`, revision 3 dated 18 October 2026, provided in the main checkout. User explicitly required v3 on 19 October. It overrides revision 2 and older roadmap assumptions where they differ. The source document and shared planning board remain local/private; Claude is the planning writer.

## Apply now

- Section 37: schedule-first navigation; Employees and Staffing are real destinations. TanStack Query owns the session-scoped server request cache; React holds editing/interaction state. dnd-kit remains available for later validated editing.
- Sections 8/18: hard minimum versus preferred staffing, regular hours versus absolute cap, outlet-local times and integer minutes. Current forms preserve revisions and the whole week's hidden intervals. They are date-specific manual editing, not the final template workflow.
- Sections 32/36: management writes carry client-generated idempotency keys and their relevant base revisions. Inputs are retained after errors. No automatic write retries, optimistic publication or silent stale overwrite.
- Section 36: full version resources are revalidated. The UI does not skip authorization or rely on immutable lifecycle-status caching from legacy fixtures.
- Sections 7/46: fixed template break duration only. No break-placement editor, paid/unpaid policy, fairness objective, demand forecast, payroll, RAG or analytics page is introduced.

## Candidate and proposal integration delivered

Provider 3.1.0-p4 (Claude commit f8837ae) is now merged and consumed. Candidate details are read-only diffs; explicit selection creates a draft. Proposals record the reviewed revision and metrics; approval handles Published, Stale, Invalid and Changed separately. Changed shows before/after metrics and requires a fresh acknowledgment. Real API/worker smoke checks passed generation without materialized drafts, selection, proposal creation, publication and readback. See UI_HANDOFF_V3_REVIEW.md.

## Manual editing delivered

Existing assignments can be reassigned/unassigned, moved/resized, given another role, locked/unlocked or removed through an accessible form. Preview results are authoritative and never replace the accepted draft. Apply sends the reviewed revision and edits only; saved responses replace the draft. Proposal approval stays hidden during editing. Closing without changes preserves its existing state; a new saved revision requires a fresh proposal. Break duration is not editable. Because the current apply endpoint has revision fencing but no idempotent replay guarantee, uncertain saves pause further writes until an explicit reload. See UI_HANDOFF_MANUAL_EDITS.md.

## Remaining integration work

- Sections 23/31: complete template-based additions, drag interactions and repair proposal entry points. Whole-snapshot hash remains provenance, not a publication gate. The direct-publish legacy endpoint is not used by the new UI.
- Sections 18/19: weekly staffing template expansion, manual overrides surviving re-expansion, and fixed-column CSV onboarding. Do not build fuzzy/AI column mapping from older plans.
- Sections 20/27/28: commit absence first, automatic repair keyed by the absence, lock-conflict authorization and independent repair admission. The UI must not treat active batch work as a blanket repair blocker.
- Sections 9/15: named strategy profiles and hours-preference alignment, without a fairness claim or editable solver weights.

Backend handoff: shared tasks A3.1-A3.13 remain under Claude's planning ownership. Current consumer review accepts the candidate/selection/proposal and cache semantics of 3.1. Templates and CSV need their declared contracts; absence APIs are present but their UI is not yet integrated. I1/I2 and complete v3 release acceptance are not declared closed by this slice.
