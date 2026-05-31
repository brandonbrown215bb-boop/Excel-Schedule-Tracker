# Technical Review: User Stories US-001, US-002, US-002b, US-003, US-004, US-005, US-007, US-018

**Reviewer:** Senior Python/Qt Developer  
**Date:** 2026-05-31  
**Scope:** Technical accuracy, implementation feasibility, architecture fit, risk assessment, point estimation

---

## US-001: Thread Synchronization for Shared Mutable State

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `gui/main_window.py` — `LoadWorker` and `SaveWorker` | Both classes exist at lines 42 and 70 | ✅ Correct |
| `_units`, `_row_by_com`, `_fingerprint_by_com` accessed by both workers | `self.units` exists (line 142). **`_row_by_com` and `_fingerprint_by_com` do NOT exist** in `main_window.py`. These are fields on the `WorkbookCache` dataclass in `data/loader.py` (lines 84–85), not on `MainWindow`. | ❌ **Incorrect variable names** |
| `_io_busy` guard is a boolean flag | `self._io_busy` exists, set via `_set_io_busy()` at line 773–775 | ✅ Correct |

**Correction:** The story says `_units`, `_row_by_com`, `_fingerprint_by_com` are on `MainWindow`. In reality:
- `self.units` is the unit list on `MainWindow` (line 142)
- `_row_by_com` and `_fingerprint_by_com` are fields of `WorkbookCache` in `data/loader.py` (lines 84–85), populated during cache save/load — they are **not** directly accessed by `LoadWorker`/`SaveWorker` in `main_window.py`

The actual shared mutable state in `MainWindow` is `self.units` (replaced atomically in `_on_load_finished` at line 649) and `self._io_busy` (boolean flag).

### 2. Implementation Feasibility

**Partially feasible, but the diagnosis is wrong.**

The story assumes `LoadWorker` and `SaveWorker` directly access `_units`, `_row_by_com`, `_fingerprint_by_com` concurrently. In reality:
- `LoadWorker.run()` calls `load_units()` which returns a **new list** — it doesn't mutate `self.units` in-place. The result is emitted via `pyqtSignal` and applied in `_on_load_finished` on the main thread.
- `SaveWorker.run()` calls `save_unit()` which writes to Excel via `data/writer.py` — it doesn't touch `self.units` at all.
- The `_io_busy` flag already prevents concurrent load/save (lines 624, 705).

**The actual race condition** is subtler: the file watcher can trigger `_load_data_async` while a `SaveWorker` is running, but `_active_save_worker_running()` is checked in `_on_file_changed` (line 708). The `_io_busy` flag is set for loads but **not** for saves (saves don't call `_set_io_busy`). This is a real gap, but it's not the one described in the story.

**QMutex is the wrong tool here.** Since `LoadWorker` and `SaveWorker` don't actually share mutable state on `MainWindow` (the load result is signal-based, and save doesn't touch `self.units`), a mutex would be unnecessary. What's actually needed is:
1. Extend `_io_busy` to cover save operations too, OR
2. Use `_active_save_worker_running()` more consistently in `_load_data_async`

### 3. Architecture Fit

- **Violates "GUI is a consumer" principle:** Adding a `QMutex` to `MainWindow` for state that isn't actually shared would add unnecessary complexity to the GUI layer.
- The existing signal/slot pattern already provides thread-safe data transfer. The real fix is simpler: ensure `_io_busy` covers the save path too.

### 4. Unmentioned Risks

- **QMutex vs QThread deadlock risk:** If a `QMutex` is held on the main thread and a worker tries to acquire it via a signal, you can deadlock the event loop. The story doesn't address this.
- **The story misdiagnoses the problem.** The actual race is: `_io_busy` is not set during saves, so a file watcher event during a save can trigger a concurrent load. The fix is a 2-line change, not a mutex.
- **QMutexLocker in a QThread worker** is unusual — `QMutex` is designed for cross-thread locking on the same thread's event loop, not for `QThread::run()` which has no event loop.

### 5. Point Estimate

**Story says: 8 points**  
**Recommended: 3 points** (if scoped to the actual bug: extend `_io_busy` to cover saves)

The story as written describes a much larger change than what's actually needed. If the story were corrected to match the real bug, it's a small fix. If implemented as described (adding QMutex), it would be 5 points but would be **wrong architecture**.

---

## US-002: Secure Cache Deserialization

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `data/loader.py` — `pickle.load()` on `.pkl` files | Line 294: `pickle.load(f)` in `_load_units_from_pickle()`; Line 381: `pickle.load(f)` in `_cache_is_fresh()` | ✅ Correct |
| `.pkl` files used for caching | `_cache_path()` returns `*_cache.pkl` (line 112) | ✅ Correct |

### 2. Implementation Feasibility

**Feasible, but the HMAC approach (Option A) has a key management problem.**

- **Option A (HMAC):** Where does the HMAC key live? If it's derived from the file path or a hardcoded string, it provides no real security (an attacker who can tamper with the `.pkl` can also read the key). If it's user-provided, it's unusable for a desktop app. **This option is not viable without a key management story.**
- **Option B (JSON):** The CSV cache already exists and is loaded via `_load_units_from_csv()`. Migrating to JSON is straightforward but loses the `row_by_com` and `fingerprint_by_com` metadata that the pickle cache carries. These are used for fast saves and conflict detection.
- **Option C (pickletools):** Correctly identified as limited.

**Better approach:** Use `pickle` with a restricted `Unpickler` that only allows `Unit`, `WorkbookCache`, `list`, `dict`, `str`, `int`, `float`, `date`, `datetime`, `None`, `bool`. This is the standard Python approach (`pickle.Unpickler` with a custom `find_class`). It's simpler than HMAC and more robust than pickletools.

### 3. Architecture Fit

- **No violations.** The change is confined to `data/loader.py`.
- The story's acceptance criterion #5 (≤10% performance impact) is reasonable — a restricted `Unpickler` has negligible overhead.

### 4. Unmentioned Risks

- **HMAC key storage is the elephant in the room.** The story doesn't address where the key lives. On a shared drive (the multi-user scenario), storing the key next to the cache is security theater.
- **The `WorkbookCache` dataclass has a `from_pickle()` migration path** (lines 91–106) that handles legacy formats. Any new format must also handle this migration.
- **Two `pickle.load()` call sites** need hardening: `_load_units_from_pickle()` (line 294) and `_cache_is_fresh()` (line 381). The story only mentions one.
- **Backward compatibility:** Old `.pkl` files without HMAC would be rejected. The story mentions this (AC #4) but doesn't address the migration path for the `row_by_com`/`fingerprint_by_com` metadata.

### 5. Point Estimate

**Story says: 5 points**  
**Recommended: 5 points** (accurate, but only if the approach is corrected to use a restricted Unpickler rather than HMAC)

---

## US-002b: File Path Input Sanitization

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| File paths from `config.yaml` passed to `openpyxl.load_workbook()` | `load_units()` at line 458, `save_unit()` at line 163 | ✅ Correct |
| Paths passed to `os.path.join()` | Used throughout | ✅ Correct |
| No validation currently exists | Confirmed — no path validation found in `main.py` or `main_window.py` | ✅ Correct |

### 2. Implementation Feasibility

**Feasible, but the proposed approach has issues.**

- **`os.path.normpath()` + `os.path.abspath()`** is good for resolving relative paths, but the story says "resolve relative to the config file's directory (not the CWD)." This is correct and important — the app already stores `_config_path` (line 172).
- **Checking for `..` components** is insufficient. A path like `....//....//etc/passwd` can bypass simple `..` checks after `normpath()`. Better: resolve the path, then verify it starts with an allowed prefix.
- **Null byte check** is good practice but Python 3's `open()` already rejects null bytes with `ValueError`. This is defense-in-depth.

### 3. Architecture Fit

- **No violations.** Validation in `main.py` before any file operations is the right place.
- **Minor concern:** The story says "apply validation in `main.py` right after loading config." This is correct per the architecture (config-driven, validate early).

### 4. Unmentioned Risks

- **Symlink attacks:** A symlink in the config path could redirect to an arbitrary file. The story doesn't mention `os.path.realpath()` or symlink checking.
- **UNC paths on Windows:** `\\server\share\...` paths could be used to access network resources. The story doesn't address this.
- **The `excel_path` is also used in `SaveWorker`** which runs in a background thread. If the path is validated at startup but the config is re-validated later, the validation must be re-applied.
- **The `csv_output_dir` and `unedited_reports_dir` paths** are also unvalidated. The story only mentions `excel_path`.

### 5. Point Estimate

**Story says: 3 points**  
**Recommended: 3 points** (accurate for the scope described)

---

## US-003: Error Dialog for Background Worker Failures

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `gui/main_window.py` — `LoadWorker` and `SaveWorker` errors logged but no `QMessageBox` shown | **Partially incorrect.** `_on_save_error()` at line 499 **already shows a `QMessageBox.warning()`**. `_on_load_error()` at line 660 **already shows a `QMessageBox.critical()`**. | ❌ **Incorrect — error dialogs already exist** |
| `error_occurred = pyqtSignal(str, str)` to be added | Current signals: `LoadWorker.error = pyqtSignal(str)` (line 46), `SaveWorker.error = pyqtSignal(str)` (line 78) — single string arg, not `(str, str)` | ❌ **Signal signature mismatch** |

### 2. Implementation Feasibility

**The story describes a problem that has already been partially fixed.**

Current state:
- `_on_load_error()` (line 660): Shows `QMessageBox.critical()` ✅
- `_on_save_error()` (line 499): Shows `QMessageBox.warning()` ✅
- `_on_save_conflict()` (line 510): Shows `ConflictDialog` ✅

**What's actually missing:**
1. **Error dialog throttling** (AC #3: "max 3 dialogs per 10 seconds") — not implemented
2. **Retry option for load errors** (AC #2: "with an option to retry") — not implemented
3. **`error_occurred` signal with `(str, str)` args** — the existing `error` signal takes a single `str`. Adding a new signal would require updating all connections.

### 3. Architecture Fit

- **No violations.** Error handling in `MainWindow` is appropriate.
- **Concern:** Adding a new `error_occurred` signal alongside the existing `error` signal creates redundancy. Better to extend the existing signal or add a separate error-type signal.

### 4. Unmentioned Risks

- **The story's core premise is wrong.** Error dialogs already exist for both load and save failures. The story should be re-scoped to: (a) add throttling, (b) add retry for load errors.
- **Signal signature change is a breaking change.** All existing connections to `error` would need updating. The story doesn't mention this.
- **`QMetaObject.invokeMethod`** (mentioned in implementation notes) is unnecessary — the existing signal/slot connections already marshal to the main thread automatically (Qt::QueuedConnection for cross-thread signals).

### 5. Point Estimate

**Story says: 5 points**  
**Recommended: 3 points** (for the actual remaining work: throttling + retry)

The story overestimates because it assumes error dialogs don't exist. The actual remaining work is smaller.

---

## US-004: Ensure Backup Directory Exists Before Writing

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `automation/vba_native.py` — `backup()` constructs archive path | Line 32: `archive_dir = os.path.join(...)` | ✅ Correct |
| `backup()` never calls `os.makedirs()` | **INCORRECT.** Line 33: `os.makedirs(archive_dir, exist_ok=True)` **already exists**. | ❌ **Already implemented** |

### 2. Implementation Feasibility

**This story describes a fix that is already in the code.**

The `backup()` function at line 30–37 of `vba_native.py`:
```python
def backup(target_path: str) -> None:
    archive_dir = os.path.join(os.path.dirname(target_path), "Archive")
    os.makedirs(archive_dir, exist_ok=True)  # <-- ALREADY HERE
    ts = datetime.now().strftime("%Y-%m-%d")
    base = os.path.splitext(os.path.basename(target_path))[0]
    dest = os.path.join(archive_dir, f"{ts}_{base}.xlsm")
    shutil.copy2(target_path, dest)
```

### 3. Architecture Fit

N/A — already implemented.

### 4. Unmentioned Risks

- **None.** The fix is already in place.
- **Possible confusion:** The story may have been written against an older version of the code. The `backup()` function was likely fixed in a previous commit.

### 5. Point Estimate

**Story says: 2 points**  
**Recommended: 0 points** (already implemented — story should be closed)

---

## US-005: Config Save Debouncing

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `gui/main_window.py` — theme toggle triggers `yaml.safe_dump()` | `_save_ui_config()` at line 1118–1138 calls `yaml.safe_dump()` | ✅ Correct |
| Rapid toggling causes multiple writes | Confirmed — `_save_ui_config()` is called on every theme change (line 1115) and on close (line 1194) | ✅ Correct |

### 2. Implementation Feasibility

**Feasible, but the story misses that `_save_ui_config()` is also called from `closeEvent()` (line 1194).**

The current code calls `_save_ui_config()` from:
1. `_apply_theme_by_name()` (line 1115) — on every theme/CVD/HC change
2. `closeEvent()` (line 1194) — on app close

**The debounce approach needs to handle:**
- Debounce timer for rapid UI changes (as described)
- **Immediate flush on close** (AC #4) — must cancel the timer and write synchronously
- **Thread safety:** `_save_ui_config()` writes to disk on the main thread. If the debounce timer fires on the main thread (which it will with `QTimer`), this is fine.

**One issue:** The story says "store pending changes in a dict, apply all at once on flush." But `_save_ui_config()` writes the entire config dict, not just the changed fields. The debounce should simply delay the call to `_save_ui_config()`, not accumulate field-level changes.

### 3. Architecture Fit

- **No violations.** Performance improvement to existing behavior.
- **Minor concern:** The story says "at most 2 config file writes occur (one debounced batch + one on close)." But `closeEvent` already calls `_save_ui_config()` directly. If the debounce timer is still running at close, you'd get: (1) debounced write from timer, (2) direct write from closeEvent = potentially 2 writes with different data. The closeEvent should cancel the timer and write once.

### 4. Unmentioned Risks

- **Config file corruption on concurrent writes:** If two instances of the app are running (multi-user scenario), both could write `config.yaml` simultaneously. The story doesn't address this.
- **`_save_ui_config()` writes the entire config** including `excel_path`, `sheet_name`, etc. If a user changes the theme and then changes `excel_path` via some future feature, the debounced write would include both. This is fine but worth noting.
- **The `config_path` key is excluded from writes** (line 1129: `k != "config_path"`). The debounce must preserve this filtering.

### 5. Point Estimate

**Story says: 3 points**  
**Recommended: 3 points** (accurate)

---

## US-007: File Watcher Debounce Reliability

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `gui/main_window.py` — 5-second debounce window | `_on_file_changed()` at line 714: `if now - getattr(self, "_last_file_change", 0) < 5.0` | ✅ Correct |
| "Simple timer + flag" for coalescing | Uses `time.monotonic()` comparison + `_last_file_change` flag | ✅ Correct |

### 2. Implementation Feasibility

**Feasible, but the story's proposed approach conflicts with the existing implementation.**

The current code already has a more sophisticated debounce than the story suggests:
- **5-second coalescing** via `_last_file_change` (line 714)
- **File readiness polling** via `_file_poll_timer` (500ms intervals, line 725)
- **8-second deadline** for file readiness (line 721)
- **PK header validation** before loading (line 749)

**The actual problem:** The story says "two saves within 5 seconds result in only one reload, potentially missing the second write." But the current code already handles this — after the first reload completes, `_last_file_change` is stale, so a second file change event would trigger a new reload.

**The real issue** is more nuanced: if the file watcher fires, the 5-second coalescing ignores subsequent events, but the file polling timer is already running. If a second save completes during polling, the polling timer will load the file at its current state (which includes the second write). So the current code may actually be correct.

### 3. Architecture Fit

- **No violations.** Improvement to existing file watcher behavior.

### 4. Unmentioned Risks

- **The story's proposed "last event wins" pattern** (restart timer once, cap at 2 reloads) could cause infinite loops if the file is being continuously written (e.g., Excel auto-save). The "cap at 2" is mentioned but not well-defined.
- **QFileSystemWatcher can fire multiple times** for a single save (Excel writes temp file, renames, etc.). The current code handles this with coalescing, but the story doesn't address the rename case.
- **The `_io_busy` flag is not set during file watcher-triggered loads** until `_load_data_async` is called (line 634). Between the file change event and the actual load, there's a window where a save could start. The story doesn't mention this race.

### 5. Point Estimate

**Story says: 5 points**  
**Recommended: 3 points** (the actual remaining edge cases are smaller than described)

---

## US-018: Workbook Locking During Save

### 1. Name/Path Accuracy

| Story Claim | Actual Code | Verdict |
|---|---|---|
| `data/writer.py` — `_safe_save_workbook()` doesn't check file locks | `_safe_save_workbook()` at line 25–60 — confirmed, no lock check | ✅ Correct |
| `save_unit()` is the entry point | `save_unit()` at line 129–195 | ✅ Correct |

### 2. Implementation Feasibility

**Partially feasible, but the proposed approach has serious problems.**

**Problem 1: `os.O_EXCL` doesn't work on Windows for this use case.**
- `os.open(path, os.O_WRONLY | os.O_EXCL)` will fail if the file exists (O_EXCL is for exclusive *creation*). To check if a file is locked, you'd need `os.open(path, os.O_WRONLY)` and catch `PermissionError`/`OSError`. But this is **inherently racy** — the lock state can change between check and write.

**Problem 2: The existing `_safe_save_workbook()` already uses atomic replace.**
- It writes to a temp file, then `os.replace()` (line 56). This is the correct pattern for atomic saves. Adding a lock check before this doesn't prevent the race — the file could be locked after the check but before `os.replace()`.

**Problem 3: The `LockManager` already exists** in `sync/lock_manager.py` and is used by `SaveWorker` (line 105–127). The story doesn't mention this existing infrastructure.

**Better approach:** Use the existing `LockManager.write_lock()` as the coordination mechanism. For detecting Excel-holding-the-file, attempt a rename test (`os.rename(excel_path, excel_path)`) or try opening with `os.open(path, os.O_WRONLY)` and catch the error.

### 3. Architecture Fit

- **Violates "no new dependencies" principle:** The story suggests a `.lock` file mechanism, but `LockManager` already provides this. The story should leverage existing infrastructure.
- **Violates separation of concerns:** Lock detection in `_safe_save_workbook()` (a low-level I/O function) mixes coordination logic with I/O. Better to handle this at the `SaveWorker` level.

### 4. Unmentioned Risks

- **The existing `LockManager` uses file-based locks** (`.lock` files in `UnitTracker/` directory). These work for inter-app coordination but **cannot detect Excel holding the file open**. The story conflates two different locking scenarios.
- **Excel file locking is OS-specific:** On Windows, Excel locks the file with a share mode that prevents other writers. On Linux/macOS, there's no mandatory file locking. The story's `os.O_EXCL` approach won't work cross-platform.
- **The `save_unit()` fast path** (line 152–158) uses `data.fast_writer.save_unit_fast()` which does direct ZIP modification. This path has different locking characteristics than the openpyxl fallback.
- **Retry with re-read (AC #4)** is dangerous: re-reading the file and re-applying the unit's changes could overwrite concurrent edits from another user. The existing `RevisionStore` mechanism handles this properly — the story should use it.

### 5. Point Estimate

**Story says: 5 points**  
**Recommended: 8 points** (if properly scoped to use existing `LockManager` + add Excel-lock detection + integrate with `RevisionStore` for retry)

The story underestimates the complexity because it doesn't account for the existing infrastructure that must be integrated.

---

## Summary Table

| Story | Points (Story) | Points (Recommended) | Critical Issues |
|---|---|---|---|
| US-001 | 8 | 3 | Wrong diagnosis; `_row_by_com`/`_fingerprint_by_com` don't exist on MainWindow; QMutex is wrong tool |
| US-002 | 5 | 5 | HMAC key management not addressed; two `pickle.load()` sites need fixing |
| US-002b | 3 | 3 | `..` check is insufficient; symlink/UNC attacks not mentioned |
| US-003 | 5 | 3 | Error dialogs already exist; story premise is wrong |
| US-004 | 2 | 0 | **Already implemented** — `os.makedirs` is on line 33 |
| US-005 | 3 | 3 | closeEvent interaction needs care; otherwise accurate |
| US-007 | 5 | 3 | Current code is more sophisticated than story suggests; actual gap is smaller |
| US-018 | 5 | 8 | `os.O_EXCL` approach is wrong; existing `LockManager` not mentioned; conflates two locking scenarios |

## Priority Recommendations

1. **Close US-004** — already implemented, no work needed.
2. **Rewrite US-001** — the actual bug is that `_io_busy` doesn't cover the save path. Fix: 2 lines.
3. **Rewrite US-003** — re-scope to throttling + retry, since dialogs already exist.
4. **Rewrite US-018** — leverage existing `LockManager` and `RevisionStore`; add Excel-lock detection at the `SaveWorker` level, not in `_safe_save_workbook()`.
5. **Fix US-002 approach** — use restricted `Unpickler` instead of HMAC.
6. **US-002b, US-005, US-007** — proceed with minor corrections noted above.
