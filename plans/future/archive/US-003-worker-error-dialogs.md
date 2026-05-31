# US-003: Error Dialog for Background Worker Failures

**Epic:** Concurrency & Reliability
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 5
**Status:** Unstarted

---

## Story

As an end user,
I want to see a clear error message when a background save or load fails,
So that I know my data was not saved and can take action instead of silently losing changes.

---

## Context

`gui/main_window.py` — When `LoadWorker` or `SaveWorker` encounters an exception, the error is logged to the log file but no `QMessageBox` is shown on the main thread. Save failures are especially dangerous because the user may assume data was persisted.

---

## Acceptance Criteria

1. Given a SaveWorker encounters an exception, when the error occurs, then a `QMessageBox.critical()` is displayed on the main thread with the error details.
2. Given a LoadWorker encounters an exception, when the error occurs, then a `QMessageBox.warning()` is displayed indicating the reload failed, with an option to retry.
3. Given multiple worker errors occur in sequence, when each fails, then each error is shown (not silently dropped), but a maximum of 3 dialogs per 10 seconds to avoid spam.
4. Given the error dialog is displayed, when the user dismisses it, then the app remains in a usable state (no crash).
5. Given the error signal is emitted from the worker thread, when it crosses to the main thread, then it uses a `pyqtSignal`/`Slot` connection (not raw callbacks) to ensure thread safety.

---

## Implementation Notes

- Add `error_occurred = pyqtSignal(str, str)` to both `LoadWorker` and `SaveWorker` (signal args: title, message).
- Connect to a slot on `MainWindow` that calls `QMessageBox` on the main thread.
- Use `QMetaObject.invokeMethod` or a signals-only pattern to avoid direct cross-thread GUI calls.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
