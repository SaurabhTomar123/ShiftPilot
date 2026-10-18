# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js and TypeScript frontend; FastAPI, PostgreSQL and CP-SAT backend as specified in `docs/Newupdate.doc`. Codex owns the whole UI; Claude owns backend/database implementation.

## Users

Restaurant managers create and repair weekly rosters. Owners coordinate outlets. Employees view schedules and request availability changes, leave and swaps.

## Product Purpose

Generate and repair staff schedules from availability, skills, demand and configured constraints, with human review before publication.

## Capabilities and Constraints

Schedule-first interaction. No core action requires a prompt. Authoritative validation, costs, coverage, permissions and optimization come from the backend. UI fixtures are synthetic and must be labelled. Payroll, voice, WhatsApp and generic chatbot features are out of scope. Source: `docs/Newupdate.doc` and revised scheduling roadmap.

## Evidence on Hand

Existing Python backend foundations and the v2 plan; no working v2 scheduling API or benchmark evidence has been established. First UI iteration uses isolated demo state.

## Product Principles

- Show schedules before analytics.
- Preview changes before publishing.
- Preserve locks and explain conflicts.
- Make every workflow usable without natural language.

## Accessibility & Inclusion

Keyboard alternatives to dragging, visible focus, semantic forms, reduced motion and usable narrow-screen layouts are required by the implementation roadmap.
