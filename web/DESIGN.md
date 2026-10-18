---
name: ShiftPilot
description: A dense, calm weekly scheduling workspace with an explicit synthetic browser demo boundary.
colors:
  canvas: "#f8f9f6"
  surface: "#fff"
  sidebar: "#f6f7f3"
  ink: "#252e29"
  muted: "#69716b"
  line: "#e5e8e1"
  green: "#285640"
  green-hover: "#1b422f"
  mint: "#e9f1e8"
  kitchen: "#e7eee2"
  kitchen-ink: "#3b5336"
  service: "#ede8f3"
  service-ink: "#655278"
  cashier: "#faecdf"
  cashier-ink: "#875a32"
  barista: "#e5edf3"
  barista-ink: "#3d5d72"
typography:
  headline:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "27px"
    fontWeight: 550
    lineHeight: 1.25
    letterSpacing: "-.035em"
  title:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "-.03em"
  body:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "13px"
    lineHeight: 1.5
  label:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "11px"
    fontWeight: 500
rounded:
  shift: "5px"
  control: "6px"
  surface: "8px"
  dialog: "12px"
spacing:
  control-gap: "7px"
  field-gap: "20px"
  content: "30px"
  dialog: "26px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    height: "35px"
    padding: "0 12px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.green-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#465045"
    rounded: "{rounded.control}"
    height: "35px"
    padding: "0 12px"
    typography: "{typography.label}"
  button-subtle:
    backgroundColor: "transparent"
    textColor: "#465045"
    rounded: "{rounded.control}"
    height: "35px"
    padding: "0 12px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 11px"
    width: "100%"
  data-surface:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.surface}"
  shift-kitchen:
    backgroundColor: "{colors.kitchen}"
    textColor: "{colors.kitchen-ink}"
    rounded: "{rounded.shift}"
    padding: "7px 6px"
    width: "100%"
---

# Design System: ShiftPilot

## Overview

**Creative North Star: "The Working Week"**

The current Operate-mode interface treats the weekly roster as a working surface: a fine grid, compact controls, quiet neutral framing and role-colored assignments. Forest green concentrates attention on actions; pastel fills let a manager scan shifts without making the whole workspace loud. This name describes the observed implementation and is not a claim of user-approved brand language.

This document captures source code in `web/src/app/globals.css`, `web/src/components/ui.tsx`, `web/src/components/workspace.tsx` and the local Geist import in `web/src/app/layout.tsx`. It is a source scan, not a browser or detector audit. The Impeccable engine could not run because its engine cache was unwritable. The user owns the product plan in `docs/Newupdate.doc`; Codex owns UI and Claude owns backend implementation. This slice uses synthetic browser state, with no connected production scheduling backend.

**Key Characteristics:**

- A dense weekly roster leads the workspace.
- Warm neutral framing supports forest actions and pastel role coding.
- Fine dividers and modest corners organize information with little elevation.
- The persistent label reads "Synthetic browser demo".
- Responsive navigation and horizontal roster scrolling preserve the weekly structure.

## Colors

The palette combines warm near-white surfaces, gray-green text, forest actions and four soft role pairs. Frontmatter values are extracted from the root CSS custom properties; component-specific literals remain in source and sidecar snippets.

### Primary

- **Forest action** (`green`): primary buttons, focus outlines, caret and text actions; `green-hover` deepens primary buttons on hover.
- **Quiet mint** (`mint`): an extracted root primitive, currently without a direct consumer in the sampled stylesheet; do not infer a new semantic role from it.

### Secondary

- **Kitchen sage** (`kitchen`, `kitchen-ink`): Kitchen assignments and role badges.
- **Service lilac** (`service`, `service-ink`): Service assignments and role badges.
- **Cashier apricot** (`cashier`, `cashier-ink`): Cashier assignments and role badges.
- **Barista mist** (`barista`, `barista-ink`): Barista assignments and role badges.

### Neutral

- **Warm canvas** (`canvas`): application background.
- **White surface** (`surface`): topbar, roster, data containers and dialogs.
- **Soft sidebar** (`sidebar`): navigation background.
- **Dark green-gray** (`ink`): primary text; **muted gray-green** (`muted`): supporting text.
- **Fine divider** (`line`): structural borders and separators.

**The Role Pair Rule.** Keep role text with its matching pastel fill and retain the written role label; color alone does not identify a shift.

## Typography

**Display and body font:** locally bundled Geist Variable through `@fontsource-variable/geist`, with Segoe UI and sans-serif fallbacks. There is no separate display face or monospace family in this slice.

### Hierarchy

- **Headline:** page title; the frontmatter headline role becomes smaller on narrow screens (24px).
- **Title:** dialog heading; becomes slightly smaller on narrow screens (21px).
- **Body:** base application type; forms inherit the family and use compact supporting labels.
- **Label:** primary and secondary control text. Supporting table labels and shift metadata are smaller (8–11px), so density is an implementation fact, not an accessibility certification.
- **Numeric data:** schedule totals, times, costs and number inputs use tabular numerals where explicitly assigned. Shift times use compact tracking (-.025em).

## Layout

The desktop shell has a fixed sidebar (216px), a matching main offset, a topbar (65px), and centered content with a maximum width (1900px). Content padding uses the frontmatter content step. The schedule grid places the roster beside an insights column (245px) with a gap (20px). The summary begins as four columns. The roster uses a real table with a minimum width (780px), a name column (170px), seven day columns and horizontal overflow.

- At widths of at least 1650px, insights widen (270px), the gap increases (26px), rows grow (74px), and shift text grows.
- At widths up to 1300px, the sidebar narrows (190px), main horizontal padding becomes smaller (22px), insights narrow (218px), and the roster minimum becomes 760px.
- At widths up to 1100px, insights move below the roster, the toolbar wraps, and the summary becomes three columns with status on its own row.
- At widths up to 760px, the sidebar becomes a toggleable drawer (230px) over a backdrop, main offset is removed, content padding narrows (16px), and the topbar becomes shorter (58px). The summary becomes two columns below its lead item. Controls wrap; less essential labels disappear. The roster retains a wide weekly table (830px minimum) and a sticky employee column (146px), allowing horizontal scrolling rather than compressing every shift. Request, rule and history rows wrap. Dialog actions wrap and dialog padding becomes 22px.

The "Synthetic browser demo" badge remains visible at narrow widths. Keep local-state explanations adjacent to generation, publication, repair and history actions.

## Elevation & Depth

Most surfaces are flat and separated by borders or tonal fills. Elevation is reserved for dialogs, notifications and the sticky employee column; this is a restrained hybrid rather than a shadow-free system.

### Shadow Vocabulary

- **Dialog:** `0 24px 90px #1926192b`; modal backdrop uses `#24302666`.
- **Toast:** `0 8px 32px #19261920`.
- **Sticky roster edge:** `2px 0 4px #253c2010` at the narrow breakpoint, separating the pinned names from scrolling days.

## Shapes

Small controls and shift tiles use compact corners; containers are slightly softer and dialogs softer again. The frontmatter radius roles capture these recurring values. Navigation has gently rounded corners (6px), avatars are circular, and legends use tiny rounded squares (2px). Fine solid strokes define surfaces; day-off cells reveal a dashed border on hover or keyboard focus. Avoid turning the schedule grid into floating individual cards.

## Components

### Buttons

Primary actions use a forest fill and white text. Secondary buttons use a white fill and fine border; subtle buttons retain the same control structure with transparent fill. Standard buttons have a compact height and padding from frontmatter, and an icon/text gap (7px). Secondary hover shifts to a pale green-gray fill (`#f0f3ec`) and a stronger border (`#bfcbb8`). Icon buttons are compact square targets (31px) with softer corners (5px). Disabled buttons use reduced opacity (.48) and a not-allowed cursor.

Buttons transition background, text and border colors over 150ms with ease. Global keyboard focus uses a forest outline (2px) with an offset (4px). Reduced-motion preferences reduce transitions and animations to .01ms and restore automatic scroll behavior; do not assume this proves broader accessibility conformance.

### Chips

Role badges reuse the role pairs, with compact text and corners. Neutral badges describe status without implying backend validation. The topbar demo badge is plain, compact text with a small green dot; its explicit wording must remain present.

### Cards / Containers

The roster and data surfaces use white backgrounds, fine divider borders, the surface radius and clipped contents. The summary adds internal padding (19px 22px). Coverage review uses a warm amber-toned inset panel; scenario help uses a pale green inset panel. These support the roster rather than replacing it.

### Inputs / Fields

Dialog fields use white fills, a fine stroke (`#dbe1d5`), the control radius and frontmatter field padding. Labels sit above fields; paired fields use a two-column grid with a gap (20px). Textareas can resize vertically and start at a minimum height (90px). Disabled time fields use a muted fill. Form errors are written inline with alert semantics. Search fields in table toolbars are lighter, borderless compositions, with compact text.

### Navigation

Desktop navigation stacks icon-and-label buttons within the sidebar. Hover uses a quiet green-gray fill; the active item has a stronger sage fill and medium-weight text. On narrow screens the same navigation opens as a drawer with a backdrop. The implementation includes a skip link that moves into view on focus.

### Weekly roster

Role-colored shift buttons show time and role; locked assignments include a lock icon. Absent shifts use a warm red tint, struck-through time and written absence status. Day-off buttons offer an add action on hover or focus. Clicking either opens the shift editor, providing the documented keyboard alternative to dragging. Dragging is available for unlocked shifts; the UI applies only simple demo checks and requests review in the editor.

### Dialogs and notices

Dialogs use the native modal dialog element, an associated title, close button, Escape cancellation, backdrop-click handling and focus restoration to the previous element on cleanup. The default width is capped (520px) with viewport gutters; a wide variant caps at 740px. Height is limited against the dynamic viewport, with internal scrolling. Toasts use status semantics and a dismiss action. These are observed implementation behaviors, not a completed keyboard, contrast or screen-reader audit.

## Do's and Don'ts

### Do:

- **Do** keep the weekly roster visually dominant and preserve its fine grid.
- **Do** keep the "Synthetic browser demo" label visible, including narrow layouts.
- **Do** retain written roles, lock indicators, absence text and draft status alongside color.
- **Do** preserve visible focus, the shift editor alternative to dragging and reduced-motion treatment.
- **Do** reuse the current local Geist typography, forest actions and paired role colors.

### Don't:

- **Don't** present local browser publication, fixture generation or simple replacement suggestions as validated production scheduling.
- **Don't** remove horizontal roster scrolling or the sticky employee column on narrow screens.
- **Don't** replace the fine-bordered roster with a collection of elevated cards.
- **Don't** claim user approval, pixel fidelity or universal accessibility from this source scan.
