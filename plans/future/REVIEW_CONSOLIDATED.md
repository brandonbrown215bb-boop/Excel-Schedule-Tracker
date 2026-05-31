# Consolidated Review — All 22 User Stories

**Date:** 2026-05-31
**Sources:** `REVIEW_invest-and-ac.md` (Agile Coach), `REVIEW_prioritization.md` (Product Owner)
**Scope:** Every unfinished item from CODE_REVIEW.md → US-001 through US-022

---

## Critical Issues (Must Fix Before Sprint Planning)

### 1. US-006 (Test Coverage, 13 pts) — SPLIT REQUIRED
**Problem:** 13 points bundles 5 unrelated domains (test fixes, GUI tests, loader edge cases, sync tests, fixture cleanup). AC1 self-forks (accepts two mutually exclusive outcomes). No coverage target defined.

**Action:** Split into 5 stories:
- **US-006a:** Fix existing test suite (signature test rewrite + formula test updates) — 3 pts
- **US-006b:** GUI component tests (EditForm, CalendarPanel, Theme) — 5 pts
- **US-006c:** Data layer edge cases (malformed dates, missing sheets, corrupt cache) — 3 pts
- **US-006d:** Sync edge cases (concurrent locks, stale locks) — 3 pts
- **US-006e:** Fixture documentation — 1 pt (or fold into 6a as a task)

### 2. Three Stories Have "OR" ACs — Decision Needed Before Sprint
| Story | Issue | Decision Needed |
|-------|-------|----------------|
| US-008 AC2 | "shows count badge '1' (or is optional)" | Badge always shown, or hidden for single-unit? |
| US-006 AC1 | "either calls save_unit OR is renamed" | Call save_unit properly. The AC should require it. |
| US-012 | "document OR remove" | Decide: document now (1 pt), or remove now (potentially 2 pts if callers need cleanup) |

### 3. US-015 (WCAG AA Contrast) — SPLIT INTO AUDIT + FIX
**Problem:** 3 pts is wrong for a story that must test 96 contrast combinations AND adjust colors that fail AND get design approval. Currently conflates audit and fix.

**Action:** Split:
- **US-015a:** Measure all 96 contrast combos, produce a matrix report — 1 pt (audit)
- **US-015b:** Adjust failing colors, get PO approval, re-verify — 4 pts (fix)

### 4. US-004 is Overestimated (2 → 1 pt)
Single-line `os.makedirs(..., exist_ok=True)` plus error logging. US-011 is 1 pt for documentation; this is 1 pt for a code-line-plus-test.

### 5. US-014 is Underestimated (3 → 5 pts)
SHA-256 computation + backward compatibility with old cache format + performance constraint (200ms for 50MB file) + large file handling. That's not a 3-pointer.

### 6. US-018 — Clarify Relationship with Existing LockManager
`sync/lock_manager.py` already exists in the codebase (per AGENTS.md). US-018 must state whether it replaces, extends, or is independent of it. AC header has typo ("Acceptness Criteria").

### 7. US-019 AC2 — Python 3.14 May Not Exist
Replace with: "when `pip install` runs on the minimum supported Python version." AC3 is tautological ("pin prevents upgrade" — that's what a pin is).

---

## Priority Recommendations

| Story | Current | Recommended | Reason |
|-------|---------|-------------|--------|
| US-003 | MEDIUM | **HIGH** | Silent save failure = data loss without user knowledge |
| US-014 | LOW | **MEDIUM** | Data integrity, tightly coupled with US-002 Sprint 1 work |
| US-018 | MEDIUM | **HIGH** | Concurrent saves can corrupt workbook (multi-user exists) |
| US-020 | LOW | **MEDIUM** | Daily UX friction for large workbooks, highest-point story |

---

## Dependency Fixes

### Sprint 1 Sequencing Risk (CRITICAL)
- **US-001 must finish before US-003 starts.** Both are in Sprint 1. US-001 defines the mutex/handoff pattern; US-003 adds error signals to the same workers. Doing US-003 first means refactoring twice.

### US-002 ↔ US-014 Dependency Window
- US-002 (Sprint 1, HMAC on pickle) and US-014 (was Sprint 4, content hash) are separated by 2 sprints. The HMAC in US-002 will sign mtime+size, and when US-014 later changes the content signature, the HMAC breaks.
- **Action:** Move US-014 to Sprint 2, sequence before or alongside US-002's security work.

### US-013 → US-015 Ordering
- US-013 (Theme Refactor, Sprint 3) must come **before** US-015 (WCAG AA, Sprint 2) because US-015 tests contrast on themed colors. Currently backwards.
- **Action:** Move US-013 to Sprint 2, or US-015 to Sprint 3.

### US-016 → US-005 Within Sprint 4
- US-016 (setup_ui refactor) should be done before US-005 (config debounce) so the timer setup goes into the right extracted method.

---

## Revised Sprint Plan

```
Sprint 1 — Foundation & Safety (19 pts)
  US-001: Thread synchronization (8)       ← Do FIRST
  US-002: Pickle security (5)
  US-003: Worker error dialogs (5)          ← After US-001
  US-004: Backup makedirs (1)

Sprint 2 — Reliability & Security Hardening (19 pts)
  US-014: Cache hash (5)                    ← Moved from Sprint 4, before US-002's HMAC
  US-007: File watcher debounce (5)
  US-018: Workbook locking (5)              ← Verify against existing LockManager
  US-002b: Path sanitization (3)
  US-008: Calendar dot count (3)            ← Resolve AC2 "decision needed" first

Sprint 3 — Performance & Quality (21 pts)
  US-020: Incremental reload (8)
  US-013: Theme refactoring (5)              ← Before US-015
  US-015a: WCAG AA audit (1)               ← Measure first
  US-006a: Test suite fixes (3)            ← Fix existing tests + formula tests
  US-006c: Loader edge cases (3)

Sprint 4 — Cleanup & Polish (16 pts)
  US-016: setup_ui refactor (3)             ← Do FIRST
  US-005: Config debounce (3)              ← After US-016
  US-015b: WCAG AA fix (4)                ← Adjust colors after audit
  US-006b: GUI tests (5)
  US-006d: Sync edge cases (3)
  Housekeeping batch: US-010 + US-011 + US-012 + US-019 (1)
  US-009: Date filter presets (2)
  US-017: milestones cache (2)
  US-021: fingerprint cache (2)
  US-022: timeline paint cache (3)
```

Total: ~75 pts over 4 sprints (vs 67 originally, after point estimate corrections and splits).

---

## Batching Recommendation

US-010, US-011, US-012, and US-019 are all 1-point documentation/cleanup chores that touch different files. Combine into one "Codebase Housekeeping" story (~1 pt, or keep as 4 individual tasks under one story). This reduces ceremony overhead for trivial items.

---

## Cross-Cutting AC Anti-Patterns to Fix

### Anti-Pattern 1: Implementation-Prescribing ACs
These ACs describe **code structure**, not **observable behavior**:
- US-003 AC5: "uses pyqtSignal/Slot" → Change to: "error dialog appears on main thread regardless of which worker emitted the error"
- US-005 AC5: "at most 2 writes" → Change to: "config file on disk reflects all setting changes"
- US-009 AC1: "adds one line to the structure" → Change to: "adding a preset requires no changes to filter logic"
- US-016 AC1: lists specific method names → Move method names to implementation notes

### Anti-Pattern 2: Performance Thresholds Without Baselines
- US-002 AC5: "≤10% vs raw pickle" → Remove. HMAC adds nanoseconds; this is a desktop app.
- US-014 AC3: "adds no more than 200ms" → Specify: "for a representative 50MB Excel file on SSD, hash computation completes within 200ms"
- US-020 AC1: "within 2 seconds" → Measure baseline first, then set target. Specify workbook size and hardware.

### Anti-Pattern 3: Process-Oriented ACs (Checklist Items)
- US-006 AC11: "fixture dependencies documented" → Move to Definition of Done, not AC
- US-011 AC1: "developer sees docstring" → Change to: "a developer can determine from code alone that purple/orange are manual-only within 30 seconds"
- US-012 AC1: "function has a docstring" → Same treatment

### Anti-Pattern 4: Vacuously-Passing ACs
- US-011 AC3: "return value is still a different color" → No code changed; this always passes. Remove.
- US-019 AC3: "pin prevents automatic upgrade" → Tautology. Remove.
- US-009 AC4: Redundant with AC3. Remove.
- US-001 AC5: "when existing tests pass" → Meta-test. Move to DoD.

---

## Missing Story to Investigate

**`Unit.checking_status` — Dead Data (1 pt)**
CODE_REVIEW.md #20 noted `checking_status` is read from Excel but never used in business logic. The dead *classes* were removed (✅), but the field may still exist in the `Unit` dataclass and `COLUMN_MAP`. If so, add a 1-point story to either use it in status calculations or remove it from the model.

---

## Stories Ready for Sprint Planning (No Changes Needed)

These stories are well-scoped, have clear ACs, and appropriate point estimates:
- **US-005** (Config debounce)
- **US-017** (milestones cache)
- **US-021** (fingerprint cache) — gold standard micro-story
- **US-022** (timeline paint cache) — minor AC4 wording issue only

---

## Summary of Changes

| Category | Count | Action |
|----------|-------|--------|
| Stories to split | 3 | US-006 (→5), US-015 (→2), US-001 (→2, optional) |
| Stories to batch | 4 | US-010 + US-011 + US-012 + US-019 → 1 housekeeping story |
| Priority changes | 4 | US-003↑, US-014↑, US-018↑, US-020↑ |
| Point estimate changes | 3 | US-004↓, US-014↑, US-015↑ (after split) |
| ACs to rewrite | ~15 | Fix anti-patterns listed above |
| Dependencies to add | 5 | US-001→US-003, US-014→US-002, US-013→US-015, US-016→US-005, US-001→US-007 |
| Missing story to verify | 1 | `checking_status` dead data |
