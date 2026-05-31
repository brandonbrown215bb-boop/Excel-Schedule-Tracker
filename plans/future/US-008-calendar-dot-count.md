# US-008: Calendar Date Dot — Show Count for Multi-Unit Dates

**Epic:** UI/UX
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user,
I want the calendar date dot to show how many units share a date,
So that I can see at a glance whether a red dot means 1 problem unit or 5 units at risk.

---

## Context

`gui/calendar_panel.py` — Date dot painting picks the "worst" status color but doesn't convey count. 3 green + 1 red = red dot with no indication there are 4 units total. The `events_by_date` dict (line 27) already maps each QDate to the full list of Units, so `len(units)` gives the count.

---

## Acceptance Criteria

1. Given a date has 4 units (3 green, 1 red), when the calendar paints the date dot, then the dot is red (worst status) and shows a count badge "4".
2. Given a date has 1 unit, when the calendar paints the dot, then a count badge "1" is shown.
3. Given a date has more than 99 units, when the calendar paints the badge, then it shows "99+" (abbreviated to prevent overflow).
4. Given a date has no units, when the calendar renders, then no dot is painted (no change from current behavior).
5. Given the count badge is shown, when the user hovers the date, then a tooltip lists each unit and its status.
6. Given the badge is rendered, then it meets WCAG AA contrast against all status colors (reference US-015a audit for contrast values).

---

## Implementation Notes

- Badge placement: render a small superscript number adjacent to or overlapping the dot cluster in the top-right corner of the calendar cell. Keep it within cell boundaries.
- Tooltip: `QCalendarWidget` doesn't natively support per-cell tooltips. Implement via an event filter on the calendar's viewport, tracking mouse position to map to a date cell using `QCalendarWidget.dateAt(pos)`.
- Badge font: use a small (7-8pt) bold font. Text color should contrast with the dot color — reuse the brightness check from `list_panel.py:488`.
- Max count: "99+" for counts > 99 to prevent badge overflow on small calendar cells.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
