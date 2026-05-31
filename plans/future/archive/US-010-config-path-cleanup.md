# US-010: Remove config_path from Source config.yaml Template

**Epic:** Maintainability
**Type:** Bug Fix
**Priority:** MEDIUM
**Story Points:** 1
**Status:** Unstarted

---

## Story

As a developer,
I want the source `config.yaml` template to contain only user-facing configuration fields,
So that runtime-injected paths don't pollute version-controlled config.

---

## Context

`config.yaml` contains a `config_path` field that is auto-populated at runtime by `main.py` and written back on every save. This is a code artifact in what should be a pure configuration file.

---

## Acceptance Criteria

1. Given the source `config.yaml` template, when viewed, then it does not contain a `config_path` field.
2. Given `config_path` is removed from the template, when the app starts, then it injects `config_path` at runtime as before (no functional change).
3. Given the app saves config on close, when the save occurs, then `config_path` is stripped from the write before serialization (existing fix in `_save_ui_config` should already handle this — verify).

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
