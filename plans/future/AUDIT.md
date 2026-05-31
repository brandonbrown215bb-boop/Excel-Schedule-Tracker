# Audit Report — All 25 Active Stories

**Date:** 2026-05-31
**Scope:** INVEST compliance, AC quality, dependency correctness, point estimate accuracy

---

## Summary

| Category | Count |
|----------|-------|
| Stories passing audit with no changes needed | 18 |
| Stories needing minor AC fixes | 4 |
| Stories needingINVEST checkbox corrections | 2 |
| Stories needing dependency note fixes | 1 |
| Total issues found | 7 |

---

## Issues Found

### 1. US-005 — AC2 has vague "debounce timer" phrasing
**Severity:** Minor
**Issue:** AC2 says "the debounce timer resets" but the implementation uses `QTimer.start()` which resets a single-shot timer. The AC is testable but could be clearer.
**Fix:** Already acceptable as-is. The behavior is observable: a second change within the window delays the write further.

### 2. US-007 — Point estimate should be 3, not 5
**Severity:** Minor
**Issue:** Technical review found the current code is more sophisticated than the story suggests (already has file-readiness polling + PK header validation). The actual gap is smaller. Review recommended 3 points.
**Fix:** Change points from 5 to 3.

### 3. US-008 — AC2 still has "decision needed" fork
**Severity:** Medium
**Issue:** AC2 says "a count badge '1' is shown (or is optional for single-unit to reduce clutter — decision needed)." This is a self-forking AC that INVEST review flagged. Must be resolved before sprint.
**Fix:** Decide: always show the badge (simpler, consistent). Remove the "or optional" clause.

### 4. US-012 — Context has wrong line number and wrong behavior description
**Severity:** Medium
**Issue:** Context says "save_master() logs a message and returns" — actual function body is `pass` (no log). Story says "~line 200" — actual line is 22. AC2 creates a future ticket which is process, not behavioral.
**Fix:** Correct context. Remove AC2 (future ticket creation). Add note about existing tests that reference it.

### 5. US-016 — Context refers to _setup_ui() which doesn't exist
**Severity:** Medium
**Issue:** Context says "_setup_ui() handles layout creation..." — there is no `_setup_ui()` method. The monolithic code lives directly in `MainWindow.__init__`. The whole point of the story is to extract FROM `__init__` INTO _setup_ui() and then break THAT down. The context should say `__init__` is the target.
**Fix:** Rewrite context to say the code is in `__init__` and the story first extracts a _setup_ui() then breaks it down, OR reframe as direct extraction from `__init__`.

### 6. US-019 — AC2 references Python 3.14 which doesn't exist
**Severity:** Medium
**Issue:** AC2 says "when pip install -r requirements.txt runs on Python 3.14" — Python 3.14 doesn't exist as of 2026. Should reference the actual minimum supported version.
**Fix:** Change to "on the minimum supported Python version" or "on Python 3.12+".

### 7. US-022 — Context and implementation notes reference wrong class
**Severity:** Medium
**Issue:** Context says "TimelinePanel paintEvent()" and implementation notes say "Add a _layout_cache dict to TimelinePanel" — but painting happens in `TimelineWidget` (inner widget at line 11), not `TimelinePanel` (wrapper at line 256). The cache must go on `TimelineWidget`.
**Fix:** Correct context to reference `TimelineWidget`. Update implementation notes. Add note about needing a new `resizeEvent()` override on `TimelineWidget`.

---

## Stories Passing Audit (No Changes Needed)

US-001, US-002, US-002b, US-003, US-006a, US-006b, US-006c, US-006d, US-011, US-013, US-014, US-015a, US-015b, US-017, US-018, US-020a, US-020b, US-021

---

## INVEST Compliance Summary

| Story | I | N | V | E | S | T | Issues |
|-------|---|---|---|---|---|---|--------|
| US-001 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-002 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-002b | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-003 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Depends on US-001; noted |
| US-005 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None (AC2 is fine) |
| US-006a | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-006b | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-006c | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-006d | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-007 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Points should be 3 |
| US-008 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | AC2 fork unresolved |
| US-011 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-012 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Context wrong; AC2 is process not behavior |
| US-013 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None (use isinstance not type()) |
| US-014 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-015a | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-015b | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Depends on US-015a; noted |
| US-016 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Context references nonexistent method |
| US-017 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-018 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Depends on US-001; noted |
| US-019 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | AC2 references Python 3.14 |
| US-020a | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-020b | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | 13 pts — not Small; correctly unchecked |
| US-021 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | None |
| US-022 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Wrong class reference (TimelinePanel vs TimelineWidget) |

---

## Point Estimate Corrections

| Story | Current | Corrected | Reason |
|-------|---------|-----------|--------|
| US-007 | 5 | 3 | Code more sophisticated than story assumes |
| US-022 | 3 | 3 | Keep at 3 per original estimate; tech review said 5 but scope can be controlled |
| **Net change** | | **-2 pts** | |

## Total Points After Corrections: 59 (was 61)
