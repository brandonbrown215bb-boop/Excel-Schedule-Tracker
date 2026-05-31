# US-015: WCAG AA Contrast Verification for Status Colors on All Row Backgrounds

**Epic:** Accessibility
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a colorblind or low-vision user,
I want all status-colored text and backgrounds to meet WCAG AA contrast requirements in both light and dark themes,
So that I can read every cell in the list table regardless of its status color or row background.

---

## Context

`gui/list_panel.py` — Alternating row backgrounds combined with status-colored cells may produce insufficient contrast, especially in dark mode. This has not been systematically tested.

---

## Acceptance Criteria

1. Given every status color (green, yellow, red, gray, purple, orange), when rendered on a light-mode alternating row background (white and light gray), then text/background contrast ratio is ≥ 4.5:1 (WCAG AA for normal text).
2. Given the same status colors, when rendered on a dark-mode alternating row background (dark gray and darker gray), then contrast ratio is ≥ 4.5:1.
3. Given the app is in colorblind mode (protanopia), when status colors are remapped, then remapped colors also meet ≥ 4.5:1 contrast on both alternating row backgrounds.
4. Given any combination fails contrast check, when the fix is applied, then the failing color is adjusted (darkened/lightened) until it passes.

---

## Implementation Notes

- Use `wcag-contrast` or compute manually: `(L1 + 0.05) / (L2 + 0.05)` where L is relative luminance.
- Test all 6 status colors × 2 row backgrounds × (1 normal + 3 CVD modes) × 2 themes = up to 96 combinations.
- Output a contrast matrix report as evidence.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
