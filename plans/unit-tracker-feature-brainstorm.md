# Unit Tracker — Future Feature Brainstorm

*Prioritized: Automation → Accessibility → Usability*

---

## 🤖 AUTOMATION

### 1. Smart Auto-Schedule Conflict Detector
**Pitch:** When a user creates or edits a detail entry, the app automatically scans for overlapping assignments, double-booked units, and resource conflicts. Instead of silently accepting bad data, it flags conflicts with a non-blocking toast notification and offers one-click resolution suggestions (shift by 1 day, swap with open slot, etc.). This eliminates the most common manual error in schedule management — the kind that only surfaces when someone shows up to the wrong place.

### 2. Recurring Detail Templates
**Pitch:** Let users define template detail patterns (e.g., "every Monday + Wednesday, 0800–1600, Alpha Squad, Range 301") and auto-populate future weeks with a single click. Templates support exceptions (skip holidays, blackout dates) and can be bulk-edited. This turns a repetitive weekly data-entry chore into a 2-second action.

### 3. Automated Pull-Sync Scheduler
**Pitch:** Replace the manual pull-sync trigger with a configurable auto-sync engine. Users set a sync interval (every 15 min, hourly, on file-change detection) and the app silently pulls the latest Excel data in the background. A status indicator shows last sync time and whether local/remote are in parity. If the source file is locked or unavailable, it queues the sync and retries with exponential backoff — no user intervention needed.

### 4. Change Detection & Diff Feed
**Pitch:** After every sync, the app computes a diff of what changed (added, modified, removed entries) and surfaces it in a collapsible "What Changed" panel. Users can review changes before they're applied, or auto-accept if they trust the source. This turns opaque data refreshes into transparent, auditable updates.

### 5. VBA Macro Auto-Trigger on Save
**Pitch:** Extend the existing VBA COM trigger so that saving the schedule in Unit Tracker automatically fires the downstream Excel macro pipeline — no manual "run macro" step. Optionally configurable per-workbook, with a dry-run mode that shows what *would* happen without actually executing.

---

## ♿ ACCESSIBILITY

### 6. Full Keyboard Navigation & Shortcuts
**Pitch:** Every UI action — creating entries, navigating the calendar, editing rows, triggering sync — is reachable via keyboard alone. A shortcut overlay (press `?`) shows all bindings. Tab order follows logical flow. This isn't just for power users; it's essential for anyone who can't or doesn't want to use a mouse, and it makes the app dramatically faster for everyone else.

### 7. High-Contrast & Colorblind-Safe Themes
**Pitch:** Ship with a high-contrast dark theme and a colorblind-safe palette (avoid red/green as the only differentiator). Status indicators use shape + color (icon + hue), never color alone. Theme is a single toggle in settings, persisted across sessions. This makes the app usable in bright sunlight, low light, and for the ~8% of men with color vision deficiency.

### 8. Screen Reader Compatibility
**Pitch:** All interactive elements carry proper `accessibleName` and `accessibleDescription` properties via Qt's accessibility layer. The calendar announces dates and event counts. The timeline announces row details on focus. This opens the app to users who rely on screen readers — and it's a one-time setup cost that pays off permanently.

### 9. Configurable Font Scaling & UI Density
**Pitch:** A slider in settings adjusts base font size (12px–24px) and UI density (compact / comfortable / spacious). The layout reflows cleanly at every setting. No horizontal scrolling, no clipped text. This is critical for users on high-DPI displays, older monitors, or anyone who just needs bigger text.

---

## 🔧 USABILITY

### 10. Drag-and-Drop Calendar Rescheduling
**Pitch:** Click and drag a detail block on the calendar to reschedule it. Drop it on a new date/time and the underlying data updates instantly. Visual feedback during the drag (ghost block, snap-to-grid, conflict highlight) makes the interaction feel physical and intuitive. This is the single biggest UX upgrade — it turns schedule editing from a form-filling exercise into a direct manipulation experience.

### 11. Multi-Select & Bulk Operations
**Pitch:** Shift-click or Ctrl-click to select multiple detail rows, then apply bulk actions: delete, reassign, shift dates, change status. A contextual toolbar appears when 2+ items are selected. This is the difference between "I need to update 30 entries" being a 2-minute task and a 20-minute nightmare.

### 12. Inline Row Editing with Validation
**Pitch:** Double-click any cell in the detail table to edit it in place. Validation fires on commit (not on every keystroke), showing a red outline and tooltip for invalid values. Press Enter to confirm, Escape to cancel. No modal dialogs for simple edits — stay in the flow.

### 13. Persistent Column Customization
**Pitch:** Let users reorder, resize, hide, and pin columns in the detail table. Preferences save to disk and restore on launch. Add a "reset to default" option. Different users care about different data — a scheduler needs dates and units, a commander needs status and notes. Let each person see what matters to them.

### 14. Quick-Filter & Search Bar
**Pitch:** A persistent search/filter bar at the top of the detail table. Type any string and the table filters in real-time across all visible columns. Add toggle filters for common dimensions (unit, status, date range). Clear with one click. When you're looking for one specific entry in a 500-row schedule, this is the difference between 5 seconds and 5 minutes.

### 15. Export to PDF / Print Preview
**Pitch:** One-click export of the current calendar view or detail table to PDF, with a print preview dialog. Configurable date range, page orientation, and whether to include summary stats. This bridges the gap between "digital tool" and "something I can hand to someone who doesn't have the app."

### 16. Undo / Redo Stack
**Pitch:** Every data mutation (create, edit, delete, bulk operation) pushes to an undo stack. Ctrl+Z undoes, Ctrl+Shift+Z redoes. Stack persists for the session. This is the safety net that makes users *willing* to experiment — they know they can always take it back.

### 17. Onboarding Walkthrough
**Pitch:** First launch triggers a step-by-step overlay walkthrough highlighting the main UI areas: calendar, detail table, sync button, settings. Each step has a 1-sentence explanation. Skippable, and a "Help → Show Walkthrough" menu item to replay it. This reduces the time-to-first-value from "I guess I click around" to "oh, that's how this works."

---

## 📊 NICE-TO-HAVE / STRETCH

### 18. Dashboard Summary Widgets
**Pitch:** A configurable dashboard view with summary widgets: total details this week, upcoming details (next 7 days), conflict count, last sync status. At-a-glance situational awareness without digging into the table.

### 19. Multi-User Sync with Locking
**Pitch:** When multiple people run Unit Tracker against the same Excel source, implement a lightweight file-locking or merge-conflict protocol so two people don't overwrite each other's changes. Show who else is currently editing.

### 20. Notification / Reminder System
**Pitch:** System tray notifications for upcoming details (e.g., "Alpha Squad detail starts in 1 hour"). Configurable lead time. Quiet hours support. Keeps the app useful even when it's not the active window.

---

*Generated: 2026-05-30*
