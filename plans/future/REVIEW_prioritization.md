# Backlog Prioritization Review

**Date:** 2026-05-31
**Reviewer:** Product Owner (AI)
**Scope:** All 22 user stories + BACKLOG_INDEX.md sprint plan
**Stakeholder Profile:** Single developer (Pigeon), pragmatic, ships fast, hates rework, values clean architecture + WCAG AA

---

## Executive Summary

The backlog is well-structured overall — the epic grouping is logical, the point totals are reasonable, and the extraction from CODE_REVIEW.md is thorough. However, there are **significant issues with priority labeling, dependency ordering, sprint balance, and coverage gaps**. The most critical finding: **three stories are miscategorized as LOW priority that should be MEDIUM**, and **the dependency graph is incomplete, creating a scheduling risk in Sprint 1**. Two stories have a hard circular dependency within Sprint 1 that needs explicit sequencing. A missing story for `parse_date` silent-failure logging was overlooked entirely. Two stories have meaningful overlap but should not be merged.

---

## 1. Priority Correctness

### 1.1 US-014 (Cache Content Hash) — Priority: LOW → **Should be MEDIUM**

**Current:** LOW (3 pts)
**Rationale for change:** US-014 is the **security-adjacent cousin of US-002 (pickle security)**. US-002 hardens the pickle deserialization path, but if the cache invalidation is also broken (returns stale data silently), users load wrong data — a data integrity bug that can cause incorrect business decisions. Since US-002 is in Sprint 1 and US-014 is in Sprint 4, this creates a window where the cache can serve stale data to a "secured" loader. The fix is tightly coupled with US-002's acceptance criteria (AC #2: "cache is rebuilt from source"). US-014 should be **MEDIUM** and moved to Sprint 2 to close this window.

### 1.2 US-018 (Workbook Locking During Save) — Priority: MEDIUM → **Should be HIGH**

**Current:** MEDIUM (5 pts)
**Rationale for change:** US-018 prevents **data corruption** from concurrent saves. For a single-user desktop app this is medium, but the app has a multi-user sync feature (`sync/lock_manager.py`, `multi_user` config). If two users save simultaneously, the workbook can be corrupted — this is a data-loss bug. The story is already in Sprint 2, which is fine, but the priority label should be HIGH to reflect the actual risk. This is the same severity class as US-001 (thread safety, HIGH) and US-002 (pickle security, HIGH).

### 1.3 US-020 (Incremental Reload) — Priority: LOW → **Should be MEDIUM**

**Current:** LOW (8 pts)
**Rationale for change:** US-020 is the highest-point story in the backlog (8 pts) and directly impacts **every user interaction** after the file watcher fires. For large workbooks (>500 rows), the current full reload causes visible UI lag. This is a daily-friction issue, not a nice-to-have. The story is already in Sprint 3, which is reasonable, but labeling it LOW understates its user impact. It should be MEDIUM.

### 1.4 US-003 (Worker Error Dialogs) — Priority: MEDIUM → **Should be HIGH**

**Current:** MEDIUM (5 pts)
**Rationale for change:** Silent save failures = **data loss without user knowledge**. This is the single most dangerous reliability gap in the app. If a save fails and the user doesn't know, they close the app and lose work. This is a higher-severity issue than file watcher debounce (US-007) or calendar dot counts (US-008). It should be HIGH. It's already in Sprint 1, which is correct, but the label should match.

### 1.5 US-015 (WCAG AA Contrast) — Priority: MEDIUM → **Correct as-is**

WCAG AA compliance is correctly MEDIUM. It's a compliance requirement but doesn't cause data loss or crashes. The story is well-scoped and correctly placed in Sprint 2.

### 1.6 US-004 (Backup makedirs) — Priority: MEDIUM → **Could be LOW**

**Current:** MEDIUM (2 pts)
**Rationale:** This is a single-line fix (`os.makedirs(..., exist_ok=True)`) that only affects the backup path. The impact is a `FileNotFoundError` crash — annoying but not data-damaging. It's already in Sprint 1 as a 2-point filler, which is fine, but the priority could honestly be LOW. Keeping it MEDIUM is acceptable since it's in Sprint 1 anyway.

### 1.7 Summary of Priority Changes

| Story | Current | Recommended | Reason |
|-------|---------|-------------|--------|
| US-003 | MEDIUM | **HIGH** | Silent data loss on save failure |
| US-014 | LOW | **MEDIUM** | Data integrity, tightly coupled with US-002 |
| US-018 | MEDIUM | **HIGH** | Data corruption from concurrent saves |
| US-020 | LOW | **MEDIUM** | Daily UX friction for large workbooks |

---

## 2. Dependency Graph

### 2.1 Hard Dependencies (Must Be Sequenced)

```
US-001 (Thread Safety)
  ├──→ US-007 (File Watcher Debounce) — US-007's "last event wins" pattern
  │       requires US-001's mutex to be in place first, otherwise the
  │       debounce timer and the reload can race on _units.
  │
  ├──→ US-003 (Worker Error Dialogs) — US-003 adds error signals to the
  │       same workers that US-001 adds mutexes to. Doing US-003 first
  │       means refactoring the worker class twice (once for signals,
  │       once for mutex). US-001 first is more efficient.
  │
  └──→ US-020 (Incremental Reload) — US-020's row-hash comparison
          requires thread-safe access to _fingerprint_by_com,
          which US-001 provides.

US-002 (Pickle Security)
  └──→ US-014 (Cache Hash) — US-014's content hash is a prerequisite
          for US-002's HMAC verification to be meaningful. If the
          cache invalidation is broken (US-014 not done), the HMAC
          in US-002 will reject valid caches or accept stale ones.
          Ideally US-014 should be done BEFORE or ALONGSIDE US-002.

US-002b (Path Sanitization)
  └──→ US-020 (Incremental Reload) — US-020 reads the excel_path
          for row-hash comparison. If the path is not sanitized
          (US-002b), US-020 could read from an unexpected location.
          This is a soft dependency but worth noting.

US-013 (Theme Refactor)
  └──→ US-015 (WCAG AA Contrast) — US-015 tests contrast ratios
          on themed colors. If US-013 changes the theme handler
          registry, US-015's test assertions may need updating.
          US-013 should be done before US-015.

US-006 (Test Coverage) — SPLIT across Sprint 3 & 4
  ├── Part 1 (Sprint 3): Depends on US-001 (thread safety tests),
  │   US-002 (cache security tests), US-003 (error dialog tests)
  ├── Part 2 (Sprint 4): Depends on US-013 (theme refactor tests),
  │   US-015 (contrast tests), US-016 (setup_ui refactor tests)
  └── This split is WELL-DESIGNED — the story correctly acknowledges
      it must be split and the split point aligns with dependencies.

US-016 (setup_ui Refactor)
  └──→ US-005 (Config Debounce) — US-005 adds a QTimer to
          main_window.py. If US-016 refactors _setup_ui() first,
          US-005's timer setup goes into the right extracted method.
          Doing US-016 before US-005 avoids rework.
```

### 2.2 Sprint 1 Dependency Conflict (CRITICAL)

**Problem:** Sprint 1 contains both US-001 (Thread Safety, 8 pts) and US-003 (Worker Error Dialogs, 5 pts). US-003 depends on US-001 (see above). If Pigeon works on US-003 first, he'll refactor the worker class twice. **Recommendation:** Explicitly sequence: US-001 must be completed before US-003 starts. Add a note to the sprint plan.

### 2.3 US-002 → US-014 Dependency Window (MODERATE)

US-002 (Sprint 1) and US-014 (Sprint 4) are separated by 2 sprints. During Sprints 2-3, the app will have HMAC-secured pickle loading but mtime+size-based cache invalidation. This means a stale cache could pass the HMAC check (the file hasn't been tampered with, it's just old) and serve outdated data. **Recommendation:** Move US-014 to Sprint 2, alongside or right after US-002's security work.

### 2.4 Dependency Matrix

| Story | Depends On | Blocks |
|-------|-----------|--------|
| US-001 | — | US-003, US-007, US-020 |
| US-002 | US-014 (ideally) | — |
| US-003 | US-001 | — |
| US-004 | — | — |
| US-005 | US-016 (soft) | — |
| US-006 | US-001, US-002, US-003, US-013 | — |
| US-007 | US-001 | — |
| US-008 | — | — |
| US-009 | — | — |
| US-010 | — | — |
| US-011 | — | — |
| US-012 | — | — |
| US-013 | — | US-015, US-006 Part 2 |
| US-014 | — | US-002 (soft) |
| US-015 | US-013 | — |
| US-016 | — | US-005 |
| US-017 | — | — |
| US-018 | — | — |
| US-019 | — | — |
| US-020 | US-001, US-002b (soft) | — |
| US-021 | — | — |
| US-022 | — | — |

---

## 3. Sprint Plan Quality

### 3.1 Capacity Analysis

| Sprint | Committed Points | At 80% velocity | At 85% velocity | Status |
|--------|-----------------|-----------------|-----------------|--------|
| Sprint 1 | 21 | 16.8–17.8 | 17.9–18.9 | ⚠️ **OVER** at 80% |
| Sprint 2 | 18 (15 + 3 stretch) | 14.4–15.3 | 15.3–16.2 | ✅ OK if stretch is truly stretch |
| Sprint 3 | 21 | 16.8–17.8 | 17.9–18.9 | ⚠️ **OVER** at 80% |
| Sprint 4 | 16 | 12.8–13.6 | 13.6–14.5 | ✅ OK |

**Problem:** Sprints 1 and 3 are both 21 points. For a single developer, 21 points is aggressive — that's the full 100% capacity, leaving zero buffer for unexpected issues, debugging, or context switching. The 80/85% rule means a single dev should commit to **17–18 points max** per sprint.

**Recommendation:**
- Move US-011 (StatusColor docs, 1 pt) from Sprint 1 to Sprint 4. It's LOW priority documentation that doesn't need to be in the foundation sprint. This brings Sprint 1 to 20 pts — still slightly over but more manageable.
- Move US-014 (Cache hash, 3 pts) from Sprint 4 to Sprint 2 (see dependency analysis). This balances Sprint 3 (21 → 21, unchanged) but improves Sprint 4 (16 → 13, very comfortable).

### 3.2 Sprint Balance

**Sprint 1 (Foundation & Safety):** Good theme. Thread safety + pickle security + error dialogs + backup fix is a coherent "make the app not crash or lose data" sprint. However, it's the heaviest sprint (21 pts) and contains the most complex story (US-001, 8 pts). This is risky — if US-001 takes longer than estimated, the entire sprint slips.

**Sprint 2 (Reliability & UX):** Good theme. File watcher + workbook locking + calendar dot + WCAG is a nice mix of backend and frontend. The stretch goal (US-002b) is correctly labeled. This sprint is well-balanced.

**Sprint 3 (Performance & Quality):** Mixed theme. Incremental reload (performance) + test coverage (quality) + theme refactor (maintainability) + cache hash (reliability). This sprint lacks a unifying theme and is also 21 pts. The stories are also the most complex in the backlog (US-020 = 8 pts, US-006 Part 1 = 5 pts, US-013 = 5 pts). This is the riskiest sprint.

**Sprint 4 (Cleanup & Polish):** Excellent theme. All LOW priority maintainability items. This is correctly positioned as the "if we get here" sprint. The 16-point total is comfortable.

### 3.3 Sprint Sequencing Issues

1. **US-013 (Theme Refactor, Sprint 3) should come before US-015 (WCAG AA, Sprint 2).** US-015 tests contrast on themed colors. If the theme system is refactored in Sprint 3, the contrast tests written in Sprint 2 may need updating. Either move US-013 to Sprint 2 or move US-015 to Sprint 3.

2. **US-016 (setup_ui Refactor, Sprint 4) should come before US-005 (Config Debounce, Sprint 4).** Both are in Sprint 4, so this is a within-sprint sequencing issue. US-016 should be done first so US-005's timer setup goes into the right extracted method.

3. **US-006 (Test Coverage) split is well-designed.** The Part 1 / Part 2 split across Sprint 3/4 correctly reflects that some tests can only be written after the code they test is refactored. No changes needed.

### 3.4 Revised Sprint Plan (Recommended)

```
Sprint 1 — Foundation & Safety (20 pts)
- US-001: Thread synchronization (8)         ← Do FIRST
- US-002: Pickle security (5)
- US-003: Worker error dialogs (5)           ← After US-001
- US-004: Backup makedirs (2)

Sprint 2 — Reliability & Security Hardening (18 pts)
- US-014: Cache hash (3)                     ← Moved from Sprint 4
- US-007: File watcher debounce (5)
- US-018: Workbook locking (5)
- US-008: Calendar dot count (3)
- US-002b: Path sanitization (2) — stretch

Sprint 3 — Performance & Maintainability (21 pts)
- US-020: Incremental reload (8)
- US-013: Theme refactoring (5)
- US-015: WCAG AA contrast (3)               ← After US-013
- US-006: Test coverage Part 1 (5)

Sprint 4 — Cleanup & Polish (15 pts)
- US-016: _setup_ui() refactor (3)           ← Do FIRST
- US-005: Config debounce (3)                ← After US-016
- US-006: Test coverage Part 2 (8)
- US-009: Date filter presets (2)
- US-017: milestones cache (2)
- US-021: fingerprint cache (2)
- US-022: timeline paint cache (3)
- US-010: config_path cleanup (1)
- US-011: StatusColor docs (1)               ← Moved from Sprint 1
- US-012: save_master noop (1)
- US-019: dependency pins (1)
```

---

## 4. Missing Stories

### 4.1 MISSING: `parse_date` Silent Failure Logging (from CODE_REVIEW.md #10, ✅ FIXED)

**Status:** This was marked as ✅ FIXED in CODE_REVIEW.md, so it's correctly excluded from the backlog. No action needed.

### 4.2 MISSING: `check_status` Column — Remove or Integrate (from CODE_REVIEW.md #20, ✅ FIXED)

**Status:** Marked ✅ FIXED (dead classes removed). Correctly excluded.

### 4.3 MISSING: Dead Commented-Out Code in `main.py` (from CODE_REVIEW.md #18, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.4 MISSING: `Unit.working_days` Type Mismatch (from CODE_REVIEW.md #5, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.5 MISSING: TimelinePanel Empty State (from CODE_REVIEW.md #15, ❌ FALSE POSITIVE)

**Status:** Correctly identified as false positive — empty states already exist. No story needed.

### 4.6 MISSING: Workbook Handle Leak (from CODE_REVIEW.md #6, ❌ FALSE POSITIVE)

**Status:** Correctly identified as false positive — already has try/finally. No story needed.

### 4.7 MISSING: `actual_hours` Field in EditForm (from CODE_REVIEW.md #4, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.8 MISSING: Formula Row-Reference Bug (from CODE_REVIEW.md #1, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.9 MISSING: QMessageBox Before QApplication (from CODE_REVIEW.md #3, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.10 MISSING: Mixed A1/R1C1 Notation (from CODE_REVIEW.md #2, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.11 MISSING: `_loading` Guard Pattern (from CODE_REVIEW.md #23, ✅ FIXED)

**Status:** Marked ✅ FIXED (replaced with `blockSignals()`). Correctly excluded.

### 4.12 MISSING: `config_path` Stripped from YAML Writes (from CODE_REVIEW.md #7, ✅ FIXED)

**Status:** Marked ✅ FIXED. Correctly excluded.

### 4.13 POTENTIAL GAP: No Story for `conftest.py` Fixture Documentation

US-006 Part 2 (Sprint 4) includes AC #11: "fixture dependencies are documented in a docstring." This is captured within US-006, so it's not missing — it's just a small item bundled into a large story. This is acceptable.

### 4.14 POTENTIAL GAP: No Story for `edit_form.py` `actual_hours` Save Behavior

The `actual_hours` field was added to EditForm (CODE_REVIEW.md #4, ✅ FIXED), but US-006's test coverage story (AC #3) includes testing that `_on_save()` persists `actual_hours`. This is correctly captured within US-006.

### 4.15 POTENTIAL GAP: No Story for `vba_native.py` Formula Test Updates

US-006 Part 1 (AC #2) includes updating formula tests to validate per-row references. This is correctly captured.

### 4.16 REAL GAP: No Story for `Unit.checking_status` — Dead Data

CODE_REVIEW.md #20 notes that `checking_status` is read from Excel but never used in business logic. This was marked ✅ FIXED (dead classes removed), but the underlying issue — that `checking_status` is stored in the Unit dataclass but never consumed — may still exist. If it does, a story should exist to either:
- (a) Use `checking_status` in status color calculations, or
- (b) Remove it from the Unit dataclass and COLUMN_MAP.

**Recommendation:** Verify whether `checking_status` is still in the Unit dataclass. If yes, add a 1-point story to US-011's epic (Maintainability) to document or remove it.

---

## 5. Duplicates and Overlaps

### 5.1 US-014 (Cache Hash) and US-002 (Pickle Security) — PARTIAL OVERLAP

**Overlap:** Both stories touch cache file integrity. US-002 adds HMAC to pickle files; US-014 replaces mtime+size with SHA-256 for cache invalidation. They both modify `data/loader.py` cache logic.

**Should they be merged?** No. They address different threats:
- US-002 = **tampering** (malicious modification of .pkl files)
- US-014 = **staleness** (legitimate but outdated cache)

However, they should be **sequentially scheduled** (US-014 before US-002) because the HMAC in US-002 should sign the content hash from US-014, not the mtime+size tuple. If done in the current order (US-002 in Sprint 1, US-014 in Sprint 4), the HMAC will sign mtime+size, and when US-014 later changes the content signature format, the HMAC verification will break.

**Recommendation:** Move US-014 to Sprint 2 and make it a prerequisite for US-002's HMAC implementation. Or, if US-002 is already implemented with mtime+size HMAC, add a follow-up task to US-014 to re-sign with content hash.

### 5.2 US-021 (Fingerprint Cache) and US-014 (Cache Hash) — MINOR OVERLAP

**Overlap:** Both involve caching hash results. US-014 caches the SHA-256 hash of the Excel file; US-021 caches the SHA-256 hash of individual units.

**Should they be merged?** No. They cache different things at different scopes (file-level vs. unit-level). But they could share a common caching utility. Consider adding a shared `_cached_hash()` helper that both stories can use.

### 5.3 US-017 (milestones Cache) and US-022 (Timeline Paint Cache) — MINOR OVERLAP

**Overlap:** Both cache computed results to avoid recomputation during paint events. US-017 caches the `milestones` property on Unit; US-022 caches layout positions in TimelinePanel.

**Should they be merged?** No. US-017 is a data model change; US-022 is a UI rendering change. They're in different layers of the architecture.

### 5.4 US-011 (StatusColor Docs) and US-012 (save_master No-Op Docs) — THEMATIC OVERLAP

**Overlap:** Both are 1-point documentation-only stories in the Maintainability epic.

**Should they be merged?** They could be combined into a single "Documentation Cleanup" story (2 pts), but keeping them separate is fine since they touch different files (`data/models.py` vs. `automation/vba_native.py`). No action needed.

### 5.5 US-010 (config_path Cleanup) and US-005 (Config Debounce) — THEMATIC OVERLAP

**Overlap:** Both touch config file handling. US-010 removes `config_path` from the YAML template; US-005 debounces config writes.

**Should they be merged?** No. US-010 is a one-line template fix; US-005 is a new feature (debounce timer). Different scope and complexity.

---

## 6. ROI Analysis

### 6.1 Highest ROI Stories (Do First)

| Story | Points | ROI Rationale |
|-------|--------|---------------|
| US-004 | 2 | Single-line fix, prevents backup crashes. 10-minute job. |
| US-011 | 1 | Documentation-only, prevents developer confusion. 5-minute job. |
| US-019 | 1 | Prevents future breakage from upstream dependency changes. 5-minute job. |
| US-012 | 1 | Documentation-only, prevents confusion about dead code. 5-minute job. |
| US-010 | 1 | One-line template fix, prevents config pollution. 5-minute job. |
| US-003 | 5 | Prevents silent data loss. High user impact, moderate effort. |
| US-002 | 5 | Security hardening. Low effort for defense-in-depth. |

### 6.2 Lowest ROI Stories (Defer if Needed)

| Story | Points | ROI Rationale |
|-------|--------|---------------|
| US-020 | 8 | High effort, only affects large workbooks. Nice-to-have for small files. |
| US-006 | 13 | Largest story. Essential for long-term maintainability but delivers no user-visible value. |
| US-013 | 5 | Refactoring for Open/Closed Principle. Valuable but no user-visible change. |
| US-022 | 3 | Paint optimization. Only noticeable with many repaints. |

### 6.3 Risk-Adjusted Priority

If Pigeon needs to cut scope to hit a deadline, the recommended cut order (last in = first cut):
1. US-022 (timeline paint cache) — LOW impact, LOW user visibility
2. US-021 (fingerprint cache) — LOW impact, LOW user visibility
3. US-017 (milestones cache) — LOW impact, LOW user visibility
4. US-020 (incremental reload) — HIGH impact but HIGH effort; defer if needed
5. US-013 (theme refactor) — No user-visible change; pure maintainability

**Never cut:** US-001, US-002, US-003, US-018 — these prevent data loss/corruption.

---

## 7. Final Recommendations

### Critical Actions (Before Sprint 1 Starts)

1. **Re-sequence Sprint 1:** US-001 must be completed before US-003 starts. Add explicit ordering note.
2. **Move US-014 to Sprint 2:** Cache hash should be done alongside pickle security, not 3 sprints later.
3. **Fix priority labels:** US-003 → HIGH, US-018 → HIGH, US-014 → MEDIUM, US-020 → MEDIUM.

### Important Actions (Before Sprint 2 Starts)

4. **Move US-013 before US-015:** Either swap US-013 to Sprint 2 or move US-015 to Sprint 3.
5. **Sequence within Sprint 4:** US-016 before US-005 to avoid rework.

### Nice-to-Have Actions

6. **Verify `checking_status` usage:** If the field is still in the Unit dataclass but unused, add a 1-point story.
7. **Consider a shared caching utility:** US-014, US-017, US-021, and US-022 all implement similar "compute once, cache until dirty" patterns. A shared decorator or mixin would reduce code duplication.
8. **Add a "Definition of Done" checklist to each story:** Currently, only INVEST checklists exist. Adding a DoD (code reviewed, tests pass, no new pyright errors) would help Pigeon ship with confidence.

---

## 8. Revised Story Point Total

| Priority | Current Count | Recommended Count |
|----------|--------------|-------------------|
| HIGH | 2 (US-001, US-002) | 4 (+US-003, US-018) |
| MEDIUM | 10 | 10 (net: US-014↑, US-003↑, US-018↑, US-020↑) |
| LOW | 10 | 8 (US-014↓, US-003↓, US-018↓, US-020↓) |

Total points unchanged at 67. Only labels and sprint positions change.
