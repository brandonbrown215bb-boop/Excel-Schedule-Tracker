# US-013: Refactor apply_theme() Using Widget-Type Handler Registry

**Epic:** Maintainability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 5
**Status:** Unstarted

---

## Story

As a developer adding a new widget type to the app,
I want to register its theme handler in a dictionary rather than modifying a recursive isinstance() chain,
So that the Open/Closed Principle is respected and theme application is extensible.

---

## Context

`gui/theme.py` — `apply_theme()` uses `isinstance()` checks to recursively apply styles to child widgets. Adding a new widget type requires adding another `isinstance` branch, violating open/closed.

---

## Acceptance Criteria

1. Given the refactored `apply_theme()`, when it processes a widget, then it looks up the handler for the widget type in a dictionary (`dict[type, callable]`).
2. Given a new widget type (e.g., `QStatusBar`) needs theme support, when a developer adds it, then they add one entry to the handler dictionary (no changes to `apply_theme` itself).
3. Given the handler registry exists, when a widget type has no registered handler, then `apply_theme` continues to the children (no error, no style applied — safe fallback).
4. Given the refactoring is complete, when themes are applied in both light and dark modes, then a developer visually confirms rendering matches the pre-refactor appearance (manual visual check; no pixel-diff tooling available).

---

## Implementation Notes

```python
_THEME_HANDLERS: dict[type, Callable] = {
    QPushButton: _style_button,
    QLabel: _style_label,
    QTableWidget: _style_table,
    # ...
}

def apply_theme(widget, theme):
    handler = _THEME_HANDLERS.get(type(widget))
    if handler:
        handler(widget, theme)
    for child in widget.children():
        if isinstance(child, QWidget):
            apply_theme(child, theme)
```

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
