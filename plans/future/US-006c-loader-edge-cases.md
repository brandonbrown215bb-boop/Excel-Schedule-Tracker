# US-006c: Add Data Layer Edge Case Tests

**Epic:** Quality Assurance
**Type:** Enabler
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer,
I want tests for edge cases in the data loader (malformed dates, missing sheets, corrupt cache),
So that the app handles bad input gracefully instead of crashing with unhelpful errors.

---

## Context

`data/loader.py` has no tests for:
- Malformed date strings (e.g., `"2024/13/45"`)
- Excel files with missing expected sheets
- Corrupt `.pkl` cache files (truncated, wrong format)

---

## Acceptance Criteria

1. Given `parse_date()` receives a malformed date string (`"2024/13/45"`), when called, then it returns `None` and logs a warning.
2. Given the loader reads an Excel file with a missing expected sheet, when `load_units()` runs, then a clear `ValueError` is raised (not a raw `KeyError`).
3. Given a corrupt `.pkl` cache file exists (truncated mid-write), when the loader reads it, then the error is caught and the loader falls back to CSV or full Excel parsing.
4. Given all edge case tests are written, when `pytest tests/test_loader.py` runs, then all tests pass.

---

## Implementation Notes

- Use `conftest.py` fixtures for mock workbooks. Add a `corrupt_pkl` fixture that writes truncated bytes to a temp file.
- For the missing-sheet test: create a real `.xlsx` with `openpyxl` that has only a "WrongSheet" instead of the expected sheet name.
- For the corrupt cache test: write 10 bytes of random data to a `.pkl` file and pass it to `_load_units_from_pickle()`.

---

## Dependencies

- None. Can be done in parallel with US-006a and US-006b.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
