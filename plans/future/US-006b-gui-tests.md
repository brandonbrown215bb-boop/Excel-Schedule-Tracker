# US-006b: Add GUI Component Unit Tests

**Epic:** Quality Assurance
**Type:** Enabler
**Priority:** MEDIUM
**Story Points:** 5
**Status:** Unstarted

---

## Story

As a developer,
I want unit tests for the core GUI components (EditForm, CalendarPanel, Theme),
So that regressions in form handling, date selection, and color mapping are caught before release.

---

## Context

There are no tests for `EditForm`, `CalendarPanel`, `A11yDialog`, or `LoadingOverlay`. The only GUI test is `test_list_panel.py`. This story adds tests for the three highest-risk components.

---

## Acceptance Criteria

1. Given `EditForm` has save/revert logic, when tests are written, then `set_unit()` populates all fields correctly, `_on_save()` persists all fields including `actual_hours`, and revert restores original values.
2. Given `CalendarPanel` paints date dots, when tests are written, then multi-unit dates appear in the event list, and selecting a date emits the correct `unit_selected` signal.
3. Given `Theme` maps status colors, when tests are written, then each status (green, yellow, red, gray, purple, orange) maps to the correct color hex code in both light and dark themes.
4. Given the new tests are written, when `pytest tests/` runs, then all new tests pass.

---

## Implementation Notes

- Use `pytest-qt` (`qtbot`) for widget testing.
- EditForm tests: instantiate the form with a mock `save_unit` callable, call `set_unit(sample_unit)`, read field values, simulate button clicks, assert the mock was called with correct data.
- CalendarPanel tests: populate `events_by_date` directly, trigger date selection, verify emitted signal data.
- Theme tests: instantiate `Theme`, call `get_color(status)` for each status in light and dark mode, assert hex values match expected tokens.
- Mock all file I/O — these are unit tests, not integration tests.

---

## Dependencies

- None. Can be done in parallel with US-006a.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
