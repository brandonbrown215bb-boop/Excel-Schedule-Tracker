# Technical Review: User Stories US-016 through US-022

**Reviewer:** Senior Python/Qt Developer (Subagent C)
**Date:** 2026-05-31
**Scope:** Technical accuracy, implementation feasibility, architecture fit

---

## US-016: Refactor _setup_ui() into Smaller Methods

**Story Points:** 3 (Fibonacci) — **Assessment: Acceptable, maybe generous to 5**

### 1. Name Accuracy

**CRITICAL FINDING: `_setup_ui()` does not exist in the codebase.**

The `MainWindow.__init__` (line 139 of `main_window.py`) is itself the monolithic ~170-line initialization method. There is no extracted `_setup_ui()` method. The story proposes renaming something that was never factored out.

The `__init__` method directly contains inline code for:
- Central widget + layout + splitter creation (lines 186–191)
- Left panel / toggle buttons / view stack / calendar + list panels (lines 196–253)
- Right panel / timeline / edit form (lines 256–278)
- Automation bar (line 274: `self._build_automation_bar()` — already extracted!)
- Loading overlay (line 290)
- File watcher setup (line 295: `self._setup_file_watcher()` — already extracted!)
- Multi-user sync setup (line 296: `self._setup_multi_user_sync()` — already extracted!)
- Auto-refresh setup (line 299: `self._setup_auto_refresh()` — already extracted!)
- Help menu (line 302: `self._build_help_menu()` — already extracted!)
- Onboarding check (lines 305–307)
- Async data load (line 311: `self._load_data_async()`)

**Existing extracted methods that the story doesn't acknowledge:**
- `_build_automation_bar()` (line 842) — already exists
- `_setup_file_watcher()` (line 687) — already exists
- `_setup_multi_user_sync()` (line 887) — already exists
- `_setup_auto_refresh()` (line 779) — already exists
- `_build_help_menu()` (line 315) — already exists

**Proposed method names in the story vs. what's missing:**
| Story proposes | Status |
|---|---|
| `_setup_central_layout()` | **NEEDS CREATION** — covers lines 186–191 |
| `_setup_toolbar()` | **NEEDS CREATION** — covers lines 200–228 (toggle + theme + a11y buttons) |
| `_setup_panels()` | **NEEDS CREATION** — covers lines 231–253 (view stack + calendar + list) |
| `_setup_edit_form()` | **NEEDS CREATION** — covers lines 266–269 |
| `_setup_automation_bar()` | **WRONG NAME** — already exists as `_build_automation_bar()` at line 274/842 |
| `_setup_connections()` | **NEEDS CREATION** — signal connections are scattered; see note below |
| `_setup_file_watcher()` | Already called at line 295 |
| `_apply_theme()` | Theme init happens inline at lines 162–171, before `_setup_ui` concept |

**Additional signal connections are scattered throughout `__init__`:**
- `self.calendar_panel.unit_selected.connect(...)` at line 236
- `self.list_panel.unit_selected.connect(...)` at line 242
- `self.edit_form.saved.connect(...)` at line 267
- `self.edit_form.dirty_changed.connect(...)` at line 268
- `self.theme_btn.clicked.connect(...)` at line 218
- `self.a11y_btn.clicked.connect(...)` at line 225
- `self._file_watcher.fileChanged.connect(...)` at line 294
- Various timer `.timeout.connect(...)` calls in other methods

A `_setup_connections()` method would need to group the panel/form/watcher signal connections. But some connections MUST be created after both endpoints exist (e.g., `edit_form.saved` requires `edit_form` to exist first), so ordering matters.

### 2. Implementation Feasibility

**Yes, the refactoring is feasible and safe** — it's a pure extract-method refactoring. The inline code blocks are already visually separated by comment headers (e.g., `# ── Left: view toggle + stacked panel ──`), making extraction boundaries clear.

**One gotcha:** The theme initialization (lines 162–171) happens BEFORE the UI is built. It's setting up theme state on `self` and calling `apply_theme(self, ...)`. If extracted to `_apply_theme()`, it must remain first in the sequence.

### 3. Architecture Fit

No violations. Pure structural refactoring within `MainWindow.__init__`. The story doesn't touch business logic, models, or pipelines.

### 4. Unmentioned Risks

- **Signal connection ordering:** If `_setup_connections()` extracts connections that reference widgets not yet created (e.g., connecting `edit_form.saved` before `edit_form` exists), it will raise `AttributeError`. The extraction order must match creation order.
- **Status bar:** The status bar (`self.status_bar`) is created at line 178 and used immediately at line 181. Any method that references `self.status_bar` must come after line 180.
- **The story says `__init__` should call `_setup_file_watcher()`** — it already does (line 295). The story is describing what's partially already done without realizing it.
- **The story says 200+ line method** — `__init__` is ~170 lines of widget/layout code (lines 162–311). Close enough.

### 5. Point Estimate

**3 points is acceptable.** The refactoring is mechanical (extract method × 5–6 extractions), low risk, and easily verified by visual inspection. Some stories undervalue this work, but the scattered signal connections add minor complexity. A 5 would also be defensible if the reviewer is strict about signal connection ordering risk.

---

## US-017: Cache milestones Property Result

**Story Points:** 2 (Fibonacci) — **Assessment: Fair**

### 1. Name Accuracy

**All names verified:**
- `data/models.py` — exists, contains `Unit` dataclass at line 30
- `milestones` property — exists at line 63, returns `list[tuple[str, date | None]]`
- The property returns 6 named tuples as documented

**The story's proposed `_milestones_cache` attribute** does not yet exist — correct, this is new.

### 2. Implementation Feasibility

**Yes, feasible.** The `milestones` property at line 63 builds a fresh list every time. Caching is straightforward:

```python
# In __post_init__ or as field:
_milestones_cache: list | None = field(default=None, init=False, repr=False, compare=False)
```

**However, there's a fundamental tension the story acknowledges but doesn't resolve:**

The `Unit` dataclass uses public fields with NO setters. The story says: *"If fields are mutated directly (no setter), consider using `__post_init__` to set a `_dirty` flag, or accept that the cache is valid as long as the instance is immutable (which it mostly is — units are re-created on load, not mutated in place)."*

**CRITICAL:** Looking at the actual codebase, `Unit` instances ARE mutated in place in `main_window.py`:
- Line 607: `unit.status_color = unit.calculated_status_color` (in `_commit_unit_to_memory`)
- Line 610: `unit.excel_row = unit.excel_row or existing.excel_row`
- Line 611: `unit.fingerprint = unit.fingerprint or existing.fingerprint`
- Line 612: `unit.base_revision = unit.base_revision or existing.base_revision`

These mutations happen AFTER `set_unit()` is called on the timeline, which triggers `paintEvent`, which reads `self.unit.milestones`. So there IS a window where `milestones` could be called, then fields mutated, then `milestones` called again returning stale data.

That said, the fields being mutated (`excel_row`, `fingerprint`, `base_revision`, `status_color`) are NOT fields read by `milestones`. The `milestones` property only reads date fields. So **in practice, the cache won't go stale from these mutations.**

The real concern: `edit_form` allows users to modify date fields (like `build_date`, `detailing_due_date`). When `on_save_unit` calls `self.edit_form.current_unit`, that unit IS the same object. If the timeline was painted with the old unit, then the user edits dates, the next `paintEvent` calling `unit.milestones` would get stale cached data if the cache wasn't invalidated.

**Looking at the actual flow:**
1. User selects unit → `on_unit_selected()` → `self.timeline_panel.set_unit(unit)` → `self.update()` → `paintEvent` reads `unit.milestones`
2. User edits form → `on_save_unit()` → `self.edit_form.current_unit = unit` (line 408)

The timeline is NOT explicitly repainted after save unless `set_unit` is called again. The timeline IS called at line 407: `self.timeline_panel.set_unit(unit)` — but this passes the SAME unit object (the one from edit_form). If `set_unit` calls `self.update()`, the paintEvent fires, reads `unit.milestones`, and gets the cached (possibly stale) result if the date fields changed.

**Verdict:** The implementation is feasible but the cache invalidation story is insufficient. The simplest approach: accept that units are effectively immutable (dates don't change within a single unit session) and skip invalidation. OR, invalidate the cache by calling `set_unit(self.unit)` after save (re-triggering paint without cache).

### 3. Architecture Fit

No violations. Adding a private cache attribute to a dataclass is consistent with existing patterns (`fingerprint`, `base_revision`, `excel_row` use the same `compare=False, repr=False` pattern).

### 4. Unmentioned Risks

- **`__post_init__` with `init=False` fields:** Python dataclasses handle `init=False` fields in `__post_init__` fine, but you must use `object.__setattr__` for frozen dataclasses. `Unit` is NOT frozen, so direct assignment works.
- **Mutable default list:** The `milestones` property returns a list. If callers mutate the returned cache, corrupt state results. Should return a `tuple` instead of `list` for the cached value, or document "do not mutate."
- **`working_days` changes:** The `working_days` field is set from config but doesn't affect `milestones` output (only dates matter). Not a staleness risk for this specific property.

### 5. Point Estimate

**2 points is fair.** Simple property caching with a private attribute. The invalidation analysis adds thought work but the implementation itself is ~5 lines.

---

## US-019: Pin Dependency Versions in requirements.txt

**Story Points:** 1 (Fibonacci) — **Assessment: Underestimated**

### 1. Name Accuracy

**requirements.txt** exists and was read. It DOES have version pins:
```
openpyxl>=3.1.0
PyQt5>=5.15.0
requests>=2.28.0
PyYAML>=6.0
```

**The story claims "Dependencies have no version pins" — this is INCORRECT.** The file already has lower-bound pins (`>=X.Y`). What it lacks is upper-bound caps (`<X+1.0`).

So the story's premise is partially wrong — versions ARE pinned, just not with upper bounds.

### 2. Implementation Feasibility

**Yes, but requires research.** Setting upper bounds like `<6.0` for PyQt5 requires knowing the actual version compatibility. The suggested pins are:
- `PyQt5>=5.15,<6.0` — safe, PyQt5 is at 5.15.x and 6.x would be a major breaking change
- `openpyxl>=3.1,<4.0` — safe, openpyxl 3.x is current
- `pyyaml>=6.0,<7.0` — safe, pyyaml 6.x is current
- `requests>=2.28,<3.0` — safe, requests 2.x is the current major version

### 3. Architecture Fit

No violations. Dependency management is infrastructure-level, not application architecture.

### 4. Unmentioned Risks

- **Python 3.14 compatibility (Story AC2):** The story says "on Python 3.14" but Python 3.14 doesn't exist as of this review. The latest stable is Python 3.13. This acceptance criterion is hypothetical/future-proofing and not testable today.
- **Upper bounds can be too restrictive:** Pinning `<6.0` means that if PyQt5 releases 5.16 with a bugfix the app needs, it won't get it automatically. The pin prevents breakage but also prevents fixes.
- **The `requests` dependency is unusual:** The app is a PyQt5 desktop app for Excel files. Why is `requests` in production deps? It's not listed in the architecture. This should probably be a dev dependency or removed.
- **Lock file suggestion is good** but generating a `requirements-lock.txt` from the current environment would require `pip freeze`, which captures the ENTIRE environment including transitive deps — this can be brittle.

### 5. Point Estimate

**1 point is slightly low.** The actual work requires: (a) auditing each dependency for appropriate upper bounds, (b) testing the install, (c) optionally generating a lock file. This is more like 2 points. However, if it's purely editing `requirements.txt` with manually chosen bounds, 1 point is defensible.

---

## US-020: Incremental Reload for Large Workbooks

**Story Points:** 8 (Fibonacci) — **Assessment: Underestimated**

### 1. Name Accuracy

**References verified:**
- `load_workbook()` — exists in `data/loader.py` line 16 (imported) and used at line 458 with `read_only=True, data_only=True`
- `openpyxl` read-only mode with `iter_rows()` — already used at line 478: `ws.iter_rows(min_row=2, max_col=max_col, values_only=True)`
- Pickle cache — exists (`WorkbookCache`, `_load_units_from_pickle`, `_cache_is_fresh`)
- `LoadingOverlay` — exists at `gui/loading_overlay.py`
- `_load_data_async()` — exists, runs in `LoadWorker` thread
- File watcher — exists (`_setup_file_watcher`, `_on_file_changed`)
- `_on_file_changed` already calls `_load_data_async(force_reload=False)` at line 757, which DOES use cache-first loading

**The story says "the entire workbook is re-parsed from scratch" — this is PARTIALLY INCORRECT.** Looking at `_on_file_changed` (line 757):
```python
self._load_data_async(force_reload=False)
```
This passes `force_reload=False`, which means `load_units()` will try the Pickle cache first via `_cache_is_fresh()` (line 431). So the cache IS already checked on file watcher reloads. The story's premise overstates the problem — the system already does cache-first reloads.

However, if the cache is stale (Excel file modified externally), it WILL re-parse the full workbook. The story's concern is legitimate for that case.

### 2. Implementation Feasibility

**The "incremental reload" concept is problematic.**

OpenPyXL does NOT support true incremental/differential reading. Once you call `load_workbook(file, read_only=True)`, you get the entire sheet into an `IterableWorksheet`. There's no API to read "only rows that changed since last read."

**The story's suggestion to "store previous row hashes per COM number; only re-parse changed rows"** doesn't work because:
1. You can't read individual rows from an openpyxl workbook without reading all rows (it's a streaming parser)
2. Even if you knew which rows changed, openpyxl doesn't support random access to rows
3. You'd need to read the entire workbook anyway to discover what changed

**What WOULD help:**
- Keep the current cache-first approach (already implemented)
- Reduce the cost of full re-reads by optimizing the parsing loop
- Use the Pickle cache more aggressively — the fingerprint_by_com could detect per-unit changes and selectively update only changed units in the list without rebuilding the entire UI

**The "no flicker" AC (AC3) is the hardest requirement.** The current code at `_on_load_finished` calls:
- `self.calendar_panel.refresh(self.units)` — full refresh
- `self.list_panel.set_units(self.units)` — full rebuild
- Both replace the unit lists entirely, causing Qt to rebuild widgets

To achieve "only changed rows update," you'd need to implement a Qt model diff (comparing old vs new unit lists and emitting `dataChanged`/`rowsInserted`/`rowsRemoved` signals). `ListPanel` uses a custom `UnitListModel` that could support diffing, but it currently calls `set_units()` which rebuilds from scratch.

### 3. Architecture Fit

**Minor concern:** The story doesn't mention that `calculated_status_color` (a computed property) must be recalculated after reload since it's based on `date.today()`. The current code already handles this at line 518: `unit.status_color = unit.calculated_status_color`. However, an incremental approach that doesn't recreate units would need to explicitly recompute statuses.

### 4. Unmentioned Risks

- **True incremental reloading is not feasible with openpyxl** — the story proposes it without acknowledging the library limitation. The actual win is optimizing the full reload path, not making it incremental.
- **UI diffing is non-trivial** — `ListPanel` would need a full model diff implementation (think React's reconciliation). This alone could be 5+ points.
- **"Within 2 seconds" benchmark (AC1)** — depends on hardware, Excel file size, and whether cache is warm. Without a specific test environment, this is hard to guarantee.
- **LoadingOverlay during reloads >500ms (AC4)** — the overlay is already shown during `_load_data_async` at line 632. However, for cache-first loads (which are fast), showing a 200ms overlay would be annoying. The current implementation shows it indiscriminately.
- **The 8-point estimate** doesn't account for the UI diffing complexity. If AC3 ("no flicker or full table rebuild") is taken seriously, this is a 13-point story at minimum.

### 5. Point Estimate

**8 points is underestimated if AC3 ("no flicker") is required.** If the story is relaxed to "use cache-first approach more effectively" (which is already mostly implemented), it's already **partially done** — maybe 3 points of remaining work for edge cases. If true UI-diff incremental updates are required, this is a **13+ point story**.

**Recommendation:** Split into two stories: (a) optimize full reload performance (3 pts), (b) implement list panel diffing for no-flicker updates (8 pts).

---

## US-021: Cache unit_fingerprint() Result

**Story Points:** 2 (Fibonacci) — **Assessment: Fair, with caveats**

### 1. Name Accuracy

**All names verified:**
- `data/loader.py`, `unit_fingerprint()` at line 175 — exists and computes SHA-256
- `Unit` dataclass at `data/models.py` line 30 — confirmed
- The function computes `hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]` — confirmed

**The story says `unit_fingerprint()` is "called for every unit on every comparison"** — let's verify the actual call sites:

Searching the codebase, `unit_fingerprint()` is called in:
1. `loader.py` line 520: `unit.fingerprint = unit_fingerprint(unit)` — once per unit during full Excel load
2. `loader.py` line 337: `fingerprint_by_com[unit.com_number] = unit_fingerprint(unit)` — once per unit when saving Pickle cache
3. `main_window.py` line 120: `unit_fingerprint(self.unit)` — once per save commit

So in the current codebase, `unit_fingerprint()` is NOT called "for every unit on every comparison." It's called at most 2 times per unit per load cycle (once during parse, once during cache save). During saves, it's called once per saved unit.

**The story's concern about repeated hash computation is valid in principle but the actual call frequency is low.** The hash IS redundant when called during load + cache save (same unit, same data). That's 2 SHA-256 computations where 1 would suffice.

### 2. Implementation Feasibility

**Yes, feasible.** The proposed approaches are sound:

**Option A: `_fingerprint_cache` field on Unit** — add to dataclass:
```python
_fingerprint_cache: str = field(default="", init=False, repr=False, compare=False)
```
Then modify `unit_fingerprint()` to check/set it. BUT `unit_fingerprint()` is a standalone function, not a method. It would need to become a method or accept a unit with a cache field.

**Option B: `WeakKeyDictionary` external cache:**
```python
_fingerprint_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
```
This is cleaner because it doesn't modify the dataclass. But `Unit` is a dataclass (uses `__hash__` based on all fields by default), so `WeakKeyDictionary` would work. However, if date fields change, the hash would change too, making the WeakKey approach problematic if units are mutated after creation.

**The story says "units are typically created fresh on each load"** — confirmed by the codebase. Units are created in `_load_units_from_csv`, `_load_units_from_pickle`, and `load_units`. So cache lifetime is naturally bounded.

### 3. Architecture Fit

**Minor concern about Option A:** Adding `_fingerprint_cache` to the `Unit` dataclass means the `data` layer now knows about fingerprint caching, which is a performance detail. The "separation of concerns" principle suggests keeping caching in the loader. Option B (external WeakKeyDictionary) is cleaner architecturally.

### 4. Unmentioned Risks

- **`WeakKeyDictionary` with dataclass keys:** If `Unit.__eq__` compares all fields (default for dataclasses), two units with the same data are "equal" but may be different objects. `WeakKeyDictionary` uses object identity by default, which is correct here. But if `Unit` is ever made `frozen=True` or `eq=True` with custom hash, this could break.
- **The actual performance gain is minimal** — `unit_fingerprint()` is called O(N) times (twice per unit at load, once per save). For 1000 units, that's ~3000 SHA-256 hashes. On modern hardware, this takes milliseconds. The story's premise that this "adds up unnecessarily" is overstated for the current call patterns.
- **The `fingerprint` field on Unit is already populated** at loader.py line 520 and loaded from cache at line 319. So the fingerprint IS already effectively cached for loaded-from-cache units. The only redundant call is during the initial pickle save after loading from Excel.

### 5. Point Estimate

**2 points is fair** for adding a WeakKeyDictionary cache. But this is a **very low-value optimization** — the actual bottleneck is never going to be SHA-256 computation. The story should be deprioritized.

---

## US-022: Cache TimelinePanel paintEvent Layout Computations

**Story Points:** 3 (Fibonacci) — **Assessment: Underestimated**

### 1. Name Accuracy

**All classes and methods verified:**
- `gui/timeline_panel.py` — exists
- `TimelineWidget` class — at line 11 (inner widget that does the actual painting)
- `TimelinePanel` class — at line 256 (wrapper with header)
- `paintEvent()` — at `TimelineWidget.paintEvent` line 49
- `set_unit()` — exists on both `TimelineWidget.set_unit()` (line 35) and `TimelinePanel.set_unit()` (line 281)

**Key architectural insight the story misses:** There are TWO classes — `TimelineWidget` (does painting) and `TimelinePanel` (wrapper). The story refers to "TimelinePanel paintEvent" but it's actually `TimelineWidget.paintEvent()` that does the computation. The story should reference `TimelineWidget`, not `TimelinePanel`.

### 2. Implementation Feasibility

**Yes, feasible.** The `paintEvent` at lines 49–214 recalculates:
1. Milestone date list (line 64) — could be cached
2. Min/max dates (lines 73–82) — derived from milestone dates
3. Layout geometry (lines 87–91) — depends on widget width
4. For each milestone: position `x`, row_y, date string (lines 125–180) — depends on width + dates
5. Date axis ticks (line 191, calls `_draw_date_axis`) — depends on date range + width

**Cache structure proposal (adjusted for actual code):**
```python
# In TimelineWidget:
_cached_layout: dict | None = None  # keys: 'milestones', 'min_date', 'max_date', 'total_days', 'positions', 'axis_ticks'
_dirty: bool = True
_cached_width: int = 0
```

**In `_recompute_layout()`:**
- Called from `set_unit()` (when milestones change) AND from `resizeEvent()` when width changes significantly
- Compute milestone positions, axis ticks, store in `_cached_layout`

**In `paintEvent()`:**
- If `_dirty`: call `_recompute_layout()`
- Paint from `_cached_layout`

**One important detail:** The story proposes `_milestone_positions`, `_axis_ticks`, `_dirty` as keys. The actual code also computes `bar_x`, `bar_width`, `marker_area_top`, `marker_area_bottom`, `bar_color`, `status_text` — all of which should be cached.

### 3. Architecture Fit

No violations. This is a QPainter optimization within a single widget. No business logic involved.

### 4. Unmentioned Risks

- **Theme colors are read at paint time** (line 93-94): `get_status_colors(self._theme_name, self._cvd_mode)`. The cached layout stores a `bar_color` computed from these. If `set_theme()` is called, the layout cache must include theme-dependent values OR the `_dirty` flag must be set. The current code calls `self.timeline.update()` from `set_theme()` but doesn't invalidate position caches.
- **The bar color comes from `self.unit.calculated_status_color`** at line 95. This is a computed property that reads `date.today()`. If the app runs across midnight, the cached color would be stale. This is a very edge-case risk.
- **`date.today()` in `paintEvent` at line 194** — the "today line" position depends on the current date. If the cache survives across midnight, the today line position is wrong. Solution: always recompute the today line position, even from cache.
- **Two classes, one cache:** `TimelinePanel.set_unit()` calls `self.timeline.set_unit(unit)`. The cache lives on `TimelineWidget` (the inner widget). The story should specify this clearly.
- **`resizeEvent` handling:** `TimelineWidget` doesn't implement `resizeEvent()` — only `LoadingOverlay` does (line 134). So the story's implementation note #4 ("invalidate only position scaling on resize") requires adding a new `resizeEvent` method to `TimelineWidget`.

### 5. Point Estimate

**3 points is slightly underestimated.** The work involves:
1. Identifying and extracting all paint-time computations into a cache structure
2. Adding `_recompute_layout()` method
3. Modifying `paintEvent()` to use cache
4. Adding `resizeEvent()` override (new method not currently present)
5. Handling theme-change invalidation
6. Edge case: today-line date dependency

Realistically this is a **5 (3+2)** — the cache structure is simple but the multiple invalidation triggers (set_unit, resize, theme change, date change) add complexity.

---

## Summary Table

| Story | Title | Points (Story) | Points (Review) | Key Finding |
|-------|-------|----------------|-----------------|-------------|
| US-016 | Refactor _setup_ui() | 3 | 3 (or 5) | `_setup_ui()` doesn't exist — `__init__` IS the monolithic method. Some extractions already done. |
| US-017 | Cache milestones | 2 | 2 | Feasible, low risk. Date field invalidation is a non-issue in practice. |
| US-019 | Pin dependencies | 1 | 2 | Premise is wrong — lower-bound pins already exist. Needs upper bounds + research. |
| US-020 | Incremental reload | 8 | 13+ (if AC3 strict) | Cache-first reload already implemented. True incremental openpyxl reading is impossible. UI diffing is hard. |
| US-021 | Cache fingerprint | 2 | 2 | Feasible but very low value. Actual call frequency is already O(N), not O(N²). |
| US-022 | Cache paint layout | 3 | 5 | Wrong class reference (TimelinePanel vs TimelineWidget). Needs new resizeEvent + multiple invalidation triggers. |

---

## Cross-Cutting Recommendations

1. **US-016 should acknowledge existing extractions** before proposing new ones. The story as written implies starting from scratch.
2. **US-020 should be split** — the "no flicker" (UI diffing) requirement is an order of magnitude harder than the reload speed optimization.
3. **US-021 has questionable ROI** — SHA-256 of ~200 bytes is microseconds. Focus optimization effort on openpyxl parsing and paint performance instead.
4. **US-019's AC2 references Python 3.14** which doesn't exist — replace with a testable criterion.
5. **US-022 mixes up TimelinePanel and TimelineWidget** — clarify which class gets the cache.
