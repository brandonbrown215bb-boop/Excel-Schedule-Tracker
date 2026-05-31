# US-002: Harden Cache Deserialization with Restricted Unpickler

**Epic:** Security
**Type:** Bug Fix
**Priority:** HIGH
**Story Points:** 5
**Status:** Unstarted

---

## Story

As a security-conscious developer,
I want to replace raw `pickle.load()` with a restricted `Unpickler` that only permits safe types,
So that a tampered `.pkl` file cannot execute arbitrary code on application startup.

---

## Context

`data/loader.py` — Two call sites use raw `pickle.load()`:
- `_load_units_from_pickle()` at line 294
- `_cache_is_fresh()` at line 381

Pickle deserialization of untrusted data is a known arbitrary-code-execution vector. The risk is low for a single-user desktop app, but violates defense-in-depth. HMAC-based signing was considered but has an unsolved key management problem (storing the key beside the cache is security theater on a shared drive).

The standard Python approach is a restricted `pickle.Unpickler` subclass that overrides `find_class()` to allowlist only the types actually stored in the cache: `Unit`, `WorkbookCache`, `list`, `dict`, `str`, `int`, `float`, `datetime.date`, `datetime.datetime`, `NoneType`, `bool`.

---

## Acceptance Criteria

1. Given a `.pkl` cache file exists, when the loader reads it, then a `SafeCacheUnpickler` is used instead of raw `pickle.load()`.
2. Given a `.pkl` file contains a class not in the allowlist, when the loader attempts deserialization, then `pickle.UnpicklingError` is raised, a warning is logged, and the cache is rebuilt from the source Excel file.
3. Given a corrupt or truncated `.pkl` file exists, when the loader reads it, then the error is caught, a warning is logged, and the app continues with a fresh load (no crash).
4. Given the cache format changes in a future release, when an old-format `.pkl` is encountered, then `WorkbookCache.from_pickle()` migrates it silently (existing backward-compatibility path).
5. Both `_load_units_from_pickle()` and `_cache_is_fresh()` use the restricted unpickler.

---

## Implementation Notes

```python
import pickle
import io

_ALLOWLIST = {
    ("__main__", "Unit"),
    ("data.models", "Unit"),
    ("__main__", "WorkbookCache"),
    ("data.loader", "WorkbookCache"),
    ("builtins", "list"),
    ("builtins", "dict"),
    ("builtins", "str"),
    ("builtins", "int"),
    ("builtins", "float"),
    ("datetime", "date"),
    ("datetime", "datetime"),
    ("builtins", "NoneType"),
    ("builtins", "bool"),
}

class SafeCacheUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in _ALLOWLIST:
            raise pickle.UnpicklingError(
                f"Blocked deserialization of {module}.{name}"
            )
        return super().find_class(module, name)

def _safe_unpickle(path: str):
    with open(path, "rb") as f:
        return SafeCacheUnpickler(f).load()
```

- Replace both `pickle.load(f)` calls with `_safe_unpickle(path)`.
- Catch `pickle.UnpicklingError` and `EOFError` at the call sites; fall back to `_load_units_from_csv()` or full Excel parse.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
