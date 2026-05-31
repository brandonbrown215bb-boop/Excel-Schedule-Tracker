# US-012: Document save_master() No-Op with Correct Line Reference

**Epic:** Maintainability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 1
**Status:** Unstarted

---

## Story

As a developer maintaining `automation/vba_native.py`,
I want the `save_master()` function to have a clear docstring explaining why it exists,
So that I don't waste time wondering if it's broken or incomplete.

---

## Context

`automation/vba_native.py` line 22 — `save_master()` is a no-op (body is `pass`). It exists for VBA API parity: the original VBA macro had a "Save" step, and `vba_runner.py` dispatches the `"Save"` macro name to this function. Without a docstring, a developer might think it's a bug or incomplete implementation.

Tests that reference `save_master`: `test_vba_native.py` (lines 20-33) and `test_imports.py` (line 41). These must be updated if the function is removed.

---

## Acceptance Criteria

1. Given `save_master()` exists in the codebase, when a developer reads it, then it has a docstring explaining: "No-op. Retained for VBA API parity. The Python equivalent does not require a separate master save step."
2. Given the `calculated_status_color` method is documented, when the `StatusColor` type is viewed, then each value has a comment indicating whether it is calculated or manual (purple/orange = manual only).
3. Given `save_master()` is called by `vba_runner.py`, when the dispatching logic runs, then it still calls `save_master()` (no behavioral change — documentation only).

---

## Implementation Notes

- Add a docstring to `save_master()` at line 22 of `vba_native.py`.
- Do NOT remove the function — it's still dispatched by `vba_runner.py` MACRO_DISPATCH.
- If VBA parity is removed in the future, both the function and the `MACRO_DISPATCH` entry must be removed, and tests updated.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
