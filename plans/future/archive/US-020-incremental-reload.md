# US-020: Incremental Reload for Large Workbooks

**Epic:** Performance
**Type:** Improvement
**Priority:** LOW
**Story Points:** 8
**Status:** Unstarted

---

## Story

As an end user with a large Excel workbook (>500 rows),
I want file watcher reloads to be fast and non-blocking,
So that the UI doesn't freeze when the workbook changes.

---

## Context

When the file watcher detects a change, the entire workbook is re-parsed from scratch via `load_workbook()`. For large workbooks, this causes visible UI lag. The cache helps with initial loads but not with watcher-triggered reloads.

---

## Acceptance Criteria

1. Given a workbook with 500+ rows, when a single cell changes and the file watcher triggers, then reload completes within 2 seconds (not 5+).
2. Given a reload is in progress, when the user interacts with the UI (scrolls, clicks), then the UI remains responsive (reload is in a background thread).
3. Given a reload finishes, when the result is applied, then the visible UI updates smoothly (no flicker or full table rebuild — only changed rows update).
4. Given a progress indicator exists, when a reload takes >1 second, then a loading overlay or status bar message shows progress.

---

## Implementation Notes

- Investigate `openpyxl` read-only mode with `iter_rows()` for faster parsing.
- Compare `pickle` cache load vs. full `load_workbook` — if cache is fresh, skip Excel entirely.
- For incremental: store previous row hashes per COM number; only re-parse changed rows.
- Show the existing `LoadingOverlay` during reloads >500ms.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [ ] Small — 8 points, near the split threshold; acceptable as a single epic feature
- [x] Testable
