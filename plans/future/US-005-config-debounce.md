# US-005: Config Save Debouncing

**Epic:** Performance & Reliability
**Type:** Improvement
**Priority:** MEDIUM
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user,
I want config file saves to be debounced so that rapidly toggling settings doesn't cause excessive disk I/O,
So that theme changes feel snappy and the config file isn't rewritten on every single checkbox click.

---

## Context

`gui/main_window.py` — Every theme toggle or a11y setting change triggers `yaml.safe_dump()` to write the full config file to disk. Rapid toggling (e.g., cycling through colorblind modes) causes multiple writes per second.

---

## Acceptance Criteria

1. Given the user toggles the theme from light to dark, when the change occurs, then the config file is not written immediately — a debounce timer starts.
2. Given the debounce timer is running, when the user changes another setting within 2 seconds, then the timer resets (not a new write queued per change).
3. Given the debounce timer expires (no changes for 2 seconds), when the timer fires, then the config file is written exactly once with the cumulative changes.
4. Given the app is closing, when `closeEvent` fires, then any pending debounced save is flushed immediately (no data loss).
5. Given the debounce logic is in place, when the user rapidly toggles a setting 10 times, then at most 2 config file writes occur (one debounced batch + one on close).

---

## Implementation Notes

- Use a `QTimer` with `setSingleShot(True)` and a 2-second interval.
- `QTimer.start()` on each setting change resets the single-shot timer.
- Connect `QCoreApplication.aboutToQuit` or override `closeEvent` to call the save directly.
- Store pending changes in a dict, apply all at once on flush.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
