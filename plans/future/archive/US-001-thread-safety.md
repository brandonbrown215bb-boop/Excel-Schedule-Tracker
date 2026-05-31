# US-001: Thread Synchronization for Shared Mutable State

**Epic:** Concurrency & Reliability
**Type:** Bug Fix
**Priority:** HIGH
**Story Points:** 8
**Status:** Unstarted

---

## Story

As a developer,
I want proper thread synchronization around shared state accessed by LoadWorker and SaveWorker,
So that race conditions during concurrent file watcher reloads and saves don't cause data corruption or crashes.

---

## Context

`gui/main_window.py` — `LoadWorker` and `SaveWorker` both access and modify `_units`, `_row_by_com`, `_fingerprint_by_com`. The `_io_busy` guard is a boolean flag that doesn't fully protect against interleaved load/save when the file watcher fires during an in-progress save.

---

## Acceptance Criteria

1. Given the SaveWorker is mid-write, when the file watcher triggers a reload, then the reload waits until the save completes before starting.
2. Given a LoadWorker and SaveWorker both need access to `_units`, when either modifies it, then a `QMutex` or `threading.Lock` guards the access.
3. Given the app runs with rapid file watcher events, when multiple events fire within the debounce window, then no crash or data corruption occurs.
4. Given the lock is held, when the worker thread finishes, then the lock is released even if an exception occurs (try/finally).
5. Given the new synchronization is in place, when existing tests pass, then no regressions are introduced.

---

## Implementation Notes

- Use `QMutex` with `QMutexLocker` for RAII-style locking, consistent with Qt conventions.
- Guard all access to `_units`, `_row_by_com`, `_fingerprint_by_com` in both workers.
- Consider a read-write lock pattern if reads outnumber writes.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
