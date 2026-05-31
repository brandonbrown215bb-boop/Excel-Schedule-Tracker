# US-017: Cache milestones Property Result

**Epic:** Performance
**Type:** Improvement
**Priority:** LOW
**Story Points:** 2
**Status:** Unstarted

---

## Story

As a developer,
I want the `milestones` property on `Unit` to cache its result after first computation,
So that repeated access (e.g., during paint events) doesn't allocate a new list every time.

---

## Context

`data/models.py` — The `milestones` property builds a new list of `(name, date)` tuples on every access. If called during `paintEvent` or in a loop by the timeline panel, this creates unnecessary garbage.

---

## Acceptance Criteria

1. Given a `Unit` instance is constructed, when `milestones` is accessed the first time, then it computes the list and caches it.
2. Given the cached result exists, when `milestones` is accessed again, then it returns the cached list (no re-computation).
3. Given a field involved in milestones is modified (via a theoretical setter), when the field changes, then the cache is invalidated.
4. Given the caching is in place with 1000 `Unit` instances, when `milestones` is accessed on each, then total list allocations equal the number of instances (not N × access_count).

---

## Implementation Notes

- Since `Unit` is a dataclass and fields are public, use a private `_milestones_cache` attribute set to `None`.
- On first access: compute and store. On subsequent access: return stored.
- Invalidation: set `_milestones_cache = None` after any field mutation. If fields are mutated directly (no setter), consider using `__post_init__` to set a `_dirty` flag, or accept that the cache is valid as long as the instance is immutable (which it mostly is — units are re-created on load, not mutated in place).

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
