# US-002: Secure Cache Deserialization

**Epic:** Security
**Type:** Bug Fix
**Priority:** HIGH
**Story Points:** 5
**Status:** Unstarted

---

## Story

As a security-conscious developer,
I want to replace or harden pickle-based cache deserialization,
So that a tampered `.pkl` file cannot execute arbitrary code on application startup.

---

## Context

`data/loader.py` — Cache loading uses `pickle.load()` on `.pkl` files. Pickle deserialization of untrusted data is a known attack vector (arbitrary code execution). The risk is low for a local desktop app but violates defense-in-depth principles.

---

## Acceptance Criteria

1. Given a cache file exists, when the loader reads it, then the data is validated before use (e.g., HMAC signature or JSON/CSV fallback).
2. Given a `.pkl` file has been tampered with, when the loader attempts to deserialize it, then the file is rejected and the cache is rebuilt from the source Excel file.
3. Given the cache integrity check fails, when the error occurs, then a warning is logged and the app continues with a fresh load (no crash).
4. Given the cache format is changed, when existing users upgrade, then old `.pkl` files are silently invalidated (backward compatible degradation).
5. Given the new serialization approach, when a full load/save cycle completes, then performance impact is ≤10% compared to raw pickle.

---

## Implementation Notes

- Option A: Add HMAC-SHA256 signature to the `.pkl` file at write time, verify at read time.
- Option B: Migrate cache format from pickle to JSON (slower but safe). CSV caching already exists as fallback.
- Option C: Use `pickletools` to disallow dangerous opcodes (limited, not recommended as primary fix).
- Recommended: Option A is lowest-effort with strong security gain.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
