# US-015b: Fix Failing Status Color Contrast Combinations

**Epic:** Accessibility
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 4
**Status:** Unstarted

---

## Story

As a colorblind or low-vision user,
I want all status-colored cells in the list panel and dots in the calendar panel to meet WCAG AA contrast (≥ 4.5:1),
So that I can read every cell regardless of its status color, row background, theme, or CVD mode.

---

## Context

US-015a produced a contrast audit report (`contrast_audit.json`) identifying all combinations that fall below 4.5:1. Those combinations need their colors adjusted.

The fix involves modifying `gui/theme.py` status color tokens — not the list panel code. The list panel reads colors from the theme, so changing the theme tokens fixes both the list panel and the calendar panel simultaneously.

When adjusting colors: preserve the hue (don't change red to blue), only adjust lightness/darkness to meet contrast. Re-run the audit after each adjustment batch to verify all 96 combinations pass.

---

## Acceptance Criteria

1. Given the US-015a audit report identifies failing combinations, when colors are adjusted in `theme.py`, then all 96 list-panel combinations meet ≥ 4.5:1 contrast.
2. Given status colors are adjusted, when the calendar panel renders status dots, then all 48 calendar combinations also meet ≥ 4.5:1 contrast against their background.
3. Given colors are adjusted, when the app runs in both light and dark themes, then the visual appearance of each status color is still recognizably distinct (no two statuses become indistinguishable).
4. Given the brightness heuristic in `list_panel.py:488`, when colors change, then the heuristic is re-evaluated — if it no longer matches the correct text color for any combination, it's replaced with a proper WCAG-based calculation.
5. Given all fixes are applied, when the audit script from US-015a re-runs, then zero combinations fail.

---

## Implementation Notes

- Edit status color tokens in `gui/theme.py` (light and dark variants, plus CVD overrides).
- Adjust in this order: (a) fix dark-theme failures first (usually need to lighten dark colors), (b) fix light-theme failures (usually need to darken light colors), (c) fix CVD mode failures, (d) re-run audit.
- Replace the brightness heuristic at `list_panel.py:488` with proper WCAG contrast calculation:
  ```python
  def _wcag_luminance(hex_color):
      r, g, b = [int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5)]
      r = r/12.92 if r <= 0.03928 else ((r+0.055)/1.055)**2.4
      g = g/12.92 if g <= 0.03928 else ((g+0.055)/1.055)**2.4
      b = b/12.92 if b <= 0.03928 else ((b+0.055)/1.055)**2.4
      return 0.2126*r + 0.7152*g + 0.0722*b
  ```

---

## Dependencies

- Depends on US-015a (contrast audit) — must be complete before this story starts.

---

## INVEST Checklist

- [x] Independent (after US-015a)
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
