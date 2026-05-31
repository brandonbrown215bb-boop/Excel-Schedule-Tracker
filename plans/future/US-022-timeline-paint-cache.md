# US-022: Cache TimelineWidget paintEvent Layout Computations

**Epic:** Performance
**Type:** Improvement
**Priority:** LOW
**Story Points:** 3
**Status:** Unstarted

---

## Story

As an end user viewing a unit's timeline,
I want the timeline to render smoothly without recalculating positions on every repaint,
So that scrolling and resizing feel responsive.

---

## Context

`gui/timeline_panel.py` — Painting happens in `TimelineWidget.paintEvent()` (line 11, inner widget), NOT in `TimelinePanel` (line 256, outer wrapper). `TimelineWidget` recalculates all milestone positions, axis ticks, and layout geometry on every `paintEvent` call.

There are two classes:
- `TimelineWidget` (line 11) — does the actual painting via `QPainter`
- `TimelinePanel` (line 256) — wrapper that adds a header label and delegates `set_unit()` to `TimelineWidget`

The cache must go on `TimelineWidget`. A new `resizeEvent()` override is needed on `TimelineWidget` (currently not implemented).

---

## Acceptance Criteria

1. Given a `TimelineWidget` has milestones set, when `paintEvent` fires for the first time, then layout positions are computed and cached.
2. Given a subsequent `paintEvent` fires (e.g., window scroll, another window passes over), when painting occurs, then the cached layout is reused without recomputing positions.
3. Given milestones change (user selects a different unit), when `set_unit()` is called on `TimelineWidget`, then the layout cache is invalidated and recomputed for the new milestones.
4. Given the widget is resized, when `resizeEvent` fires, then only positions proportional to width are recomputed (not the full layout).
5. Given the cache exists, when `set_theme()` changes colors, then the cache is invalidated (colors are read at paint time, not layout time).

---

## Implementation Notes

- Add `_layout_cache` dict and `_dirty: bool` attribute to `TimelineWidget`.
- Add `_recompute_layout()` method: computes milestone positions, axis ticks, date ranges. Called when `_dirty` is True.
- Add `resizeEvent()` override to `TimelineWidget` (doesn't currently exist): sets a `_width_dirty` flag that triggers proportional scaling (not full re-layout) on next paint.
- Invalidate cache in `set_unit()` and `set_theme()`.
- Only cache geometry, not colors. Colors change with themes mid-session and are cheap to look up.
- Do NOT add cache to `TimelinePanel` (the wrapper). It doesn't paint anything.

---

## INVEST Checklist

- [x] Independent
- [x] Negotiable
- [x] Valuable
- [x] Estimable
- [x] Small
- [x] Testable
