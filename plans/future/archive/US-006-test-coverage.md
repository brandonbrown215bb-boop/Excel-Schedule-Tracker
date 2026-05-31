# US-006: Comprehensive Test Coverage Expansion

**Epic:** Quality Assurance
**Type:** Enabler
**Priority:** MEDIUM
**Story Points:** 13
**Status:** Unstarted

---

## Story

As a developer,
I want comprehensive unit and integration tests for all GUI components and edge cases,
So that regressions are caught before release and refactoring can proceed with confidence.

---

## Context

The test suite has gaps:

- **`test_writer.py`** — `test_save_updates_fields` only checks function signature via `inspect`, never calls `save_unit`.
- **`test_vba_native.py`** — Formula tests assert on hardcoded `"L2"`/`"K2"` strings (the bug itself, now fixed).
- **No GUI tests** for CalendarPanel, TimelinePanel, EditForm, A11yDialog, LoadingOverlay.
- **`test_loader.py`** — Missing tests for malformed dates, negative floats, missing sheets, corrupt cache.
- **`test_sync.py`** — No concurrent lock acquisition or stale lock tests.
- **`conftest.py`** — Implicit fixture dependencies with no documentation.

---

## Acceptance Criteria

### test_writer.py fixes

1. Given `test_save_updates_fields` exists, when it runs, then it either actually calls `save_unit` and verifies the saved Excel data, or is renamed to `test_save_unit_signature` to reflect what it tests.

### test_vba_native.py fixes

2. Given the formula row-reference bug is fixed (formulas now use per-row references like `L{i}`), when formula tests run, then they assert on the correct row-relative formula strings.

### New GUI unit tests

3. Given `EditForm` has save/revert logic, when tests are written, then `set_unit()` populates all fields correctly, `_on_save()` persists all fields including `actual_hours`, and revert restores original values.
4. Given `CalendarPanel` paints date dots, when tests are written, then multi-unit dates appear in the event list, and selecting a date emits the correct signal.
5. Given `Theme` maps status colors, when tests are written, then each status (green/yellow/red/gray/purple/orange) maps to the correct color hex code in both light and dark modes.

### Loader edge cases

6. Given `parse_date()` handles multiple formats, when a malformed date string (`"2024/13/45"`) is passed, then it returns `None` and logs a warning.
7. Given the loader reads Excel files, when a workbook has a missing expected sheet, then a clear `ValueError` is raised (not a `KeyError`).
8. Given a corrupt `.pkl` cache file exists, when the loader reads it, then it falls back to CSV or full Excel parsing.

### Sync edge cases

9. Given the `LockManager` coordinates file access, when two threads attempt to acquire the same lock, then one blocks until the other releases (no deadlock within timeout).
10. Given a lock file exists from a crashed process, when the `LockManager` starts, then it detects the stale lock and allows re-acquisition.

### Fixture cleanup

11. Given `conftest.py` has interdependent fixtures, when a developer reads each fixture, then its dependencies are documented in a docstring.

---

## Implementation Notes

- GUI tests: use `pytest-qt` (`qtbot`) for widget testing. Already a likely dependency given PyQt5 project.
- EditForm tests: instantiate the form, call `set_unit(sample_unit)`, read field values, simulate button clicks, mock `save_unit` to avoid real file I/O.
- CalendarPanel tests: mock the event list, trigger date selection signals, verify emitted data.
- Theme tests: instantiate `Theme`, call `get_color(status)` and assert hex values.
- Loader edge cases: add to `conftest.py` fixture for corrupt workbooks.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [ ] Small — 13 points, intentionally a large enabler story to be split across sprints
- [x] Testable
