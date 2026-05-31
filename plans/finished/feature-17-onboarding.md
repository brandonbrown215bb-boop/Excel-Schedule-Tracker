# Feature 17: Onboarding Walkthrough — Spec Document

**Priority:** High (Usability pillar)
**Effort:** Low (~0.5 day)
**Risk:** Low (additive — overlay only, no existing behavior changes)

---

## Problem Statement

New users open Unit Tracker and see a split-panel UI with a calendar, list view toggle, timeline, edit form, macro combo, pull/sync buttons, and filter controls — but no guidance on what anything does. The learning curve is "I guess I click around." There's no in-app explanation of the workflow: browse → select → edit → save.

---

## Design Goals

1. **First-launch detection** — Show walkthrough automatically only on first run (config flag `onboarding_completed: false`)
2. **Step-by-step overlay** — Each step highlights one UI area with a tooltip-style callout, a 1-sentence explanation, and Next/Back/Skip buttons
3. **Non-blocking** — Semi-transparent overlay dims the rest of the UI. User can still click through if they want.
4. **Skippable** — "Skip" button on every step dismisses the entire walkthrough
5. **Re-playable** — "Help → Show Walkthrough" menu item lets users replay it anytime
6. **Config persistence** — After completion (or skip), sets `onboarding_completed: true` in config so it doesn't reappear

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        config.yaml                               │
│  ui:                                                             │
│    onboarding_completed: false   # set true after walkthrough    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ checked at startup
                             ▼
┌──────────────────────────────────────────────────────────────────�
│                   gui/onboarding.py                              │
│                                                                  │
│   WalkthroughStep(NamedTuple):                                   │
│     widget: QWidget     # target widget to highlight             │
│     title: str          # short heading ("Calendar")             │
│     description: str    # 1-sentence explanation                 │
│     position: str       # "top" | "bottom" | "left" | "right"   │
│                                                                  │
│   ONBOARDING_STEPS: list[WalkthroughStep] = [...]                │
│                                                                  │
│   OnboardingOverlay(QWidget):                                    │
│     ├── Semi-transparent backdrop (dim everything except target) │
│     ├── Highlight ring around target widget                      │
│     ├── Callout bubble (title + description)                     │
│     ├── Navigation: [Back] [Next] [Skip]                         │
│     └── Step indicator: ● ○ ○ ○ ○                                │
│                                                                  │
│   show_onboarding(parent: MainWindow) → None                     │
│   should_show_onboarding(config) → bool                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## New File: `gui/onboarding.py`

```python
"""
gui/onboarding.py — First-launch walkthrough overlay.

Shows a step-by-step highlight of the main UI areas with 1-sentence
explanations. Skippable. Replayable via Help menu.

Usage (in MainWindow.__init__):
    from gui.onboarding import should_show_onboarding, show_onboarding
    if should_show_onboarding(config):
        QTimer.singleShot(500, lambda: show_onboarding(self))

Usage (in Help menu):
    action = menu.addAction("Show Walkthrough")
    action.triggered.connect(lambda: show_onboarding(self))
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from PyQt5.QtCore import Qt, QTimer, QRect, QPoint
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication, QFrame, QGraphicsDropShadowEffect,
)


# ─── Walkthrough Steps ───────────────────────────────────────────────

class WalkthroughStep(NamedTuple):
    widget_name: str        # objectName of the widget to highlight
    title: str              # short heading
    description: str        # 1-sentence explanation
    position: str = "bottom"  # callout position: top, bottom, left, right


ONBOARDING_STEPS: list[WalkthroughStep] = [
    WalkthroughStep(
        widget_name="calendar_panel",
        title="Calendar & List",
        description="Browse units by date (calendar) or see everything sorted by due date (list). Toggle between them with the buttons above.",
        position="bottom",
    ),
    WalkthroughStep(
        widget_name="view_stack",
        title="View Toggle",
        description="Switch between Calendar view and List view. Your preference is saved automatically.",
        position="top",
    ),
    WalkthroughStep(
        widget_name="timeline_panel",
        title="Unit Timeline",
        description="See the selected unit's milestone dates, progress, and status at a glance.",
        position="left",
    ),
    WalkthroughStep(
        widget_name="edit_form",
        title="Edit Form",
        description="Modify any field of the selected unit. Press Ctrl+S or click Save to write changes back to Excel.",
        position="left",
    ),
    WalkthroughStep(
        widget_name="macro_combo",
        title="Macros & Pull",
        description="Run VBA macros directly, or pull fresh data from an external source file. Changes auto-refresh the view.",
        position="top",
    ),
    WalkthroughStep(
        widget_name="status_bar",
        title="Status Bar",
        description="Messages, sync status, and unit count appear here. The app auto-reloads when the Excel file changes.",
        position="top",
    ),
]


# ─── Onboarding Overlay ──────────────────────────────────────────────

class OnboardingOverlay(QWidget):
    """Semi-transparent overlay that highlights one widget at a time.

    Covers the entire parent window. Paints a dark mask with a
    transparent "hole" around the target widget, plus a callout bubble.
    """

    def __init__(self, parent: QWidget, steps: list[WalkthroughStep],
                 on_complete=None, on_skip=None):
        super().__init__(parent)
        self.steps = steps
        self.current_step = 0
        self.on_complete = on_complete
        self.on_skip = on_skip

        # Make this widget cover the entire parent
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Build the callout UI
        self._target_widget: QWidget | None = None
        self._highlight_rect = QRect()
        self._build_callout()
        self._update_highlight()

    def _build_callout(self):
        """Create the callout bubble."""
        self.callout = QFrame(self)
        self.callout.setStyleSheet("""
            QFrame {
                background: #1e293b;
                border: 1px solid #475569;
                border-radius: 8px;
            }
        """)
        self.callout.setFixedWidth(320)

        layout = QVBoxLayout(self.callout)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)

        # Step indicator (dots)
        self.step_indicator = QLabel()
        self.step_indicator.setAlignment(Qt.AlignCenter)
        self.step_indicator.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(self.step_indicator)

        # Title
        self.title_label = QLabel()
        title_font = self.title_label.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #f1f5f9;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Description
        self.desc_label = QLabel()
        self.desc_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        # Navigation buttons
        nav = QHBoxLayout()
        nav.setSpacing(6)

        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet(self._btn_secondary_style())
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setStyleSheet(self._btn_secondary_style())
        self.skip_btn.clicked.connect(self._skip)
        nav.addWidget(self.skip_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet(self._btn_primary_style())
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        layout.addLayout(nav)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self.callout)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 2)
        self.callout.setGraphicsEffect(shadow)

    @staticmethod
    def _btn_primary_style() -> str:
        return """
            QPushButton {
                background: #3b82f6; color: white; border: none;
                border-radius: 6px; padding: 5px 14px; font-weight: 500;
            }
            QPushButton:hover { background: #2563eb; }
        """

    @staticmethod
    def _btn_secondary_style() -> str:
        return """
            QPushButton {
                background: transparent; color: #94a3b8; border: 1px solid #475569;
                border-radius: 6px; padding: 5px 12px;
            }
            QPushButton:hover { background: #334155; color: #e2e8f0; }
        """

    def _update_highlight(self):
        """Update the target highlight, callout content, and button state."""
        step = self.steps[self.current_step]

        # Update text
        self.title_label.setText(step.title)
        self.desc_label.setText(step.description)

        # Update step indicator dots
        dots = []
        for i, _ in enumerate(self.steps):
            dots.append("●" if i == self.current_step else "○")
        self.step_indicator.setText("  ".join(dots))

        # Update button state
        self.back_btn.setVisible(self.current_step > 0)
        if self.current_step == len(self.steps) - 1:
            self.next_btn.setText("Done ✓")
        else:
            self.next_btn.setText("Next →")

        # Find target widget by objectName
        target = self.parent().findChild(QWidget, step.widget_name)
        self._target_widget = target

        if target and target.isVisible():
            # Map target geometry to overlay (MainWindow) coordinates.
            # target.geometry() is relative to the target's *immediate parent*,
            # not the MainWindow.  Use mapTo() to map both corners into the
            # overlay's coordinate space (which covers the entire MainWindow).
            tl = target.mapTo(self, QPoint(0, 0))
            br = target.mapTo(self, QPoint(target.width(), target.height()))
            self._highlight_rect = QRect(tl, br)

            # Position the callout relative to the target
            self._position_callout(self._highlight_rect, step.position)
        else:
            # Widget not found or hidden (e.g., wrong view) — center the callout
            self._highlight_rect = QRect()
            self._position_centered()

        self.update()  # trigger repaint

    def _position_callout(self, target_rect: QRect, position: str):
        """Position the callout bubble relative to the target widget."""
        padding = 12
        cw, ch = 320, self.callout.sizeHint().height()

        if position == "bottom":
            x = target_rect.center().x() - cw // 2
            y = target_rect.bottom() + padding
        elif position == "top":
            x = target_rect.center().x() - cw // 2
            y = target_rect.top() - ch - padding
        elif position == "right":
            x = target_rect.right() + padding
            y = target_rect.center().y() - ch // 2
        elif position == "left":
            x = target_rect.left() - cw - padding
            y = target_rect.center().y() - ch // 2
        else:
            x = target_rect.center().x() - cw // 2
            y = target_rect.bottom() + padding

        # Clamp to overlay bounds
        x = max(8, min(x, self.width() - cw - 8))
        y = max(8, min(y, self.height() - ch - 8))

        self.callout.setGeometry(x, y, cw, ch)

    def _position_centered(self):
        """Center the callout in the overlay (fallback)."""
        cw, ch = 320, self.callout.sizeHint().height()
        x = (self.width() - cw) // 2
        y = (self.height() - ch) // 2
        self.callout.setGeometry(x, y, cw, ch)

    def paintEvent(self, event):
        """Paint the dim overlay with a transparent hole around the target."""
        if not self._target_widget or self._highlight_rect.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Full-screen dark mask
        mask = QPainterPath()
        mask.addRect(self.rect())

        # Transparent hole around the target
        hole = QPainterPath()
        padding = 6
        r = self._highlight_rect.adjusted(-padding, -padding, padding, padding)
        hole.addRoundedRect(r, 8, 8)

        # Subtract hole from mask
        final = mask.subtracted(hole)

        painter.fillPath(final, QBrush(QColor(0, 0, 0, 140)))

        # Highlight border around target
        painter.setPen(QPen(QColor(96, 165, 250), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(r, 8, 8)

    def _go_next(self):
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self._update_highlight()
        else:
            self._finish()

    def _go_back(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._update_highlight()

    def _skip(self):
        self._finish()

    def _finish(self):
        """Dismiss the overlay and invoke callbacks."""
        self.hide()
        self.deleteLater()
        if self.on_complete:
            self.on_complete()

    def resizeEvent(self, event):
        """Re-center when parent resizes."""
        super().resizeEvent(event)
        self.setGeometry(self.parent().rect())
        self._update_highlight()


# ─── Public API ──────────────────────────────────────────────────────

def should_show_onboarding(config: dict) -> bool:
    """Check if the walkthrough should be shown."""
    return not config.get("ui", {}).get("onboarding_completed", False)


def show_onboarding(parent: QWidget, config: dict = None) -> None:
    """Show the onboarding walkthrough overlay."""
    def on_complete():
        if config is not None:
            config.setdefault("ui", {})["onboarding_completed"] = True

    overlay = OnboardingOverlay(parent, ONBOARDING_STEPS, on_complete=on_complete)
    overlay.show()
    overlay.raise_()
```

---

## Modified Files

### `gui/main_window.py` — First-launch detection + Help menu

**New imports:**

```python
from gui.onboarding import should_show_onboarding, show_onboarding
```

**New in `__init__`, after all UI is built and data loaded (at the very end):**

```python
# Show onboarding on first launch (after UI is ready)
if should_show_onboarding(self.config):
    # Delay 500ms so the window is fully painted first
    QTimer.singleShot(500, lambda: show_onboarding(self, self.config))
```

**New method — add Help menu to the menu bar:**

```python
def _build_help_menu(self):
    """Build the Help menu with walkthrough and about actions."""
    menubar = self.menuBar()
    help_menu = menubar.addMenu("&Help")

    # Show Walkthrough
    walkthrough_action = help_menu.addAction("&Show Walkthrough")
    walkthrough_action.setToolTip("Show the onboarding walkthrough")
    walkthrough_action.triggered.connect(
        lambda: show_onboarding(self, self.config)
    )

    help_menu.addSeparator()

    # About
    about_action = help_menu.addAction("&About Unit Tracker")
    about_action.triggered.connect(self._show_about)

def _show_about(self):
    QMessageBox.about(
        self,
        "About Unit Tracker",
        "<b>Unit Tracker</b><br><br>"
        "A desktop viewer/editor for detailing schedules.<br>"
        f"Python {__import__('sys').version.split()[0]} | "
        f"PyQt5 | openpyxl<br><br>"
        "© 2026",
    )
```

**Note:** Add `self._build_help_menu()` at the end of `__init__`, before the onboarding check.

### `config.yaml` — New setting

```yaml
ui:
  # ... existing fields ...
  onboarding_completed: false   # set to true after first walkthrough
```

---

## Walkthrough Steps (6 steps)

| # | Widget | Title | Description | Callout Position |
|---|--------|-------|-------------|-----------------|
| 1 | `calendar_panel` | Calendar & List | "Browse units by date (calendar) or see everything sorted by due date (list). Toggle between them with the buttons above." | bottom |
| 2 | `view_stack` | View Toggle | "Switch between Calendar view and List view. Your preference is saved automatically." | top |
| 3 | `timeline_panel` | Unit Timeline | "See the selected unit's milestone dates, progress, and status at a glance." | left |
| 4 | `edit_form` | Edit Form | "Modify any field of the selected unit. Press Ctrl+S or click Save to write changes back to Excel." | left |
| 5 | `macro_combo` | Macros & Pull | "Run VBA macros directly, or pull fresh data from an external source file. Changes auto-refresh the view." | top |
| 6 | `status_bar` | Status Bar | "Messages, sync status, and unit count appear here. The app auto-reloads when the Excel file changes." | top |

---

## Object Names Required

The walkthrough finds widgets by `objectName`. These need to be set on the relevant widgets:

| Widget | Required objectName | Where to set |
|--------|---------------------|--------------|
| Calendar/List stacked panel | `calendar_panel` | Already the attribute name; set `self.view_stack.setObjectName("view_stack")` + `self.calendar_panel.setObjectName("calendar_panel")` |
| View toggle row | `toggle_layout` | Already implicit via `view_stack` |
| Timeline panel | `timeline_panel` | `TimelinePanel.__init__` → `self.setObjectName("timeline_panel")` |
| Edit form | `edit_form` | `EditForm.__init__` → `self.setObjectName("edit_form")` |
| Macro combo | `macro_combo` | `MainWindow._build_automation_bar` → `self.macro_combo.setObjectName("macro_combo")` |
| Status bar | `status_bar` | Already set via `self.status_bar.setObjectName("status_bar")` in `__init__` |

---

## Execution Plan

### Step 1: `gui/onboarding.py` — Overlay widget
**Effort: ~0.3 day**

- `WalkthroughStep` named tuple
- `ONBOARDING_STEPS` list (6 steps)
- `OnboardingOverlay` QWidget with:
  - `paintEvent` — dim mask + transparent highlight hole + blue border ring
  - Callout bubble with title, description, step dots
  - Back / Next / Done / Skip buttons
  - Auto-positioning relative to target widget
- `should_show_onboarding()` and `show_onboarding()` API
- ~150 lines

### Step 2: Wire into `main_window.py`
**Effort: ~0.15 day**

- Import and call `should_show_onboarding` in `__init__`
- Add `QTimer.singleShot(500, ...)` delay
- Add `_build_help_menu()` with "Show Walkthrough" and "About" actions
- Set `objectName` on widgets that need it (timeline_panel, edit_form, macro_combo, status_bar)

### Step 3: Set objectNames on child widgets
**Effort: ~0.05 day**

- In `TimelinePanel.__init__`: `self.setObjectName("timeline_panel")`
- In `EditForm.__init__`: `self.setObjectName("edit_form")`
- In `CalendarPanel.__init__`: `self.setObjectName("calendar_panel")`
- In `ListPanel.__init__`: `self.setObjectName("list_panel")`
- In `MainWindow._build_automation_bar`: `self.macro_combo.setObjectName("macro_combo")`
- In `MainWindow.__init__`: `self.status_bar.setObjectName("status_bar")`

### Step 4: Config update
**Effort: ~0.05 day**

- Add `ui.onboarding_completed: false` to `config.yaml`

---

## Testing Checklist

- [ ] First launch (fresh config) shows walkthrough automatically after 500ms
- [ ] Each of the 6 steps highlights the correct widget
- [ ] Callout bubble is positioned adjacent to the target (not overlapping it off-screen)
- [ ] Next button advances through all steps
- [ ] Back button goes back (hidden on step 1)
- [ ] Skip button dismisses the overlay immediately
- [ ] "Done" on the last step dismisses the overlay
- [ ] After completion, `onboarding_completed: true` is set in config
- [ ] Subsequent launches do NOT show the walkthrough
- [ ] Help → Show Walkthrough replays the walkthrough
- [ ] Help → About shows the about dialog
- [ ] Resize during walkthrough repositions the callout
- [ ] All 204 existing tests still pass

---

## Known Limitations

1. **Object name coupling** — The walkthrough finds widgets by `objectName` string. If a widget is renamed, the step silently skips (centered fallback). Mitigation: use constants for object names.

2. **QCalendarWidget styling** — The calendar grid is native Qt painting. The overlay can highlight the panel frame but can't draw individual date cells differently.

3. **No animations** — The overlay jumps between steps. A smooth crossfade between highlight positions (QPropertyAnimation on the highlight rect) is nice-to-have but not required for v1.

4. **Single-language (English)** — All walkthrough text is hardcoded English. No i18n framework exists. Defer.

---

*Estimated total: ~0.5 day*
*Generated: 2026-05-30*
