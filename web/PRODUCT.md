# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js and TypeScript frontend; FastAPI, PostgreSQL and CP-SAT backend under the governing `ShiftPilot System Architecture v3.docx` (local source in the main checkout). Codex owns the whole UI; Claude owns backend/database implementation.

## Users

Restaurant managers create and repair weekly rosters. Owners coordinate outlets. Employees view schedules and request availability changes, leave and swaps.

## Product Purpose

Generate and repair staff schedules from availability, skills, demand and configured constraints, with human review before publication.

## Capabilities and Constraints

Schedule-first interaction. No core action requires a prompt. Authoritative validation, costs, coverage, permissions and optimization come from the backend. UI fixtures are synthetic and must be labelled. Payroll, voice, WhatsApp and generic chatbot features are out of scope. Source: `docs/Newupdate.doc` and revised scheduling roadmap.

## Evidence on Hand

Provider contract 2.3 data APIs and seed are delivered; the UI has a fixture preview and isolated compatibility smoke checks. Architecture v3 supersedes older behavior where it differs; revised candidates, proposals, staffing templates and other v3 contracts require consumer review before integration. The fixture preview remains explicit.

## Product Principles

- Show schedules before analytics.
- Preview changes before publishing.
- Preserve locks and explain conflicts.
- Make every workflow usable without natural language.

## Accessibility & Inclusion

Keyboard alternatives to dragging, visible focus, semantic forms, reduced motion and usable narrow-screen layouts are required by the implementation roadmap.
