# AGENTS.md

This file describes the project structure, conventions, and guidance for AI agents (and human contributors) working in this codebase.

---

## Project Overview

A PyQt5 desktop application for viewing and editing schedule data stored in an Excel workbook. The app loads configuration from `config.yaml`, presents data in a GUI with a calendar view, list view, timeline panel, and edit form, and runs Python-implemented pipelines that replace the original VBA/COM macros. Load and save operations run in background threads to keep the UI responsive. The app supports theme toggling (light/dark), colorblind mode (protanopia/deuteranopia/tritanopia), high-contrast mode, and optional multi-user sync.

---

## Repository Layout

```
├── main.py                           # Entry point: loads config, creates Qt app and MainWindow
├── config.yaml                       # Central config (Excel paths, sheet names, detailer schedules, macros, UI prefs)
├── requirements.txt                  # Python dependencies
├── UnitTracker.spec                  # PyInstaller spec file
├── pyrightconfig.json                # Pyright type-checker config
├── Makefile                          # Build/run targets
├── pyproject.toml                    # Python project metadata
├── setup.bat                         # Windows setup script
├── setup.sh                          # Unix setup script
├── .gitignore                        # Git ignore rules
├── gui/
│   ├── main_window.py                # MainWindow: calendar/list toggle+timeline+edit form, background workers, automation bar, file watcher, multi-user sync, theme/a11y
│   ├── calendar_panel.py             # CalendarPanel: QCalendarWidget with colored date dots + event list
│   ├── list_panel.py                 # ListPanel: sortable/filterable QTableWidget of units with composable filters
│   ├── timeline_panel.py             # TimelinePanel: horizontal milestone bar with date axis + today line
│   ├── edit_form.py                  # EditForm: editable form for all Unit fields with save/revert
│   ├── theme.py                      # Theme definitions (light/dark), CVD-safe adjustments, status shape icons, stylesheet applicator
│   ├── a11y_dialog.py                # A11yDialog: modal for colorblind mode + high contrast settings
│   └── loading_overlay.py            # LoadingOverlay: semi-transparent spinner overlay during I/O
├── data/
│   ├── loader.py                     # Data loader: COLUMN_MAP, Excel parsing, dual Pickle/CSV caching, date filter, WorkbookCache, unit_fingerprint
│   ├── models.py                     # Data models (Unit dataclass, status color calculation, working days)
│   └── writer.py                     # Persistence helpers (find_row_by_com, save_unit, _safe_save_workbook)
├── automation/
│   ├── csv_sync.py                   # CSV sync pipeline (pull_and_sync → delegates to move_data_in)
│   ├── vba_runner.py                 # Macro dispatch table (run_macro → MACRO_DISPATCH)
│   └── vba_native.py                 # Pure-Python macro implementations (move_data_in, coms_into_list, backup, etc.)
├── sync/
│   ├── __init__.py
│   ├── lock_manager.py               # File-level locking for multi-user coordination
│   └── revision_store.py             # Revision tracking for optimistic conflict detection
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared fixtures (mock workbooks, sample Units, temp dirs)
│   ├── test_models.py                # Unit dataclass, status colors, _working_days_between
│   ├── test_loader.py                # COLUMN_MAP, parse_date, parse_float, cache paths/freshness
│   ├── test_writer.py                # find_row_by_com, save_unit with real .xlsx files
│   ├── test_vba_runner.py            # MACRO_DISPATCH table, run_macro dispatch, pull_and_sync
│   ├── test_vba_native.py            # backup, apply_formulas, coms_into_list, move_data_in
│   ├── test_list_panel.py            # UnitListModel filters/sort, ListPanel widget
│   ├── test_sync.py                  # Multi-user sync tests (lock_manager, revision_store)
│   ├── test_theme.py                 # Theme/CVD tests
│   └── test_imports.py              # Module import verification
├── Archive/                          # Timestamped backup copies created by backup()
├── App/                              # App bundling resources
├── build/                            # PyInstaller build output
├── dist/                             # PyInstaller dist output
└── plans/                            # Development planning documents
```

---

## Architecture Principles

- **Config-driven**: All file paths and sheet names live in `config.yaml`. Never hardcode paths in source files.
- **No COM/VBA dependencies**: All macro logic has a pure-Python equivalent in `automation/vba_native.py`. The `vba_runner.py` dispatch table maps original macro names to these implementations.
- **Separation of concerns**: Colour/status logic belongs in `data/models.py` and is applied by the UI layer. `data/writer.py` does not touch cell colours.
- **GUI is a consumer, not a source of truth**: The UI reads and triggers pipelines; it does not own business logic.
- **Background threading**: Loading and saving run in `QThread` workers (`LoadWorker`, `SaveWorker`) to keep the UI responsive.
- **Smart caching**: Data is cached in both Pickle (fast binary) and CSV (legacy) formats. Cache staleness is checked via `mtime` and content signature (mtime_ns + file size) stored in `WorkbookCache`.

---

## Key Entry Points

| Task | How to invoke |
|------|---------------|
| Launch the GUI | `python main.py` |
| Run the CSV sync pipeline | `python -c "import automation.csv_sync as cs; cs.pull_and_sync('source.xlsm', 'target.xlsm')"` |
| Execute a specific macro | `python -c "import automation.vba_runner as vr; vr.run_macro('myfile.xlsm', 'Backup')"` |
| Run tests | `pytest` or `pytest -v --cov=. --cov-report=term-missing` |

---

## Configuration

`config.yaml` must be present in the same directory as `main.py` (or the bundled binary). It is loaded and validated at startup; the app shows an error dialog and exits if it is missing or malformed.

Key fields expected in `config.yaml`:

| Field | Description |
|-------|-------------|
| `excel_path` | Path to the target `.xlsm` workbook |
| `sheet_name` | Sheet to read/write (default: `"Sheet1"`, typically `"Current List"`) |
| `unedited_reports_dir` | Directory for file dialog when pulling unedited reports |
| `csv_output_dir` | Directory used for intermediate CSV output |
| `pull_macros` | List of macro names run after pulling data (in order) |
| `macros` | List of macro names available in the GUI dropdown |
| `default_detailers` | List of recognized detailer names (first entry = unassigned sentinel) |
| `detailer_schedules` | Dict mapping detailer name → working weekdays (0=Mon … 4=Fri); `"default"` for fallback |
| `status_labels` | Dict mapping color key → human-readable label (gray/yellow/purple/orange/green/red) |
| `config_path` | (Internal) Absolute path to the loaded `config.yaml` file |
| `multi_user` | Dict with `enabled` (bool), `fallback_mode` ("block"/"warn"), `machine`, `username` |
| `ui.theme` | `"light"` or `"dark"` (persisted on app close) |
| `ui.colorblind_mode` | `"none"`, `"protanopia"`, `"deuteranopia"`, `"tritanopia"` (persisted on app close) |
| `ui.high_contrast` | `true` or `false` (persisted on app close) |
| `ui.last_view` | `"calendar"` or `"list"` (persisted on app close) |
| `ui.splitter_sizes` | List of integers for `QSplitter` sizes (persisted on app close) |
| `ui.list_sort_column` | Column key for list view sort (persisted) |
| `ui.list_sort_ascending` | Boolean for sort direction (persisted) |
| `ui.list_visible_columns` | List of column keys visible in list view (persisted) |
| `ui.auto_refresh_minutes` | Auto-refresh interval in minutes (0 = disabled) |

When modifying `config.yaml`, validate structure with:
```bash
python -c "import yaml; d=yaml.safe_load(open('config.yaml')); assert isinstance(d, dict)"
```

---

## Data Model

### `Unit` (`data/models.py`)

A `@dataclass` with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `com_number` | `str` | Unique identifier (column C) |
| `job_name` | `str` | Job name (column F) |
| `contract_number` | `str` | Contract number (column G) |
| `description` | `str` | Description (column H) |
| `detailer` | `str` | Assigned detailer (column E) |
| `checking_status` | `str` | Checking status (column U) |
| `status_color` | `StatusColor` | One of: gray, yellow, purple, orange, green, red |
| `department_hours` | `float` | Dept hours (column K) |
| `target_department_hours` | `float` | Target dept hours (column V) |
| `iec_internal_hours` | `float` | IEC internal hours (column W) |
| `percent_complete` | `float` | 0–100 (column L, stored as decimal in Excel) |
| `actual_hours` | `float` | Actual hours to detail (column N) |
| `working_days` | `list[int]` | Working weekdays for this unit's detailer |
| `unit_detailing_start_date` | `Optional[date]` | (column X) |
| `unit_moved_to_checking_date` | `Optional[date]` | (column Y) |
| `unit_detailing_completion_date` | `Optional[date]` | (column Z) |
| `dept_due_date_previous` | `Optional[date]` | (column B) |
| `detailing_due_date` | `Optional[date]` | (column A) |
| `build_date` | `Optional[date]` | (column I) |
| `excel_row` | `Optional[int]` | (internal) Excel row index for fast saves |
| `fingerprint` | `str` | (internal) SHA-256 hash of editable fields for conflict detection |
| `base_revision` | `int` | (internal) Revision number for multi-user sync |

Key properties:
- `milestones` — ordered list of `(name, date)` tuples for timeline display
- `calculated_status_color` — computed status: green (100%), red (overdue or behind capacity), yellow/gray otherwise; purple/orange are set manually
- `status_label(color)` — static method mapping color key to display text

### `COLUMN_MAP` (`data/loader.py`)

Maps field names to Excel column letters. Central reference for all read/write operations.

### `WorkbookCache` (`data/loader.py`)

Pickle cache payload dataclass that stores:
- `units` — list of Unit objects
- `row_by_com` — dict mapping COM number to Excel row index
- `fingerprint_by_com` — dict mapping COM number to fingerprint hash
- `excel_mtime_ns` — nanosecond mtime of Excel at cache creation
- `excel_size` — file size of Excel at cache creation
- `schema_version` — cache schema version (currently 2)

---

## Data Loading & Caching (`data/loader.py`)

The loader uses a **dual-cache system** for performance:

1. **Fast path**: If a Pickle cache (`*_cache.pkl`) exists and is fresh (mtime >= Excel mtime AND embedded signature matches current file) → deserialize with `pickle.load()` → apply current filter → return.
2. **Fallback path**: If only a CSV cache (`*_cache.csv`) exists and is fresh → parse CSV rows → create Units → save Pickle cache for next time.
3. **Slow path**: Parse the full Excel workbook with `openpyxl` (`data_only=True, keep_vba=False`) → iterate rows → parse dates/floats → filter by date range (±90 days to +365 days) → save both caches.
4. **Rescue path**: If Excel is unreadable (corrupt/locked), fall back to any available cache with a warning.

**Date filtering**: Only units with at least one milestone date within ±90 days to +365 days from today are included. This keeps the UI manageable.

Key functions:
- `load_units(excel_path, sheet_name, detailer_schedules, force_reload)` → `list[Unit]`
- `_cache_is_fresh(excel_path)` → checks Pickle cache mtime + embedded signature vs Excel file
- `save_csv_cache(excel_path, units)` → writes both Pickle and CSV caches
- `unit_fingerprint(unit)` → stable SHA-256 hash of editable fields for conflict detection
- `parse_date(cell_value)` → handles `date`, `datetime`, string (multiple formats), Excel serial numbers
- `parse_float(cell_value)` → safe float parsing with 0.0 default

---

## GUI Components (`gui/`)

### `MainWindow` (`gui/main_window.py`)

- **Layout**: Horizontal `QSplitter` — left panel (CalendarPanel or ListPanel via QStackedWidget) | right panel containing TimelinePanel + EditForm + automation bar
- **View toggle**: Calendar/List toggle buttons; saved to config as `ui.last_view`
- **Splitter Persistence**: QSplitter sizes are saved to `config.yaml` (`ui.splitter_sizes`) and restored on launch.
- **Automation bar**: VBA macro combo box + Run button, Pull CSV button, Refresh button, Reload Excel button
- **File watcher**: `QFileSystemWatcher` auto-reloads data when the Excel file changes (with non-blocking polling for file readiness, debounced to avoid duplicate events within 5 seconds)
- **Keyboard shortcuts**: Ctrl+S (save), Ctrl+T (toggle theme), F5 (refresh), Ctrl+F (focus search), Escape (clear selection)
- **Background workers**: `LoadWorker` (load units async), `SaveWorker` (save unit async + update cache + optional multi-user lock/commit)
- **Multi-user sync**: Optionally enabled via `config.yaml` `multi_user.enabled`; uses `LockManager` and `RevisionStore` from `sync/` module
- **Theme**: Toggle dark/light via button or Ctrl+T; accessibility dialog for CVD + high contrast
- **IO bus**y guard: Prevents overlapping load/save operations and file watcher re-triggers

### `CalendarPanel` (`gui/calendar_panel.py`)

- `EventCalendarWidget` — custom `QCalendarWidget` that paints colored dots on dates with due units
- Color priority: red > orange > purple > yellow > gray > green (worst status wins on multi-unit dates)
- Clicking a date populates the event list below
- "Show All Units" button lists every unit with at least one milestone
- "Today" button jumps to current date
- Supports `set_theme()` for theme-aware dot rendering

### `ListPanel` (`gui/list_panel.py`)

- Sortable/filterable QTableWidget of all units
- Composable filters: Status (combo), Detailer (combo), Due date preset (combo), COM/job name search (debounced text input)
- Date filter presets: All, Overdue, Today, Next 3/7/30 days, This Month, Next Month, Past 30 Days
- Sort by clicking column headers (ascending/descending toggle)
- Column chooser dialog for showing/hiding columns
- Alternating row colors, status-colored cells with shape icons, overdue date highlighting
- Emits `unit_selected(Unit)` signal (same as CalendarPanel) for integration with timeline + edit form
- Used via QStackedWidget in MainWindow (index 1)

### `TimelinePanel` (`gui/timeline_panel.py`)

- `TimelineWidget` — custom QWidget that renders a horizontal status-colored bar
- Milestone rows (alternating backgrounds) with dots, names, and date labels
- Vertical guide lines from bar to each milestone row
- Bottom date axis with monthly tick marks and labels
- Red dashed "TODAY" marker line when today falls within the date range
- Dynamically resizes to fit content

### `EditForm` (`gui/edit_form.py`)

- Scrollable form with fields for all Unit properties
- COM Number is read-only (it's the key)
- Detailer is a `QComboBox` with presets from config (no status field — status is auto-computed)
- Numeric fields use `QDoubleSpinBox` (max 99999, 2 decimal places)
- Date fields use `ClearableDateEdit` (`QDateEdit` with calendar popup and "—" sentinel (2000-01-01); Delete/Backspace clears to sentinel)
- Dirty tracking: any field change marks the form as dirty; unsaved changes prompt confirmation on navigation
- Save + Revert buttons; emits `saved` signal with the updated Unit; emits `dirty_changed` signal

### `Theme` (`gui/theme.py`)

- Two built-in themes ("light" and "dark") with full color token dictionaries
- Status colors per theme (`STATUS_COLORS`) with WCAG AA 4.5:1 verified contrast
- Status shape icons (`STATUS_SHAPES`): ● gray, ◆ yellow, ▲ purple, ■ orange, ✓ green, ✕ red
- CVD-safe overrides for deuteranopia, protanopia, tritanopia
- `get_status_colors()` — single source of truth for theme-aware + CVD-adjusted status colors
- `status_style()` — returns (hex_color, icon, label) for any status level
- `get_badge_style()` — CSS string for inline status badges
- `boost_contrast()` — high contrast mode variant
- `apply_theme()` — recursive stylesheet applicator for all widget types (QPushButton, QTableWidget, inputs, QCalendarWidget, QFrame, QGroupBox)
- `init_labels()` — populates display labels from config.yaml at startup

### `A11yDialog` (`gui/a11y_dialog.py`)

- Modal dialog for colorblind mode selection and high contrast toggle
- Opens from MainWindow's accessibility button (♿)
- Returns selected CVD mode and high contrast state

---

## Pipelines

### CSV Sync (`automation/csv_sync.py`)

- **Function**: `pull_and_sync(source_path, target_path, macros=None)` → row count
- Delegates entirely to `vba_native.move_data_in(source_path, target_path)`
- Note: The `macros` parameter is accepted for call-site compatibility (e.g., from GUI) but ignored — `move_data_in` always runs the full pipeline (coms_into_list + backup).

### Move Data In (`automation/vba_native.py`)

- **Function**: `move_data_in(source_path, target_path)` → row count
- Reads `SCHDetailingReport` sheet from source
- Clears and writes to `Unedited Report` sheet in target
- Calls `coms_into_list(target_path)` to merge into `Current List`
- Calls `backup(target_path)` to create timestamped archive copy
- Returns number of rows imported

### COMs Into List (`automation/vba_native.py`)

- **Function**: `coms_into_list(target_path)` → rows processed
- Merges rows from `Unedited Report` into `Current List` sheet
- Builds COM number lookup for existing rows (column C)
- For each unedited row: update existing (shift old date → col B) or append new
- Calls `apply_formulas(ws_current)` after merge
- Saves and closes the workbook

### Apply Formulas (`automation/vba_native.py`)

- **Function**: `apply_formulas(ws)`
- Sets formulas for columns M (Remaining Hours), R (Weekly Dept Hours Sum), S (Weekly Actual Hours Sum), T (Percentage)
- Applies number formats: L/R/S to 0.00, L/T to percentage, M to 0.00

### Backup (`automation/vba_native.py`)

- **Function**: `backup(target_path)`
- Copies the workbook to `Archive/YYYY-MM-DD_<basename>.xlsm` beside the target

### Save Master (`automation/vba_native.py`)

- **Function**: `save_master(target_path)` — no-op placeholder for API parity with VBA

### Macro Runner (`automation/vba_runner.py`)

- **Function**: `run_macro(excel_path, macro_name)`
- Dispatches via `MACRO_DISPATCH` dict
- Registered macros: `COMs_into_List`, `Backup`, `Save`, `ApplyFormulas`
- Unknown macros log a message and silently skip (no exception)

---

## Multi-User Sync (`sync/`)

Optional feature enabled via `config.yaml` `multi_user.enabled`. When active:

- **LockManager** (`sync/lock_manager.py`): Provides file-level locking for coordinated writes. Supports `write_lock()` and `commit_lock()` context managers.
- **RevisionStore** (`sync/revision_store.py`): Tracks per-COM revision numbers for optimistic conflict detection. `baseline(com_number)` returns the current revision; `commit(com_number, base_revision, fingerprint, owner_id)` creates a new revision if the base matches.
- **SaveWorker** integration: When both lock_manager and revision_store are available, the save pipeline acquires a commit lock and write lock, saves to Excel, then commits the revision with the unit's fingerprint.
- **Fallback behavior**: If sync initialization fails and `fallback_mode` is `"block"`, saves are disabled with a warning. If `"warn"`, saves proceed without sync coordination.
- **Owner identity**: Built from `username@machine` (or config overrides).

---

## Adding New Features

### New pipeline
1. Create a new module under `automation/`.
2. Expose the pipeline as a callable function with a clear signature.
3. Wire it into the GUI via `gui/main_window.py` or a CLI wrapper in `main.py`.
4. Document the new pipeline in this file under the **Pipelines** section.

### New macro
1. Implement the logic in `automation/vba_native.py`.
2. Register the macro name → function mapping in `MACRO_DISPATCH` inside `automation/vba_runner.py`.
3. Add the macro name to the `macros` list in `config.yaml` if it should appear in the GUI dropdown.
4. Add a row to the **Macro Runner** section above.

### New config field
1. Add the field to `config.yaml` with a sensible default or a clear comment.
2. Update validation logic in `main.py` to check for the new field if required at startup.
3. Pass the field through `config` dict to whichever component needs it.

---

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Error dialog on launch, app exits | `config.yaml` missing or not a YAML mapping | Ensure `config.yaml` is next to `main.py`; validate with `yaml.safe_load` |
| `FileNotFoundError` from openpyxl | `excel_path` in `config.yaml` is wrong | Use absolute paths or correct relative paths for the OS |
| `ValueError: COM number X not found` | Data mismatch between UI state and workbook | Re-run the CSV sync pipeline or save to refresh |
| `VBA runner: <name> not implemented` | Macro called with no Python equivalent | Add the implementation to `vba_native.py` and register it in `MACRO_DISPATCH` |
| `ImportError` for PyQt5 / openpyxl | Missing or mismatched dependencies | Run `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'automation.vba_native'` | `vba_native.py` file is missing or renamed | Ensure `automation/vba_native.py` exists (not accidentally renamed) |
| Date fields show 2000-01-01 | Unset sentinel value displayed as date | This is by design — 2000-01-01 represents `None` |
| UI freezes during load/save | Background worker crashed | Check console output for worker error messages |
| Multi-user sync unavailable on startup | LockManager/RevisionStore init failed | Check `sync/` module imports; set `multi_user.enabled: false` in config to disable |

---

## Testing

The project uses **pytest** with test coverage via **pytest-cov**. Tests live under `tests/`.

### Running tests

```bash
# Run all tests
pytest

# Run with verbose output and coverage report
pytest -v --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_models.py -v

# Run only fast tests (skip integration tests)
pytest -m "not integration" -v
```

### Test structure

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

### Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `sample_unit` | A typical Unit with 50% completion, due in 30 days |
| `unassigned_unit` | 0%, no due date — tests gray status |
| `completed_unit` | 100% — tests green status |
| `overdue_unit` | Past due, behind capacity — tests red status |
| `unit_list` | List of all 4 above |
| `mock_workbook` | Minimal openpyxl Workbook with headers |
| `mock_workbook_with_units` | Pre-populated with all sample units |
| `temp_excel_file` | Temporary .xlsx path for writer tests |
| `temp_dir` | `tempfile.TemporaryDirectory()` as Path |

### Adding new tests
- Place test files under `tests/` prefixed with `test_`.
- Use `tmp_path` (built-in pytest fixture) for any file I/O.
- For `save_unit` tests: create a real `.xlsx` via `openpyxl.Workbook` → save → test → reload → assert.
- For mock-based patches: use `unittest.mock.patch` via `automation.vba_runner.<func>`.
- Mark integration tests (those needing the real `.xlsm`) with `@pytest.mark.integration`.
- Mark slow tests with `@pytest.mark.slow`.

---

## Dependencies

Install all dependencies before running:
```bash
pip install -r requirements.txt
```

Core dependencies: `PyQt5`, `openpyxl`, `pyyaml`. Optional: `pywin32` (legacy COM, not used).

---

## Packaging

The app supports PyInstaller bundling (`UnitTracker.spec`). When building:
- Include `config.yaml` as a data file.
- Ensure `config.yaml` lands beside the bundled executable at runtime.
- The base-path detection in `main.py` handles both script and frozen-executable contexts (`sys.frozen`).