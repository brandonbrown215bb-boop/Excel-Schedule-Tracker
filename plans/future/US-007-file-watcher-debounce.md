# US-007: File Watcher Debounce Reliability

**Epic:** Concurrency & Reliability
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user,
I want the file watcher to always load the most recent state after rapid file changes,
So that two saves within the debounce window don't cause the UI to stale-out.

---

## Context

`gui/main_window.py` — The current debounce implementation is already sophisticated: 5-second coalescing via `_last_file_change` (line 714), file-readiness polling at 500ms intervals via `_file_poll_timer` (line 725), an 8-second deadline for file readiness, and PK header validation before loading (line 749).

**The remaining edge case:** If two Excel saves complete within the same debounce window AND the first save's reload catches the file in a partially-written state, the second save's changes may be missed.

---

## Acceptance Criteria

1. Given two Excel saves complete within 3 seconds, when the debounce timer fires after the first event, then a second reload is queued to capture the latest file state after the debounce expires.
2. Given the file watcher fires N events within the debounce window, when the window expires, then the most recent file state is loaded (not the state from the oldest event).
3. Given the app is idle (no rapid saves), when the debounce fires, then behavior is identical to the current implementation (no regression).
4. Given consecutive reloads are triggered, when the second reload starts, then the first reload's result is discarded (only latest state is displayed).

---

## Implementation Notes

- The existing `_file_poll_timer` already handles file-readiness polling. The fix adds a "pending reload" flag: if a new file change event arrives while a reload is queued but not yet started, mark the queued reload as "stale" and schedule one additional reload after the current one completes.
- Cap total chained reloads at 2 to prevent infinite loops (e.g., if Excel auto-save keeps triggering events).
- Use a simple counter: `_pending_reload_count` incremented on each event within the window, decremented after each reload. If > 0 after a reload completes, schedule one more.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
