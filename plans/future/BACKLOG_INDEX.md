# Backlog Index — Revised (Post-Review)

**Generated:** 2026-05-31
**Source:** CODE_REVIEW.md unfinished items, rewritten after 3-part technical review
**Stories closed:** 3 (US-004, US-009, US-010 — already implemented)
**Stories rewritten:** 7 (US-001, US-002, US-003, US-018, US-020→2, US-015→2)
**Stories split:** 1 (US-006→4)
**Total active stories:** 25
**Total points:** 87

---

## Epics

### 🔴 Security (2 stories, 8 pts)
| ID | Story | Points |
|----|-------|--------|
| US-002 | Harden Cache Deserialization (restricted Unpickler) | 5 |
| US-002b | File Path Input Sanitization | 3 |

### 🟠 Concurrency & Reliability (3 stories, 9 pts)
| ID | Story | Points |
|----|-------|--------|
| US-001 | Extend _io_busy Guard to Cover Saves | 3 |
| US-003 | Add Throttling and Retry to Error Dialogs | 3 |
| US-007 | File Watcher Debounce Reliability | 3 |

### 🟡 UI/UX (1 story, 3 pts)
| ID | Story | Points |
|----|-------|--------|
| US-008 | Calendar Date Dot — Show Count for Multi-Unit Dates | 3 |

### 🟢 Reliability (1 story, 8 pts)
| ID | Story | Points |
|----|-------|--------|
| US-018 | Save Conflict Detection Using Existing LockManager | 8 |

### 🔵 Performance (4 stories, 16 pts)
| ID | Story | Points |
|----|-------|--------|
| US-020a | Optimize Full Reload Performance | 3 |
| US-020b | List Panel Diffing for No-Flicker Updates | 13 |
| US-021 | Cache unit_fingerprint() Result | 2 |
| US-022 | Cache TimelineWidget paintEvent Layout | 3 |

### 🟣 Maintainability (6 stories, 14 pts)
| ID | Story | Points |
|----|-------|--------|
| US-005 | Config Save Debouncing | 3 |
| US-011 | Document StatusColor Purple/Orange as Manual-Only | 1 |
| US-012 | Document or Remove save_master() No-Op | 1 |
| US-013 | Refactor apply_theme() Using Handler Registry | 5 |
| US-016 | Refactor MainWindow.__init__ into Setup Methods | 3 |
| US-019 | Add Upper-Bound Pins to requirements.txt | 1 |

### 🟤 Code Quality (2 stories, 5 pts)
| ID | Story | Points |
|----|-------|--------|
| US-014 | Use Content Hash for Cache Invalidation | 3 |
| US-017 | Cache milestones Property Result | 2 |

### 🟠 Accessibility (2 stories, 5 pts)
| ID | Story | Points |
|----|-------|--------|
| US-015a | Audit Status Color Contrast (all themes/CVD) | 1 |
| US-015b | Fix Failing Status Color Contrast Combinations | 4 |

### 🟠 Quality Assurance (4 stories, 14 pts)
| ID | Story | Points |
|----|-------|--------|
| US-006a | Fix Existing Test Suite Bugs (writer + formula tests) | 3 |
| US-006b | Add GUI Component Tests (EditForm, CalendarPanel, Theme) | 5 |
| US-006c | Add Data Layer Edge Case Tests (loader) | 3 |
| US-006d | Add Sync Edge Case Tests (concurrent locks, stale locks) | 3 |

---

## Closed Stories (Already Implemented)

| ID | Story | Finding |
|----|-------|---------|
| US-004 | Backup Directory makedirs | `os.makedirs(exist_ok=True)` already at vba_native.py:33 |
| US-009 | Date Filter Presets | `DATE_FILTER_PRESETS` data structure already exists at list_panel.py:92 |
| US-010 | config_path Cleanup | Already stripped from YAML writes at main_window.py:1129; stored as `self._config_path` |

---

## Key Dependency Map

```
US-001 (io-busy guard)
  ├──→ US-003 (error dialog throttling) — sequence within sprint
  └──→ US-018 (save conflict detection) — coordinates _io_busy clearing

US-020a (reload perf)
  └──→ US-020b (list panel diffing)

US-015a (contrast audit)
  └──→ US-015b (contrast fix)

No other hard dependencies. All US-006 sub-stories are independent.
```

---

## Recommended Sprint Plan

### Sprint 1 — Foundation & Safety (22 pts)
- US-001: Extend _io_busy to saves (3) ← Do FIRST
- US-002: Restricted Unpickler (5)
- US-003: Error dialog throttling + retry (3) ← After US-001
- US-011: StatusColor docs (1)
- US-012: save_master noop doc (1)
- US-019: Upper-bound pins (1)
- US-015a: Contrast audit (1)
- US-006a: Test writer + formula fixes (3)
- US-006d: Sync edge cases (3) — stretch

### Sprint 2 — Reliability & Security (17 pts)
- US-018: Save conflict detection (8)
- US-005: Config debounce (3)
- US-002b: Path sanitization (3)
- US-007: File watcher debounce (3)

### Sprint 3 — Performance & Quality (16 pts)
- US-020a: Reload performance (3)
- US-014: Cache content hash (3)
- US-006b: GUI component tests (5)
- US-006c: Loader edge cases (3)
- US-021: Fingerprint cache (2)

### Sprint 4 — Maintainability & Accessibility (16 pts)
- US-013: Theme refactoring (5)
- US-016: __init__ refactor (3)
- US-015b: Contrast fix (4)
- US-008: Calendar dot count (3)
- US-017: Milestones cache (2) — stretch (1 pt under)

### Sprint 5 — Advanced Polish (16 pts)
- US-020b: List panel diffing (13)
- US-022: Timeline paint cache (3)

---

## Changes from Original Backlog

| Change | From | To | Reason |
|--------|------|----|--------|
| US-001 rewritten | Thread safety QMutex (8 pts) | Extend _io_busy to saves (3 pts) | Actual bug was _io_busy not covering save path; variable names in original were wrong |
| US-002 approach | HMAC on pickle (5 pts) | Restricted Unpickler (5 pts) | HMAC key management unsolved; Unpickler is standard Python pattern; two pickle.load sites |
| US-003 rewritten | Add error dialogs (5 pts) | Throttling + retry for existing dialogs (3 pts) | Error dialogs already exist in code |
| US-018 rewritten | File locking from scratch (5 pts) | Leverage existing LockManager (8 pts) | LockManager and RevisionStore already exist; os.O_EXCL approach was wrong |
| US-020 split | Incremental reload (8 pts) | US-020a: Optimize reload (3 pts) + US-020b: List diffing (13 pts) | Cache-first reload already works; openpyxl can't do true incremental read; UI diffing is separate hard problem |
| US-015 split | WCAG contrast (3 pts) | US-015a: Audit (1 pt) + US-015b: Fix (4 pts) | Measuring and fixing are different scopes; 96+ combinations take real time |
| US-006 split | Test coverage (13 pts) | US-006a–d: 4 domain-specific stories (14 pts total) | Single 13-pt story bundles unrelated domains |
| 3 stories closed | US-004, US-009, US-010 | Archived | Already implemented in current codebase |
