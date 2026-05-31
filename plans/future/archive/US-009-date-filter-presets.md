# US-009: Extract Date Filter Presets into Configurable Data Structure

**Epic:** Maintainability
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 2
**Status:** Unstarted

---

## Story

As a developer,
I want date filter presets defined in a data structure rather than hardcoded logic,
So that adding or reordering presets requires changing only the data, not the filter logic.

---

## Context

`gui/list_panel.py` — Presets like "Overdue", "Today", "Next 3/7/30 days" are hardcoded in the filter logic. Adding a new preset (e.g., "Next 14 days") requires modifying the filtering code.

---

## Acceptance Criteria

1. Given the date presets are defined in a data structure (list of tuples: `(label, days_offset, is_past)`), when a developer wants to add a preset, then they add one line to the structure without touching filter logic.
2. Given the data structure exists, when the list panel builds its filter dropdown, then it iterates over the structure dynamically (no hardcoded menu items).
3. Given the presets are loaded, when the filter is applied, then behavior for each preset matches the current implementation exactly (no regression).
4. Given a preset has `days_offset=0`, when applied, then it filters to today only (matches existing "Today" preset).

---

## Implementation Notes

```python
DATE_PRESETS = [
    ("Overdue", -1, True),      # special: before today
    ("Today", 0, False),
    ("Next 3 days", 3, False),
    ("Next 7 days", 7, False),
    ("Next 30 days", 30, False),
]
```

- "Overdue" remains a special case in the filter function (date < today).
- All others: `today <= date <= today + timedelta(days=offset)`.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
