# US-006a: Fix Existing Test Suite Bugs

**Epic:** Quality Assurance
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer,
I want the existing test suite to actually test behavior rather than just checking signatures,
So that regressions in writer and formula logic are caught by CI.

---

## Context

Two tests encode bugs as expected behavior:

1. **`test_writer.py` — `test_save_updates_fields`:** Uses `inspect.signature()` to check parameter names — it never calls `save_unit` or verifies any write behavior. The name implies functional testing.

2. **`test_vba_native.py` — formula tests:** Assert on hardcoded `"L2"`/`"K2"` strings in formula output. The row-reference bug (CODE_REVIEW.md #1) has been fixed — formulas now use per-row references like `L{i}`. The tests still assert on the old buggy strings.

---

## Acceptance Criteria

1. Given `test_save_updates_fields` exists, when it runs, then it calls `save_unit` with a mock unit and verifies the correct cells are written to a real `.xlsx` file (using a temp file, not `inspect`).
2. Given the formula row-reference bug is fixed, when formula tests run, then they assert on per-row formula strings (e.g., `L5`, `K5` for row 5) instead of hardcoded `L2`/`K2`.
3. Given both fixes are applied, when `pytest tests/test_writer.py tests/test_vba_native.py` runs, then all tests pass.

---

## Implementation Notes

- For `test_save_updates_fields`: use the existing `conftest.py` fixtures (`tmp_path`, `sample_unit`). Create a real `.xlsx`, call `save_unit`, re-open with `openpyxl`, and assert cell values.
- For formula tests: update assertions to match the current `apply_formulas()` output. The formulas now use f-string interpolation for row numbers.
- Rename `test_save_updates_fields` to something accurate if the scope changes significantly.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
