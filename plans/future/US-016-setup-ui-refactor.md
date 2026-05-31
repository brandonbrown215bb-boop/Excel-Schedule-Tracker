# US-016: Refactor MainWindow.__init__ into Focused Setup Methods

**Epic:** Maintainability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer working on `MainWindow`,
I want the monolithic `__init__` method broken into focused, well-named private methods,
So that I can find and modify specific UI sections without scrolling through a 170+ line initialization.

---

## Context

`gui/main_window.py` — `MainWindow.__init__` (line 139) is a ~170-line method that directly contains all UI construction code: central layout, toolbar, panels, edit form, automation bar, loading overlay, file watcher setup, multi-user sync, auto-refresh, help menu, onboarding, and async data load.

Several extractions **already exist**: `_build_automation_bar()` (line 842), `_setup_file_watcher()` (line 687), `_setup_multi_user_sync()` (line 887), `_setup_auto_refresh()` (line 779), `_build_help_menu()` (line 315).

This story extracts the **remaining inline blocks** into named methods. The existing extracted methods are left as-is.

---

## Acceptance Criteria

1. Given `main_window.py` is refactored, when a developer reads `__init__`, then it calls clearly named setup methods in sequence:

```python
def __init__(self, ...):
    self._init_theme()          # lines 162–171
    self._init_status_bar()     # lines 178–183
    self._setup_central_layout()# lines 186–191
    self._setup_toolbar()       # lines 200–228
    self._setup_panels()        # lines 231–253
    self._setup_right_panel()   # lines 256–278
    self._build_automation_bar()# already exists, line 274/842
    self._setup_loading_overlay() # line 290
    self._setup_file_watcher()  # already exists, line 295/687
    self._setup_multi_user_sync() # already exists, line 296/887
    self._setup_auto_refresh()  # already exists, line 299/779
    self._build_help_menu()     # already exists, line 302/315
    self._check_onboarding()    # lines 305–307
    self._load_data_async(force_reload=True)
```

2. Given each extracted method, when read, then it focuses on a single responsibility and is ≤50 lines.
3. Given the refactoring is complete, when the app launches, then a developer visually confirms the UI matches the pre-refactor appearance (manual visual check; no pixel-diff tooling available).
4. Given signal connections are extracted, when widgets are created in a given method, then their signals are connected within that same method or in a dedicated `_setup_connections()` method. No `AttributeError` from connecting signals before widgets exist.

---

## Implementation Notes

- Extraction boundaries are already visible: comment headers like `# ── Left: view toggle + stacked panel ──` mark natural split points.
- Signal connection ordering matters: `edit_form.saved` can only be connected after `edit_form` exists. Keep connections in creation order.
- `self._config_path` (line 172) is assigned before the UI is built. Any method referencing it must come after that assignment.
- This is a pure extract-method refactoring. No behavioral changes. No new logic.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
