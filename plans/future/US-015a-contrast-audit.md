# US-015a: Audit Status Color Contrast Across All Themes and CVD Modes

**Epic:** Accessibility
**Type:** Audit
**Priority:** MEDIUM
**Story Points:** 1
**Status:** Unstarted

---

## Story

As a developer,
I want a complete contrast ratio report for every status color against every row background across all themes and CVD modes,
So that I know exactly which combinations fail WCAG AA and need adjustment.

---

## Context

`gui/list_panel.py` — Status-colored cells (`list_panel.py:487`) are rendered on alternating row backgrounds. The current code uses a brightness heuristic (`(R*299 + G*587 + B*114)/1000` at line 488) to choose text color (white vs dark) but doesn't compute actual WCAG contrast ratios.

The full test matrix is: 6 status colors × 2 alternating row backgrounds × (1 normal + 3 CVD modes) × 2 themes = **96 combinations**.

This story is the **audit only** — it produces a report. Fixing the failing combinations is US-015b.

---

## Acceptance Criteria

1. Given a contrast audit script runs, when it evaluates all 96 combinations, then it outputs a matrix report (status color × row background × CVD mode × theme) showing the contrast ratio for each.
2. Given the report identifies combinations below 4.5:1, when viewed, then each failing combination lists the exact foreground color, background color, and computed contrast ratio.
3. Given the script runs, when it completes, then it also checks the calendar panel's status-colored dots against their background (6 status colors × 2 themes × 4 CVD modes = 48 additional combinations for the calendar).
4. Given the audit is complete, when the report is produced, then it's saved to a file (e.g., `contrast_audit.json`) for reference during US-015b.

---

## Implementation Notes

- Write a standalone Python script (not a GUI test) that:
  1. Loads the `Theme` class to get token colors for light/dark + each CVD mode.
  2. Computes relative luminance per WCAG 2.1: `L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin` where `R_lin = (R_sRGB/255)^2.2` (simplified).
  3. Computes contrast ratio: `(L1 + 0.05) / (L2 + 0.05)` where L1 is the lighter color.
  4. Outputs JSON with all 96+ results and a FAIL/PASS flag per combination.
- Reference: WCAG AA requires ≥ 4.5:1 for normal text, ≥ 3:1 for large text. Use 4.5:1 as the threshold.
- Use `pytest` to wrap the script so it runs as part of the test suite.

---

## Dependencies

- None. This is a standalone audit.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
