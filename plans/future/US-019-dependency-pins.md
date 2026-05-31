# US-019: Add Upper-Bound Version Caps to requirements.txt

**Epic:** Maintainability
**Type:** Improvement
**Priority:** LOW
**Story Points:** 1
**Status:** Unstarted

---

## Story

As a developer setting up the project,
I want all dependencies in `requirements.txt` to have both lower and upper version bounds,
So that `pip install -r requirements.txt` produces a consistent environment and doesn't break on upstream major-version changes.

---

## Context

`requirements.txt` — Dependencies already have lower-bound pins (e.g., `PyQt5>=5.15.0`). What's missing are upper-bound caps to prevent automatic upgrades to breaking major versions (e.g., PyQt6, openpyxl 4.x).

---

## Acceptance Criteria

1. Given `requirements.txt` is updated, when read, then every line specifies both a lower and upper bound (e.g., `PyQt5>=5.15,<6.0`).
2. Given the pinned ranges, when `pip install -r requirements.txt` runs on the minimum supported Python version (3.12+), then all packages install without conflicts.
3. Given a pin exists, when a new major version of a dependency is released, then the upper bound prevents automatic upgrade (developer must consciously update the range).

---

## Implementation Notes

- Add upper-bound caps: `PyQt5>=5.15,<6.0`, `openpyxl>=3.1,<4.0`, `pyyaml>=6.0,<7.0`, `requests>=2.28,<3.0`.
- Verify each bound by checking the current major version on PyPI. Don't guess — check the actual latest release.
- Pin format: `>=X.Y,<X+1.0` (allows patch/minor updates, blocks major breaking changes).

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
