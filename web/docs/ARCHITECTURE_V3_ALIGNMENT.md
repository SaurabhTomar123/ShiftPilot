# UI alignment with architecture v3

Governing source: `ShiftPilot System Architecture v3.docx`, revision 3 dated 18 October 2026, provided in the main checkout. User explicitly required v3 on 19 October. It overrides revision 2 and older roadmap assumptions where they differ. The source document and shared planning board remain local/private; Claude is the planning writer.

## Apply now

- Section 37: schedule-first navigation; Employees and Staffing are real destinations. TanStack Query owns the session-scoped server request cache; React holds editing/interaction state. dnd-kit remains available for later validated editing.
- Sections 8/18: hard minimum versus preferred staffing, regular hours versus absolute cap, outlet-local times and integer minutes. Current forms preserve revisions and the whole week's hidden intervals. They are date-specific manual editing, not the final template workflow.
- Sections 32/36: management writes carry client-generated idempotency keys and their relevant base revisions. Inputs are retained after errors. No automatic write retries, optimistic publication or silent stale overwrite.
- Section 36: full version resources are revalidated. The UI does not skip authorization or rely on immutable lifecycle-status caching from legacy fixtures.
- Sections 7/46: fixed template break duration only. No break-placement editor, paid/unpaid policy, fairness objective, demand forecast, payroll, RAG or analytics page is introduced.

## Requires revised provider contract

- Sections 23/36: lightweight candidates with diffs, metrics, explanation facts and validation. Selecting a candidate materializes a draft. The current 2.3 preview's draft_version_id is legacy compatibility, not the v3 selection API.
- Sections 23/31: draft -> proposal -> approve; explicit Published, Stale, Invalid and Changed results. Changed must show metric deltas and require acknowledgment. Whole-snapshot hash is provenance, not a publication gate.
- Sections 18/19: weekly staffing template expansion, manual overrides surviving re-expansion, and fixed-column CSV onboarding. Do not build fuzzy/AI column mapping from older plans.
- Sections 20/27/28: commit absence first, automatic repair keyed by the absence, lock-conflict authorization and independent repair admission. The UI must not treat active batch work as a blanket repair blocker.
- Sections 9/15: named strategy profiles and hours-preference alignment, without a fairness claim or editable solver weights.

Backend handoff: the shared board tracks A3.1-A3.13. Claude's branch now advertises a newer 2.4 compatibility update; this slice pins the tested 2.3 data contract and does not claim approval of unreviewed candidate/proposal changes. Request the authoritative revised OpenAPI/fixtures for selection, proposals/four outcomes, templates and absence repair before those UI integrations. I1/I2 and the complete v3 MVP are not declared finished by this delivery.
