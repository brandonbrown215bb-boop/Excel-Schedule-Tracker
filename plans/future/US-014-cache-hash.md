# US-014: Use Content Hash for Cache Invalidation

**Epic:** Reliability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer,
I want cache freshness determined by file content hash rather than mtime + size,
So that edge cases (e.g., two files with identical mtime and size but different content) don't result in stale cache.

---

## Context

`data/loader.py` — The `WorkbookCache` content signature is `(mtime_ns, file_size)`. Two files with the same size and modification time could theoretically have different content (rapid saves within the same nanosecond).

---

## Acceptance Criteria

1. Given a cache file exists, when the loader checks freshness, then it computes a SHA-256 hash of the source Excel file and compares it to the stored hash.
2. Given the file content changes but mtime and size remain the same (edge case), when the hash is compared, then the cache is invalidated and rebuilt.
3. Given the hash is computed, when a large Excel file (>50MB) is loaded, then the hash computation adds no more than 200ms to the load time.
4. Given the new content signature format, when an old-format cache file (mtime+size only) is found, then it is silently invalidated (backward compatible).

---

## Implementation Notes

- Compute `hashlib.sha256(open(path, 'rb').read()).hexdigest()` or read in chunks for memory efficiency.
- Store the hash in the `.pkl` cache file or a sidecar `.hash` file.
- For performance: cache the hash itself and only recompute when mtime changes (optimization: use mtime as fast path, hash as confirmation).

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
