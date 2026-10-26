---
name: ShiftPilot
description: An operational roster with deliberate typography, selectable color treatments and accessible collapsible navigation.
colors:
  canvas: "#f2f3f4"
  surface: "#fff"
  sidebar: "#e7eaef"
  ink: "#26303b"
  muted: "#56606d"
  line: "#d7dce2"
  green: "#2a4f9e"
  green-hover: "#203c78"
  mint: "#dee5f1"
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
    fontFamily: "'IBM Plex Sans', sans-serif"
    fontSize: "38px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.035em"
  title:
    fontFamily: "'IBM Plex Sans', sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-.025em"
  body:
    fontFamily: "'IBM Plex Sans', sans-serif"
    fontSize: "15px"
    lineHeight: 1.5
  label:
    fontFamily: "'IBM Plex Sans', sans-serif"
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

The roster is a working document, not an analytics dashboard. The default treatment pairs blue pencil-like actions and light ink-gray surfaces with locally bundled IBM Plex Sans for working text and Bricolage Grotesque for headings. User feedback rejected the earlier Geist/green treatment and excessive minimalism; the implementation now retains useful detail while making type and color independently switchable.

Appearance offers three palettes (Ink, Paprika, Olive), three typography choices (Workshop: Bricolage/Plex, Editorial: Fraunces/Plex, Plain: Plex), and three sidebar transitions (slide, dissolve, fold). Preferences apply to the current visit. These are working experiments, not a claim of approved branding.

This document describes `/`. `/sandbox` retains its older Geist-based editing prototype. Architecture v4 governs product behavior; visual experiments do not replace its candidate, proposal, validation or human-approval requirements.

## Colors

The frontmatter defines the default Ink palette. Paprika uses warm paper, dark brown ink and rust actions. Olive uses pale field-note surfaces and restrained olive actions. All treatments use one action accent. Schedule tiles use neutral surfaces; small written skill labels retain five meaningful skill pairs rather than filling the entire grid with pastel blocks. Unknown skills use a neutral fallback.

Published, draft, warning and error states retain explicit words. A theme must never turn an invalid state into a successful one. Cost controls remain capability-gated. The fixture label remains visible at narrow widths.

## Typography

Self-host IBM Plex Sans at 400/500/600, plus variable Bricolage Grotesque and Fraunces. No remote font request is required. Headings use the selected display family, while working text, numbers and controls remain Plex. The old sandbox alone retains Geist.

Page headings are fluid (30-38px), working section titles are 21-23px, body is 15px, supporting explanations are 12-14px, shift times are 12px and break metadata is 11px. Use tabular figures for time, staffing and money. Written labels remain distinct from helper text; controls use explicit accessible names and relevant descriptions.

## Layout

Desktop navigation expands to 225px and collapses to a 72px icon rail. The toggle stays available, destinations keep accessible names, and hovered/focused rail controls reveal labels. The roster remains the largest working surface. Employee and staffing forms are real destinations with contextual headings, not decorative navigation.

Below 900px, navigation is an off-canvas menu. Closed content is inert and invisible. Opening moves focus to Close; Tab stays inside; Escape and the backdrop close it and restore focus. The normal mobile workspace also retains a short section navigation row. Header controls stay compact; layouts at 1600px, 768px and 390px are checked for page overflow.

The seven-day table keeps horizontal scrolling and a pinned employee column. Skill labels get their own line beneath shift times. Employee editors stack on phones; availability windows use two columns; demand rows wrap without shrinking their controls.

## Elevation & Depth

Use fine structural borders and modest tonal differences. The Appearance panel has a bounded soft shadow; schedule tiles do not float on ornamental shadows. No decorative gradients, texture overlays or marketing imagery sit behind working data.

## Shapes

Controls and shift tiles use 7px corners; working containers use 10px. Role markers and labels use tighter corners. Navigation is a continuous rail/panel rather than a stack of cards.

## Components

- **Sidebar:** Schedule, Employees, Staffing, Repair Inbox and History are real destinations. Manager controls are absent from the employee view. Collapse remains operable in the rail. Mobile menu focus and scroll-lock cleanup run independently of animation completion.
- **Sidebar motion:** routine transitions remain under 300ms. Reversible CSS transitions retarget when toggled. Slide uses translation, Dissolve combines opacity with bounded 4px blur, Fold uses clipping. Reduced motion removes spatial effects. Semantic state changes immediately and does not wait for transitionend.
- **Appearance:** native disclosure and labelled selects. Type, palette and motion can be compared on real roster data without changing the session or losing form inputs.
- **Roster and review:** explicit draft/published state, provider-reported metrics and explanatory staffing gaps. Shift disclosures retain template break and lock details; break placement and pay rules are not editable features.
- **Employees:** exact-paise hourly rate entry, status, skill levels, regular hours versus absolute cap, preferred hours, tags, overtime and cross-outlet eligibility. Unchanged fields are omitted from updates; nullable preferred hours can be cleared.
- **Availability:** full recurring-window replacement, explicit same-day/next-day offsets and written errors. Overnight values remain integer minutes in the outlet's local time.
- **Staffing:** edit, add and remove date-specific intervals. Minimum and preferred counts stay distinct. Filters never omit hidden intervals from a save. The initial skill prefers one with demand instead of assuming API list order. Template expansion awaits the v3 contract.
- **History:** chronological version rows with recorded coverage/cost, clear missing-record text and explicit comparison direction. Current-fact metrics are separated from historical recorded metrics. Restore names the current base, produces a validated draft and reuses proposal approval. Pending proposals can be discovered after leaving the schedule view.
- **Save/error states:** no optimistic success message, automatic write retry or silent stale overwrite. Inputs survive errors. Explicit reload replaces inputs with current values. Synthetic edits are session-scoped and do not alter fixed roster/solver fixtures.

## Do's and Don'ts

- Let the schedule, people and staffing details lead; keep the working surface understandable without a prompt.
- Retain written skill and state labels, visible focus and keyboard alternatives.
- Keep TanStack Query caches, credentials and synthetic input state scoped to the session.
- Keep human approval and architecture v3's Published/Stale/Invalid/Changed distinction in subsequent publication work.
- Do not mistake fixed fixture previews or legacy sandbox publication for v3's candidate-selection/proposal workflow.
- Do not infer fairness, paid-break policies or forecast capabilities from the current metrics.

- **Repair Inbox:** a labelled reporting form beside weekly saved records; a single-column layout below 1100px. Saved facts, repair status and proposal decisions are separate. Repair widening uses an ordered list; employee reasoning displays only returned facts. Locked assignments have individual consent checkboxes. Status changes have an explicit decision step.

- **V4 decision surfaces:** Repair Inbox and Plan Compare prioritize recovery trade-offs. Comparison uses a keyboard-focusable horizontal table on phones, separate recorded-baseline and engine-reference labels. Portfolio policy, weekly burden components and employee reasoning use progressive disclosures. Missing legacy metrics remain unreported. Scenario Lab will be a distinct isolated workflow against its published contract. No generic dashboard or invented solver recommendation.

- **Run protection:** progressive disclosure beside Schedule and explicit Repair. Fieldsets separate employee, day and individual shift choices. The preview counts a union; server-confirmed scope is a distinct read-only section. Conflict recovery requires checked assignment consent and a separate start action. Permanent locks never share a release control with run protections.

- **Decision evidence:** distinguish rolling historical imbalance from this week's component points. Show all six change categories with explicit missing values. Eligible alternatives are not presented as rejected. Constraint references appear only when returned; cost access applies inside detailed explanations as well as headline metrics. A provider delta that contradicts its displayed reference scores gets a visible consistency warning without client correction.

- **Find cover:** a focused working panel opened from Schedule or Repair Inbox. A shift picker precedes provider-ranked people, with written priorities and owner-only borrowing consent. Exclusion facts are separate disclosures. Preparing a draft, validating, saving and proposing remain distinct actions; the panel preserves the draft on validation failure and restores focus when closed. Narrow layouts stack the form while keeping full names and exact costs readable.

- **Scenario Lab:** a distinct destination with a persistent hypothetical-workspace explanation, saved what-ifs, ordered event rows and typed forms. Comparison uses a run-matched simulated baseline under identical assumptions, rather than recorded published metrics. Run, convert, propose and approve remain explicit actions. Real-fact writes are absent from event forms. Old results with unverified event revisions cannot be converted; unknown outcomes remain visible and recoverable.
