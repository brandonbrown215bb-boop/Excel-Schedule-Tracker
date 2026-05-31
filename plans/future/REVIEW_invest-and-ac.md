# INVEST & Acceptance Criteria Review — All 22 User Stories

**Reviewer:** Agilent Coach (Subagent)  
**Date:** 2026-05-31  
**Scope:** All 22 user stories in `plans/future/` derived from `CODE_REVIEW.md`  
**Total Points in Backlog:** 67

---

## Executive Summary

The backlog is well-structured overall: stories are derived from a code review, grouped into logical epics, and most have Given-When-Then acceptance criteria. However, several systemic issues cut across the set:

1. **Two stories are genuinely too large** (US-006 at 13 pts, US-001 at 8 pts touches multiple concurrency concerns) and should be split.
2. **Three stories have implicit hidden dependencies** that will create sprint-planning friction.
3. **~40% of acceptance criteria have testability gaps** — vague verbs ("feels snappy," "smooth," "briefly waits"), implementation-prescribing language, or missing edge cases.
4. **Several point estimates are inconsistent** with the apparent complexity when compared to sibling stories.
5. **11 stories are documentation/refactor-only** (aggregate ~19 pts) — low risk but also low user value per point; consider batching them.

Detailed findings follow, story by story, then cross-cutting themes.

---

## Story-by-Story Critique

---

### US-001: Thread Synchronization for Shared Mutable State
**Points:** 8 | ** epic:** Concurrency & Reliability | **INVEST claims:** All checked

#### INVEST Assessment

- **Independent?** ⚠️ Partial. US-001 shares the `_units` / `_row_by_com` / `_fingerprint_by_com` mutable state with US-007 (file watcher debounce) and US-003 (worker error signals). If US-001 defines the locking API (e.g., a `QMutex` wrapper), US-007 and US-003 must consume it. This is a **hidden dependency** that should be called out: *"US-001 must land before US-007 and US-003, as both consume the synchronization primitives US-001 introduces."*
- **Small?** ⚠️ Borderline at 8 pts. The story covers: (a) mutual exclusion via `QMutex`/`threading.Lock`, (b) ordering guarantees (reload waits for save), (c) exception safety (try/finally), (d) regression testing. That's arguably 3 sub-stories bundled: (i) locking, (ii) save/reload ordering, (iii) exception safety + regression. Consider: US-001a (locking only, 5 pts), US-001b (ordering + wait queue, 3 pts).

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Clear trigger and expected behavior. Testable via concurrent worker execution with assertions on ordering. |
| AC2 | ✅ Testable | Could be verified via a deterministic unit test with two threads. |
| AC3 | ⚠️ Vague | "No crash or data corruption" is the *absence* of a negative. What constitutes "data corruption"? Needs a positive assertion, e.g., "then all N units are present and no unit's fields contain values from a different unit's load cycle." |
| AC4 | ✅ Testable | Synthetically throw in worker body, assert lock released. |
| AC5 | ⚠️ Behavioral | "When existing tests pass" is a meta-test about the test suite, not about the feature. It belongs in the definition of done, not in AC. Replace with a concrete behavioral assertion. |

#### Missing AC
- What happens on **lock timeout**? If the save takes >N seconds, does the reload abort or wait indefinitely?
- What happens when the **GUI thread** needs to read `_units` while a worker holds the lock? (Potential UI freeze concern.)

#### Suggested Point Revision
- **8 → keep, but annotate as upper bound.** If split into two stories, 5 + 3 = same total but better flow.

---

### US-002: Secure Cache Deserialization
**Points:** 5 | **Epic:** Security | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Self-contained in `data/loader.py`.
- **Small?** ✅ 5 pts is appropriate for the HMAC approach (Option A).
- **Negotiable?** ✅ Yes — three implementation options given, story doesn't dictate the solution.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | "Data is validated before use" — test by constructing a valid cache, then mutating it, asserting rejection. |
| AC2 | ✅ Testable | Good negative case. Tamper with .pkl on disk, verify fallback to Excel parse. |
| AC3 | ✅ Testable | Verify that on tampered cache, the app logs a warning and returns valid units from Excel. |
| AC4 | ✅ Testable | Deploy new app version against old .pkl files, verify silent rebuild. |
| AC5 | ⚠️ Irrelevant | ≤10% vs. raw pickle is a **performance** criterion, not a **security** criterion. If security is the story's value proposition, mixing in a performance constraint muddies the acceptance. Either move to a performance epic or relax it (HMAC adds nanoseconds; this is a desktop app, not a high-frequency trading system). |

#### Missing AC
- AC for **HMAC key management**: Where does the key live? If it's embedded in the binary, what's the rotation strategy? Even acknowledging "this is a local desktop app, key is stored alongside the cache" would be better than silence.
- AC for **corrupt (non-tampered) cache**: What if a .pkl is truncated due to a crash mid-write? Is the fallback the same as for tampering?

#### Suggested Point Revision
- **5 → appropriate.**

---

### US-002b: File Path Input Sanitization
**Points:** 3 | **Epic:** Security | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Ties only to `config.yaml` loading.
- **Small?** ✅ 3 pts is right for a validation function + tests.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Under-specified | "Path is validated and rejected" — what is the rejection boundary? Is `../../allowed_dir/file.xlsx` rejected? It has `..` components but stays within the workspace. The AC should specify the **rejection policy**, e.g., "then the path is rejected if it resolves outside the directory containing `config.yaml` or the directory containing the `.xlsm` file." |
| AC2 | ✅ Testable | Happy path, no regression. |
| AC3 | ✅ Testable | Specific and concrete. |
| AC4 | ⚠️ Implementation-prescribing | "Resolved relative to the config file's directory" describes **how**, not **what behavior the user observes**. Rephrase as: "then the path is resolved correctly regardless of the current working directory from which the app is launched." |

#### Missing AC
- **Symlinks**: What if the path contains symlinks that traverse to `/etc/passwd`? The validation may pass on the literal string but the resolved path is the real attack vector.
- **UNC paths on Windows**: `\\server\share\file.xlsx` — is this valid or rejected?
- **Very long paths**: >260 chars on Windows could cause issues with `os.path` functions.

#### Suggested Point Revision
- **3 → appropriate**, but the missing edge cases will reveal themselves mid-sprint, effectively adding scope. Consider 5.

---

### US-003: Error Dialog for Background Worker Failures
**Points:** 5 | **Epic:** Concurrency & Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ⚠️ Partial. Depends on US-001's work being done first if the error signaling must go through the new synchronization layer (AC5 mentions `pyqtSignal`/`Slot` connection which is fine, but if US-001 restructures the worker, US-003's signal integration depends on it). **Add explicit dependency note.**
- **Small?** ✅ 5 pts for signal/slot wiring, dialog creation, rate-limiting logic, and tests.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Inject a failing save, assert `QMessageBox.critical` called on main thread. |
| AC2 | ⚠️ Under-specified | "With an option to retry" — what does retry mean? Re-emit the failed load? Show a Retry button? The AC specifies a UI element (retry option) without defining its behavior. Expand: "…and clicking retry re-queues the failed load." |
| AC3 | ⚠️ Untestable timing dependency | "Maximum of 3 dialogs per 10 seconds" — to test this, you need to simulate 4 errors within 10 seconds and assert only 3 dialogs. This is a rate limiter that would need time control (mocking time) to test deterministically. |
| AC4 | ✅ Testable | Straightforward. |
| AC5 | ⚠️ Implementation-prescribing | "It uses a pyqtSignal/Slot connection (not raw callbacks)" is about **how**, not **what**. This belongs in the implementation notes. Reformulate as a behavioral AC: "then the error dialog appears on the main thread regardless of which worker thread emitted the error." |

#### Missing AC
- **Logging consistency**: The existing behavior logs to the log file. Does the error dialog replace logging, or supplement it? Need AC: "then the error is both displayed in the dialog AND written to the log file."
- **User data on failure**: If a save fails, what happens to the user's in-memory edits? Are they preserved so retry is possible?

#### Suggested Point Revision
- **5 → appropriate.**

---

### US-004: Ensure Backup Directory Exists Before Writing
**Points:** 2 | **Epic:** Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 2 pts. This is arguably a 1-pointer (one line addition), but 2 pts accounts for the error-handling AC (#4) and test writing.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Delete archive dir, call backup(), verify dir created and file exists. |
| AC2 | ✅ Testable | Idempotency check. |
| AC3 | ✅ Testable | Assert return value. |
| AC4 | ✅ Testable | Remove write permissions, verify logged error. |

#### Missing AC
- **Atomicity**: If the directory is created but the copy fails partway, is the partial backup file cleaned up?
- **Path validity**: What if `archive_dir` is an empty string or a file path (not a directory)?
- **Available disk space**: Silently relevant, but probably overkill for this story.

#### Suggested Point Revision
- **2 → 1.** This is a single-line fix plus logging permission error handling. The scope is minimal. The "permissions error" AC is a stretch addition but still doesn't warrant 2 points when US-011 is 1 point for documentation-only.

---

### US-005: Config Save Debouncing
**Points:** 3 | **Epic:** Performance & Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 3 pts for QTimer setup, closeEvent integration, and test suite.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Verify no immediate file write after toggle. |
| AC2 | ✅ Testable | Verify timer reset behavior. |
| AC3 | ✅ Testable | Verify single write with cumulative changes. |
| AC4 | ✅ Testable | Close app mid-debounce, verify no data loss. |
| AC5 | ⚠️ Impl-detail leaking into AC | "At most 2 writes" is an assertion about **internal behavior**, not observable external behavior. Rephrase as: "then the config file on disk reflects all 10 setting changes." The "at most 2 writes" is an optimization detail the implementer can verify via spy. |

#### Missing AC
- **Crash during debounce**: If the app crashes before the debounce fires, are the pending changes lost? This is a real-world scenario for a desktop app that users force-close.

#### Suggested Point Revision
- **3 → appropriate.**

---

### US-006: Comprehensive Test Coverage Expansion
**Points:** 13 | **Epic:** Quality Assurance | **INVEST claims:** All checked except Small (correctly unchecked)

#### INVEST Assessment
- **Independent?** ⚠️ Yes in isolation, but AC2 depends on an external fix ("the formula row-reference bug is fixed") — this is a **cross-story dependency** that isn't tracked. If that fix is in a different story, AC2 must either be part of that story or a dependency must be recorded.
- **Small?** ✅ Honestly flagged. 13 is far too large. The story bundles: fixing existing tests (AC1-2), GUI tests (AC3-5), loader edge cases (AC6-8), sync tests (AC9-10), and fixture cleanup (AC11). That's **5 distinct sub-stories**.

**Recommendation: Split into:**
- **US-01a**: Fix existing test suite bugs (AC1-2) — 3 pts
- **US-01b**: GUI component tests (AC3-5) — 5 pts
- **US-01c**: Data layer edge cases (AC6-8) — 3 pts
- **US-01d**: Sync edge cases (AC9-10) — 3 pts
- **US-01e**: Fixture cleanup (AC11) — 1 pt

This split also explains the Sprint 3/Sprint 4 split already in the BACKLOG_INDEX (using 5 + 8 points), but the current split is ad-hoc (first 5 points for "fix existing + loader" and remaining 8 for "GUI tests"). The split should follow **domain boundaries**, not point arithmetic.

#### Acceptance Criteria Quality

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ❌ Untestable as stated | "…either actually calls save_unit and verifies the saved Excel data, or is renamed" — this AC **forks itself**. It accepts either of two mutually exclusive outcomes. Pick one: calling `save_unit` is the right behavior; the AC should require it. |
| AC2 | ⚠️ External dependency | Depends on a prior bug fix that's not in this story. If the formula fix is in a separate story, this AC is not actionable until that story lands. |
| AC3 | ⚠️ Vague behavior spec | "populates all fields correctly" — which fields? All fields in the Unit dataclass? All fields visible in the form? The AC should enumerate the fields or reference the Unit model by name: "then each field in `[list]` matches the corresponding attribute of the Unit passed to `set_unit()`." Same issue for "save persists all fields including `actual_hours`" — this is redundant with "all fields" unless it's a specific edge case being called out. |
| AC4 | ✅ Testable | Good specificity: multi-unit dates, signal emission. |
| AC5 | ✅ Testable | Specific: status names, color hex codes, both themes. |
| AC6 | ✅ Testable | Concrete: input `"2024/13/45"`, expect `None` + warning log. |
| AC7 | ✅ Testable | Good: clear error type (`ValueError`) replaces wrong error type (`KeyError`). |
| AC8 | ✅ Testable | Corrupt pkl → CSV/Excel fallback. |
| AC9 | ✅ Testable | Can be unit-tested with real threads. |
| AC10 | ✅ Testable | Stale lock detection. |
| AC11 | ⚠️ Process-oriented | "Dependencies are documented in a docstring" — this is a code quality gate, not a behavioral AC. It's a valid task but tested by **reading the code**, not by running software. Belongs in the Definition of Done or as a checklist item. |

#### Missing AC (for a test coverage story, the bar is high)
- **Coverage target**: No coverage percentage is defined. "Comprehensive" is subjective. Consider: "then overall line coverage is ≥ 80% and branch coverage is ≥ 70% as measured by `pytest-cov`."
- **CI integration**: Are these tests expected to run in CI, or just locally? An AC for CI would prevent the "test suite that no one runs" failure mode.
- **Performance baseline**: After all these tests are added, what's the max acceptable test suite runtime? For a 90-second test suite, developers stop running it.

---

### US-007: File Watcher Debounce Reliability
**Points:** 5 | **Epic:** Concurrency & Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ⚠️ Partial. AC1 and AC4 both reference behavior from US-001 (concurrent reloads and saves). The "second reload is queued" (AC1) and "first reload's result is discarded" (AC4) interaction depends on whether US-001's locking strategy serializes or allows interleaving. **Hidden dependency on US-001.**
- **Small?** ✅ 5 pts for the timer redesign + tests.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Contradicts stated context | Context says "cap at 2 total reloads to prevent loops" (Implementation Notes), but AC1 says "a second reload is queued." If the cap is 2, these are the same thing. But AC2 says "exactly one reload is triggered" — which is the current behavior! AC1 describes a *different* behavior. Clarify: After debounce fires once and catches the second event as pending, does it fire a *second* reload (contradicting AC2), or does the first reload *include* the data from AC1's second save? The ACs contradict each other. |
| AC2 | ⚠️ Same as current | This restates existing behavior. Not sure this is an acceptance criterion for a change. |
| AC3 | ✅ Testable | Regression guard. |
| AC4 | ✅ Testable | Testable with two sequential reload operations where the second has different data. |

#### Resolution Needed
The AC set needs a rewrite. The intent is: "after debounce fires, if events arrived during the wait, schedule ONE additional reload capped at 2 total." AC1 and AC2 should be consolidated.

#### Missing AC
- **File watcher desync**: If the file changes during the reload itself (e.g., while reading the Excel file), what happens? Is there a re-read guard?

#### Suggested Point Revision
- **5 → appropriate.**

---

### US-008: Calendar Date Dot — Show Count for Multi-Unit Dates
**Points:** 3 | **Epic:** UI/UX | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Purely in `calendar_panel.py`.
- **Small?** ✅ 3 pts. Visual rendering + accessibility check.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Concrete: 3 green + 1 red → red dot + "4" badge. |
| AC2 | ❌ Self-forking | "A count badge '1' is shown (or is optional for single-unit to reduce clutter — decision needed)." This AC presents two options and says "decision needed." This is a **product decision** that must be resolved **before** the story enters a sprint, not during implementation. Decide and select one. |
| AC3 | ✅ Testable | No-op baseline. |
| AC4 | ⚠️ Implementation-prescribing | "A tooltip lists each unit and its status" — this is fine as a UX spec, but a tooltip is a UI mechanism. Prefer: "then the user can discover the status of each unit on that date without navigating away." Let the implementer choose tooltip, popup, or inline. |
| AC5 | ⚠️ Cross-story dependency | "Meets WCAG AA contrast against **all** status colors" — this is the same concern as US-015. If US-015 adjusts status colors to pass WCAG AA, US-008's AC5 may need re-verification. **Add cross-reference to US-015.** |

#### Missing AC
- **Maximum count display**: What if a date has 97 units? Does the badge show "97"? Does it overflow? Need: "then the badge renders legibly for counts up to 99; counts >99 display '99+'."
- **Colorblind mode**: The badge renders on a colored dot. In colorblind modes (from AGENTS.md: protanopia/deuteranopia/tritanopia), do the worst-status colors change? Does the badge still make sense?

---

### US-009: Extract Date Filter Presets into Data Structure
**Points:** 2 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Self-contained refactor in `list_panel.py`.
- **Small?** ✅ 2 pts.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Impl-describing | "Adds one line to the structure" describes the developer's work, not system behavior. Prefer: "then adding a new filter preset requires no changes to filter logic." |
| AC2 | ✅ Testable | Verify dropdown items come from data structure. |
| AC3 | ✅ Testable | Regression test. |
| AC4 | ⚠️ Redundant/subsumed by AC3 | If AC3 says "behavior matches current implementation exactly," then today's behavior (days_offset=0 = today) is already covered. This AC is implied and adds no value. |

#### Missing AC
- **Serialization**: If the presets become user-configurable later, the data structure should be serializable. Not needed now, but worth noting.
- **Internationalization**: The labels ("Today," "Overdue") are in English. If this app is used by French/Japanese speakers, the data structure should keep labels separate from logic. Mention in implementation notes.

---

### US-010: Remove config_path from Source config.yaml Template
**Points:** 1 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 1 pt.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Visual/textual inspection of the template. |
| AC2 | ✅ Testable | Regression. |
| AC3 | ⚠️ Weak phrasing | "_should_ already handle this — verify" is not an AC. It's an investigation task. Either the code handles this (in which case it's a documentation story only) or it doesn't (in which case it's a fix). **Decide which and write the AC accordingly.** If it does handle it already, delete AC3. If not, rephrase: "when the save occurs, then `config_path` is never written to the on-disk config file." |

#### Missing AC
This story is so small and the ACs are so thin that it's effectively a 15-minute chore. Consider batching it with other 1-point chores into a "housekeeping" story.

---

### US-011: Document StatusColor Purple/Orange as Manual-Only
**Points:** 1 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Documentation only.
- **Small?** ✅ 1 pt.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Process-oriented | "When they see the docstring" — this AC is about code content, not behavior. Documentation-only stories are valid enablers, but the ACs should still describe the behavioral knowledge gap being closed. Prefer: "then a developer can determine from reading the code alone that purple and orange are manual-only within 30 seconds." |
| AC2 | ✅ | Good — annotating the type definition. |
| AC3 | ✅ | Regression guard (documentation shouldn't change behavior). |

#### Missing AC
None significant. This is a well-scoped documentation micro-story.

---

### US-012: Document or Remove save_master() No-Op
**Points:** 1 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ⚠️ This is simultaneously too small and too ambiguous. The story says "document OR remove" — it doesn't decide. Like US-008 AC2, this is a **pre-sprint decision**. The team needs to choose: document now (1 pt), or document now + schedule removal (1 pt), or remove now (maybe 2 pts if callers need cleanup).

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Same issue as US-011 | Docstring check — valid but process-oriented. |
| AC2 | ⚠️ Future-ticket creation | "A ticket is created to remove the function entirely" — this is a task, not an AC for current software behavior. If the decision is "document," then AC2 is irrelevant. If the decision is "remove," then AC2 should be "the function is removed from `vba_native.py` and `MACRO_DISPATCH`." |
| AC3 | ✅ | Regression, appropriate. |

#### Recommendation
Decide: document for now, schedule removal in a follow-up. Pick one path. The OR creates sprint-planning ambiguity.

---

### US-013: Refactor apply_theme() Using Widget-Type Handler Registry
**Points:** 5 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 5 pts for a refactoring of this complexity.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Verify dict lookup mechanism. |
| AC2 | ✅ Testable. | Add a test widget type, register handler, verify no apply_theme changes. |
| AC3 | ✅ Testable. | Safe fallback, no crash. |
| AC4 | ⚠️ "Pixel-identical" is untestable | Pixel-identical comparison requires visual regression testing (screenshot diffing), which this project doesn't have tooling for. Manual verification is fine but shouldn't be framed as an automatable AC. Prefer: "then a developer visually confirms that light and dark theme rendering matches the pre-refactor appearance in a side-by-side comparison." Or just trust the manual check. |

#### Missing AC
- **Handler execution order**: Is there a specific order in which handlers are applied? If a parent widget and child widget both have handlers, which fires first? This could matter for CSS-like cascade behavior.
- **Performance**: No regression in theme application time. (Probably fine, but worth a note if the isinstance chain was the slow part.)

---

### US-014: Use Content Hash for Cache Invalidation
**Points:** 3 | **Epic:** Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ⚠️ Partial. This story interacts with US-002 (cache serialization format). If US-002 picks Option A (HMAC on pickle), US-014's hash may be redundant — HMAC already detects tampering *and* content changes. If US-002 picks Option B (migrate to JSON), the caching format changes entirely and US-014's approach needs to be compatible. **Cross-reference needed: "if US-002 Option A is chosen, the hash verifies content not covered by the HMAC; if Option B, adapt accordingly."**
- **Small?** ⚠️ 3 pts for this feature seems low. You're adding SHA-256 computation for potentially large files, adding hash storage/serialization, handling backward compatibility with old cache format, and adding performance testing. That's a real implementation story, not a tweak. **5 pts is more honest.**

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Modify file, verify hash mismatch, cache rebuilt. |
| AC2 | ⚠️ Extremely unlikely edge case | Files with identical mtime_ns AND size but different content are essentially impossible in practice (mtime_ns has nanosecond resolution on modern filesystems). This AC protects against a scenario that will never occur. It's fine as a correctness property, but testing it requires creating an artificial scenario (manipulating stat data with `os.utime`), which adds test complexity for negligible value. |
| AC3 | ⚠️ Arbitrary threshold | "Adds no more than 200ms" — where did 200ms come from? What's the tolerance? On HDD vs. SSD? On a 50MB vs. 200MB file? Define the benchmark: "then the hash computation for a representative 50MB Excel file on an SSD completes within 200ms." Document the test file and hardware baseline. |
| AC4 | ✅ Testable | Deploy new version, old cache exists, verify silent invalidation. |

#### Missing AC
- **Memory usage**: `hashlib.sha256(open(path, 'rb').read())` reads the entire file into memory. For a 200MB Excel file, that's 200MB of RAM for hashing. The implementation note says "read in chunks" but there's no AC enforcing this.
- **Concurrent access**: What if the file is being written (by another process) while the hash is being computed?

---

### US-015: WCAG AA Contrast Verification for Status Colors
**Points:** 3 | **Epic:** Accessibility | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ⚠️ This story is **color science + accessibility compliance**, not a code change story. The AC requires computing 96 contrast combinations (6 statuses × 2 row backgrounds × 4 CVD modes × 2 themes) AND adjusting colors that fail AND re-verifying. Yet it's 3 points — the same as US-009, which is data-structure extraction. The point estimate feels wrong: either this is an **audit** (1 pt, just measure) or a **fix** (5-8 pts, measure + adjust + re-verify + document). **Currently it conflates audit and fix.**

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Automated contrast calculation. |
| AC2 | ✅ Testable | Same as AC1, dark mode. |
| AC3 | ✅ Testable | Same with CVD color remapping. |
| AC4 | ⚠️ Open-ended | "The failing color is adjusted until it passes" — this is the fix loop. Who decides the replacement color? This is a design decision, not a developer task. If there's a design system, reference it. If not, the AC should say: "then the adjusted color is approved by [designer / product owner] and passes ≥ 4.5:1." |

#### Missing AC
- **High-contrast mode**: `ui.high_contrast` exists in config.yaml (from AGENTS.md). Does this mode have its own color set that also needs AA verification?
- **Calendar dot contrast**: The calendar panel (US-008) paints colored dots. Status colors appear there too. Are calendar dots covered by this story?

---

### US-016: Refactor _setup_ui() into Smaller Methods
**Points:** 3 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes. Pure refactoring.
- **Small?** ✅ 3 pts for a mechanical refactor with behavioral regression check.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Prescribes method names | The AC literally lists the method names. This belongs in implementation notes or the task breakdown. The AC should state the **intent**: "then `__init__` delegates to focused setup methods, each handling a single UI concern." The implementer can then name them. |
| AC2 | ✅ Testable | Can be verified by code review or a lint rule. |
| AC3 | ⚠️ Same pixel-identical issue as US-013 AC4 | See US-013 AC4 critique. Prefer manual visual confirmation. |

#### Missing AC
None significant. This is a clean mechanical refactor story.

---

### US-017: Cache milestones Property Result
**Points:** 2 | **Epic:** Performance | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 2 pts.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Call twice, assert same returned object (identity check). |
| AC2 | ✅ Testable | Same as AC1, stronger assertion. |
| AC3 | ⚠️ Hypothetical | "Via a theoretical setter" — the implementation notes say Units don't have setters; they're dataclasses with public fields. This AC describes a scenario that doesn't exist in the current codebase. Either: (a) this AC assumes the codebase adds setters in the future, or (b) it's irrelevant and should be dropped. If (a), it's speculative — don't write ACs for future features. |
| AC4 | ✅ Testable | Create 1000 units, mock/observe list allocation count. |

#### Missing AC
- **Thread safety**: If `milestones` is accessed from a background thread (TimelinePanel likely lives on the main thread, but worth confirming), does the cache need to be thread-safe? (Probably not for this app.)

---

### US-018: Workbook Locking During Save
**Points:** 5 | **Epic:** Reliability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ⚠️ Partial. The story mentions "another instance of the app is saving" — this interacts with the `sync/lock_manager.py` module that already exists (per AGENTS.md). Is US-018 a *replacement* for `sync/lock_manager.py`, an *enhancement*, or unrelated? **Must clarify relationship with existing LockManager.** If LockManager already exists, this story may be partially done or may need to be scoped as "Lock currently exists but doesn't work for SaveWorker thread — fix it."
- **Small?** ✅ 5 pts is appropriate for the cross-platform file locking + retry dialog.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ❌ Typo in header | "Acceptness Criteria" — should be "Acceptance Criteria." Telling because it signals this file may not have had a close review. |
| AC2 | ⚠️ Platform-dependent behavior | File locking works fundamentally differently on Windows (`PermissionError` on locked file) vs. Linux (`fcntl.flock`). The AC should specify behavior per platform or acknowledge: "on Windows: catches PermissionError and waits; on Linux: uses flock advisory lock." As written, it's testing a Windows-centric scenario that may not reproduce on Linux. |
| AC3 | ✅ Testable | Happy path. |
| AC4 | ✅ Testable | Re-read behavior verification. |

#### Missing AC
- **Network drive scenario**: The Excel file may be on a network share (common in multi-user scenarios). File locking on SMB shares behaves differently. Worth acknowledging even if the AC is "behavior on network drives is best-effort."

#### Suggested Point Revision
- **5 → appropriate, given the cross-platform complexity.**

---

### US-019: Pin Dependency Versions in requirements.txt
**Points:** 1 | **Epic:** Maintainability | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ⚠️ This is a 5-minute chore disguised as a 1-point story. If the team can pin versions in the time it takes to run `pip freeze`, it's not a story. If the team needs to actually test against multiple Python versions (Python 3.14 is mentioned in AC2), it's genuinely complex. But the implementation note says to just write major version bounds — that's a text edit.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ | Visual inspection. |
| AC2 | ⚠️ "Python 3.14" is speculative | Python 3.14 may not exist yet or may not support PyQt5. The AC should say: "when `pip install -r requirements.txt` runs on the minimum supported Python version, then all packages install." Define the version. |
| AC3 | 🍌 Vacuous | "The pin prevents automatic upgrade" is a tautology — pins do that by definition. This isn't an AC; it's a description of what a pin is. |

#### Recommendation
Batch this into a "dev chores" story with US-010, US-011, US-012.

---

### US-020: Incremental Reload for Large Workbooks
**Points:** 8 | **Epic:** Performance | **INVEST claims:** All except Small checked

#### INVEST Assessment
- **Independent?** ⚠️ Partial. AC4 mentions "loading overlay" — the LoadingOverlay component exists (`gui/loading_overlay.py` per AGENTS.md), so AC4 is a *consumption* of existing infrastructure. AC3 requires a diffing mechanism that depends on US-014 (content hash) or US-021 (fingerprint cache) to detect "changed rows." Without those, how do you know which rows changed? **US-020 implicitly depends on either US-014 or US-021 (or both).**
- **Small?** Correctly unchecked. 8 pts is the declared max.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ⚠️ Benchmark-dependent | "Completes within 2 seconds" — on what hardware? What workbook size exactly? Specify: "then reloading a 500-row workbook with a single changed cell completes within 2 seconds on the reference development machine (document specs)." Also: 500 rows takes 5+ seconds *today* according to AC text, and a 2-second target may not be achievable without the incremental part (the story's actual value). Need a baseline measurement. |
| AC2 | ✅ Testable | UI thread responsiveness is testable via signal-based detection of paint events during reload. |
| AC3 | ✅/⚠️ Partial | "No flicker or full table rebuild" — flicker is a perceptual property. Automated test would require frame-level capture. Change to: "then only rows with changed data are updated in the QTableWidget; unchanged rows are not re-created." |
| AC4 | ✅ Testable | Verify LoadingOverlay appears for reloads >500ms. |

#### Missing AC
- **Memory**: Incremental reload with row hashing stores per-row state. What's the memory overhead for a 10,000-row workbook?
- **Progress granularity**: AC4 says "progress" but doesn't define granularity. Is it indeterminate spinner or percentage? UX decision needed.

---

### US-021: Cache unit_fingerprint() Result
**Points:** 2 | **Epic:** Performance | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 2 pts.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Call twice, assert same hash string returned. |
| AC2 | ✅ Testable | Mutate field, verify hash changes. |
| AC3 | ✅ Testable | Create 1000 units, count SHA-256 calls. |

#### Missing AC
- None. This is a well-scoped micro-optimization with clear ACs.

#### Suggested Point Revision
- **2 → appropriate.** This is the gold standard for a small story in this backlog.

---

### US-022: Cache TimelinePanel paintEvent Layout Computations
**Points:** 3 | **Epic:** Performance | **INVEST claims:** All checked

#### INVEST Assessment
- **Independent?** ✅ Yes.
- **Small?** ✅ 3 pts.

#### Acceptance Criteria

| # | Verdict | Notes |
|---|---------|-------|
| AC1 | ✅ Testable | Set milestones, call `_recompute_layout`, verify cache populated. |
| AC2 | ✅ Testable | Override `paintEvent` to count layout invocations. |
| AC3 | ✅ Testable | Call `set_unit`, verify cache invalidated and recomputed. |
| AC4 | ⚠️ Under-specified | "Only positions affected by width change are recomputed" — what does "positions affected by width change" mean? All positions are proportional to width, so they're ALL affected. What the AC means is: only the *scaling* step runs, not the full layout. Clarify: "then only the proportional scaling function is recomputed (not milestone date-to-pixel mapping if already cached at the current unit)." Or simplify: "then resize does not trigger `set_unit`-level full re-layout." |

#### Missing AC
- **Cache invalidation on theme change**: If the user switches themes, do colors change in the timeline? Does the layout cache need to be aware of theme? (Probably not, but worth confirming.)

---

## Cross-Cutting Issues

### 1. Hidden Dependencies Map

| Story | Depends On | Nature of Dependency |
|-------|-----------|---------------------|
| US-003 | US-001 | Worker signal integration assumes worker architecture from US-001 |
| US-007 | US-001 | Reload ordering depends on US-001's locking API |
| US-006 (AC2) | External fix | Formula row-reference bug fix not tracked as a story |
| US-008 (AC5) | US-015 | WCAG AA status color compliance is US-015's scope |
| US-014 | US-002 | Cache format changes from US-002 affect US-014's approach |
| US-018 | Existing LockManager | Must clarify relationship with `sync/lock_manager.py` |
| US-020 | US-014 or US-021 | Diffing mechanism for incremental reload depends on row hashing |

### 2. Point Inconsistencies

| Story | Pts | Complexity vs. Peers | Verdict |
|-------|-----|---------------------|---------|
| US-004 | 2 | Same scope as US-011 (1 pt) but with code changes | **Overestimated. Should be 1.** |
| US-011 | 1 | Docstring-only, low risk | **Fair.** |
| US-012 | 1 | Docstring-only, same as US-011 | **Fair (but ambiguous as-is).** |
| US-014 | 3 | SHA-256 computation, backward compat, perf testing, large file handling | **Underestimated. Should be 5.** |
| US-015 | 3 | 96 contrast combinations, color adjustment loop, design approval | **Underestimated. Should be 5.** |
| US-019 | 1 | A `pip freeze` or bounds definition | **Overestimated if bounds; appropriate if tested.** |

### 3. Documentation/Chore Stories Batching

There are 8 stories (US-009 through US-019) that are 1-3 points each, all internal-quality focused, totaling ~17 points. They are independent, small, and unblock no user-facing features. Consider:

- **US-010 + US-011 + US-012 + US-019** → "Codebase housekeeping" batch (4 pts total, 1 story)
- **US-009** remains standalone (2 pts, adds developer velocity)
- **US-013** remains standalone (5 pts, significant refactor)
- **US-016** remains standalone (3 pts, significant refactor)

### 4. AC Anti-Patterns Found Across Multiple Stories

**Anti-Pattern 1: Fork-accepting ACs**
- US-008 AC2: "shows a count badge '1' (or is optional)"
- US-006 AC1: "either actually calls save_unit OR is renamed"
- US-012: "document OR remove"

These stories need a **pre-sprint decision**. They cannot be estimated or implemented while the AC is bifurcated.

**Anti-Pattern 2: Implementation-prescribing ACs**
- US-003 AC5: "uses a pyqtSignal/Slot connection (not raw callbacks)"
- US-005 AC5: "at most 2 config file writes" (spy on internals)
- US-009 AC1: "adds one line to the structure"
- US-016 AC1: lists specific method names

ACs should describe **observable behavior**, not **code structure**. Move implementation preferences to Implementation Notes.

**Anti-Pattern 3: Performance thresholds without baselines**
- US-002 AC5: "≤10% compared to raw pickle" (HMAC adds microseconds; relative to what?)
- US-014 AC3: "adds no more than 200ms" (for what file size, on what hardware?)
- US-020 AC1: "completes within 2 seconds" (baseline not yet measured)

**Anti-Pattern 4: Vacuous/vacuously-passing ACs**
- US-011 AC3: "return value is still a different color" — no code changed, so this always passes
- US-019 AC3: "pin prevents automatic upgrade" — tautological
- US-009 AC4: redundant with AC3
- US-001 AC5: "when existing tests pass" — meta-test, not behavioral

**Anti-Pattern 5: Process-oriented ACs**
- US-006 AC11: "fixture dependencies are documented"
- US-011 AC1: "developer sees docstring"
- US-012 AC1: "function has a docstring"

These are checklist items, not acceptance criteria. They can be verified by reading code, not by running software.

---

## Recommendations Summary

### Must Fix Before Sprint Planning

| Priority | Story | Issue |
|----------|-------|-------|
| 🔴 High | US-006 | Split into 5+ domain-specific stories; fix AC1's self-fork; add coverage target metric |
| 🔴 High | US-008 | Resolve AC2's "decision needed" before sprint |
| 🔴 High | US-012 | Decide: document OR remove, not both |
| 🔴 High | US-015 | Separate "measure contrast" (1 pt) from "fix failing colors" (5 pts) |
| 🟡 Med | US-018 | Clarify relationship with existing `sync/lock_manager.py` |
| 🟡 Med | US-014 | Reconcile with US-002 Option A (HMAC makes hash partially redundant) |
| 🟡 Med | US-020 | Add dependencies on US-014/US-021 for diffing; establish performance baseline |
| 🟡 Med | US-001 | Annotate hidden dependencies on US-007 and US-003 |
| 🟢 Low | US-009 AC4 | Delete redundant AC |
| 🟢 Low | US-013 AC4 / US-016 AC3 | Change "pixel-identical" to "visually confirmed" |
| 🟢 Low | US-019 AC2 | Replace "Python 3.14" with actual minimum supported version |

### Point Estimate Revisions

| Story | Current | Recommended | Rationale |
|-------|---------|-------------|-----------|
| US-004 | 2 | **1** | Single-line fix; US-011 is 1 pt for same effort type |
| US-014 | 3 | **5** | SHA-256, backward compat, perf constraint, large file handling |
| US-015 | 3 | **5** (or split to 1+4) | 96 combinations + color adjustment loop + design approval |
| US-019 | 1 | **1 (or batch)** | Fine alone; better batched with US-010/011/012 |

### Stories That Should Be Split

| Story | Split Into | Rationale |
|-------|-----------|-----------|
| US-001 (8 pts) | US-001a: Locking (5), US-001b: Ordering (3) | Independent deliverables |
| US-006 (13 pts) | 5 domain-specific stories | See detailed breakdown above |
| US-015 (3 pts) | Audit (1) + Fix (4) | Measure first, then act on findings |

### Stories Ready for Sprint Planning (No Changes Needed)

- **US-005** — Well-scoped, clear ACs, appropriate points
- **US-017** — Trivial, well-specified
- **US-021** — Gold standard for micro-stories
- **US-022** — Clear, appropriate points, minor AC4 issue

---
*End of review.*
