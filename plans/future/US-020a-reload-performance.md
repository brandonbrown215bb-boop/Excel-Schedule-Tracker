# US-020a: Optimize Full Reload Performance for Large Workbooks

**Epic:** Performance
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user with a large Excel workbook (500+ rows),
I want file watcher reloads to complete quickly by making better use of the existing cache,
So that the UI doesn't hang when the workbook changes externally.

---

## Context

When the file watcher detects a change, `_on_file_changed` already calls `_load_data_async(force_reload=False)`, which triggers `load_units()` with `force_reload=False`. This path checks `WorkbookCache._cache_is_fresh()` using mtime+file_size — if the cache is still valid, it loads from the `.pkl` file and skips the Excel parse entirely.

**What can be improved:**
1. When the cache IS stale (file was modified), the full `load_workbook()` + parse loop runs. OpenPyXL's streaming read-only mode is already used, but the per-unit Python object creation is the bottleneck.
2. After loading, `calculated_status_color` recomputes for every unit because it depends on `date.today()`. This is necessary but could be batched more efficiently.
3. After loading, `ListPanel.set_units()` and `CalendarPanel.refresh()` both rebuild from scratch — fine for now, but the load itself should be fast.

This story focuses on making the **full reload fast** (not on incremental UI diffing — that's US-020b).

---

## Acceptance Criteria

1. Given a cache-stale reload of a 500-row workbook, when the full Excel parse runs, then the units-per-second parsing rate is measured and logged (baseline for future comparison).
2. Given a cache-fresh reload of a 500-row workbook, when the `.pkl` file is loaded, then the complete reload (parse + UI update) completes within 1 second.
3. Given a reload is in progress (cache-stale), when the user interacts with the UI, then the UI remains responsive (the reload is in `LoadWorker` on a background thread — verify this still works after any optimizations).
4. Given a cache-stale reload completes, when the result is applied, then `LoadingOverlay` is shown during the reload (existing behavior — verify it fires correctly for reloads >500ms).

---

## Implementation Notes

- Profile the current reload to find the bottleneck:
  - `load_workbook(path, read_only=True, data_only=True)` — already streaming
  - `ws.iter_rows()` loop — likely the per-unit `Unit(...)` construction
  - `calculated_status_color` property access per unit
- If object creation is the bottleneck: consider using `__slots__` on `Unit`, or constructing units from tuples and converting lazily.
- If the parse loop is already fast enough, just add a benchmark test and close.
- Do NOT attempt "incremental reading" — openpyxl is a streaming parser with no random access. True incremental reads are impossible.
- Do NOT implement UI diffing (only changed rows update) — that's US-020b, a separate story.

---

## Dependencies

- None. This is a pure performance optimization of existing code.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
