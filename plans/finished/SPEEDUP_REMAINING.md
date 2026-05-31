# Speedup Project — Implementation Status & Remaining Specs

## Already Implemented ✅

| # | Strategy | Status | Location |
|---|----------|--------|----------|
| 4a | QThread for loading | ✅ Done | `LoadWorker(QThread)` in `gui/main_window.py` |
| 4b | QThread for saving | ✅ Done | `SaveWorker(QThread)` in `gui/main_window.py` |
| 1b | Pickle + CSV dual cache | ✅ Done | `data/loader.py` — `_load_units_from_pickle()` fast path, `_load_units_from_csv()` fallback, `_cache_is_fresh()` mtime check |
| 6a | File watcher | ✅ Done | `QFileSystemWatcher` in `gui/main_window.py` `_setup_file_changed()` + coalescing + readiness polling (the fix we just applied) |

## Remaining Items — Grouped by Effort & Volatility

---

### Group A: Low Effort, Low Volatility (safe wins)

These are straightforward additions that don't change existing file formats or data flow.

#### A1. Scheduled Auto-Refresh
**Effort:** ~0.25 day | **Risk:** Low

Add a background timer that periodically refreshes data (configurable interval, default 5 min). User never has to manually click Refresh when the Excel file changes externally.

**Spec:**
- Add `QTimer` in `MainWindow.__init__` that fires every N minutes
- Calls `_load_data_async(force_reload=True)` on tick
- Configurable via `config.yaml` → `ui.auto_refresh_minutes` (0 = disabled, default 5)
- Pause timer while a manual load/save is in progress (avoid conflicts)
- Status bar shows "Auto-refresh: 5min" indicator when active

#### A2. Loading Spinner / Skeleton State
**Effort:** ~0.25 day | **Risk:** Low

Show visual feedback while background load is in progress instead of just "Loading..." text.

**Spec:**
- Replace `status_bar.showMessage("Loading...")` with a proper loading indicator
- Options: animated spinner widget, or semi-transparent overlay with "Loading..." centered
- Disable the UI (buttons, table interaction) while loading to prevent race conditions
- Re-enable on `_on_load_finished` or `_on_load_error`
- Simple approach: set `setEnabled(False)` on central widget during load, show `QLabel("Loading...")` overlay

#### A3. Refresh Cooldown / Debounce
**Effort:** ~0.1 day | **Risk:** Low

Prevent rapid-fire refreshes from the Refresh button.

**Spec:**
- Disable the Refresh button for 3 seconds after each click
- Show countdown tooltip ("Refresh ready in 2s...")
- Applies to both the Refresh button and the file watcher path
- No config needed — just a simple `QTimer`-based cooldown on the button

---

### Group B: Medium Effort, Low Volatility (new capabilities)

These add new features without changing the existing data model or file formats.

#### B1. Direct ZIP/XML Save (Strategy 2a)
**Effort:** ~0.5 day | **Risk:** Low-Medium

Bypass openpyxl entirely on save. Modify the xlsx's inner XML directly via `zipfile` + `lxml`. Expected 5-10x faster save for large files.

**Spec:**
- New function `data/fast_writer.py` → `save_unit_fast(excel_path, unit, sheet_name)`
- Open the `.xlsm` as a ZIP with `zipfile.ZipFile`
- Extract only `xl/worksheets/sheet1.xml` → parse with `lxml`
- Find row by COM number, modify cells in-place
- Repack the ZIP and write back
- Fallback to existing `save_unit()` if the fast path fails (sheet not found, etc.)
- No changes to the `SaveWorker` — it just calls the new function
- Cache update still uses `save_csv_cache` as before

#### B2. Two-Tier Cache (Strategy 3b)
**Effort:** ~0.5 day | **Risk:** Medium

Keep a "light" cache with just COM number + due date + status for the calendar. Load full unit details only when a unit is selected. Faster startup for large datasets.

**Spec:**
- On Excel load, create two cache files:
  - `*_light.pkl`: `list[dict]` with `{com, due_date, status_color, detailer}` only
  - `*_full.pkl`: complete `list[Unit]` (current behavior)
- Calendar only needs the light cache → loads faster
- When user selects a unit, load full details from the full cache
- `load_units()` returns both tiers
- UI changes: calendar panel reads from light tier, edit form reads from full tier
- If full cache is stale, rebuild both from Excel

#### B3. Checksum-Based Refresh Skip (Strategy 6b)
**Effort:** ~0.25 day | **Risk:** Low

Before reloading, compute a fast checksum of the file. Skip reload if unchanged.

**Spec:**
- Before `_load_data_async(force_reload=True)` from the file watcher, compute `xxhash` or `hashlib.md5` of the file
- Compare to `_last_file_checksum` stored on `MainWindow`
- If identical → skip reload entirely (file changed but content didn't — e.g., just the mtime)
- Only compute checksum if `force_reload=False` (user-initiated reloads always reload)
- Config: `ui.smart_refresh: true` (default) to enable checksum comparison

---

### Group C: Medium Effort, Medium Volatility (data flow changes)

These modify how data flows through the app. Tests need updating.

#### C1. SQLite Cache (Strategy 1c)
**Effort:** ~1 day | **Risk:** Medium

Replace Pickle/CSV cache with SQLite. Enables typed columns, partial queries, and incremental updates.

**Spec:**
- New `data/sqlite_cache.py` module
- Table schema mirrors `Unit` datatypes (text, real, date columns)
- `save_to_sqlite(path, units)` — bulk insert/replace
- `load_from_sqlite(path, date_range=None)` — partial loading by date
- On `save_unit()`, update only the changed row in SQLite (not full rewrite)
- Migration: if SQLite cache doesn't exist, create from Pickle/CSV on first load
- Keeps the same `_cache_is_fresh()` mtime check (SQLite file vs Excel file)
- Remove CSV cache path entirely in v2 (keep Pickle as emergency fallback)

#### C2. XLSM Save Optimization — Write-Only Mode (Strategy 2d)
**Effort:** ~0.5 day | **Risk:** Medium

Use openpyxl's `write_only=True` mode for saves. This avoids loading the full workbook into memory — we write only the changed cells.

**Spec:**
- Modify `data/writer.py` → `save_unit()` to support two modes:
  - `mode="full"` (current) — reads entire workbook, modifies, saves
  - `mode="write_only"` — creates a minimal new workbook with just the changed row
- On `mode="write_only"`, we still need to read the original to preserve other rows
- Actually, the better approach: use `openpyxl` in `read_only=True` mode to find the row, then use a simple `openpyxl` write to a temp file, then swap
- This is more of a save Band-Aid — the real win is B1 (ZIP/XML direct write)

---

### Group D: High Effort, High Volatility (significant restructure)

These are larger architectural changes. Defer until quick wins are validated.

#### D1. Separate Data from Presentation (Strategy 5a)
**Effort:** ~2 days | **Risk:** High

Keep a clean `.xlsx` for the app, separate `.xlsm` for human reports.

**Spec:**
- Add config: `excel_data_path` (clean .xlsx) and `excel_report_path` (original .xlsm)
- App reads from `excel_data_path` on startup
- On Pull Data, sync to `excel_data_path` and optionally copy to `excel_report_path`
- Update `load_units()` and `save_unit()` to use `excel_data_path`
- If `excel_data_path` not set, fall back to `excel_path` (backward compatible)
- This is the single biggest performance win long-term but requires process changes

#### D2. Lazy Loading with SQLite + Pagination (Strategies 3a + 3d)
**Effort:** ~1.5 days | **Risk:** High

Only query units needed for the current view. Load more on scroll/navigation.

**Spec:**
- Requires SQLite cache (C1) as prerequisite
- Calendar: only load units with due dates in the visible month ± 1 month
- List: load first 100 units, paginate on scroll
- "Show All" button triggers full load
- `_on_load_finished` replaced with `on_load_finished_partial(count)`
- UI shows "Showing 47 of 1203 units" with a "Load more" button
- Significant refactor to `CalendarPanel` + `ListPanel` data flow

#### D3. Vectorized Status Calculation (Strategy 4c)
**Effort:** ~0.5 day | **Risk:** Medium

Replace per-unit Python `calculated_status_color` loop with vectorized numpy/pandas operations.

**Spec:**
- In `data/loader.py`, after loading all units into a list, compute status colors in bulk
- Convert to a pandas DataFrame or numpy arrays for `percent_complete`, `department_hours`, `detailing_due_date`
- Compute `calculated_status_color` for all rows at once using vectorized conditions
- Only beneficial for large datasets (>500 units)
- Add `import numpy as np` and `import pandas as pd` to requirements.txt
- Fallback to per-unit loop if numpy not available

---

## Recommended Execution Order

| Phase | Items | Total Effort | Rationale |
|-------|-------|-------------|-----------|
| **Phase 1** (today) | A1 + A2 + A3 | ~0.6 day | Immediate UX wins, zero risk |
| **Phase 2** (this week) | B3 + B1 | ~0.75 day | Speed wins, low volatility |
| **Phase 3** (next) | B2 + C1 | ~1.5 days | Architectural improvements |
| **Phase 4** (defer) | D1 + D2 + D3 | ~4 days | Major restructure, validate need first |

---

*Analysis generated: 2026-05-30*
*Based on: plans/SPEEDUP_PROJECT.md + codebase audit*
