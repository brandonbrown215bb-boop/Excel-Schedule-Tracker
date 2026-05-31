# Technical Review B — User Stories US-008 through US-015

**Reviewer:** Senior Python/Qt Developer (subagent)  
**Date:** 2026-05-31  
**Scope:** Technical accuracy, implementation feasibility, architecture fit, risk assessment, and point estimation for 8 user stories.

---

## US-008: Calendar Date Dot — Show Count for Multi-Unit Dates

### Verdict: ✅ Technically sound, minor issues

**1. Name Accuracy**
- `gui/calendar_panel.py` — ✅ File exists.
- `EventCalendarWidget` — ✅ Class exists (line 20).
- `events_by_date: dict[QDate, list[Unit]]` — ✅ Exists (line 27). This dict already contains all units per date, so count data is available.
- `paintCell` — ✅ Method exists (line 57).
- `calculated_status_color` — ✅ Property exists on Unit (models.py line 88).

**2. Implementation Feasibility**
The approach works. The `events_by_date` dict already maps each QDate to the full list of Units, so `len(units)` gives the count. The current code paints up to 6 individual dots (one per unit). Adding a count badge (e.g., small text overlay or superscript number) is straightforward in `paintCell` after the dot loop.

**3. Architecture Fit**
No violations. The calendar panel is a UI consumer; adding a visual badge to existing dot painting is purely presentational.

**4. Unmentioned Risks**
- **Dot-overlap with count badge:** The current code paints dots at fixed positions in the top-right corner of each cell. Adding a count badge needs to avoid overlapping the dots. The badge should be placed *next to* or *on top of* the dot cluster, not in a separate location that might be clipped by the cell boundary.
- **Cell size constraints:** Calendar cells in `QCalendarWidget` can be small (especially in compact layouts). A count badge with text "12" may not fit. Need a minimum cell size check or abbreviated format (e.g., "9+").
- **Tooltip on hover (AC4):** The story says "when the user hovers the date, a tooltip lists each unit and its status." `QCalendarWidget` doesn't natively support per-cell tooltips. Implementing this requires installing an event filter on the calendar's viewport and tracking mouse position to map to a date cell — non-trivial but doable. The story doesn't mention this implementation cost.
- **WCAG AA contrast (AC5):** The badge text needs to be readable against the dot color. Since dot colors vary (red, green, yellow, etc.), the badge text color must adapt. This is the same problem the list panel already solved with the brightness check at list_panel.py:488. That logic should be reused, not reinvented.

**5. Point Estimate Assessment**
Story says **3 points**. This is accurate. The core count badge is ~1 point. The tooltip requirement (AC4) adds significant complexity (event filter, date-at-position mapping, tooltip formatting). WCAG contrast (AC5) adds testing overhead. Total: 3 is reasonable, maybe even generous if tooltip is included.

---

## US-009: Extract Date Filter Presets into Configurable Data Structure

### Verdict: ⚠️ Story describes a different data structure than what exists; proposed structure is less capable

**1. Name Accuracy**
- `gui/list_panel.py` — ✅ File exists.
- The story claims presets are "hardcoded in the filter logic" — ❌ **Partially incorrect.** The presets are ALREADY defined in a data structure: `DATE_FILTER_PRESETS: list[tuple[str, str | None]]` at line 92-102. The filter dropdown is already built dynamically from this structure (line 343-344: `for label, value in DATE_FILTER_PRESETS`).

**2. Implementation Feasibility**
The story proposes this structure:
```python
DATE_PRESETS = [
    ("Overdue", -1, True),
    ("Today", 0, False),
    ("Next 3 days", 3, False),
    ("Next 7 days", 7, False),
    ("Next 30 days", 30, False),
]
```

This is **less capable** than the existing structure. The existing code already supports 8 presets including "This Month", "Next Month", and "Past 30 Days" — none of which can be expressed as a simple `(label, days_offset, is_past)` tuple. The proposed structure would be a **regression**.

The actual improvement needed (if any) is to make the presets externally configurable via `config.yaml` rather than a Python constant — but that's a different story.

**3. Architecture Fit**
No violations, but the story's proposed approach would reduce functionality.

**4. Unmentioned Risks**
- The existing `_filter_by_date` method (lines 165-228) uses string-based preset keys (`"overdue"`, `"today"`, `"next_3_days"`, etc.) with dedicated if/elif branches. The story's proposed `(label, days_offset, is_past)` structure would require rewriting this logic to compute date ranges from offsets — but this would lose "This Month", "Next Month", and "Past 30 Days" which aren't simple offsets.
- The story's AC4 says "Given a preset has `days_offset=0`, when applied, then it filters to today only" — but the existing code already has a `"today"` preset that works correctly.

**5. Point Estimate Assessment**
Story says **2 points**. Since the data structure already exists and the dropdown is already dynamic, this story is either:
- Already done (if the intent is just "presets in a data structure"), or
- A net-negative change (if the intent is to replace the current structure with the simpler tuple format).

**Recommendation:** Close this story as already implemented, or rewrite it to capture the actual value (e.g., "make presets configurable via config.yaml").

---

## US-010: Remove config_path from Source config.yaml Template

### Verdict: ✅ Already mostly done; story is a verification/documentation task

**1. Name Accuracy**
- `config.yaml` — ✅ File exists. Does NOT currently contain a `config_path` field in the source template (confirmed: the current config.yaml has no `config_path` key).
- `main.py` — ✅ Passes `config_path` separately to `MainWindow(config, config_path=config_path)` at line 58.
- `_save_ui_config` — ✅ Exists at main_window.py:1118. Already strips `config_path` at line 1129: `save_config = {k: v for k, v in self.config.items() if k != "config_path"}`.
- `self._config_path` — ✅ Stored as a separate attribute at main_window.py:172, NOT injected into the config dict.

**2. Implementation Feasibility**
The fix is already in place. The `config_path` is:
- NOT in the source config.yaml template ✅
- Injected at runtime via `main.py` and stored as `self._config_path` ✅
- Stripped from YAML writes in `_save_ui_config` ✅

**3. Architecture Fit**
No violations. The current implementation follows the architecture principle that config.yaml should only contain user-facing configuration.

**4. Unmentioned Risks**
- The `backup_20260529_183459/config.yaml` file DOES contain a `config_path` field — this is a backup from before the fix was applied. If someone restores from this backup, `config_path` would re-enter the config dict. However, since `_save_ui_config` now strips it on save, it would be cleaned up on next app close.
- AC3 says "existing fix in `_save_ui_config` should already handle this — verify." The verification is complete: **it does handle this correctly.**

**5. Point Estimate Assessment**
Story says **1 point**. This is accurate for a verification/documentation task. If the story is "verify and document that the fix works," it's a 1-pointer. If there's remaining work (e.g., adding a comment to config.yaml template), it's still a 1.

**Recommendation:** Accept the story as a verification task. All three ACs are already satisfied by the current code.

---

## US-011: Document StatusColor Purple/Orange as Manual-Only

### Verdict: ✅ Accurate and well-scoped

**1. Name Accuracy**
- `data/models.py` — ✅ File exists.
- `StatusColor` — ✅ Type alias exists at line 27: `Literal["gray", "yellow", "purple", "orange", "green", "red"]`
- `calculated_status_color` — ✅ Property exists at line 88-119.
- The story claims it "never produces" purple/orange — ✅ **Confirmed.** The property only returns `"green"`, `"gray"`, `"yellow"`, or `"red"`. Purple and orange are never returned.

**2. Implementation Feasibility**
Trivial. Add a docstring to `calculated_status_color` and comments to the `StatusColor` type. No behavioral changes.

**3. Architecture Fit**
No violations. Documentation-only change.

**4. Unmentioned Risks**
- The `Unit.status_label()` static method (lines 76-85) has hardcoded labels that include purple ("Ready for Checking (90%)") and orange ("Checked & Returned (95%)"). These labels are misleading since `calculated_status_color` never returns those values. The story could also update these labels to note they're manual-only.
- The `checking_status` field (which drives purple/orange in the Excel) is a separate field from `status_color`. The story correctly identifies that purple/orange come from the Excel file's `checking_status` column, but the relationship between `checking_status` and the color isn't documented anywhere. A developer might still wonder how purple/orange get set.

**5. Point Estimate Assessment**
Story says **1 point**. Accurate for a documentation-only change.

---

## US-012: Document or Remove save_master() No-Op

### Verdict: ✅ Accurate, but story has a factual error about line number

**1. Name Accuracy**
- `automation/vba_native.py` — ✅ File exists.
- `save_master()` — ✅ Function exists at line 22 (not "~line 200" as the story claims).
- The story says "logs a message and returns" — ❌ **Incorrect.** The function body is literally just `pass` (line 27). It does NOT log anything. The docstring says "Save the workbook to the master path" but the implementation is a bare `pass`.
- `vba_runner.py` — ✅ Does import and dispatch `save_master` (line 8, line 14: `"Save": save_master`).

**2. Implementation Feasibility**
Trivial. Add a docstring or remove the function. The function is called via the `"Save"` macro dispatch, so if removed, the dispatch table entry must also be removed.

**3. Architecture Fit**
No violations either way. The function exists for VBA API parity, which is a documented architecture pattern.

**4. Unmentioned Risks**
- Tests exist for `save_master` (test_vba_native.py lines 20-33). If the function is removed, tests must be updated. If documented only, tests should be updated to verify the docstring.
- The `test_imports.py` test (line 41) imports `save_master` and asserts it's callable. Removal requires updating this test too.
- AC3 says "when VBA parity is no longer needed, then a ticket is created to remove the function." This is a process step, not an AC. It can't be tested or verified.

**5. Point Estimate Assessment**
Story says **1 point**. Accurate for documentation-only. If removal is chosen, it's still 1 point but touches more files (vba_runner.py, tests).

---

## US-013: Refactor apply_theme() Using Widget-Type Handler Registry

### Verdict: ✅ Sound approach, but the story underestimates the isinstance() chain complexity

**1. Name Accuracy**
- `gui/theme.py` — ✅ File exists.
- `apply_theme()` — ✅ Function exists at line 400.
- `_apply_to_widget()` — ✅ Internal function exists at line 342. This is the function that contains the isinstance() chain.
- The story says "isinstance() checks to recursively apply styles" — ✅ Accurate. Lines 348-366 contain 5 isinstance() branches.

**2. Implementation Feasibility**
The proposed approach works. The `_apply_to_widget` function already separates the per-type logic from the recursion. Extracting each branch into a named function and registering them in a dict is a straightforward refactoring.

However, the story's example code has an issue:
```python
handler = _THEME_HANDLERS.get(type(widget))
```
Using `type(widget)` instead of `isinstance()` means subclasses won't match. The current code uses `isinstance()` specifically to handle subclasses like `EventCalendarWidget(QCalendarWidget)`. The registry should use `isinstance()` checks or iterate through the dict with `isinstance()` — a simple `type()` lookup would break subclass matching.

**3. Architecture Fit**
No violations. This is a pure maintainability improvement.

**4. Unmentioned Risks**
- **Subclass matching:** As noted above, `type(widget)` lookup breaks subclass matching. The fix is to iterate the dict and use `isinstance()`:
  ```python
  for widget_type, handler in _THEME_HANDLERS.items():
      if isinstance(widget, widget_type):
          handler(widget, tokens)
          break
  ```
  This is slightly slower than a dict lookup but preserves the current behavior.
- **QCalendarWidget special case:** The current `QCalendarWidget` branch (lines 366-397) has a large, complex stylesheet. Extracting this to a named function is clean but the function will be long. Consider whether this is worth it for a single widget type.
- **"Pixel-identical" (AC4):** Verifying pixel-identical output requires visual regression testing, which the project doesn't have (AGENTS.md says "no automated test suite"). This AC is hard to verify without manual testing or screenshot comparison.

**5. Point Estimate Assessment**
Story says **5 points**. This is reasonable. The refactoring touches the core theme application logic. Each isinstance branch must be extracted to a named function, the registry dict must be created, and the fallback behavior must be verified. The QCalendarWidget handler alone is ~30 lines. Testing across all widget types in both themes adds verification overhead. 5 points is accurate.

---

## US-014: Use Content Hash for Cache Invalidation

### Verdict: ✅ Technically sound, but the story's performance AC is naive

**1. Name Accuracy**
- `data/loader.py` — ✅ File exists.
- `WorkbookCache` — ✅ Class exists at line 80.
- Content signature is `(mtime_ns, file_size)` — ✅ Confirmed at lines 86-87 and `_workbook_signature()` at line 121-127.
- `excel_mtime_ns` and `excel_size` — ✅ Fields exist on WorkbookCache.

**2. Implementation Feasibility**
The approach works. The `_workbook_signature` function currently returns `(mtime_ns, size)`. Replacing this with a SHA-256 hash is straightforward.

The story's implementation note suggests: "cache the hash itself and only recompute when mtime changes (optimization: use mtime as fast path, hash as confirmation)." This is the right approach — use mtime as a quick reject, then hash to confirm.

**3. Architecture Fit**
No violations. The caching layer is an internal implementation detail of `data/loader.py`.

**4. Unmentioned Risks**
- **AC3 performance claim ("no more than 200ms for >50MB files"):** SHA-256 of a 50MB file takes ~50-100ms on modern hardware (SHA-256 is ~500 MB/s). The 200ms budget is reasonable, but the story should specify this is for initial load only. On cache hits, the hash should be read from the cache, not recomputed.
- **Cache format change:** The `WorkbookCache` dataclass stores `excel_mtime_ns` and `excel_size`. Adding a content hash requires either replacing these fields or adding a new field. If replacing, old cache files will fail the `from_pickle` backward compatibility check. The story's AC4 addresses this ("old-format cache silently invalidated") — the `from_pickle` method already handles schema_version checking, so this is feasible.
- **Memory-mapped files:** For very large Excel files, reading the entire file into memory for hashing could cause memory pressure. Using chunked reading (`hashlib.sha256()` with `update()` in chunks) is safer. The story mentions "read in chunks for memory efficiency" in the implementation notes — this should be a requirement, not a suggestion.
- **Concurrent access:** If the Excel file is being written to while the hash is computed, the hash may be of a partially-written file. The current mtime check has the same problem, but the hash makes it more likely to produce a false "cache valid" if the file is locked during hash computation.

**5. Point Estimate Assessment**
Story says **3 points**. Accurate. The core change is ~1 point (replace signature computation). Backward compatibility handling is ~1 point. Performance optimization (mtime fast path + chunked hashing) is ~1 point. Total: 3.

---

## US-015: WCAG AA Contrast Verification for Status Colors on All Row Backgrounds

### Verdict: ⚠️ Scope is larger than estimated; story conflates two different concerns

**1. Name Accuracy**
- `gui/list_panel.py` — ✅ File exists.
- Alternating row backgrounds — ✅ `setAlternatingRowColors(True)` at line 382.
- Status-colored cells — ✅ Background coloring at list_panel.py:487.
- The story says "this has not been systematically tested" — ✅ Accurate, no contrast tests exist.

**2. Implementation Feasibility**
The approach is feasible but the scope is large. The story says to test "all 6 status colors × 2 row backgrounds × (1 normal + 3 CVD modes) × 2 themes = up to 96 combinations." This is a significant testing and remediation effort.

The actual fix would involve:
1. Computing relative luminance for each status color + row background combination.
2. Checking contrast ratios against WCAG AA thresholds.
3. Adjusting colors that fail.
4. Repeating for all CVD modes.

**3. Architecture Fit**
No violations. Accessibility is a cross-cutting concern, and the theme module already has CVD overrides.

**4. Unmentioned Risks**
- **Row background colors are theme-dependent:** The alternating row colors come from the theme's `bg_primary` and `bg_tertiary` tokens. In light mode: `#ffffff` and `#f1f5f9`. In dark mode: `#0f172a` and `#334155`. The story should specify which exact colors to test against.
- **Status colors are ALSO theme-dependent:** The status colors differ between light and dark themes (e.g., light red `#c0392b` vs dark red `#ff6b6b`). The story correctly notes this but the matrix is actually: 6 status colors × 2 row backgrounds × 4 CVD modes × 2 themes = 96 combinations. This is a lot of manual or scripted verification.
- **The list_panel.py brightness heuristic (line 488):** The current code uses `(R*299 + G*587 + B*114)/1000` to decide text color (white vs dark). This is an approximation of luminance, not a proper WCAG contrast calculation. The story should note that this heuristic may need to be replaced with proper contrast calculation.
- **Calendar panel also has status colors:** The story only mentions `list_panel.py`, but `calendar_panel.py` also renders status-colored dots. If the status colors change, the calendar dots change too. Should the story also cover calendar contrast?
- **"Contrast matrix report as evidence" (Implementation Notes):** This is a deliverable, not just a note. The story should have an AC about producing this report.

**5. Point Estimate Assessment**
Story says **3 points**. This is **underestimated**. Testing 96 color combinations, computing contrast ratios, adjusting failing colors, and verifying fixes across all themes and CVD modes is a 5-8 point effort. If the story is scoped to "test and produce a report" (no fixes), 3 is reasonable. If fixes are included, it's at least 5.

**Recommendation:** Split into two stories: (1) Audit/report on contrast compliance (3 points), (2) Fix failing combinations (3-5 points).

---

## Summary Table

| Story | Names Accurate? | Approach Works? | Arch Fit? | Risks Not Mentioned | Points Accurate? |
|-------|----------------|-----------------|-----------|---------------------|-----------------|
| US-008 | ✅ Yes | ✅ Yes | ✅ Yes | Tooltip implementation complexity; cell size constraints; dot-badge overlap | ✅ 3 is right |
| US-009 | ⚠️ Structure already exists | ⚠️ Proposed structure is less capable | ✅ Yes | Would lose "This Month", "Next Month", "Past 30 Days" presets | ⚠️ Story may be unnecessary |
| US-010 | ✅ Yes | ✅ Already done | ✅ Yes | Backup files may re-introduce config_path | ✅ 1 is right |
| US-011 | ✅ Yes | ✅ Yes | ✅ Yes | status_label() static method also misleading | ✅ 1 is right |
| US-012 | ⚠️ Line number wrong; no log call | ✅ Yes | ✅ Yes | Tests must be updated if removed | ✅ 1 is right |
| US-013 | ✅ Yes | ⚠️ type() vs isinstance() issue | ✅ Yes | Subclass matching broken by type() lookup; pixel-identical verification hard | ✅ 5 is right |
| US-014 | ✅ Yes | ✅ Yes | ✅ Yes | Chunked reading should be required; concurrent file access risk | ✅ 3 is right |
| US-015 | ✅ Yes | ⚠️ Scope too large for points | ✅ Yes | 96 combinations is a lot; brightness heuristic may need replacement; calendar panel also affected | ❌ 3 is low; should be 5+ |

---

## Top Recommendations

1. **US-009** should be closed as already implemented or rewritten to capture actual value (externalizing presets to config.yaml).
2. **US-010** is essentially done — verify AC3 and close.
3. **US-013** must use `isinstance()` in the handler lookup, not `type()`, to preserve subclass matching.
4. **US-015** should be split into audit and fix stories; 3 points is insufficient for the full scope.
5. **US-008** tooltip requirement (AC4) is the hidden complexity — consider making it a separate story.
