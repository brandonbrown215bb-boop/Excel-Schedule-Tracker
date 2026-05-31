# US-021: Cache unit_fingerprint() Result

**Epic:** Performance
**Type:** Improvement
**Priority:** LOW
**Story Points:** 2
**Status:** Unstarted

---

## Story

As a developer,
I want `unit_fingerprint()` to cache its SHA-256 hash result,
So that repeated comparisons of the same unit don't recompute the hash each time.

---

## Context

`data/loader.py` — `unit_fingerprint()` computes a SHA-256 hash. If called for every unit on every comparison (e.g., during save detection or diff), this adds up unnecessarily.

---

## Acceptance Criteria

1. Given a `Unit` is fingerprinted, when `unit_fingerprint(unit)` is called multiple times on the same unit, then SHA-256 is computed only once; subsequent calls return the cached value.
2. Given the fingerprint is cached, when a unit's field changes, then the cache is invalidated and the next call recomputes.
3. Given 1000 units with fingerprinting, when a full comparison pass runs, then SHA-256 is called exactly 1000 times (not N×M for N units and M comparisons).

---

## Implementation Notes

- Add a `_fingerprint_cache` attribute to the `Unit` dataclass (excluded from `__init__` and `__repr__`).
- Or cache in a `WeakKeyDictionary` externally to avoid modifying the dataclass.
- Since units are typically created fresh on each load, the cache lifespan is one session — acceptable.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
