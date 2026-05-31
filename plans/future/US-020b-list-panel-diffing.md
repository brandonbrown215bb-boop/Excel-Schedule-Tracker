# US-020b: List Panel Diffing for No-Flicker Reload Updates

**Epic:** Performance
**Type:** Improvement
**Priority:** LOW
**Story Points:** 13
**Status:** Unstarted

---

## Story

As an end user with a large Excel workbook,
I want the list panel to update only the rows that changed after a reload,
So that the table doesn't visibly flicker or completely rebuild every time the file changes.

---

## Context

Currently, `_on_load_finished()` calls `self.list_panel.set_units(self.units)` which replaces the entire unit list, causing Qt to rebuild the entire `QTableWidget` from scratch. For large workbooks, this produces visible flicker and loses scroll position/selection.

To achieve no-flicker updates, the list panel needs to **diff the old unit list against the new one** and emit fine-grained Qt model signals (`dataChanged`, `rowsInserted`, `rowsRemoved`) instead of a full rebuild.

`gui/list_panel.py` uses `UnitListModel` (a custom `QAbstractTableModel`) which already has the infrastructure for per-row signals. Currently it calls `beginResetModel()`/`endResetModel()` on reload.

---

## Acceptance Criteria

1. Given a reload completes with 500 units where only 5 units changed, when the list panel updates, then only those 5 rows emit `dataChanged` signals (not a full model reset).
2. Given a reload completes where new units were added, when the list panel updates, then `rowsInserted` is emitted for the new rows (not a full rebuild).
3. Given a reload completes where units were removed, when the list panel updates, then `rowsRemoved` is emitted for the removed rows.
4. Given the list panel diffs units, when the diff is computed, then units are matched by `com_number` (not list index) so that reordering is handled correctly.
5. Given a reload occurs while the user has scrolled, when the update completes, then the scroll position and selection are preserved.

---

## Implementation Notes

- Implement `_diff_units(old_units, new_units)` on `UnitListModel`:
  - Build a dict of `com_number → index` for both old and new.
  - Identify: unchanged (same fingerprint), added, removed, changed.
  - Call `beginInsertRows`/`endInsertRows`, `beginRemoveRows`/`endRemoveRows`, and `dataChanged` accordingly.
- Use `unit.fingerprint` (already stored on each unit) to detect changes without recomputing.
- `com_number` is the stable identity key — units are looked up by COM throughout the codebase.
- If the diff algorithm is complex, use Python's `difflib.SequenceMatcher` on COM-number sequences as a starting point.
- This story is 13 points because: the diff algorithm, the Qt model signal sequencing, the fingerprint comparison, and the scroll/selection preservation are all non-trivial and easy to get wrong.

---

## Dependencies

- Depends on US-020a (reload performance optimization) — complete that first so reload is fast before investing in diffing.

---

## INVEST Checklist

- [x] Independent (after US-020a)
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [ ] Small — 13 points, split into multiple sprints if needed
- [x] Testable
