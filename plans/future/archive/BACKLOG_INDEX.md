# Backlog Index — CODE_REVIEW.md Unfinished Items

**Generated:** 2026-05-31
**Source:** `CODE_REVIEW.md` — all items not marked ✅ or ❌
**Total Stories:** 22
**Total Points:** 67

---

## Epics

### 🔴 Security (2 stories, 8 pts)
| ID | Story | Points |
|----|-------|--------|
| US-002 | Secure Cache Deserialization (replace/harden pickle) | 5 |
| US-002b | File Path Input Sanitization | 3 |

### 🟠 Concurrency & Reliability (3 stories, 18 pts)
| ID | Story | Points |
|----|-------|--------|
| US-001 | Thread Synchronization for Shared Mutable State | 8 |
| US-003 | Error Dialog for Background Worker Failures | 5 |
| US-007 | File Watcher Debounce Reliability | 5 |

### 🟡 UI/UX (2 stories, 6 pts)
| ID | Story | Points |
|----|-------|--------|
| US-008 | Calendar Date Dot — Show Count for Multi-Unit Dates | 3 |
| US-015 | WCAG AA Contrast Verification for Status Colors | 3 |

### 🟢 Reliability (2 stories, 7 pts)
| ID | Story | Points |
|----|-------|--------|
| US-004 | Ensure Backup Directory Exists Before Writing | 2 |
| US-018 | Workbook Locking During Save | 5 |

### 🔵 Performance (3 stories, 13 pts)
| ID | Story | Points |
|----|-------|--------|
| US-020 | Incremental Reload for Large Workbooks | 8 |
| US-021 | Cache unit_fingerprint() Result | 2 |
| US-022 | Cache TimelinePanel paintEvent Layout | 3 |

### 🟣 Maintainability (8 stories, 16 pts)
| ID | Story | Points |
|----|-------|--------|
| US-005 | Config Save Debouncing | 3 |
| US-009 | Extract Date Filter Presets into Data Structure | 2 |
| US-010 | Remove config_path from Source config.yaml | 1 |
| US-011 | Document StatusColor Purple/Orange as Manual-Only | 1 |
| US-012 | Document or Remove save_master() No-Op | 1 |
| US-013 | Refactor apply_theme() Using Handler Registry | 5 |
| US-016 | Refactor _setup_ui() into Smaller Methods | 3 |
| US-019 | Pin Dependency Versions in requirements.txt | 1 |

### 🟤 Code Quality (2 stories, 7 pts)
| ID | Story | Points |
|----|-------|--------|
| US-014 | Use Content Hash for Cache Invalidation | 3 |
| US-017 | Cache milestones Property Result | 2 |

### 🟠 Quality Assurance (1 story, 13 pts)
| ID | Story | Points |
|----|-------|--------|
| US-006 | Comprehensive Test Coverage Expansion | 13 |

---

## Recommended Sprint Plan

### Sprint 1 — Foundation & Safety (21 pts, committed)
- US-001: Thread synchronization (8)
- US-002: Pickle security (5)
- US-003: Worker error dialogs (5)
- US-004: Backup makedirs (2)
- US-011: StatusColor docs (1)

### Sprint 2 — Reliability & UX (18 pts, committed)
- US-007: File watcher debounce (5)
- US-018: Workbook locking (5)
- US-008: Calendar dot count (3)
- US-015: WCAG AA contrast (3)
- US-002b: Path sanitization (3) — *stretch*

### Sprint 3 — Performance & Quality (21 pts, committed)
- US-020: Incremental reload (8)
- US-006: Test coverage — Part 1: fix existing tests + loader edge cases (5 of 13)
- US-013: Theme refactoring (5)
- US-014: Cache hash (3)

### Sprint 4 — Cleanup & Polish (16 pts)
- US-005: Config debounce (3)
- US-006: Test coverage — Part 2: GUI tests (remaining 8 of 13)
- US-016: _setup_ui() refactor (3)
- US-009: Date filter presets (2)
- US-017: milestones cache (2)
- US-021: fingerprint cache (2)
- US-022: timeline paint cache (3)
- US-010: config_path cleanup (1)
- US-012: save_master noop (1)
- US-019: dependency pins (1)

---

## Key

- ✅ = already completed (not in this backlog)
- ❌ = false positive (not in this backlog)
- All items above are **unfinished** action items from CODE_REVIEW.md
