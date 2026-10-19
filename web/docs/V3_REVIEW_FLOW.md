# Candidate and proposal review

Use the existing Ink palette: canvas #f2f3f4, surface #fdfdfc, text #26303b, secondary text #56606d, dividers #d7dce2 and action blue #2a4f9e. Keep Workshop typography (Bricolage headings, IBM Plex Sans controls and tables), with the existing appearance alternatives. This is a scheduling decision screen: assignments, coverage and cost carry the hierarchy.

Left-align a single review area between the run results and roster. Candidate rows compare named strategies and metrics. Opening an option reads its diff; a separate selection action creates a draft. A compact summary of added/changed/removed assignments leads into an expandable table with employee, skill, local time, break and lock information. No candidate is rendered as an accepted version.

    run options -> read-only option review -> select -> draft roster
                                                     -> create proposal
                                                     -> approve / reject
                                                     -> outcome + next action

Proposal review uses plain state labels and a table for before/after metric deltas. Published gets a confirmed result and reloads the week. Stale and Invalid retain their server reasons and offer an explicit route to current data. Changed requires a fresh, visible acknowledgment before another approval. Transport errors preserve the proposal and stable request key; writes never retry automatically. Capability checks control selection/publication actions; the API remains the authorization authority.

This extends the existing operational UI rather than adding a marketing-style hero, decorative cards or a new visual theme. On phones the summary stacks, actions wrap and the assignment/delta tables scroll inside their own region. Use the existing focus treatment and reduced-motion rules. No automatic scrolling or celebratory animation.

Fixture scope: use reviewed contract 3.1 provider records. The balanced candidate is the only detailed candidate fixture; other candidates must report missing provider data rather than fabricate their diff. Publication state in the synthetic preview is visit-scoped and combines provider-owned records only. Actual live API acceptance is a separate check.
