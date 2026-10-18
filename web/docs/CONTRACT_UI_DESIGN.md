# Contract UI design extension

Source scan dated 2026-10-18. This records an extension of the established Operate system in `DESIGN.md` and `.impeccable/design.json`; those files remain normative and unchanged. Sources: `PRODUCT.md`, both design files, `src/app/globals.css`, `src/components/contract-workspace.tsx`, `src/components/roster-drag.tsx`, route entry points and the shared button primitive. No browser or accessibility audit was performed.

## Observed reuse

The weekly table remains the primary working surface. The extension retains local Geist typography, warm canvas and sidebar, white surfaces, fine divider borders, forest primary actions and the four pastel role/text pairs. Written skill names accompany color. Shared avatars, empty states, neutral badges, search fields, week controls and the existing `.button` variants preserve the incumbent hierarchy. Containers remain flat with 8px corners; shifts use 5px corners and controls 6px. No new root color or typography tokens were introduced.

The contract shell uses a 70px header, a 210px sidebar and content capped at 1700px with 30px padding. This is a surface-specific arrangement within Operate, distinct from the sandbox's fixed sidebar and insights column.

## Routes and evidence boundary

`/` renders the contract workspace. The default `/api/fixture` mode displays **Synthetic contract preview**, provider fixture context and explanations near generation and roster actions. Current imported Claude provider contract2.1 fixtures identify themselves as `2.1.0-p1p2` in the generated manifest. Fixture outcomes demonstrate presentation states; they do not establish live solver behavior, production publication or release readiness. The optional API base URL changes the header wording to **Connected scheduling API**; the wording alone is not connection evidence.

`/sandbox` retains the local editing workspace and its **Synthetic browser demo** boundary. Its editing, drag, repair and local publication demonstrations are separate from the root contract preview. The root provides a direct sandbox link and explicitly says editing, repair and publication contracts remain to be connected.

## Components and states

- **Metrics:** bordered white grid with auto-fitting columns of at least 150px, 18px cell padding and 22px tabular values. Coverage, assigned time and hard minimum shortfall remain distinct labels; cost appears only with the relevant capability.
- **Roster:** real table with scoped headers, a descriptive hidden caption and horizontal scrolling. Native `details`/`summary` shift tiles reveal breaks, lock reasons and overlapping confirmed absence text. Day off is explicit text; unfilled assignments have a separate written list. Root tiles are disclosures rather than editing or drag controls.
- **Versions and generation:** neutral labels distinguish published versions, no published schedule and unpublished draft previews. Busy actions are disabled. The fixture's published week points to next week for generation. Draft previews offer a return to the published roster.
- **Results:** pale green run panels (`#eef3e9`) and amber warning panels (`#f5eedf`) carry written state explanations. Candidates use a divider, compact metrics and a preview action. Optimality wording follows supplied candidate fields. Run identifiers wrap anywhere; updates use a polite live status region.
- **Errors and loading:** static pale skeleton blocks use status semantics. Warm error panels (`#f7eee4`, text `#795a30`) use alert semantics, written permission/stale/general messages and optional support traces. Reload, retry and expired-session recovery are explicit actions. Constraint details retain written severities.
- **Employee assignments:** flat divided rows show date, local time, outlet, breaks and written lock status. Request workflows are described as forthcoming.

## Role privacy

The returned session role selects the employee or management view. Staff session setup skips management outlet and skill collections and uses the personal-week resource. Management generation and monetary metrics/candidate costs are gated by `generate` and `view_costs` capabilities. Changing personas remounts the session workspace. These are observed UI boundaries; authoritative authorization and response filtering belong to the service contract, and this scan does not certify them.

## Focus, motion and responsive behavior

The skip link targets main content. Native controls and summaries retain global 2px forest focus outlines; buttons, links and form controls have a 4px outline offset. The existing reduced-motion rule applies to elements and pseudo-elements, reducing animation/transition duration to `.01ms` and restoring automatic scrolling. Loading blocks have no animation.

Sandbox dragging adds a 6px pointer activation threshold and keyboard Space start/end with Escape cancellation. Locked shifts disable dragging while retaining their editor button. Dragged tiles use a transform, elevated stacking and 0.7 opacity; empty-cell drop targets use sage fill and an inset forest outline. Reduced-motion CSS does not remove the directly applied drag transform. The shift editor remains the non-drag alternative.

At 900px and below the contract sidebar becomes a wrapping horizontal identity row; header, candidate and roster-heading controls wrap and content padding becomes 24px 16px. Sidebar explanatory small print is hidden, while the header fixture badge and main-content fixture notes remain. The contract roster keeps a 1000px minimum width. At 760px and below inherited roster rules pin the 146px employee column and preserve horizontal scrolling.

## Recorded drift and review limits

The incumbent design files describe the original sandbox, so their route-wide demo wording, mint-without-consumer observation, layout measurements and listed breakpoints do not describe every contract surface. This extension now consumes `--mint` in its sidebar and adds a 900px breakpoint; neither changes the normative primitives.

Skill colors currently follow the position of skills in the supplied collection, with a kitchen fallback; labels preserve meaning if ordering changes. Hard-violation counts always receive forest text, including nonzero values, so the written count must remain visible and this treatment warrants semantic review. Warning candidate metadata retains its green-gray text. Compact 10px disclosure text, clipped tile containers, focus visibility, long translated content and narrow layouts require rendered verification before making accessibility or visual-fidelity claims.
