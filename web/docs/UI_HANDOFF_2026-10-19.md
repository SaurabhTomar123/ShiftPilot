# UI delivery: 19 October 2026

Architecture v3 governs this delivery. The tested provider baseline is contract 2.3.0-p3 from backend commit bd149c5. Claude's newer 2.4 work is visible but has not been merged or approved by this UI slice. See [v3 alignment](ARCHITECTURE_V3_ALIGNMENT.md) for the remaining integration boundaries.

## Delivered

- Employee creation and editing: exact paise, regular/absolute/preferred hour limits, skill proficiency, status and eligibility settings. Updates send changed fields and their base revision. Creation retains an idempotency key for the same payload.
- Recurring availability: editable windows, explicit day offsets, Sunday-to-Monday overnight values and full replacement with the base revision.
- Date-specific staffing: minimum/preferred validation, day/skill filtering, interval addition/removal and full-week saves that preserve filtered-out intervals. Initial selection chooses a skill with demand rather than an empty alphabetically first skill.
- Session-scoped TanStack Query server reads, ETag revalidation, write invalidation, cancellation and credential/cache clearing on persona change or expiration.
- Schedule, Employees and Staffing navigation. Desktop collapses to a usable icon rail; mobile opens a focus-managed drawer with Escape, backdrop close and focus restoration.
- Three typography treatments (Bricolage Grotesque with IBM Plex Sans, Fraunces with Plex, or Plex), three color treatments and slide/dissolve/fold sidebar transitions. Default is Ink with Workshop typography. Fonts are self-hosted. Appearance choices last for the current visit and remain experiments awaiting user preference.
- Synthetic management state is scoped by a separate preview-session nonce. It is volatile, bounded and isolated from the real API. Unsupported fixture data remains explicit rather than invented.

## Verification

- Type checking, lint, production build and 90 unit/contract tests passed.
- Provider contract verification passed for 61 fixtures.
- All 50 desktop/mobile browser cases passed against the final production build. Coverage includes exact money, stale-input retention without automatic write retries, overnight windows, full-week staffing saves, unused-first-skill regression, interrupted sidebar transitions, keyboard/focus behavior, reduced motion, axe checks and viewport overflow.
- Two bounded visual inspection rounds covered desktop, collapsed rail, tablet, phone and the mobile menu. No claim of user design approval is made.

An isolated PostgreSQL database and API on 127.0.0.1:8011 were used for compatibility checks. Playwright forwarded requests from the preview to this API only inside the smoke script, stripping fixture headers. Employee create returned 201; employee edit and availability replacement returned 200. Sunday 22:00 to Monday 02:00 saved successfully. Staffing replacement returned 200 and its original intervals were restored. Owner reads displayed all three seeded outlets; the employee own-week view loaded without manager generation controls.

This validates specific data paths against the 2.3 API. It does not validate deployed CORS, default live-mode configuration, complete tenant-isolation gates, solver acceptance, candidate selection or proposal publication. The normal preview at http://127.0.0.1:3001 remains synthetic; no tracked environment configuration switches it to a live API.

## Skills inspected

The requested improve-animations, frontend-design and ui-ux-pro-max skills are installed locally. frontend-design informed deliberate typography and restrained structural color. UI/UX Pro Max guidance informed visible focus and cancellable transitions. improve-animations is a read-only audit/planning skill; its timing, interruption and reduced-motion criteria were inspected as advice, without launching a formal audit or generating execution plans. Existing taste/redesign and Impeccable guidance also informed the UI. These are development tools, not application dependencies.

## Next integration work with Claude

1. Review and import the authoritative v3 OpenAPI and fixtures, including the newer admission/absence contract work.
2. Build lightweight candidate comparison and selection, which materializes a draft only after selection.
3. Integrate proposal approval with distinct Published, Stale, Invalid and Changed outcomes; require acknowledgment of changed metric deltas.
4. Add staffing templates with preserved manual overrides, fixed-column CSV onboarding, absence-triggered repair, Rules and History against their actual contracts.
5. Complete live integration and tenant-isolation acceptance gates separately. Existing legacy sandbox interactions do not close those gates.

Claude's database/backend files and the main checkout's local architecture/shared planning files were not edited by this UI slice. Backend changes included on the UI branch come from the explicit backend merge.
