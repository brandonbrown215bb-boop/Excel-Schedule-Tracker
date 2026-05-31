# Technical Review — Consolidated Findings (All 22 Stories)

**Date:** 2026-05-31
**Parts:** REVIEW_technical_A (US-001,002,002b,003,004,005,007,018), REVIEW_technical_B (US-008-015), REVIEW_technical_C (US-016-022)

---

## Stories That Should Be CLOSED (Already Implemented)

| Story | Finding | Action |
|-------|---------|--------|
| **US-004** (Backup makedirs, 2 pts) | `os.makedirs(archive_dir, exist_ok=True)` is already on line 33 of `vba_native.py`. | **CLOSE** — zero work remaining. |
| **US-010** (config_path cleanup, 1 pt) | `config_path` not in source `config.yaml`; already stored as `self._config_path`; already stripped from YAML writes at main_window.py:1129. | **CLOSE** — verification only; all ACs satisfied. |

---

## Stories That Need Significant Rewrites

### US-001 — Thread Safety (8 pts)
**Problem:** Misdiagnosis. The story claims `_row_by_com`/`_fingerprint_by_com` are on `MainWindow` — they're on `WorkbookCache` in `data/loader.py`. `self.units` is the only shared mutable state on MainWindow, and it's replaced atomically via signal/slot. `_io_busy` already prevents concurrent access. The `_io_busy` flag is NOT set during saves.

**Actual bug:** `_io_busy` doesn't cover the save path. Fix: extend `_set_io_busy(True/False)` to `SaveWorker`. **2 lines, not a QMutex.**

**Rewrite to:** Extend `_io_busy` to guard saves → **3 pts**

### US-003 — Worker Error Dialogs (5 pts)
**Problem:** Error dialogs **already exist** — `_on_load_error()` shows `QMessageBox.critical()` and `_on_save_error()` shows `QMessageBox.warning()`. The story's core premise is wrong.

**Actual gap:** Missing throttling (max 3 dialogs/10s) and retry option for load errors. Existing `error` signal takes single `str`, not `(str, str)`.

**Rewrite to:** Add throttling + retry to existing error handling → **3 pts**

### US-018 — Workbook Locking (5 pts)
**Problem:** Proposes `os.O_EXCL` which doesn't work for this use case (it's for exclusive *creation*, not locking). **Fails to mention existing `LockManager` in `sync/lock_manager.py`** which already handles inter-app coordination. Conflates two different locking scenarios (inter-app vs. Excel-has-file-open).

**Rewrite to:** Leverage existing `LockManager.write_lock()` + add Excel-lock detection at `SaveWorker` level + integrate with `RevisionStore` for retry → **8 pts**

### US-020 — Incremental Reload (8 pts)
**Problem:** Cache-first reload is **already implemented** (`force_reload=False` → `_cache_is_fresh()` check). True incremental reading is **impossible with openpyxl** (streaming parser, no random access). The "no flicker" AC3 would require implementing a full Qt model diff (React-style reconciliation) — alone worth 13+ pts.

**Rewrite / split:**
- **US-020a:** Optimize full reload performance (better cache utilization, faster parsing) — **3 pts**
- **US-020b:** Implement list panel diffing for no-flicker updates — **8-13 pts** (new story, separate sprint)

---

## Stories With Premise/Approach Errors

### US-002 — Pickle Security (5 pts)
- HMAC key management problem: where does the key live? Storing next to the cache is security theater.
- **Better approach:** Use a restricted `Unpickler` with a custom `find_class` that only allows safe types (`Unit`, `WorkbookCache`, primitives). Standard Python pattern.
- **Two `pickle.load()` call sites** need hardening: `_load_units_from_pickle()` (line 294) AND `_cache_is_fresh()` (line 381). Story only mentions one.
- **Point estimate: 5 pts — accurate** (if approach corrected to Unpickler).

### US-005 — Config Debounce (3 pts)
- Improvement needed: `closeEvent` already calls `_save_ui_config()` directly. Must cancel debounce timer on close to avoid double-write.
- `config_path` filtering in `_save_ui_config()` must be preserved through debounce.
- **Point estimate: 3 pts — accurate.**

### US-007 — File Watcher Debounce (5 pts)
- Current code is **more sophisticated** than story suggests: has 5-second coalescing + file-readiness polling (500ms) + 8-second deadline + PK header validation.
- The actual gap is smaller than described.
- **Point estimate: 3 pts** — actual remaining edge cases are fewer.

### US-009 — Date Filter Presets (2 pts)
- **Already implemented.** `DATE_FILTER_PRESETS` at list_panel.py:92 is a data structure; dropdown is built dynamically. Proposed `(label, days_offset, is_past)` format is **less capable** than existing (loses "This Month", "Next Month", "Past 30 Days").
- **CLOSE** or rewrite to "make presets configurable via config.yaml".

### US-012 — save_master() No-Op (1 pt)
- Story says line ~200 — **actual line is 22**. Story says it "logs a message" — **actual body is `pass`**.
- Tests exist that reference it (test_vba_native.py:20-33, test_imports.py:41) — must be updated if removed.
- **Point estimate: 1 pt — accurate** if documenting; 2 pts if removing.

### US-014 — Cache Hash (3 pts)
- Chunked reading should be a **requirement**, not a suggestion.
- `WorkbookCache.from_pickle()` backward compatibility already handles schema migration.
- HMAC from US-002 (Sprint 1) and content hash from US-014 must be coordinated — HMAC should sign the content hash, not mtime+size.
- **Point estimate: 3 pts — accurate.**

### US-019 — Dependency Pins (1 pt)
- **Premise is wrong:** `requirements.txt` already has lower-bound pins (`>=X.Y`). What's missing is upper-bound caps (`<X+1.0`).
- AC2 references "Python 3.14" which doesn't exist. Replace with actual minimum supported version.
- `requests` dependency is suspicious in a desktop PyQt5 app — may be leftover from prototyping.
- **Point estimate: 1 pt — defensible** if just adding upper bounds; 2 pts if testing compatibility.

---

## Stories Where Point Estimates Need Adjustment

| Story | Current | Recommended | Reason |
|-------|---------|-------------|--------|
| US-001 | 8 | 3 | Wrong diagnosis; actual fix is 2 lines |
| US-003 | 5 | 3 | Dialogs already exist; just add throttling + retry |
| US-004 | 2 | **0 (close)** | Already implemented |
| US-007 | 5 | 3 | Code is more sophisticated than story assumes |
| US-009 | 2 | **0 (close)** | Already implemented |
| US-010 | 1 | **0 (close)** | Already implemented |
| US-015 | 3 | 5 (or split 1+4) | 96 contrast combos + color adjustment loop |
| US-018 | 5 | 8 | os.O_EXCL wrong approach; must integrate LockManager + RevisionStore |
| US-019 | 1 | 1-2 | Premise wrong; actual work is adding upper bounds |
| US-020 | 8 | 3 (part A) + 8-13 (part B) | Already partially done; UI diffing is huge |
| US-022 | 3 | 5 | Wrong class ref; needs new resizeEvent + multiple invalidation triggers |

---

## Well-Scoped Stories (Proceed As-Is)

These stories are technically sound, correctly referenced, and properly estimated:
- **US-005** (Config debounce, 3 pts) — minor closeEvent interaction to handle
- **US-008** (Calendar dot count, 3 pts) — tooltip complexity is manageable; watch badge-dot overlap
- **US-011** (StatusColor docs, 1 pt) — `calculated_status_color` indeed never returns purple/orange
- **US-013** (Theme refactor, 5 pts) — use `isinstance()` not `type()` for handler lookup
- **US-016** (setup_ui refactor, 3 pts) — note: `_setup_ui()` doesn't exist; it's `__init__` that's monolithic
- **US-017** (milestones cache, 2 pts) — straightforward; date mutations don't affect milestones
- **US-021** (fingerprint cache, 2 pts) — feasible but very low ROI; consider deprioritizing

---

## Recommended Technical Approach Changes

1. **US-002:** Use restricted `Unpickler` instead of HMAC. Simpler, no key management problem, standard Python pattern.
2. **US-001:** Don't add QMutex. Extend `_io_busy` to cover saves. 2 lines.
3. **US-018:** Leverage existing `LockManager` + `RevisionStore`. Don't implement new file locking from scratch.
4. **US-020:** Split into "optimize full reload" (3 pts) and "UI diffing" (new story, 8-13 pts). Don't claim "incremental openpyxl reading" — it's impossible.
5. **US-013:** Handler registry must iterate with `isinstance()`, not `type()` dict lookup, to preserve subclass matching (e.g., `EventCalendarWidget` → `QCalendarWidget`).
6. **US-022:** Cache goes on `TimelineWidget` (inner), not `TimelinePanel` (outer wrapper). Must add new `resizeEvent()` override to `TimelineWidget`.

---

## Corrected Point Total

| Category | Original | Corrected |
|----------|----------|-----------|
| Stories to close | 0 | 3 (US-004, US-009, US-010) = -5 pts |
| Point adjustments | 67 | ~53 (net of closes + estimates - splits) |
| New story from split (US-020b) | 0 | +8 to +13 |
| **Adjusted total** | **67** | **~56-61** (without US-020b) or **~64-69** (with US-020b) |
