# Feature 20: Cache-First Multi-User Sync and Fast I/O

**Priority:** High  
**Risk:** Medium-High  
**Status:** Foundation implemented; full shared-cache merge UI remains future work.

---

## Goal

Make normal load, refresh, and save feel instant while still protecting the shared Excel workbook when multiple users run Unit Tracker at the same time.

The app should treat its cache as the working store and Excel as the durable backing file. Excel parsing and `.xlsm` rewrites are the slow path, not the default interaction path.

---

## Design

### Fast Local Path

1. Load from pickle cache when workbook signature matches.
2. Fall back to CSV cache when pickle is missing but CSV is fresh.
3. Parse Excel only when the workbook changed externally or the user forces `Reload Excel`.
4. Keep `COM -> row` hints in the pickle payload so saves can avoid scanning column C.
5. Store per-unit fingerprints for conflict checks.

### Multi-User Safety

Use shared-drive lock files, but only with atomic creation:

- `commit.lock`: protects shared revision/cache metadata updates.
- `excel.lock`: protects `.xlsm` writes, pull operations, and macro operations.
- `revisions.json`: tracks latest committed revision per COM.

Shared revisions are global. Each client keeps its own baseline revision on loaded units. A save compares the unit's local baseline to the latest shared revision before writing.

### Save Flow

1. User saves a unit.
2. Acquire `commit.lock`.
3. Compare local base revision with latest shared revision.
4. Acquire `excel.lock`.
5. Write the workbook row.
6. Commit the new revision and fingerprint.
7. Update local cache and UI from memory.
8. Release locks.

This first implementation keeps the Excel write inside the save worker for correctness. A later phase can make the UI even faster by committing to cache immediately and flushing dirty rows to Excel in a debounced batch.

---

## Implemented Foundation

- Rich pickle cache payload with units, row hints, workbook signature, and fingerprints.
- Backward-compatible pickle loading for old list-only caches.
- CSV fallback freshness check that works even when pickle is absent.
- Read-only/value-only Excel parsing for faster forced reloads.
- `save_unit(..., row_idx=None)` accepts cached row hints and validates them before falling back to a scan.
- Cache-first Refresh button; separate `Reload Excel` button for forced workbook parsing.
- Atomic `sync.lock_manager.LockManager` using exclusive file creation.
- `sync.revision_store.RevisionStore` with per-COM optimistic revisions.
- Optional `multi_user` config section, disabled by default.
- Save worker integration for `commit.lock`, `excel.lock`, and revision commits when `multi_user.enabled` is true.

---

## Completed Work

All six remaining items have been implemented and verified (204/204 tests pass):

### 1. Conflict Dialog (`gui/conflict_dialog.py`)
- **New file**: `gui/conflict_dialog.py` — `ConflictDialog` shows a side-by-side diff table of local vs. remote field values
- Three actions: **Overwrite** (force-save ignoring conflict), **Reload** (discard local, reload from workbook), **Cancel** (keep form as-is)
- Only shows fields where values actually differ (yellow highlight)
- Connected via `SaveWorker.conflict` signal → `MainWindow._on_save_conflict()`

### 2. Shared Cache (`sync/shared_cache.py`)
- **New file**: `sync/shared_cache.py` — stores per-COM remote field values in `UnitTracker/units.json`
- `SharedUnitEntry` dataclass mirrors the `unit_fingerprint` field set, plus revision metadata
- Atomically updated alongside `revisions.json` via `RevisionStore.commit(..., unit=unit)`
- `SharedCache.get(com_number)` returns field dict for conflict diffs — no Excel re-parse needed

### 3. Session Presence (`sync/session_registry.py`)
- **New file**: `sync/session_registry.py` — heartbeat files in `UnitTracker/sessions/<owner>.json`
- `SessionRegistry.start(parent)` begins 30-second heartbeat timer; `stop()` removes session file
- Stale sessions (>90s old) are filtered out via `SessionInfo.is_stale`
- **UI integration**: Status bar label shows "👤 2 others online" with clickable tooltip listing active sessions; 60-second poll timer updates presence

### 4. Batch Dirty Excel Writes (`gui/main_window.py`)
- `on_save_unit()` now commits to memory/cache immediately, then queues to `_pending_excel_sync`
- 5-second debounce timer (`_debounce_flush_timer`) coalesces rapid saves
- `_flush_pending_syncs()` processes queue one-by-one in background, chaining via `_on_save_finished`
- Before: each save triggered an immediate Excel write. Now: cache commit is instant; Excel flush is debounced.

### 5. Lock Wrapping (`gui/main_window.py`)
- `_run_vba()`: macro execution wrapped in `lock_manager.write_lock()` when multi-user enabled
- `_pull_csv()`: pipeline wrapped in `lock_manager.write_lock()` when multi-user enabled
- `closeEvent()`: stops session heartbeat, flushes pending syncs synchronously (best-effort)
- `save_unit()`: new `force=True` parameter skips COM-column row validation for conflict overwrites

### 6. Integration Tests (`tests/test_multi_user_integration.py`)
- **New file**: 14 tests covering:
  - `test_save_no_conflict` — Alice & Bob save different COMs → both succeed
  - `test_detect_conflict` — Bob uses stale baseline → `RevisionConflictError` with correct `modified_by`
  - `test_force_overwrite` — Bob accepts conflict and force-saves → revision bumps to 2
  - `test_lock_blocks_concurrent_excel_write` — Thread A holds lock, thread B times out
  - `test_lock_release_allows_later_acquire` — Lock release enables subsequent acquire
  - `test_shared_cache_store_and_retrieve` — Write unit to cache, read back full entry + raw dict
  - `test_shared_cache_missing_com` — Unknown COM returns `None`
  - `test_shared_cache_clear` — Clear removes all entries
  - `test_session_registry_heartbeat` — Single session, heartbeat file created/removed
  - `test_session_registry_multi_user` — Two simultaneous sessions both visible
  - `test_session_stale_detection` — Backdated heartbeat → filtered as stale
  - `test_save_unit_and_revision` — Excel save + revision store consistency
  - `test_concurrent_save_with_lock` — Two threads serialize via excel lock
  - `test_save_unit_force` — `force=True` skips COM-column validation

---

## Operational Notes

- `multi_user.enabled: false` keeps single-user behavior.
- If multi-user sync is enabled and locking cannot initialize, `fallback_mode: "block"` refuses saves. This is safer than warning and continuing because an unlocked save can overwrite another user's work.
- Manual refresh should stay cache-first. Forced Excel parsing belongs behind an explicit `Reload Excel` action.
