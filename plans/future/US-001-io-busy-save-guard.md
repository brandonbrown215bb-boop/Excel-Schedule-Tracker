# US-001: Extend _io_busy Guard to Cover Save Operations

**Epic:** Concurrency & Reliability
**Type:** Bug Fix
**Priority:** HIGH
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user,
I want the file watcher to wait for an in-progress save to complete before triggering a reload,
So that rapid save-then-reload cycles don't cause data loss or corruption.

---

## Context

`gui/main_window.py` — `MainWindow._io_busy` (managed via `_set_io_busy()` at lines 773–775) prevents concurrent load operations, but **is never set during saves**. `SaveWorker` doesn't call `_set_io_busy(True)` before writing or `_set_io_busy(False)` after completion. This means `_on_file_changed` can call `_load_data_async` while `SaveWorker` is mid-write.

The actual race: the file watcher fires, `_on_file_changed` checks `_active_save_worker_running()` but `_io_busy` is `False`, so `_load_data_async` proceeds concurrently with the save.

The shared state (`self.units`) is replaced atomically via signal/slot in `_on_load_finished`, so a mutex is unnecessary. The fix is to extend the existing `_io_busy` guard to cover the save path.

---

## Acceptance Criteria

1. Given a `SaveWorker` is mid-write when the file watcher triggers, when `_on_file_changed` fires, then the reload waits until `_io_busy` is cleared before starting.
2. Given `_set_io_busy(True)` is called at `SaveWorker` start, when the save completes (success or failure), then `_set_io_busy(False)` is called in a `finally` block.
3. Given a rapid file watcher event arrives during a save, when `_load_data_async` checks `_io_busy`, then it defers the load rather than proceeding concurrently.
4. Given the fix is in place, when existing tests pass, then no concurrency regressions are introduced.

---

## Implementation Notes

- In `SaveWorker.run()`: call `QMetaObject.invokeMethod(self.window, "_set_io_busy", Qt.QueuedConnection, Q_ARG(bool, True))` before the save, and `Q_ARG(bool, False)` in a `finally` block after.
- Alternative: `_on_save_worker_started` / `_on_save_worker_finished` slots on `MainWindow` that set/clear `_io_busy` directly — simpler and doesn't require `QMetaObject`.
- Do NOT add `QMutex` or `threading.Lock` — the signal/slot pattern already provides thread-safe data transfer.
- Do NOT guard `self.units` with a mutex — it's replaced atomically, not mutated in place.

---

## Dependencies

- Blocks US-003 (worker error throttling) — that story should sequence after this one.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
