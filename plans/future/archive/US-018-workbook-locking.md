# US-018: Workbook Locking During Save

**Epic:** Reliability
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 5
**Status:** Unstarted

---

## Story

As an end user running multiple instances of the app,
I want the save process to detect and handle file locks from other processes,
So that simultaneous saves don't corrupt the workbook.

---

## Context

`data/writer.py` — `_safe_save_workbook()` doesn't check if the Excel file is locked by another process (e.g., another app instance or Excel itself). This could cause data loss or corruption.

---

## Acceptness Criteria

1. Given the target Excel file is open in Microsoft Excel, when the app attempts a save, then a clear error dialog is shown: "The file is locked by another program. Close Excel and try again."
2. Given another instance of the app is saving simultaneously, when the second instance attempts a save, then it waits briefly (up to 3 seconds) for the lock to clear, or shows a retry dialog.
3. Given the file is not locked, when a save is attempted, then it proceeds normally (no regression).
4. Given a save fails due to a lock, when the user retries, then the retry re-reads the file to ensure no stale data is written.

---

## Implementation Notes

- Attempt to open the file in exclusive mode (`os.open(path, os.O_WRONLY | os.O_EXCL)`) before calling `wb.save()`.
- On Windows, a locked file will raise `PermissionError` — catch and surface to user.
- Consider a lock file (`.lock`) as an additional coordination mechanism between app instances.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
