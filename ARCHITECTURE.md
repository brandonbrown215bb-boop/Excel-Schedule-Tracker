# Architecture Overview

## 1. Project Purpose
A desktop application (PyQt5) for viewing and editing schedule data stored in an Excel workbook. The app loads configuration from `config.yaml`, presents the data in a GUI with a calendar view and/or list view, milestone timeline, and editable form, and provides a set of Python-implemented pipelines that replace the original VBA/COM macros. All heavy operations run in background threads. The app supports theme toggling (light/dark), colorblind mode (protanopia/deuteranopia/tritanopia), high-contrast mode, and optional multi-user sync.

## 2. High-Level Components

| Component | Language / Tech | Role |
|-----------|----------------|------|
| **main.py** | Python | Application entry point; loads config, creates the Qt application and the main window. |
| **gui/main_window.py** | Python (PyQt5) | MainWindow: assembles calendar/list toggle + timeline + edit form + automation bar; manages a `QSplitter` for layout with state persisted in `config.yaml` (`ui.splitter_sizes`); background workers; file watcher; multi-user sync; theme/a11y |
| **gui/calendar_panel.py** | Python (PyQt5) | CalendarPanel: custom QCalendarWidget with colored date dots, event list, "Show All" and "Today" buttons. |
| **gui/list_panel.py** | Python (PyQt5) | ListPanel: sortable/filterable QTableWidget of units with composable filters, column chooser dialog. |
| **gui/timeline_panel.py** | Python (PyQt5) | TimelinePanel: horizontal milestone bar, date axis, "TODAY" line. |
| **gui/edit_form.py** | Python (PyQt5) | EditForm: scrollable form for all Unit fields; `detailer` field is a `QComboBox` populated from `config.yaml`; status is auto-computed (no status field in form); dirty tracking; save/revert; emits `saved` signal. |
| **gui/theme.py** | Python (PyQt5) | Theme definitions (light/dark), CVD-safe adjustments (protanopia/deuteranopia/tritanopia), status shape icons, stylesheet applicator. |
| **gui/a11y_dialog.py** | Python (PyQt5) | A11yDialog: modal for colorblind mode selection and high contrast toggle. |
| **data/models.py** | Python | Data models: `Unit` dataclass, `StatusColor` type, status color calculation, working days helper. |
| **data/loader.py** | Python | `COLUMN_MAP`, Excel parsing, dual Pickle/CSV caching with mtime + content signature staleness check, `WorkbookCache`, `unit_fingerprint`, date filtering, rescue path. |
| **data/writer.py** | Python | `find_row_by_com`, `save_unit` (write Unit back to Excel with percent formatting), `_safe_save_workbook` (atomic save with .bak backup). |
| **automation/csv_sync.py** | Python | `pull_and_sync` — delegates to `move_data_in`. |
| **automation/vba_runner.py** | Python | `run_macro` + `MACRO_DISPATCH` table. |
| **automation/vba_native.py** | Python | Pure-Python macro implementations: `move_data_in`, `coms_into_list`, `apply_formulas`, `backup`, `save_master`. |
| **sync/lock_manager.py** | Python | File-level locking for multi-user coordination. |
| **sync/revision_store.py** | Python | Revision tracking for optimistic conflict detection. |
| **config.yaml** | YAML | Central configuration. |
| **requirements.txt** | — | Python dependencies. |

## 3. Pipelines & Data Flow

### 3.1. Application Startup
1. `main.py` determines the application base path (supports PyInstaller bundles via `sys.frozen`).
2. Loads `config.yaml` and validates it is a dict.
3. Creates `QApplication` and `MainWindow(config)`.
4. `MainWindow.__init__` builds the UI (calendar/list toggle, timeline, edit form, automation bar, theme/a11y buttons).
5. Sets up `QFileSystemWatcher` to auto-refresh when the Excel file changes.
6. Starts `LoadWorker` (a `QThread`) to load units in the background.

### 3.2. Data Loading (`data/loader.py`)
1. **Fast path**: If `*_cache.pkl` exists and is fresh (mtime >= Excel mtime AND embedded mtime_ns/size signature matches current file) → deserialize with `pickle.load()` → apply current date filter → return.
2. **Fallback path**: If `*_cache.csv` exists and is fresh → parse CSV rows → create Units → save Pickle cache for next time.
3. **Slow path**: Open Excel with `openpyxl` (`read_only=True, data_only=True, keep_vba=False`) → iterate rows → parse dates/floats → filter by date range (±90 days to +365 days) → save both caches.
4. **Rescue path**: If Excel is unreadable (corrupt/locked), fall back to any available cache with a warning.

Units receive a `working_days` schedule from `config.yaml`'s `detailer_schedules` dict at load time. Each unit gets a `fingerprint` (SHA-256 hash of editable fields) and `excel_row` index for fast saves.

### 3.3. GUI Interaction (`gui/main_window.py`)
- **View toggle**: Calendar/List toggle buttons switch between CalendarPanel and ListPanel via QStackedWidget; saved to config as `ui.last_view`.
- **Unit selection**: Calendar date click, event list click, or list panel row click → `on_unit_selected()` → updates timeline + edit form.
- **Save**: Edit form emits `saved` signal → `on_save_unit()` caches in-memory → spawns `SaveWorker` thread → `save_unit()` writes to Excel → caches rewritten → calendar/list refreshed.
- **Refresh**: "Refresh" button → `_load_data_async(force_reload=False)`.
- **Reload Excel**: "Reload Excel" button → `_load_data_async(force_reload=True)` (bypasses cache).
- **CSV Pull**: "Pull CSV" button → file dialog for source → confirmation → `pull_and_sync(source, target)` → auto-reload.
- **Macro Run**: Dropdown selection → `run_macro(path, name)` → dispatched to pure-Python implementation.
- **File watcher**: `QFileSystemWatcher` auto-reloads data when the Excel file changes (non-blocking polling for file readiness, debounced to avoid duplicate events within 5 seconds, IO-busy guard prevents loops).
- **Multi-user sync**: Optionally enabled via `config.yaml` `multi_user.enabled`; `SaveWorker` acquires locks and commits revisions.
- **Theme**: Toggle dark/light via button or Ctrl+T; accessibility dialog for CVD + high contrast.
- **Keyboard shortcuts**: Ctrl+S (save), Ctrl+T (toggle theme), F5 (refresh), Ctrl+F (focus search in list panel), Escape (clear selection).

### 3.4. CSV Synchronisation Pipeline (`automation/csv_sync.py` → `automation/vba_native.py`)

`pull_and_sync(source_path, target_path)` → `move_data_in(source_path, target_path)`:

1. **Read** `SCHDetailingReport` sheet from source workbook (read-only mode).
2. **Clear** existing data in target's `Unedited Report` sheet (keep header).
3. **Write** source rows to `Unedited Report` with date formatting on columns 1 and 7.
4. **Merge** into `Current List` via `coms_into_list()`:
   - Build COM number lookup for existing rows (column C).
   - For each unedited row: update existing (shift old date → col B) or append new.
   - Apply formulas to all rows via `apply_formulas()`.
5. **Backup** via `backup()` — copy to `Archive/YYYY-MM-DD_<name>.xlsm`.

### 3.5. VBA-Like Macro Runner (`automation/vba_runner.py`)
- `run_macro(excel_path, macro_name)` looks up `MACRO_DISPATCH`.
- Registered macros: `COMs_into_List`, `Backup`, `Save`, `ApplyFormulas`.
- Unknown macros: print warning, return silently (no exception).

### 3.6. Data Persistence (`data/writer.py`)
- `find_row_by_com(ws, com_number)` — scans column **C** (COM Number) for a matching value; returns the row index or `None` if not found.
- `save_unit(excel_path, unit, sheet_name="Sheet1")` —
    1. Loads the workbook with `keep_vba=True` (preserves any VBA macros).
    2. Determines the correct row (uses the `excel_row` cached on the `Unit`, falls back to a lookup via `find_row_by_com`).
    3. Writes each field defined in `COLUMN_MAP` using the values from the `Unit` instance. The `percent_complete` field is stored as a **decimal fraction** (e.g., `0.75` for 75 %) and the cell number format is set to a percentage (`"0%"`). All other numeric fields are written as raw floats.
    4. Persists the workbook atomically via `_safe_save_workbook`, which writes to a temporary file and then replaces the original, creating a `.bak` backup if the target already existed.

**Note**: `save_unit` opens/closes the full workbook each time (read-modify-write). This is the main save performance bottleneck.

### 3.7. Status Color Calculation (`data/models.py`)
- `calculated_status_color` property on `Unit`:
  - `percent_complete >= 100` → green
  - No due date: 0% → gray, else → yellow
  - Past due → red
  - Capacity check: if `remaining_hours > working_days × 10 hrs/day` → red
  - Otherwise → yellow
- Purple and orange statuses are set manually (read from Excel, not auto-computed).

### 3.8. Multi-User Sync (`sync/`)
- Optional feature enabled via `config.yaml` `multi_user.enabled`.
- **LockManager**: File-level locking for coordinated writes; supports `write_lock()` and `commit_lock()` context managers.
- **RevisionStore**: Tracks per-COM revision numbers for optimistic conflict detection.
- **SaveWorker** integration: When activated, the save pipeline acquires commit lock and write lock, saves to Excel, then commits the revision.
- **Fallback behavior**: If sync initialization fails and `fallback_mode` is `"block"`, saves are disabled. If `"warn"`, saves proceed without sync.
- **Owner identity**: Built from `username@machine`.

## 4. Configuration (`config.yaml`)

```yaml
excel_path              # Path to the .xlsm workbook
sheet_name              # Sheet to read/write
unedited_reports_dir    # File dialog default directory for pull source
csv_output_dir          # Intermediate CSV output directory
pull_macros             # Macros run after pull (ordered list)
macros                  # Macros available in GUI dropdown
default_detailers       # Recognized detailer names
detailer_schedules      # Detailer → working weekdays (0=Mon … 4=Fri)
status_labels           # Color key → display label
multi_user:
  enabled               # bool: enable multi-user sync
  fallback_mode         # "block" or "warn"
  machine               # optional machine name override
  username              # optional username override
config_path             # (Internal) Absolute path to loaded config.yaml
ui:
  theme                 # "light" or "dark"
  colorblind_mode       # "none", "protanopia", "deuteranopia", "tritanopia"
  high_contrast         # true or false
  last_view             # "calendar" or "list"
  splitter_sizes        # List of integers for QSplitter sizes
  list_sort_column      # Column key for list view sort
  list_sort_ascending   # Boolean for sort direction
  list_visible_columns  # List of column keys visible in list view
```

## 5. Testing

The project uses **pytest** with test coverage via **pytest-cov**. Tests live under `tests/`:

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures (mock workbooks, sample Units, temp dirs)
├── test_models.py        # Unit dataclass, status colors, _working_days_between
├── test_loader.py        # COLUMN_MAP, parse_date, parse_float, cache paths/freshness
├── test_writer.py        # find_row_by_com, save_unit with real .xlsx files
├── test_vba_runner.py    # MACRO_DISPATCH table, run_macro dispatch, pull_and_sync
├── test_vba_native.py    # backup, apply_formulas, coms_into_list, move_data_in
├── test_list_panel.py    # UnitListModel filters/sort, ListPanel widget
├── test_sync.py          # Multi-user sync tests (lock_manager, revision_store)
├── test_theme.py         # Theme/CVD tests (status colors, get_status_colors, status_style)
└── test_imports.py       # Module import verification
```

Detailed test structure and conventions are documented in `AGENTS.md`.

## 6. Extensibility & Future Work

- **Add new pipelines**: Create additional modules under `automation/` and expose them via CLI wrapper.
- **Direct ZIP/XML save**: Bypass `openpyxl` full load on save by manipulating the `.xlsm` ZIP archive directly (5–10× faster save).
- **Separate data from presentation**: Keep a data-only `.xlsx` for the app, separate report `.xlsm` for humans.
- **SQLite cache**: Replace Pickle/CSV with SQLite for partial queries and lazy loading.
- **Vectorized status computation**: Use `pandas`/`numpy` for batch status color calculation.
- **Testing**: Introduce unit tests for `data.writer`, `data.loader`, and macro runners using mock workbooks.

---

*This overview reflects the actual codebase after inspecting all source files, config, automation modules, sync module, and tests.*