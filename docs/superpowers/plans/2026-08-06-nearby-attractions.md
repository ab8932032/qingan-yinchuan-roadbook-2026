# Nearby Attractions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add low-effort, in-place optional-attraction decisions to every itinerary day from Yinchuan onward without changing the main route.

**Architecture:** Keep the existing single-file page structure. Add semantic `details` blocks inside each day, a small reusable CSS component, and optional map points in the existing per-day route data. Validate the static HTML with a lightweight PowerShell test script before and after implementation.

**Tech Stack:** HTML, CSS, vanilla JavaScript, PowerShell static assertions, Gaode navigation URLs.

## Global Constraints

- Existing main route, accommodation, default departure times, and budget remain unchanged except for the separately approved removal of Lanzhou.
- Optional-attraction prose reads like travel writing, not a report or slide deck.
- Each option states detour cost, suggested stay, decision threshold, and the main-plan trade-off.
- Optional content stays inside its related day and is collapsed by default.
- Navigation is the only new external jump.

---

### Task 1: Static acceptance test

**Files:**
- Create: `scripts/check-nearby-attractions.ps1`
- Test: `scripts/check-nearby-attractions.ps1`

**Interfaces:**
- Consumes: `index.html`
- Produces: exit code `0` only when required day blocks, accessibility labels, option tiers, and route invariants are present.

- [ ] Write assertions for required dates from 9.26 through 10.4, `.nearby-options`, tier labels, navigation links, and unchanged primary route strings.
- [ ] Run `powershell -ExecutionPolicy Bypass -File scripts/check-nearby-attractions.ps1` and verify it fails because the new blocks are absent.
- [ ] Keep the failing test unchanged while implementing Tasks 2–4.

### Task 2: Reusable in-place interaction

**Files:**
- Modify: `index.html` styles near the day-card component rules.

**Interfaces:**
- Consumes: native `details/summary` behavior.
- Produces: `.nearby-options`, `.nearby-option`, `.nearby-tier`, `.nearby-cost`, and responsive/print styles.

- [ ] Add compact collapsed summaries that expose option count and the most useful choice.
- [ ] Add readable expanded cards with textual tier labels, time cost first on narrow screens, and restrained colors.
- [ ] Make nested details keyboard accessible and hide redundant navigation controls in print.

### Task 3: Route research and travelogue copy

**Files:**
- Modify: `index.html` day sections from 9.26 through 10.4.

**Interfaces:**
- Consumes: verified coordinates, route proximity, opening constraints, and the existing day narrative.
- Produces: one collapsed nearby-options block per relevant day with prose, cost, cutoff, trade-off, and Gaode navigation.

- [ ] Research official or current primary sources for plausible nearby options along each day's route.
- [ ] Write only options that support a real same-day decision; reject repetitive or unsafe roadside stops.
- [ ] Insert the blocks without changing the default itinerary timeline.

### Task 4: Map points and approved return-route revision

**Files:**
- Modify: `index.html` route strip, trip timeline, route table, accommodation/budget/checklist copy, and `routeLayers` data.

**Interfaces:**
- Consumes: existing per-day map layer objects.
- Produces: optional points marked `optional: true`; 10.4 direct return toward Chengdu with 10.5 as a buffer day and no fixed Lanzhou stay.

- [ ] Remove the fixed Lanzhou overnight from visible itinerary, map, budget, and checklist references.
- [ ] Add optional attraction points to their matching dates without turning them into route waypoints.
- [ ] Preserve existing hotel and main attraction coordinates.

### Task 5: Green verification and visual review

**Files:**
- Test: `scripts/check-nearby-attractions.ps1`
- Verify: `index.html`

**Interfaces:**
- Consumes: completed page.
- Produces: passing static test and reviewed desktop/mobile rendering.

- [ ] Run the acceptance test and fix only implementation defects until it passes.
- [ ] Run HTML/JavaScript syntax checks available in the workspace.
- [ ] Open the page at desktop and narrow widths; verify nested folding, scrolling, keyboard focus, print rules, and map fallback.
- [ ] Run `git diff --check` and review the final diff for accidental route changes or document-style prose.
