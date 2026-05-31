# Feature 6: Full Keyboard Navigation & Shortcuts — Spec Document

**Priority:** High (Accessibility pillar)
**Effort:** Medium (1–1.5 days)
**Risk:** Low (additive — no existing behavior changes)

---

## Problem Statement

Today, Unit Tracker is mouse-only. Every action — selecting a unit, switching views, saving, triggering macros, pulling data — requires clicking a button or widget. This excludes users who can't use a mouse efficiently (RSI, motor impairments) and slows down power users who could work faster from the keyboard.

The existing `keyPressEvent` in MainWindow handles exactly one shortcut: **Ctrl+S** to save. Everything else is unreachable without a mouse.

---

## Design Goals

1. **Every UI action reachable via keyboard** — calendar date selection, list row navigation, view toggle, edit form field navigation, save/revert, macro run, pull data, refresh, filter changes.
2. **Shortcut overlay** — Press `?` to show a modal overlay listing all available shortcuts. Closes on `Escape` or clicking outside.
3. **Logical tab order** — Tab moves through UI sections left-to-right, top-to-bottom. Shift+Tab reverses. No "tab traps."
4. **Arrow-key navigation** — Within a list or calendar, arrow keys move the selection. Enter activates.
5. **Discoverable** — Hover tooltips show shortcut hints. The `?` overlay is the authoritative reference.
6. **Configurable** — Shortcuts defined in one place (`config/keybindings.yaml`), editable without code changes.
7. **No conflicts** — Shortcuts don't clash with Qt widget defaults (e.g., Tab for focus, Enter for button press, arrow keys for spin boxes).

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        config.yaml                               │
│  keyboard:                                                       │
│    shortcuts:                                                    │
│      save: "Ctrl+S"                                              │
│      refresh: "Ctrl+R"                                           │
│      toggle_view: "Ctrl+L"                                       │
│      pull_data: "Ctrl+P"                                         │
│      run_macro: "Ctrl+Shift+M"                                   │
│      help: "?"                                                   │
│      search: "Ctrl+F"                                            │
│      clear_filters: "Escape"                                     │
│      next_unit: "Down"          # in list/calendar               │
│      prev_unit: "Up"                                             │
│      select_unit: "Enter"                                        │
│      first_unit: "Home"                                          │
│      last_unit: "End"                                            │
│      prev_field: "Shift+Tab"                                     │
│      next_field: "Tab"                                           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ loaded at startup
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   gui/keybinding_manager.py                      │
│                                                                  │
│   KeyBindingManager(config)                                      │
│     ├── load(keybindings_dict)                                   │
│     ├── get_shortcut(action) → QKeySequence                      │
│     ├── get_all_bindings() → dict[action → QKeySequence]         │
│     ├── show_help_overlay(parent)                                │
│     └── install_shortcuts(widget, bindings)                      │
│                                                                  │
│   ShortcutHelpDialog(QDialog)                                    │
│     ├── Grid layout: action name │ keys │ description            │
│     ├── Filterable by typing                                    │
│     └── Closes on Escape / click-outside                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────────────┐
              ▼              ▼                      ▼
┌──────────────────┐ ┌──────────────┐ ┌─────────────────────┐
│   MainWindow     │ │ CalendarPanel│ │    ListPanel        │
│   (key router)   │ │ (arrow keys, │ │ (arrow keys,        │
│                  │ │  Enter, Tab) │ │  Enter, PageUp/Dn)  │
└──────────────────┘ └──────────────┘ └─────────────────────┘
```

---

## New File: `gui/keybinding_manager.py`

```python
"""
Keyboard shortcut manager for Unit Tracker.

Loads shortcut definitions from config.yaml, installs them on widgets,
and provides the ? help overlay.

Design:
- One KeyBindingManager instance per MainWindow (created in __init__).
- Shortcuts are installed on specific widgets using QShortcut.
- The ? key opens a ShortcutHelpDialog modal.
- Arrow-key navigation in panels is handled by the panels themselves
  (not QShortcut) so Qt's native focus/selection behavior is preserved.
- Config can be reloaded at runtime (pressing ? shows current bindings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QKeySequence, QKeyEvent
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QGroupBox, QGridLayout, QPushButton, QScrollArea, QWidget,
    QFrame, QSizePolicy, QApplication,
)


# ─── Default Shortcuts ────────────────────────────────────────────────

DEFAULT_SHORTCUTS: dict[str, dict[str, str]] = {
    "global": {
        "save": "Ctrl+S",
        "refresh": "Ctrl+R",
        "toggle_view": "Ctrl+L",
        "pull_data": "Ctrl+P",
        "run_macro": "Ctrl+Shift+M",
        "help": "?",
        "search": "Ctrl+F",
        "clear_filters": "Escape",
    },
    "calendar": {
        "next_date": "Right",
        "prev_date": "Left",
        "next_row": "Down",
        "prev_row": "Up",
        "select_unit": "Enter",
        "today": "T",
        "show_all": "A",
    },
    "list": {
        "next_row": "Down",
        "prev_row": "Up",
        "page_down": "PageDown",
        "page_up": "PageUp",
        "first_row": "Home",
        "last_row": "End",
        "select_unit": "Enter",
        "sort_column": "Space",  # cycles sort on current column
    },
    "edit_form": {
        "next_field": "Tab",
        "prev_field": "Shift+Tab",
        "save": "Ctrl+S",
        "revert": "Escape",
        "toggle_status": "S",  # cycle status color
    },
}


# ─── Data Classes ──────────────────────────────────────────────────────

@dataclass
class KeyBinding:
    action: str
    keys: str
    description: str
    context: str = "global"
    qkeysequence: QKeySequence = field(default=None)  # type: ignore[assignment]

    def __post_init__(self):
        if self.qkeysequence is None:
            self.qkeysequence = QKeySequence(self.keys)


# ─── Key Binding Manager ──────────────────────────────────────────────

class KeyBindingManager:
    """Loads, stores, and installs keyboard shortcuts."""

    def __init__(self, config: dict):
        self.config = config
        self.bindings: list[KeyBinding] = []
        self._shortcuts: list = []  # QShortcut refs (prevent GC)
        self._load_defaults()
        self._load_config_overrides()

    def _load_defaults(self):
        """Populate bindings from DEFAULT_SHORTCUTS."""
        for context, actions in DEFAULT_SHORTCUTS.items():
            for action, keys in actions.items():
                self.bindings.append(KeyBinding(
                    action=action,
                    keys=keys,
                    description=self._default_description(action),
                    context=context,
                ))

    def _load_config_overrides(self):
        """Override defaults with user config from config.yaml."""
        kb_config = self.config.get("keyboard", {}).get("shortcuts", {})
        for context, actions in kb_config.items():
            for action, keys in actions.items():
                # Find and update existing binding
                for b in self.bindings:
                    if b.action == action and b.context == context:
                        b.keys = keys
                        b.qkeysequence = QKeySequence(keys)
                        break
                else:
                    # New binding not in defaults
                    self.bindings.append(KeyBinding(
                        action=action,
                        keys=keys,
                        description=action.replace("_", " ").title(),
                        context=context,
                    ))

    @staticmethod
    def _default_description(action: str) -> str:
        descriptions = {
            "save": "Save current unit",
            "refresh": "Reload data from Excel",
            "toggle_view": "Switch calendar ↔ list view",
            "pull_data": "Pull data from source file",
            "run_macro": "Run selected VBA macro",
            "help": "Show keyboard shortcuts",
            "search": "Focus search/filter box",
            "clear_filters": "Clear all filters",
            "next_date": "Move to next date",
            "prev_date": "Move to previous date",
            "next_row": "Move to next row",
            "prev_row": "Move to previous row",
            "page_down": "Scroll down one page",
            "page_up": "Scroll up one page",
            "first_row": "Jump to first row",
            "last_row": "Jump to last row",
            "select_unit": "Select highlighted unit",
            "today": "Jump to today on calendar",
            "show_all": "Show all units",
            "sort_column": "Cycle sort order",
            "next_field": "Next form field",
            "prev_field": "Previous form field",
            "revert": "Discard form changes",
            "toggle_status": "Cycle status color",
        }
        return descriptions.get(action, action.replace("_", " ").title())

    def get_shortcut(self, action: str, context: str = "global") -> Optional[QKeySequence]:
        """Get the QKeySequence for a named action."""
        for b in self.bindings:
            if b.action == action and b.context == context:
                return b.qkeysequence
        # Fall back to global
        if context != "global":
            return self.get_shortcut(action, "global")
        return None

    def get_bindings_for_context(self, context: str) -> list[KeyBinding]:
        return [b for b in self.bindings if b.context == context]

    def get_all_bindings(self) -> dict[str, list[KeyBinding]]:
        result: dict[str, list[KeyBinding]] = {}
        for b in self.bindings:
            result.setdefault(b.context, []).append(b)
        return result

    def show_help_overlay(self, parent: QWidget = None):
        """Show the shortcut help dialog."""
        dialog = ShortcutHelpDialog(self, parent)
        dialog.exec_()

    def get_help_text(self) -> str:
        """Return a plain-text summary of all shortcuts."""
        lines: list[str] = []
        lines.append("Keyboard Shortcuts")
        lines.append("=" * 40)
        contexts = self.get_all_bindings()
        for context, bindings in contexts.items():
            lines.append(f"\n  [{context.upper()}]")
            for b in bindings:
                lines.append(f"    {b.keys:<20} {b.description}")
        return "\n".join(lines)


# ─── Shortcut Help Dialog ─────────────────────────────────────────────

class ShortcutHelpDialog(QDialog):
    """Modal overlay showing all keyboard shortcuts.

    Features:
    - Grouped by context (Global, Calendar, List, Edit Form)
    - Filterable search box at top
    - Closes on Escape or clicking outside
    - Scrollable for small screens
    """

    def __init__(self, manager: KeyBindingManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(480, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background: #1e293b; }
            QLabel { color: #e2e8f0; }
            QLineEdit {
                background: #334155; color: #e2e8f0;
                border: 1px solid #475569; border-radius: 4px;
                padding: 6px 10px; font-size: 13px;
            }
            QGroupBox {
                color: #94a3b8; font-size: 11px; font-weight: 600;
                border: 1px solid #334155; border-radius: 6px;
                margin-top: 12px; padding-top: 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """)

        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title = QLabel("⌨ Keyboard Shortcuts")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #f1f5f9; padding: 4px 0;")
        layout.addWidget(title)

        # Instructions
        hint = QLabel("Press <b>?</b> to toggle this overlay. Press <b>Escape</b> to close.")
        hint.setStyleSheet("color: #64748b; font-size: 11px; padding-bottom: 4px;")
        layout.addWidget(hint)

        # Search filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter shortcuts...")
        self.filter_edit.textChanged.connect(self._populate)
        layout.addWidget(self.filter_edit)

        # Scroll area for bindings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll, stretch=1)

        # Close button
        close_btn = QPushButton("Close (Esc)")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #334155; color: #e2e8f0;
                border: 1px solid #475569; border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background: #475569; }
        """)
        layout.addWidget(close_btn)

    def _populate(self):
        """Rebuild the bindings display, applying the current filter."""
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filter_text = self.filter_edit.text().lower()
        contexts = self.manager.get_all_bindings()

        for context, bindings in contexts.items():
            # Filter bindings
            if filter_text:
                bindings = [
                    b for b in bindings
                    if filter_text in b.action.lower()
                    or filter_text in b.keys.lower()
                    or filter_text in b.description.lower()
                ]
                if not bindings:
                    continue

            group = QGroupBox(context.upper())
            grid = QGridLayout()
            grid.setColumnStretch(1, 1)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(4)

            for row, b in enumerate(bindings):
                # Key badge
                key_label = QLabel(b.keys)
                key_label.setStyleSheet("""
                    QLabel {
                        background: #334155; color: #60a5fa;
                        border: 1px solid #475569; border-radius: 4px;
                        padding: 2px 8px; font-weight: 600;
                        font-size: 11px;
                    }
                """)
                key_label.setAlignment(Qt.AlignCenter)
                grid.addWidget(key_label, row, 0)

                # Description
                desc_label = QLabel(b.description)
                desc_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
                grid.addWidget(desc_label, row, 1)

            group.setLayout(grid)
            self.content_layout.addWidget(group)

        self.content_layout.addStretch()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


# ─── Tray Notification (for shortcuts executed) ───────────────────────

class TrayNotifier:
    """Brief status-bar or OSD-style notification for shortcut actions.

    Instead of QMessageBox for every shortcut confirmation,
    flash a brief message in the status bar.
    """

    # Messages shown for toggle actions
    MESSAGES = {
        "toggle_view_calendar": "Switched to Calendar view",
        "toggle_view_list": "Switched to List view",
        "search": "Search — type to filter",
        "clear_filters": "Filters cleared",
        "revert": "Form reverted",
        "today": "Calendar jumped to today",
        "show_all": "Showing all units",
    }

    @staticmethod
    def flash(status_bar, action_key: str):
        msg = TrayNotifier.MESSAGES.get(action_key, action_key)
        status_bar.showMessage(msg, 2000)
```

---

## Modified Files

### `gui/main_window.py` — Key router + shortcut installation

**Changes:**

```python
from gui.keybinding_manager import KeyBindingManager

# In __init__:
# After config is loaded
self.keybindings = KeyBindingManager(config)

# Connect global shortcuts
kb = self.keybindings
self.keybindings.install_shortcuts(self, {
    "save": lambda: self.edit_form._on_save() if self.edit_form.current_unit else None,
    "refresh": self._refresh_data,
    "toggle_view": lambda: self._switch_view(
        "list" if self.view_stack.currentIndex() == 0 else "calendar"
    ),
    "pull_data": self._pull_csv,
    "run_macro": self._run_vba,
    "help": lambda: kb.show_help_overlay(self),
})

# ── Updated keyPressEvent ──
def keyPressEvent(self, a0: QKeyEvent | None) -> None:
    if a0 is None:
        super().keyPressEvent(a0)
        return

    # Let focused widget handle its own keys first
    focused = QApplication.focusWidget()
    if isinstance(focused, (QLineEdit, QTextEdit)):
        super().keyPressEvent(a0)
        return

    # Route through keybinding manager
    handled = self._route_key(a0)
    if not handled:
        super().keyPressEvent(a0)

def _route_key(self, event: QKeyEvent) -> bool:
    """Route key event through keybinding manager. Returns True if handled."""
    # Check ? for help overlay
    if event.key() == Qt.Key_Question or (
        event.key() == Qt.Key_Slash and event.modifiers() & Qt.ShiftModifier
    ):
        self.keybindings.show_help_overlay(self)
        return True

    # Ctrl+S — save
    if event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
        if self.edit_form.current_unit is not None:
            self.edit_form._on_save()
        return True

    # Ctrl+R — refresh
    if event.key() == Qt.Key_R and event.modifiers() & Qt.ControlModifier:
        self._refresh_data()
        return True

    # Ctrl+L — toggle view
    if event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
        self._switch_view("list" if self.view_stack.currentIndex() == 0 else "calendar")
        return True

    # Ctrl+P — pull data
    if event.key() == Qt.Key_P and event.modifiers() & Qt.ControlModifier:
        self._pull_csv()
        return True

    # Ctrl+Shift+M — run macro
    if (event.key() == Qt.Key_M
            and event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
        self._run_vba()
        return True

    # Ctrl+F — focus search (list panel) or show help on calendar
    if event.key() == Qt.Key_F and event.modifiers() & Qt.ControlModifier:
        if self.view_stack.currentIndex() == 1:  # list view
            self.list_panel.com_search.setFocus()
            self.list_panel.com_search.selectAll()
        return True

    # Escape — clear filters (list) or ignore
    if event.key() == Qt.Key_Escape:
        if self.view_stack.currentIndex() == 1:  # list view focused
            self.list_panel._clear_filters()
            return True

    return False
```

### `gui/calendar_panel.py` — Arrow key + Enter navigation

**Changes to `CalendarPanel`:**

```python
def keyPressEvent(self, event: QKeyEvent):
    """Handle arrow keys for date/highlight navigation."""
    key = event.key()

    if key in (Qt.Key_Right, Qt.Key_Left, Qt.Key_Up, Qt.Key_Down):
        # Navigate the selected date by one day
        current = self.calendar.selectedDate()
        delta = {
            Qt.Key_Right: 1,
            Qt.Key_Left: -1,
            Qt.Key_Down: 7,
            Qt.Key_Up: -7,
        }[key]
        new_date = current.addDays(delta)

        # Only navigate if the new date has events
        if new_date in self.calendar.events_by_date:
            self.calendar.setSelectedDate(new_date)
            self._on_date_clicked(new_date)
        event.accept()
        return

    if key == Qt.Key_Return or key == Qt.Key_Enter:
        # Activate the first selected event in the list
        items = self.event_list.selectedItems()
        if items:
            self._on_event_clicked(items[0])
        event.accept()
        return

    if key == Qt.Key_T:
        self._go_today()
        event.accept()
        return

    if key == Qt.Key_A:
        self._show_all_units()
        event.accept()
        return

    super().keyPressEvent(event)
```

**Changes to `EventCalendarWidget`:** Ensure `WA_KeyboardFocusPolicy` is set so the widget receives key events.

```python
def __init__(self, parent=None):
    super().__init__(parent)
    self.setFocusPolicy(Qt.StrongFocus)  # ← ADD
    self.events_by_date: dict[QDate, list[Unit]] = defaultdict(list)
    ...
```

### `gui/list_panel.py` — Arrow/Home/End/Enter navigation

**Changes to `ListPanel`:**

```python
# In __init__, after building UI:
self.table.setFocusPolicy(Qt.StrongFocus)

# New method:
def keyPressEvent(self, event: QKeyEvent):
    """Arrow-key row navigation for the table."""
    key = event.key()

    if key in (Qt.Key_Down, Qt.Key_Up, Qt.Key_Home, Qt.Key_End,
               Qt.Key_PageDown, Qt.Key_PageUp):
        self.table.keyPressEvent(event)  # QTableWidget handles natively
        self._on_selection_changed()
        event.accept()
        return

    if key in (Qt.Key_Return, Qt.Key_Enter):
        item = self.table.currentItem()
        if item:
            unit = item.data(Qt.UserRole)
            if unit:
                self.unit_selected.emit(unit)
        event.accept()
        return

    super().keyPressEvent(event)
```

### `gui/edit_form.py` — Tab field cycling + Escape revert + S status cycle

**Changes:**

```python
# In __init__:
# Set tab order explicitly
tab_order = [
    self.job_name_edit,
    self.contract_edit,
    self.description_edit,
    self.detailer_edit,
    self.checking_status_edit,
    self.status_combo,
    self.dept_hours_spin,
    self.target_hours_spin,
    self.iec_hours_spin,
    self.actual_hours_spin,
    self.percent_spin,
    self.start_date_edit,
    self.checking_date_edit,
    self.completion_date_edit,
    self.due_prev_date_edit,
    self.due_date_edit,
    self.build_date_edit,
]
for i in range(len(tab_order) - 1):
    self.setTabOrder(tab_order[i], tab_order[i + 1])

def keyPressEvent(self, event: QKeyEvent):
    """Handle Escape (revert) and S (cycle status)."""
    key = event.key()

    if key == Qt.Key_Escape:
        if self.current_unit is not None:
            self.set_unit(self.current_unit)
        event.accept()
        return

    if key == Qt.Key_S and not event.modifiers():
        # Cycle status color forward
        colors = ["gray", "yellow", "purple", "orange", "green", "red"]
        current = self.status_combo.currentText()
        try:
            idx = colors.index(current)
            next_idx = (idx + 1) % len(colors)
        except ValueError:
            next_idx = 0
        self.status_combo.setCurrentText(colors[next_idx])
        event.accept()
        return

    super().keyPressEvent(event)
```

### `config.yaml` — New keyboard shortcuts section

```yaml
# Keyboard shortcuts — customize without code changes
# Format: Qt key names (https://doc.qt.io/qt-5/qt.html#Key-enum)
keyboard:
  shortcuts:
    global:
      save: "Ctrl+S"
      refresh: "Ctrl+R"
      toggle_view: "Ctrl+L"
      pull_data: "Ctrl+P"
      run_macro: "Ctrl+Shift+M"
      help: "?"
      search: "Ctrl+F"
    calendar:
      today: "T"
      show_all: "A"
    list:
      sort_column: "Space"
    edit_form:
      revert: "Escape"
      toggle_status: "S"
```

---

## Shortcut Reference Table

| Context | Shortcut | Action | Notes |
|---------|----------|--------|-------|
| **Global** | `Ctrl+S` | Save current unit | Only when edit form has a unit |
| **Global** | `Ctrl+R` | Refresh data | Same as clicking Refresh |
| **Global** | `Ctrl+L` | Toggle calendar ↔ list view | Saves preference to config |
| **Global** | `Ctrl+P` | Pull data | Opens source file dialog |
| **Global** | `Ctrl+Shift+M` | Run macro | Runs selected VBA macro |
| **Global** | `?` | Show help overlay | Esc to close |
| **Global** | `Ctrl+F` | Focus search box | Only in list view |
| **Global** | `Tab` / `Shift+Tab` | Next/prev widget | Standard Qt behavior |
| **Calendar** | `←` `→` | Move ±1 day | Only to dates with events |
| **Calendar** | `↑` `↓` | Move ±7 days (week) | Only to dates with events |
| **Calendar** | `Enter` | Select highlighted event | Activates first selected item |
| **Calendar** | `T` | Jump to today | Same as Today button |
| **Calendar** | `A` | Show all units | Same as Show All button |
| **List** | `↑` `↓` | Move selection | QTableWidget native |
| **List** | `Home` / `End` | First / last row | |
| **List** | `PageUp` / `PageDown` | Scroll one page | |
| **List** | `Enter` | Select highlighted unit | Updates timeline + edit form |
| **List** | `Space` | Cycle sort on current column | Toggles asc/desc |
| **Form** | `Tab` / `Shift+Tab` | Next / prev field | Explicit tab order |
| **Form** | `Escape` | Revert changes | Discards unsaved edits |
| **Form` | `S` | Cycle status color | gray→yellow→purple→orange→green→red→gray |
| **Help** | `Escape` | Close overlay | |
| **Help** | `Ctrl+F` type | Filter shortcuts | Search within overlay |

---

## Execution Plan

### Step 1: `gui/keybinding_manager.py` — Core manager + help dialog
**Effort: ~0.5 day**

- `KeyBindingManager` class with load/defaults/overrides
- `KeyBinding` dataclass
- `ShortcutHelpDialog` with filterable grid layout
- `TrayNotifier` flash messages
- Unit tests for parsing and override logic

### Step 2: Integrate into `main_window.py`
**Effort: ~0.25 day**

- Create `KeyBindingManager` in `__init__`
- Replace existing `keyPressEvent` with routed version
- Add `_route_key()` method
- Install shortcuts via `_route_key` for all global actions

### Step 3: Per-panel key handlers
**Effort: ~0.5 day**

- `calendar_panel.py` — arrow keys, Enter, T, A
- `list_panel.py` — arrow keys, Enter, PageUp/Dn, Space for sort (ensure table has focus policy)
- `edit_form.py` — Escape revert, S status cycle, explicit tab order

### Step 4: Config integration
**Effort: ~0.25 day**

- Add `keyboard.shortcuts` section to `config.yaml`
- Validate config loading handles missing section gracefully
- Add unit test for config override

### Step 5: PyInstaller + polish
**Effort: ~0.25 day**

- Rebuild `.exe`
- Test all shortcuts in the built binary
- Verify help overlay renders correctly
- Test Tab order in both views

---

## Testing Checklist

- [ ] `?` opens help overlay from any view
- [ ] Help overlay shows all shortcuts grouped by context
- [ ] Help overlay filter works (type to narrow)
- [ ] `Escape` closes help overlay
- [ ] `Ctrl+S` saves when edit form has a unit
- [ ] `Ctrl+S` is a no-op when no unit selected
- [ ] `Ctrl+R` refreshes data
- [ ] `Ctrl+L` toggles between calendar and list views
- [ ] `Ctrl+P` opens pull data dialog
- [ ] `Ctrl+Shift+M` runs selected macro
- [ ] `Ctrl+F` focuses list search box (in list view)
- [ ] Arrow keys navigate calendar dates (only to dates with events)
- [ ] `Enter` on calendar selects highlighted event
- [ ] `T` jumps calendar to today
- [ ] `A` shows all units on calendar
- [ ] Arrow keys navigate list rows
- [ ] `Home`/`End` jump to first/last list row
- [ ] `PageUp`/`PageDown` scroll list
- [ ] `Enter` on list selects unit → updates timeline + edit form
- [ ] `Space` toggles list sort direction on current column
- [ ] `Tab` cycles edit form fields in logical order
- [ ] `Escape` reverts edit form changes
- [ ] `S` cycles status color in edit form
- [ ] Config overrides apply (edit config.yaml, restart, verify)
- [ ] Missing `keyboard` section in config → uses defaults (no crash)
- [ ] Shortcut tooltips shown on hover for buttons (optional)

---

## Known Limitations

1. **Single-key shortcuts conflict** — `S` for status cycle and `T` for today only work when the relevant panel has focus (not a text field). The `_route_key` method checks for focused text widgets to avoid conflicts.
2. **QCalendarWidget arrow key hijacking** — Qt's calendar widget natively handles arrow keys for date selection. Our approach piggybacks on this by intercepting only at the panel level and accepting the event only when the new date has events.
3. **No macOS-specific shortcuts** — All shortcuts use `Ctrl`. On macOS, Qt maps `Ctrl` to `Command` automatically in most cases, but testing on Mac is recommended.
4. **Shortcut overlay not auto-updating** — If shortcuts are changed in config.yaml, the overlay only reflects the change after restart. Runtime reload is out of scope for v1.

---

*Estimated total: 1–1.5 days*
*Generated: 2026-05-30*
