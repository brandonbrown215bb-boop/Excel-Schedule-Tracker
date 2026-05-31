# US-004: Ensure Backup Directory Exists Before Writing

**Epic:** Reliability
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 2
**Status:** Unstarted

---

## Story

As an end user,
I want the backup function to create the backup directory if it doesn't exist,
So that backups don't silently fail with an unhelpful `FileNotFoundError`.

---

## Context

`automation/vba_native.py` — `backup()` constructs an archive path using `os.path.join(archive_dir, ...)` but never calls `os.makedirs(archive_dir, exist_ok=True)`. If the archive directory is missing, the function crashes with a raw `FileNotFoundError`.

---

## Acceptance Criteria

1. Given the archive directory does not exist, when `backup()` is called, then `os.makedirs(archive_dir, exist_ok=True)` is called before writing the backup file.
2. Given the archive directory exists, when `backup()` is called, then no error occurs and the backup file is written normally.
3. Given `backup()` creates the directory, when the backup completes, then the function returns the path to the created archive file.
4. Given `os.makedirs` fails due to permissions, when the backup is attempted, then a clear error is logged (not a raw traceback).

---

## Implementation Notes

- Single line addition: `os.makedirs(archive_dir, exist_ok=True)` before the `shutil.copy2` or file-write call.
- Add a `logger.info(f"Created backup directory: {archive_dir}")` for observability.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
