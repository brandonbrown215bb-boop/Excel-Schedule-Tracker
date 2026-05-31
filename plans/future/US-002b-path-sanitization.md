# US-002b: File Path Input Sanitization

**Epic:** Security
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer,
I want file paths from `config.yaml` validated before being passed to filesystem operations,
So that path traversal or malformed paths can't cause unexpected behavior.

---

## Context

File paths from `config.yaml` are passed directly to `openpyxl.load_workbook()` and `os.path.join()` without validation. While this is a desktop app, path traversal could be an issue if config files are shared between users.

---

## Acceptance Criteria

1. Given a `config.yaml` with an `excel_path` like `../../etc/passwd`, when the app loads, then the path is validated and rejected with a clear error message.
2. Given a valid absolute or relative path, when the app loads, then it is accepted and used normally (no regression).
3. Given a path containing null bytes or control characters, when validation runs, then it is rejected before any filesystem call.
4. Given the validation is applied, when a path is relative, then it is resolved relative to the config file's directory (not the CWD).

---

## Implementation Notes

- Check for `..` components that escape the intended directory.
- Reject paths containing `\0` (null bytes).
- Use `os.path.normpath()` + `os.path.abspath()` to resolve relative paths safely.
- Apply validation in `main.py` right after loading config, before any file operations.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
