# US-003: Add Throttling and Retry to Existing Error Dialogs

**Epic:** Concurrency & Reliability
**Type:** Improvement
**Priority:** HIGH
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user,
I want error dialogs from background workers to be throttled during rapid failures and include a retry option for load errors,
So that I'm not flooded with duplicate dialogs and can recover from transient failures without restarting the app.

---

## Context

`gui/main_window.py` — Error dialogs **already exist**:
- `_on_load_error()` at line 660 shows `QMessageBox.critical()`
- `_on_save_error()` at line 499 shows `QMessageBox.warning()`
- `_on_save_conflict()` at line 510 shows `ConflictDialog`

The existing `LoadWorker.error` and `SaveWorker.error` signals (both `pyqtSignal(str)`) already marshal to the main thread via Qt queued connections. No need for `QMetaObject.invokeMethod`.

**What's missing:**
1. **Throttling:** Rapid consecutive failures (e.g., file locked by Excel, momentary network hiccup) can spawn many dialogs in quick succession.
2. **Retry for load errors:** When a load fails, the user has no option to retry — they must close and reopen the app.

---

## Acceptance Criteria

1. Given a `LoadWorker` error occurs, when the error dialog is displayed, then a "Retry" button is included that re-queues the failed load.
2. Given more than 3 error dialogs occur within 10 seconds, when subsequent errors arise, then they are logged but no additional dialog is shown to the user.
3. Given a "Retry" button is clicked, when the retry is triggered, then `_load_data_async(force_reload=True)` is called.
4. Given a `SaveWorker` error occurs, when the error is displayed, then the user's in-memory edits are preserved (not lost) so they can attempt the save again.
5. Given the error dialog is displayed, when the user dismisses it, then the app remains in a usable state with no crash.

---

## Implementation Notes

- Add a `self._error_dialog_count` and `self._error_dialog_window_start` timestamp to `MainWindow`.
- Before showing any error dialog: check if `time.monotonic() - window_start < 10.0 and count >= 3`. If throttled, log and return.
- Reset the counter window when `time.monotonic() - window_start >= 10.0`.
- For the retry button: connect a signal from the custom button to `_load_data_async`. Use `QMessageBox` with custom buttons (`QMessageBox.Retry | QMessageBox.Ok`).
- For preserving edits on save failure: the `EditForm` already holds a reference to the current unit. Don't clear it on save error.
- Existing signal/slot connections already marshal to the main thread — no need to change signal signatures from `pyqtSignal(str)`.

---

## Dependencies

- Depends on US-001 (io-busy save guard) — complete US-001 first.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
