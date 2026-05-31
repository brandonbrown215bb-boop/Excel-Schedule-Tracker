# US-018: Save Conflict Detection Using Existing LockManager

**Epic:** Reliability
**Type:** Improvement
**Priority:** HIGH
**Story Points:** 8
**Status:** Unstarted

---

## Story

As an end user running the app while Excel has the workbook open,
I want the save process to detect the conflict and offer a retry after the file is released,
So that I don't silently lose edits or corrupt the workbook.

---

## Context

The codebase already has infrastructure for this:
- `sync/lock_manager.py` — `LockManager` with `write_lock()` for inter-app coordination
- `sync/revision_store.py` — `RevisionStore` for optimistic conflict detection
- `data/writer.py` — `_safe_save_workbook()` already uses atomic write-to-temp-then-rename

**What's missing:** Neither `SaveWorker` nor `_safe_save_workbook()` checks whether Excel (or another process) has the file locked **at write time**. The atomic rename protects against mid-write crashes but not against writing on top of Excel's held file.

The two locking scenarios are distinct:
1. **Inter-app coordination** (two instances of the app) — handled by `LockManager.write_lock()`. Currently used but not at the `SaveWorker` level for the actual file write.
2. **Excel-has-file-open** — not handled. On Windows, Excel locks with a share mode that blocks other writers. On Linux there's no mandatory locking.

---

## Acceptance Criteria

1. Given the Excel file is open in Microsoft Excel (Windows), when `SaveWorker` attempts to save, then a `PermissionError` is caught and the user sees a clear dialog: "The file is locked by another program. Close Excel and click Retry."
2. Given another instance of the app holds a write lock via `LockManager`, when the second instance attempts a save, then it waits up to 3 seconds for the lock to release, or shows a retry dialog.
3. Given a save fails due to a conflict, when the user retries, then the file is re-read and the `RevisionStore` is checked to ensure the user's changes don't overwrite concurrent edits from another instance.
4. Given the file is not locked, when a save is attempted, then it proceeds normally (no regression from existing `LockManager` behavior).
5. Given a SaveWorker conflict is detected, when the error is handled, then `_io_busy` is cleared (coordinated with US-001 fix).

---

## Implementation Notes

- At the **SaveWorker level** (not inside `_safe_save_workbook`), before calling `save_unit()`:
  1. Acquire `LockManager.write_lock()` with a 3-second timeout.
  2. Attempt `os.open(excel_path, os.O_WRONLY)` — on Windows, this raises `PermissionError` if Excel has the file locked. On Linux this won't fail (no mandatory locking), so treat Linux as best-effort.
  3. On failure: emit error signal with a "retry" flag; do NOT call `_safe_save_workbook()`.
- Integrate with `RevisionStore`: on retry, read the current file, check the stored revision against the current file revision. If different, surface a conflict dialog showing both versions.
- Do NOT use `os.O_EXCL` — it's for exclusive *creation*, not locking, and will fail if the file already exists.
- Do NOT add a new lock file mechanism — extend the existing `LockManager`.

---

## Dependencies

- Depends on US-001 (io-busy save guard) for correct `_io_busy` clearing on conflict.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
