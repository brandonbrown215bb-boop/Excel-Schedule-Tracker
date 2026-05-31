# US-006d: Add Sync Edge Case Tests

**Epic:** Quality Assurance
**Type:** Enabler
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As a developer,
I want tests for concurrent lock acquisition and stale lock detection in the sync layer,
So that multi-user coordination works correctly under contention and after crashes.

---

## Context

`sync/lock_manager.py` and `sync/revision_store.py` have basic tests but don't cover:
- Two threads attempting to acquire the same lock simultaneously
- A lock file left behind by a crashed process (stale lock)

---

## Acceptance Criteria

1. Given the `LockManager` coordinates file access, when two threads attempt to acquire the same write lock, then one blocks until the other releases (no deadlock within the configured timeout).
2. Given a lock file exists from a crashed process (no owning process running), when the `LockManager` starts, then it detects the stale lock and allows re-acquisition.
3. Given both edge case tests are written, when `pytest tests/test_sync.py` runs, then all tests pass.

---

## Implementation Notes

- Use `threading.Thread` with a `threading.Barrier` to synchronize concurrent lock acquisition.
- For the stale lock test: create a `.lock` file with a fake PID that doesn't correspond to any running process, then call `LockManager.write_lock()` and verify it succeeds.
- Use short timeouts (1 second) to keep tests fast.

---

## Dependencies

- None. Can be done in parallel with other US-006 stories.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
