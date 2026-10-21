# Schedule history and restore

Continue the existing Ink palette (#f2f3f4 canvas, #fdfdfc surface, #26303b ink, #56606d secondary text, #d7dce2 lines, #2a4f9e actions) and Workshop typography. History is a chronological operational record: left-aligned version rows with source, status, dates and stored coverage/cost. Avoid a decorative timeline or repeated dashboard cards.

    selected outlet/week -> history rows -> explicit comparison
                         -> choose older published version -> restore draft
                         -> current validation -> proposal -> approval outcome

Comparison selectors name the direction: From and To. Assignment changes show actual before/after teammate, role, local times, breaks and locks. Metric comparisons are evaluated by the service against current facts; the history rows instead show recorded metrics, with a clear missing-record fallback for older data. No inferred cost or coverage.

Restoration names the source version and current published base before the user commits. It creates a new draft with current validation. Show violations and the restored assignments, then reuse proposal review. A stale restore retains its selection and requires reload; a lost response can be retried explicitly with the same key. Nothing is published optimistically. A subsequent explicit Schedule visit can reopen the saved draft.

History is a real navigation destination. Empty, denied, missing-version and transport errors stay scoped to the selected outlet/week. Reads cancel on navigation. On phones the version facts stack; long comparison tables scroll inside named keyboard-accessible regions. Existing appearance controls and reduced-motion behavior remain available.

Provider pin for this slice: 3.3.0-p4 (d66ad33), including the 3.1 consumer fixture fixes. Later provider 3.11 work is visible but is not imported or declared reviewed by this delivery.
