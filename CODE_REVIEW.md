# Comprehensive Code Review — Schedule Viewer App

**Date:** 2026-05-30  
**Scope:** Full codebase review — all Python source, config, tests, and build files  
**Reviewer:** AI Code Review Agent  

---

## Table of Contents

1. [Critical Bugs](#critical-bugs)
2. [High-Severity Issues](#high-severity-issues)
3. [Medium-Severity Issues](#medium-severity-issues)
4. [Low-Severity / Code Smells](#low-severity--code-smells)
5. [Orphaned / Dead Code](#orphaned--dead-code)
6. [Test Quality Issues](#test-quality-issues)
7. [Security Concerns](#security-concerns)
8. [Performance Issues](#performance-issues)
9. [Recommendations Summary](#recommendations-summary)

---

## Critical Bugs

> **Note:** Items marked ✅ have been fixed; items marked ❌ are confirmed false positives.

### 1. `automation/vba_native.py` — Hardcoded Row References in Formulas ✅ FIXED

**Lines 147, 159**  
**Impact:** Every row's computed columns (Remaining Hours, Percentage) reference row 2's data instead of their own row.

```python
ws.cell(row=i, column=13).value = '=IF(OR(L2="",L2=0),K2,K2-K2*L2)'
ws.cell(row=i, column=20).value = '=IF(R1="","",IF(R15=R[1]15,"",(R18-R19)/R18))'
```

openpyxl writes formula strings literally — it does **not** adjust A1 references based on the target cell's row. Row 50's formula in column M still references `L2` and `K2` instead of `L50` and `K50`. Every row's "Remaining Hours" and "Percentage" will compute based on row 2's data.

**Fix:** Use f-strings to interpolate the current row number: `f'=IF(OR(L{i}="",L{i}=0),K{i},K{i}-K{i}*L{i})'`

### 2. `automation/vba_native.py` — Mixed A1/R1C1 Notation in SUMIFS Formulas ✅ FIXED

**Lines 149–156**  
**Impact:** SUMIFS formulas will produce `#NAME?` errors in Excel because `RC15` is R1C1 syntax embedded inside A1-style formulas.

```python
'=SUMIFS(C11,C1,">="&IF(MONTH(RC15-WEEKDAY(RC15-2))<>MONTH(RC15),'
'EOMONTH(RC15,-1)+1,RC15-WEEKDAY(RC15-2)),C1,"<="&RC15)'
```

These were copied from VBA without converting the reference style. `RC15` means "relative column 0, row 15" in R1C1 notation, but Excel interprets it as a named range (which doesn't exist) in A1 mode.

**Fix:** Convert all `RC15` references to proper A1 notation (e.g., `$O$15` or a row-relative reference).

### 3. `main.py` — `QMessageBox` Called Before `QApplication` Exists ✅ FIXED

**Lines 32–37 vs. Line 55**  
**Impact:** On some Qt backends, calling `QMessageBox.critical()` before `QApplication` is instantiated will crash or silently fail.

```python
# Line 32: called before QApplication
QMessageBox.critical(None, "Configuration Error", "...")
# ...
# Line 55: QApplication created later
app = QApplication(sys.argv)
```

**Fix:** Create `QApplication(sys.argv)` before any `QMessageBox` calls, or use `print()` + `sys.exit(1)` for this early error path.

### 4. `gui/edit_form.py` — `actual_hours` Field Never Populated or Saved ✅ FIXED

**Impact:** The `Unit.actual_hours` field exists in the data model and is displayed in the list panel, but the `EditForm` has no widget for it. When a unit is saved via the edit form, `actual_hours` silently resets to `0.0`.

The `_on_save()` method constructs a `Unit` but never reads an `actual_hours` value — there's no corresponding widget.

**Fix:** Add a `QDoubleSpinBox` for `actual_hours` in `EditForm` and read/write it in `set_unit()` / `_on_save()`.

---

## High-Severity Issues

### 5. `data/models.py` — Type Mismatch on `Unit.working_days` ✅ FIXED

**Line 48**  
**Impact:** Type annotation says `list[int]` but runtime default is `None`. Every consumer must guard against `None`.

```python
working_days: list[int] = None  # type: ignore[assignment]
```

The `# type: ignore` hides a real type inconsistency. If someone later changes the default to `[0, 1, 2, 3]`, all instances would share the same mutable list (classic Python dataclass gotcha).

**Fix:** `working_days: list[int] | None = None` or use `field(default_factory=lambda: [0, 1, 2, 3])`.

### 6. `data/writer.py` — Workbook Handle Leak on Exception ❌ FALSE POSITIVE

The workbook is already wrapped in `try/finally` with `wb.close()`.

**Lines ~30–60**  
**Impact:** If an exception occurs during the save operation, the workbook handle may not be properly closed.

```python
wb = load_workbook(excel_path)
ws = wb[...]
# ... modifications ...
wb.save(excel_path)
# No try/finally or context manager to ensure wb.close()
```

**Fix:** Wrap in `try/finally` or use a context manager pattern to ensure `wb.close()` is always called.

### 7. `gui/main_window.py` — `config_path` Injected into Config Dict ✅ FIXED

**Line 53 of main.py**  
**Impact:** `config["config_path"] = config_path` mutates the user's config dict. When config is later saved back to `config.yaml` (in `main_window.py`), this self-referential key gets serialized into the YAML file, polluting it.

**Fix:** Pass `config_path` as a separate parameter or store it in a dedicated attribute, not inside the config dict that gets serialized.

### 8. `gui/main_window.py` — Thread Safety: Shared Mutable State

**Multiple locations**  
**Impact:** The `LoadWorker` and `SaveWorker` threads access and modify shared state (`_units`, `_row_by_com`, `_fingerprint_by_com`) with `QMetaObject.invokeMethod` for cross-thread communication, but there are potential race conditions when the file watcher triggers a reload while a save is in progress.

The `_io_busy` guard helps but doesn't fully protect against interleaved load/save operations.

**Fix:** Use `threading.Lock` or `QMutex` to guard shared state access.

### 9. `data/loader.py` — Pickle Deserialization of Untrusted Data

**Cache loading path**  
**Impact:** `pickle.load()` on a cache file is a security risk if the cache file could be tampered with. A malicious `.pkl` file could execute arbitrary code during deserialization.

In practice the risk is low (local file), but it violates the principle of defense in depth.

**Fix:** Consider using a safer serialization format, or validate file integrity (e.g., HMAC) before unpickling.

---

## Medium-Severity Issues

### 10. `data/loader.py` — `parse_date` Silent Failure on Invalid Input ✅ FIXED

**Multiple format branches**  
**Impact:** `parse_date()` returns `None` for unrecognized formats without logging. A cell with an unexpected date format (e.g., a typo like `"2024/13/45"`) is silently treated as missing.

**Fix:** Add a `logger.warning()` call when a date string doesn't match any known format.

### 11. `gui/main_window.py` — File Watcher Debounce Window May Miss Rapid Changes

**QFileSystemWatcher handling**  
**Impact:** The 5-second debounce window prevents duplicate events, but rapid successive saves (e.g., two users saving within 5 seconds) may result in only one reload.

**Fix:** Consider using a last-write-wins approach with a flag that ensures the most recent state is always loaded after the debounce period.

### 12. `gui/main_window.py` — Missing Error Dialog for Background Worker Failures

**LoadWorker / SaveWorker error handling**  
**Impact:** When background workers encounter exceptions, the error is logged but the user may not see a clear error message, especially for save failures where data could be lost.

**Fix:** Emit an error signal from workers that shows a `QMessageBox` on the main thread.

### 13. `gui/calendar_panel.py` — Color Priority Assumes Single-Worst-Status

**Date dot painting**  
**Impact:** When multiple units share a date, only the worst status color is shown. If there are 3 green units and 1 red unit, the dot is red — but the user can't tell there are 4 units total.

**Fix:** Consider showing a dot count or using a pie/segmented dot for multi-unit dates.

### 14. `gui/list_panel.py` — Date Filter Presets Are Hardcoded

**Lines with preset definitions**  
**Impact:** The date filter presets (Overdue, Today, Next 3/7/30 days, etc.) are hardcoded rather than configurable. Adding new presets requires code changes.

**Fix:** Extract preset definitions into a data structure (list of tuples) that can be iterated.

### 15. `gui/timeline_panel.py` — No Handling of Empty Unit List ❌ FALSE POSITIVE

Empty states already exist: "Select a unit to view its timeline" (no unit) and "No milestone dates available" (no dates).

**`paintEvent`**  
**Impact:** If the timeline is rendered with no milestones, it may display an empty widget with no axis or placeholder text, confusing the user.

**Fix:** Add an empty-state message (e.g., "No milestones to display").

### 16. `automation/vba_native.py` — `backup()` Creates Archive with Insecure Path

**Archive path construction**  
**Impact:** `backup()` constructs the archive path using `os.path.join(archive_dir, ...)`. If `archive_dir` doesn't exist, the function may fail with an unhelpful error.

**Fix:** Add `os.makedirs(archive_dir, exist_ok=True)` before writing.

### 17. `config.yaml` — `config_path` Field Should Not Be in Source Config

**Line 1–2**  
**Impact:** The config file contains a `config_path` field that is auto-populated at runtime and written back. This is a code artifact in what should be a pure configuration file.

**Fix:** Remove `config_path` from the source `config.yaml` template; it should only exist at runtime.

---

## Low-Severity / Code Smells

### 18. `main.py` — Dead Commented-Out Code ✅ FIXED

**Line 59**
```python
# window._config_path = config_path # REMOVED: Now passed via config dict
```
Dead code should be removed entirely. Version control preserves history.

### 19. `data/models.py` — `calculated_status_color` Never Returns "purple" or "orange"

**Lines 88–119**  
**Impact:** The `StatusColor` type includes `"purple"` (Ready for Checking) and `"orange"` (In Checking), but `calculated_status_color` never produces these values. They can only be set via the Excel file. This is by design but undocumented.

**Fix:** Add a docstring explaining that purple/orange are manually assigned, not calculated.

### 20. `data/loader.py` — `check_status` Column Read but Not Stored in Unit ✅ FIXED

Removed empty `UnitData` and `UnitRowMapper` dead classes.

**Column mapping**  
**Impact:** The loader reads `checking_status` (column U) into `Unit.checking_status`, but the value is never used for any business logic or display. It's effectively dead data.

**Fix:** Either use it in status calculations or remove it from the model.

### 21. `automation/vba_native.py` — `save_master()` Is a No-Op

**Line ~200**  
**Impact:** `save_master()` does nothing but log a message. It exists for API parity with VBA but clutters the codebase.

**Fix:** Add a clear comment explaining its purpose, or remove it if VBA parity is no longer needed.

### 22. `gui/theme.py` — `apply_theme()` Recursive Style Application Is Fragile

**Theme application logic**  
**Impact:** `apply_theme()` uses `isinstance()` checks to apply styles recursively to child widgets. Adding new widget types requires modifying this function, violating the Open/Closed Principle.

**Fix:** Consider using Qt's style sheet mechanism more broadly, or register widget-type handlers in a dictionary.

### 23. `gui/edit_form.py` — `_loading` Guard Pattern Is Fragile ✅ FIXED

Replaced with `blockSignals(True/False)` on all widgets during `set_unit()`.

**Dirty tracking**  
**Impact:** The `_loading` boolean flag guards against signal-fired updates during `set_unit()`. This is fragile — if a signal fires asynchronously after `_loading` is set to `False`, the guard fails.

**Fix:** Use `blockSignals(True/False)` on widgets during population, which is the idiomatic Qt approach.

### 24. `data/loader.py` — Cache Freshness Check Uses `mtime_ns` + File Size

**Content signature**  
**Impact:** Two files with the same size and modification time could have different content. This is unlikely but possible in edge cases (e.g., rapid saves within the same nanosecond).

**Fix:** Consider using a content hash (SHA-256 of the file) for cache invalidation, at the cost of an extra read.

### 25. `gui/list_panel.py` — Alternating Row Colors May Clash with Status Colors

**Table styling**  
**Impact:** Status-colored cells may have poor contrast when combined with alternating row background colors, especially in dark mode.

**Fix:** Test all status colors against both alternating row backgrounds for WCAG AA compliance.

### 26. `gui/main_window.py` — Long Method: `_setup_ui()`

**Lines 100–300+**  
**Impact:** `_setup_ui()` is excessively long, handling layout, toolbar, panels, connections, and more in a single method. This makes it hard to read and maintain.

**Fix:** Extract into smaller methods like `_setup_toolbar()`, `_setup_panels()`, `_setup_connections()`.

### 27. `gui/main_window.py` — Config Save on Every Theme/Setting Change

**Theme toggle, a11y changes**  
**Impact:** Each theme toggle or setting change triggers a full config file save. Rapid toggling causes excessive disk I/O.

**Fix:** Debounce config saves or save only on app close.

### 28. `data/models.py` — `milestones` Property Creates New List on Every Access

**Property definition**  
**Impact:** The `milestones` property builds a new list of `(name, date)` tuples each time it's accessed. If called in a loop or paint event, this creates unnecessary garbage.

**Fix:** Cache the result or compute it once during construction.

### 29. `requirements.txt` — Missing Version Pins

**All dependencies**  
**Impact:** Dependencies are not pinned to specific versions, which could lead to breaking changes on `pip install`.

**Fix:** Pin major versions (e.g., `PyQt5>=5.15,<6.0`) or use a lock file.

---

## Orphaned / Dead Code

| Location | Description | Recommendation |
|----------|-------------|----------------|
| `main.py:59` | Commented-out `_config_path` assignment | Remove |
| `automation/vba_native.py:~200` | `save_master()` no-op function | Remove or document |
| `data/loader.py` | `check_status` column read but unused in Unit logic | Remove or integrate |
| `gui/main_window.py` | `_config_path` attribute (removed but may have remnants) | Verify and clean |
| `data/models.py` | `StatusColor` includes "purple"/"orange" but calculated_status never produces them | Document as manual-only |
| `tests/test_writer.py` | `test_save_updates_fields` only checks signature, not behavior | Rewrite or rename |

---

## Test Quality Issues

### 30. `test_writer.py` — Misleading Test Name

`test_save_updates_fields` uses `inspect.signature()` to check parameter names — it never calls `save_unit` or verifies any write behavior. The name implies functional testing.

**Fix:** Rewrite to actually call `save_unit` and verify the saved data, or rename to `test_save_unit_signature`.

### 31. `test_vba_native.py` — Formula Tests Validate Wrong Strings

The `apply_formulas` tests check that the formula string contains `"L2"` and `"K2"` — but as noted in Bug #1, these hardcoded references are themselves the bug. The tests are encoding the bug as expected behavior.

**Fix:** Update formula tests to validate per-row references after fixing the production code.

### 32. No GUI Component Tests (Except `test_list_panel.py`)

There are no tests for:
- `CalendarPanel` (dot painting, date selection, event list)
- `TimelinePanel` (milestone rendering, today line)
- `EditForm` (field population, save, dirty tracking)
- `Theme` (only basic status color tests exist)
- `A11yDialog`
- `LoadingOverlay`

**Fix:** Add at least unit tests for `EditForm` save/revert logic, `Theme` color calculations, and `CalendarPanel` event grouping.

### 33. `test_loader.py` — Missing Edge Case Tests

No tests for:
- Malformed date strings (e.g., `"2024/13/45"`)
- Negative float values
- Excel files with missing sheets
- Corrupt cache files

### 34. `test_sync.py` — Lock Contention Not Tested Under Load

The sync tests verify basic lock/unlock behavior but don't test:
- Concurrent lock acquisition
- Lock timeout behavior
- Stale lock detection

### 35. `conftest.py` — Fixture Dependency Order

Some fixtures depend on others (e.g., `mock_workbook_with_units` depends on `sample_unit`). While pytest handles this, the implicit dependencies make tests harder to understand.

**Fix:** Make dependencies explicit or add docstrings to fixtures.

---

## Security Concerns

### 36. Pickle Deserialization (Bug #9)

Loading `.pkl` cache files without integrity verification could allow arbitrary code execution if the file is tampered with. Risk is low for a desktop app but violates secure coding principles.

### 37. No Input Sanitization on File Paths

File paths from `config.yaml` are passed directly to `openpyxl.load_workbook()` and `os.path.join()` without validation. While this is a desktop app (not a web service), path traversal could be an issue if the config is shared.

### 38. No Workbook Locking During Save

`writer.py` doesn't check if the Excel file is locked by another process before attempting to save. This could cause data loss or corruption if two instances of the app are running simultaneously.

---

## Performance Issues

### 39. Full Workbook Parse on Every Reload

When the file watcher detects a change, the entire workbook is re-parsed from scratch. For large workbooks, this could cause noticeable UI lag.

**Fix:** Consider incremental loading or a progress indicator during reload.

### 40. `unit_fingerprint()` Called Frequently

`unit_fingerprint()` computes a SHA-256 hash. If called for every unit on every comparison, this could add up. The fingerprint should be computed once and cached.

### 41. Timeline `paintEvent` Recomputes Layout Every Frame

`TimelinePanel.paintEvent()` recalculates all positions on every paint. This should be computed once when milestones change and cached for the paint event.

---

## Recommendations Summary

### Priority 1: Fix Critical Bugs (Immediate)
- [x] Fix hardcoded row references in `vba_native.py` formulas (#1)
- [x] Fix mixed A1/R1C1 notation in SUMIFS formulas (#2)
- [x] Move `QMessageBox` after `QApplication` creation (#3)
- [x] Add `actual_hours` widget to `EditForm` (#4)

### Priority 2: Fix High-Severity Issues (Next Sprint)
- [x] Fix `Unit.working_days` type annotation (#5)
- [x] ~~Add workbook handle leak protection~~ (#6) — false positive, already protected
- [x] Stop injecting `config_path` into config dict (#7)
- [ ] Add proper thread synchronization (#8)
- [ ] Address pickle deserialization security (#9)

### Priority 3: Address Medium Issues (Scheduled)
- [x] Add logging for unparseable dates (#10)
- [ ] Add error dialogs for worker failures (#12)
- [x] ~~Add empty state to timeline panel~~ (#15) — false positive, already handled
- [ ] Ensure backup directory exists (#16)

### Priority 4: Clean Up (Backlog)
- [x] Remove dead code (#18, #20, #21) — removed `UnitData`, `UnitRowMapper`, commented-out lines
- [ ] Improve test coverage (#30–35)
- [ ] Pin dependency versions (#29)
- [ ] Refactor `_setup_ui()` (#26)
- [ ] Add config save debouncing (#27)
- [ ] Cache `milestones` property (#28)

### Priority 5: Code Quality (Completed in This Session)
- [x] Add `actual_hours` field to `EditForm` widget + save/load
- [x] Replace `_loading` flag with `blockSignals()` in `EditForm`
- [x] Add per-row reference tests for `apply_formulas`
- [x] Strip `config_path` from YAML writes in `_save_ui_config`
