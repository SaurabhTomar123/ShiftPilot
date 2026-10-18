---
name: ShiftPilot
description: A colorful, detailed scheduling workspace with clear roster status and explicit synthetic data boundaries.
colors:
  canvas: "#f4f7f8"
  surface: "#fff"
  sidebar: "#133e3a"
  ink: "#1e3336"
  muted: "#566d72"
  line: "#dbe5e8"
  green: "#087364"
  green-hover: "#075c50"
  mint: "#dcf4ec"
  grill: "#ffe5d2"
  grill-ink: "#8c3d0b"
  prep: "#d8f2e5"
  prep-ink: "#176042"
  service: "#eae1ff"
  service-ink: "#613ba1"
  cashier: "#fff0be"
  cashier-ink: "#775500"
  barista: "#dcedff"
  barista-ink: "#265b91"
typography:
  headline:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "34px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.035em"
  title:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-.025em"
  body:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "'Geist Variable', 'Segoe UI', sans-serif"
    fontSize: "13px"
    fontWeight: 550
rounded:
  shift: "7px"
  control: "7px"
  surface: "10px"
spacing:
  content: "28px"
  field-gap: "10px"
  section-gap: "28px"
---

# Design System: ShiftPilot

## Overview

The working week is the visual center: a strong green navigation frame, a light blue-gray canvas, legible shift blocks and five distinct written skill labels. Color carries operational meaning. Explanations sit next to numbers and controls so a new manager can understand the schedule without interpreting unexplained metrics.

This direction implements the user's request for more vibrancy and detail. It uses the full installed taste-skill package's existing-project redesign guidance. The public marketing-page skill explicitly excludes app dashboards, so its photographic hero, randomized marketing compositions and cinematic scroll requirements are not imposed on this scheduling tool.

This document describes the API workspace at `/`, scoped by `.contract-app` in `src/app/globals.css`. `/sandbox` retains the earlier local editing prototype and its own neutral root palette. It remains a separate interaction demo, not a second live scheduling application.

## Colors

**The Skill Pair Rule.** Grill is orange, Prep is mint, Server is violet, Cashier is gold and Barista is blue. Every color includes a written skill name. Skill filters, shift blocks and coverage gaps share these pairs. Unknown skills use a neutral fallback.

**The Status Rule.** Published status uses a green field, draft review uses violet, and an unplanned week uses blue. Warnings use warm amber. A draft's written status always says it is not published. Never use success green for nonzero hard violations.

The dark green sidebar separates identity and workflow context from the lighter working surface. Primary controls use the green action token and white text. Muted text remains readable; colored fields use darker text from their own hue family.

## Typography

Use the locally bundled Geist Variable font. Page headings are fluid (26-34px), roster headings are 21px, shift times and role labels are 12px, and supporting break metadata is 10px. This raises roster legibility over the earlier 8-10px treatment. Use tabular figures for time, hours, money and staffing counts. Supporting paragraphs keep a readable measure rather than spanning the viewport.

## Layout

Desktop uses a 225px navigation column and a flexible working area with a maximum width of 1800px. The heading and outlet selector lead into week controls, status/action ribbon, week facts, four metric groups, skill filters and the weekly roster. The detailed staffing review follows the roster.

At 1150px the sidebar narrows to 195px, metrics form two columns and status actions wrap. At 900px the sidebar becomes a compact identity strip and the staffing review stacks. At 480px controls wrap and the identity avatars in roster rows are hidden to preserve reading space. The seven-day table keeps a minimum width of 1110px with horizontal scrolling and a pinned employee column (190px desktop, 165px phone). Do not squeeze seven days into unreadable cells.

## Elevation & Depth

Surfaces use fine borders or meaningful tonal fields. No ornamental shadows, photographic backgrounds or marketing effects sit behind schedule data. A selected skill filter gets a one-pixel inset stroke in addition to its border. Expanded shifts use an inset outline to distinguish their open state.

## Shapes

Containers use 10px corners; controls and shift blocks use 7px corners. Identity avatars use rounded squares. Skill color markers are small squares with 3px corners. The roster remains one continuous table rather than floating cards.

## Components

- **Week status:** icon, explicit publication state, supporting explanation and relevant actions. The published demo offers a working Plan upcoming week shortcut; the disabled generation action has adjacent guidance.
- **Week facts:** total employees, shifts, locked assignments and outlet timezone. Totals describe the whole version and do not change when filtering rows.
- **Metrics:** preferred coverage with a native meter, assigned hours with overtime, capability-gated estimated cost, and minimum staffing shortfall. Each metric explains what it means; money retains exact paise.
- **Skill filters:** native buttons with aria-pressed state. These filter teammates by their skills; shift assignments keep their actual roles. Name search combines with the selected skill and provides a written no-results state.
- **Roster:** written roles, shift times, visible break duration and lock status. Native details reveal the break start, lock reason and confirmed overlapping absence. Day headers show total shifts. Employee hours are explicitly across all outlets.
- **Staffing review:** preferred deficit in staff-minutes, employee preference match, and up to four provider-reported staffing gaps ordered with minimum deficits first. Explain staff-minutes and minimum versus preferred requirements. Do not invent interval durations or recompute authoritative metrics.
- **Employee view:** dates, times, outlet, assigned skill and break/lock details. It does not fetch employee costs or show manager planning instructions.
- **Controls and states:** at least 42px for main buttons and 44px for week navigation/selects; clear focus outlines, pressed feedback, loading skeletons, errors and permission recovery. Existing reduced-motion rules remain in force. No decorative entrance animation delays schedule access.

## Do's and Don'ts

- Keep role text, break and lock details visible; color adds meaning rather than replacing words.
- Keep the synthetic contract preview label visible at every width.
- Preserve token clearing, scoped caches, cancellation, generation idempotency and review before publication.
- Keep minimum staffing distinct from preferred staffing and UNKNOWN distinct from INFEASIBLE.
- Never add fictional approvals, live solves, persisted edits or publication controls for missing backend contracts.
- Preserve native keyboard interaction, pinned roster names and horizontal scrolling.
