# US-011: Document StatusColor Purple/Orange as Manual-Only

**Epic:** Maintainability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 1
**Status:** Unstarted

---

## Story

As a developer reading `models.py`,
I want clear documentation that purple and orange status colors are manually assigned only,
So that I don't waste time debugging why `calculated_status_color` never returns those values.

---

## Context

`data/models.py` — `StatusColor` includes `"purple"` (Ready for Checking) and `"orange"` (In Checking), but `calculated_status_color` (lines 88–119) never produces these. They can only be set via the Excel file. This is by design but undocumented.

---

## Acceptance Criteria

1. Given a developer reads the `calculated_status_color` method, when they see the docstring, then it states clearly: `"purple" and "orange" are not calculated; they are read from the Excel file's checking_status column (manual assignment only).`
2. Given the `StatusColor` type definition, when viewed, then each value has a comment indicating whether it is calculated or manual.
3. Given the docstring is updated, when the method is called with inputs that might intuitively produce purple/orange, then the return value is still a different color (no behavioral change — documentation only).

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
