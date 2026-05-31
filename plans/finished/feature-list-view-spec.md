# Feature: List View Panel — Spec Document

**Priority:** High  
**Effort:** Medium (1.5–2.5 days)  
**Risk:** Low-Medium (new panel, no changes to existing panels)

---

## Problem Statement

The calendar view is great for "what's happening on a given date" but terrible for "show me everything due this week" or "show me all units assigned to Jackie sorted by due date." Users need a sortable, filterable list view that shows all units in a flat table — ordered by due date by default — with the ability to swap between calendar and list views without losing their place in the edit form or timeline.

---

## Design Goals

1. **Swap, don't duplicate** — List view replaces the calendar panel in-place. Same left-panel slot. Edit form and timeline on the right are completely unaffected.
2. **Sort by due date default** — Most urgent stuff at the top. Always.
3. **Rich filtering** — Status, detailer, date range, COM search, % complete range. Filters compose (AND logic).
4. **Same selection model** — Clicking a row in the list emits the same `unit_selected(Unit)` signal the calendar does. Zero changes to `MainWindow.on_unit_selected()`.
5. **Persist view preference** — Remember which view (calendar or list) the user was on when they closed the app. Restore on next launch.
6. **Column chooser** — Let users pick which columns to show and in what order.

---

## Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Unit Tracker                                    [📅 Calendar] [📋 List] │
├──────────────────────┬───────────────────────────────────────────────┤
│                      │                                               │
│  ┌─ View Toggle ──┐  │  Unit Timeline                                │
│  │ 📅  │ 📋       │  │  COM 20045 — (RGV) Mathworks 7-31-24         │
│  └────────────────┘  │  ████████████████████ 100%                     │
│                      │  ●─────●──────●──────●─────●─────●             │
│  ┌─ Filters ──────┐  │                                               │
│  │ Status: [All ▼] │  ├───────────────────────────────────────────────┤
│  │ Detailer:[All ▼] │  │                                               │
│  │ Due: [Next 7d ▼] │  │  Edit Unit                                    │
│  │ COM:  [______]   │  │  ┌─ Identity ──────────────────────────────┐  │
│  │ [Clear Filters]  │  │  │ COM: 20045          Job: (RGV) Math... │  │
│  └────────────────┘  │  │ ...                                       │  │
│                      │  └───────────────────────────────────────────┘  │
│  ┌─ List Table ───┐  │                                               │
│  │ COM  │ Due    │  │                                               │
│  │ 20045│ Jun 29 │  │                                               │
│  │ 20078│ Jul 03 │  │                                               │
│  │ 20103│ Jul 12 │  │                                               │
│  │ ...  │ ...    │  │                                               │
│  └────────────────┘  │                                               │
│                      │                                               │
├──────────────────────┴───────────────────────────────────────────────┤
│  Status: 47 units loaded │ Showing 12 of 47 │ View: List (sorted by  │
│                          │                  │ due date, ascending)   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## New File: `gui/list_panel.py`

This is the only new file. It drops into the existing left-panel slot.

```python
"""
List Panel — sortable, filterable table view of all units.

Emits the same `unit_selected(Unit)` signal as CalendarPanel,
so the rest of the app (timeline, edit form) works unchanged.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt5.QtGui import QColor, QBrush, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QComboBox, QLineEdit, QLabel, QPushButton, QGroupBox,
    QAbstractItemView, QSizePolicy
)

from data.models import Unit


# ─── Column Definitions ─────────────────────────────────────────────

# Each column: (key, header, width, sortable, default_visible)
COLUMN_DEFS = [
    ("com_number",          "COM",              70,  True,  True),
    ("detailing_due_date",  "Due Date",         80,  True,  True),
    ("job_name",            "Job Name",         180, True,  True),
    ("detailer",            "Detailer",         100, True,  True),
    ("status_color",        "Status",           60,  True,  True),
    ("percent_complete",    "% Complete",       70,  True,  True),
    ("department_hours",    "Dept Hours",       70,  True,  False),
    ("actual_hours",        "Actual Hours",     70,  True,  False),
    ("target_department_hours", "Target Hrs",   70,  True,  False),
    ("checking_status",     "Checking",         80,  True,  False),
    ("contract_number",     "Contract #",       90,  False, False),
    ("build_date",          "Build Date",       80,  True,  False),
    ("unit_detailing_start_date", "Start Date", 80,  True,  False),
]

# ─── Filter Presets ─────────────────────────────────────────────────

DATE_FILTER_PRESETS = [
    ("All",            None),
    ("Overdue",        "overdue"),
    ("Today",          "today"),
    ("Next 3 Days",    "next_3_days"),
    ("Next 7 Days",    "next_7_days"),
    ("Next 30 Days",   "next_30_days"),
    ("This Month",     "this_month"),
    ("Next Month",     "next_month"),
    ("Past 30 Days",   "past_30_days"),
]

STATUS_OPTIONS = ["All", "gray", "yellow", "purple", "orange", "green", "red"]

STATUS_LABELS = {
    "All": "All",
    "gray": "⬤ Unassigned",
    "yellow": "⬤ In Progress",
    "purple": "⬤ Ready for Checking",
    "orange": "⬤ Checked & Returned",
    "green": "⬤ Released",
    "red": "⬤ Overdue",
}

STATUS_COLORS = {
    "gray":   QColor(148, 163, 184),
    "yellow": QColor(234, 179, 8),
    "purple": QColor(168, 85, 247),
    "orange": QColor(249, 115, 22),
    "green":  QColor(34, 197, 94),
    "red":    QColor(239, 68, 68),
}


# ─── Table Model ────────────────────────────────────────────────────

class UnitListModel:
    """
    Lightweight wrapper that presents a list[Unit] as a table model
    for QTableView. Does NOT subclass QAbstractTableModel — instead
    we use QTableWidget for simplicity since the dataset is small
    (< 500 units).
    """

    def __init__(self, units: list[Unit]):
        self._all_units = units
        self._filtered_units: list[Unit] = list(units)
        self._visible_columns: list[str] = [
            d[0] for d in COLUMN_DEFS if d[4]  # default_visible=True
        ]

    @property
    def filtered_units(self) -> list[Unit]:
        return self._filtered_units

    @property
    def visible_columns(self) -> list[str]:
        return self._visible_columns

    def set_visible_columns(self, keys: list[str]):
        self._visible_columns = keys

    def apply_filters(
        self,
        status: str = "All",
        detailer: str = "All",
        date_preset: str = "All",
        com_search: str = "",
        min_percent: Optional[float] = None,
        max_percent: Optional[float] = None,
    ):
        """Apply all active filters. AND logic between filter dimensions."""
        today = date.today()
        result = list(self._all_units)

        # ── Status filter ──
        if status != "All":
            result = [u for u in result if u.status_color == status]

        # ── Detailer filter ──
        if detailer != "All":
            result = [u for u in result if u.detailer == detailer]

        # ── Date range filter ──
        if date_preset and date_preset != "All":
            result = self._filter_by_date(result, date_preset, today)

        # ── COM search (substring, case-insensitive) ──
        if com_search:
            query = com_search.lower().strip()
            result = [
                u for u in result
                if query in u.com_number.lower()
                or query in u.job_name.lower()
            ]

        # ── % Complete range ──
        if min_percent is not None:
            result = [u for u in result if (u.percent_complete or 0) >= min_percent]
        if max_percent is not None:
            result = [u for u in result if (u.percent_complete or 0) <= max_percent]

        self._filtered_units = result

    def _filter_by_date(self, units: list[Unit], preset: str, today: date) -> list[Unit]:
        """Filter units based on the detailing_due_date."""
        if preset == "overdue":
            return [
                u for u in units
                if u.detailing_due_date and u.detailing_due_date < today
            ]
        elif preset == "today":
            return [
                u for u in units
                if u.detailing_due_date and u.detailing_due_date == today
            ]
        elif preset == "next_3_days":
            end = today + timedelta(days=3)
            return [
                u for u in units
                if u.detailing_due_date and today <= u.detailing_due_date <= end
            ]
        elif preset == "next_7_days":
            end = today + timedelta(days=7)
            return [
                u for u in units
                if u.detailing_due_date and today <= u.detailing_due_date <= end
            ]
        elif preset == "next_30_days":
            end = today + timedelta(days=30)
            return [
                u for u in units
                if u.detailing_due_date and today <= u.detailing_due_date <= end
            ]
        elif preset == "this_month":
            return [
                u for u in units
                if u.detailing_due_date
                and u.detailing_due_date.month == today.month
                and u.detailing_due_date.year == today.year
            ]
        elif preset == "next_month":
            next_m = today.month + 1 if today.month < 12 else 1
            next_y = today.year if today.month < 12 else today.year + 1
            return [
                u for u in units
                if u.detailing_due_date
                and u.detailing_due_date.month == next_m
                and u.detailing_due_date.year == next_y
            ]
        elif preset == "past_30_days":
            start = today - timedelta(days=30)
            return [
                u for u in units
                if u.detailing_due_date and start <= u.detailing_due_date <= today
            ]
        return units

    def sort_by(self, column_key: str, ascending: bool = True):
        """Sort the filtered list by a given column key."""
        def sort_key(unit):
            val = getattr(unit, column_key, None)
            if val is None:
                # None sorts to the end regardless of direction
                return (1, "") if ascending else (0, "")
            return (0, val)

        # Special: status_color sorts by severity, not alphabetically
        if column_key == "status_color":
            severity = {"red": 0, "orange": 1, "purple": 2, "yellow": 3, "gray": 4, "green": 5}
            def sort_key(unit):
                return severity.get(unit.status_color, 99)

        self._filtered_units.sort(key=sort_key, reverse=not ascending)

    def get_unique_detailers(self) -> list[str]:
        """Return sorted list of unique detailer values for the dropdown."""
        detailers = set()
        for u in self._all_units:
            if u.detailer:
                detailers.add(u.detailer)
        return sorted(detailers)


# ─── List Panel Widget ──────────────────────────────────────────────

class ListPanel(QWidget):
    """
    Left-panel widget that shows units in a sortable, filterable table.

    Emits `unit_selected(Unit)` when the user clicks a row — same signal
    as CalendarPanel, so MainWindow needs no changes to handle selection.
    """

    unit_selected = pyqtSignal(object)  # emits Unit

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[UnitListModel] = None
        self._sort_column = "detailing_due_date"
        self._sort_ascending = True
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Filter bar ──
        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(4)

        # Row 1: Status + Detailer
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        for opt in STATUS_OPTIONS:
            self.status_combo.addItem(STATUS_LABELS.get(opt, opt), opt)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        row1.addWidget(self.status_combo)

        row1.addWidget(QLabel("Detailer:"))
        self.detailer_combo = QComboBox()
        self.detailer_combo.addItem("All", "All")
        self.detailer_combo.currentIndexChanged.connect(self._on_filter_changed)
        row1.addWidget(self.detailer_combo)
        filter_layout.addLayout(row1)

        # Row 2: Date range + COM search
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Due:"))
        self.date_combo = QComboBox()
        for label, value in DATE_FILTER_PRESETS:
            self.date_combo.addItem(label, value)
        self.date_combo.currentIndexChanged.connect(self._on_filter_changed)
        row2.addWidget(self.date_combo)

        row2.addWidget(QLabel("COM:"))
        self.com_search = QLineEdit()
        self.com_search.setPlaceholderText("Search COM or job name...")
        self.com_search.setClearButtonEnabled(True)
        self.com_search.textChanged.connect(self._on_filter_changed)
        row2.addWidget(self.com_search)
        filter_layout.addLayout(row2)

        # Row 3: Clear filters button
        row3 = QHBoxLayout()
        self.clear_btn = QPushButton("Clear All Filters")
        self.clear_btn.clicked.connect(self._clear_filters)
        row3.addWidget(self.clear_btn)
        row3.addStretch()

        # Column chooser button
        self.columns_btn = QPushButton("Columns...")
        self.columns_btn.clicked.connect(self._show_column_chooser)
        row3.addWidget(self.columns_btn)
        filter_layout.addLayout(row3)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # ── Table ──
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Style
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                font-size: 12px;
                selection-background-color: #dbeafe;
                selection-color: #1e293b;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        """)

        layout.addWidget(self.table, stretch=1)

        # ── Status label ──
        self.status_label = QLabel("No units loaded")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self.status_label)

    # ── Data Loading ─────────────────────────────────────────────────

    def set_units(self, units: list[Unit]):
        """Load units into the model and refresh the table."""
        self._model = UnitListModel(units)

        # Populate detailer dropdown
        self.detailer_combo.clear()
        self.detailer_combo.addItem("All", "All")
        for d in self._model.get_unique_detailers():
            self.detailer_combo.addItem(d, d)

        # Default sort: due date ascending (most urgent first)
        self._sort_column = "detailing_due_date"
        self._sort_ascending = True

        self._refresh_table()

    def refresh(self):
        """Re-apply filters and refresh (call after data reload)."""
        if self._model:
            self._on_filter_changed()

    # ── Table Rendering ──────────────────────────────────────────────

    def _refresh_table(self):
        """Rebuild the table from the filtered/sorted model."""
        if not self._model:
            return

        units = self._model.filtered_units
        visible_cols = self._model.visible_columns

        # Build column headers
        col_headers = []
        col_keys = []
        for key, header, width, sortable, _ in COLUMN_DEFS:
            if key in visible_cols:
                # Add sort indicator to header
                if key == self._sort_column:
                    arrow = " ▲" if self._sort_ascending else " ▼"
                    col_headers.append(header + arrow)
                else:
                    col_headers.append(header)
                col_keys.append(key)

        self.table.setColumnCount(len(col_headers))
        self.table.setHorizontalHeaderLabels(col_headers)
        self.table.setRowCount(len(units))

        # Set column widths
        width_map = {d[0]: d[2] for d in COLUMN_DEFS}
        for col_idx, key in enumerate(col_keys):
            w = width_map.get(key, 80)
            self.table.setColumnWidth(col_idx, w)

        # Populate rows
        for row_idx, unit in enumerate(units):
            for col_idx, key in enumerate(col_keys):
                value = getattr(unit, key, None)
                display = self._format_cell(key, value, unit)
                item = QTableWidgetItem(display)

                # Alignment
                if key in ("percent_complete", "department_hours", "actual_hours",
                           "target_department_hours"):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif key == "status_color":
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                # Status color: paint the cell background
                if key == "status_color":
                    color = STATUS_COLORS.get(value, QColor(200, 200, 200))
                    item.setBackground(QBrush(color))
                    # White text for dark backgrounds, black for light
                    brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
                    item.setForeground(QBrush(QColor("white") if brightness < 160 else QColor("#1e293b")))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    item.setText("")  # Color block, no text needed
                elif key == "detailing_due_date" and value:
                    # Highlight overdue dates
                    from datetime import date as date_type
                    if isinstance(value, date_type) and value < date_type.today():
                        item.setForeground(QBrush(QColor("#dc2626")))
                        item.setFont(QFont("Segoe UI", 9, QFont.Bold))

                # Store the unit object on the row for selection retrieval
                item.setData(Qt.UserRole, unit)

                self.table.setItem(row_idx, col_idx, item)

        # Update status label
        total = len(self._model._all_units)
        showing = len(units)
        sort_info = f"sorted by {self._sort_column}"
        if self._sort_column in ("detailing_due_date", "com_number", "percent_complete",
                                  "department_hours", "actual_hours"):
            sort_info += " ▲" if self._sort_ascending else " ▼"
        self.status_label.setText(
            f"Showing {showing} of {total} units │ {sort_info}"
        )

    def _format_cell(self, key: str, value, unit: Unit) -> str:
        """Format a unit attribute for display in a table cell."""
        if value is None:
            return "—"

        if key == "detailing_due_date" or key == "build_date" or key == "unit_detailing_start_date":
            if hasattr(value, "strftime"):
                return value.strftime("%m/%d/%Y")
            return str(value)

        if key == "percent_complete":
            pct = value * 100 if isinstance(value, float) and value <= 1 else value
            return f"{pct:.0f}%"

        if key in ("department_hours", "actual_hours", "target_department_hours"):
            return f"{value:.2f}"

        if key == "status_color":
            return ""  # Color block cell, text handled by background

        return str(value)

    # ── Filtering ────────────────────────────────────────────────────

    def _on_filter_changed(self):
        """Called when any filter widget changes."""
        if not self._model:
            return

        status = self.status_combo.currentData()
        detailer = self.detailer_combo.currentData()
        date_preset = self.date_combo.currentData()
        com_search = self.com_search.text()

        self._model.apply_filters(
            status=status or "All",
            detailer=detailer or "All",
            date_preset=date_preset or "All",
            com_search=com_search,
        )

        # Re-apply current sort
        self._model.sort_by(self._sort_column, self._sort_ascending)

        self._refresh_table()

    def _clear_filters(self):
        """Reset all filters to defaults."""
        self.status_combo.setCurrentIndex(0)
        self.detailer_combo.setCurrentIndex(0)
        self.date_combo.setCurrentIndex(0)
        self.com_search.clear()
        self._on_filter_changed()

    # ── Sorting ──────────────────────────────────────────────────────

    def _on_header_clicked(self, column_index: int):
        """Toggle sort on the clicked column."""
        visible_cols = self._model.visible_columns if self._model else []
        if column_index >= len(visible_cols):
            return

        clicked_key = visible_cols[column_index]

        if clicked_key == self._sort_column:
            # Toggle direction
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = clicked_key
            self._sort_ascending = True

        if self._model:
            self._model.sort_by(self._sort_column, self._sort_ascending)
            self._refresh_table()

    # ── Selection ────────────────────────────────────────────────────

    def _on_selection_changed(self):
        """Emit unit_selected when the user clicks a row."""
        selected = self.table.selectedItems()
        if not selected:
            return

        # Get the unit from the first item in the selected row
        item = selected[0]
        unit = item.data(Qt.UserRole)
        if unit:
            self.unit_selected.emit(unit)

    # ── Column Chooser ───────────────────────────────────────────────

    def _show_column_chooser(self):
        """Show a dialog to toggle visible columns."""
        from PyQt5.QtWidgets import QDialog, QCheckBox, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Choose Columns")
        dialog.setMinimumWidth(220)
        layout = QVBoxLayout(dialog)

        checkboxes = []
        current_visible = set(self._model.visible_columns) if self._model else set()

        for key, header, width, sortable, default in COLUMN_DEFS:
            cb = QCheckBox(header)
            cb.setChecked(key in current_visible)
            cb.setProperty("key", key)
            layout.addWidget(cb)
            checkboxes.append(cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            new_visible = [
                cb.property("key") for cb in checkboxes if cb.isChecked()
            ]
            if new_visible and self._model:
                self._model.set_visible_columns(new_visible)
                self._refresh_table()
```

---

## Modified Files

### `gui/main_window.py` — View Toggle + Left Panel Swap

**Changes:**

```python
from gui.calendar_panel import CalendarPanel
from gui.list_panel import ListPanel

# In __init__:
# ── View toggle bar (above left panel) ──
self.view_toggle = QHBoxLayout()
self.calendar_view_btn = QPushButton("📅 Calendar")
self.list_view_btn = QPushButton("📋 List")
self.calendar_view_btn.setCheckable(True)
self.list_view_btn.setCheckable(True)
self.calendar_view_btn.setChecked(True)  # default
self.view_toggle.addWidget(self.calendar_view_btn)
self.view_toggle.addWidget(self.list_view_btn)

# ── Left panel container (stacked) ──
self.left_panel_stack = QStackedWidget()
self.calendar_panel = CalendarPanel()
self.list_panel = ListPanel()
self.left_panel_stack.addWidget(self.calendar_panel)  # index 0
self.left_panel_stack.addWidget(self.list_panel)       # index 1

# ── Connect view toggle ──
self.calendar_view_btn.clicked.connect(lambda: self._switch_view("calendar"))
self.list_view_btn.clicked.connect(lambda: self._switch_view("list"))

# ── Connect selection signals from BOTH panels ──
self.calendar_panel.unit_selected.connect(self.on_unit_selected)
self.list_panel.unit_selected.connect(self.on_unit_selected)

# ── Load saved view preference ──
saved_view = self.config.get("ui", {}).get("last_view", "calendar")
if saved_view == "list":
    self._switch_view("list")
```

**New methods:**

```python
def _switch_view(self, view_name: str):
    """Swap between calendar and list views."""
    if view_name == "calendar":
        self.left_panel_stack.setCurrentIndex(0)
        self.calendar_view_btn.setChecked(True)
        self.list_view_btn.setChecked(False)
    elif view_name == "list":
        self.left_panel_stack.setCurrentIndex(1)
        self.calendar_view_btn.setChecked(False)
        self.list_view_btn.setChecked(True)
        # If list panel has no data yet, populate it
        if self._units:
            self.list_panel.set_units(self._units)

    # Save preference
    self.config.setdefault("ui", {})["last_view"] = view_name
    self._save_config()

def _refresh_data(self):
    """Override existing refresh to update both panels."""
    units = load_units(...)
    self._units = units
    self.calendar_panel.set_events(units)
    self.calendar_panel.refresh()
    self.list_panel.set_units(units)
```

### `config.yaml` — New Settings

```yaml
# UI preferences
ui:
  last_view: "calendar"   # "calendar" or "list"
  list_columns:           # visible columns in list view (ordered)
    - com_number
    - detailing_due_date
    - job_name
    - detailer
    - status_color
    - percent_complete
  list_sort_column: "detailing_due_date"
  list_sort_ascending: true
  list_filters:           # last-used filter state (optional)
    status: "All"
    detailer: "All"
    date_preset: "All"
```

---

## Signal Flow (Unchanged for Right Panel)

```
User clicks row in ListPanel
  → ListPanel.unit_selected(Unit)
    → MainWindow.on_unit_selected(Unit)
      ├── TimelinePanel.set_unit(Unit)    ← unchanged
      └── EditForm.set_unit(Unit)         ← unchanged
           → User edits and clicks Save
             → EditForm.saved(Unit)
               → MainWindow.on_save_unit(Unit)
                 ├── save_unit()
                 ├── load_units()          ← reloads
                 ├── calendar_panel.refresh()
                 └── list_panel.refresh()  ← NEW: also refreshes list
```

The key insight: **the right panel doesn't know or care which left panel emitted the signal.** Both `CalendarPanel` and `ListPanel` emit the same `unit_selected(Unit)` signal. `MainWindow.on_unit_selected()` is completely unchanged.

---

## Filter Behavior Details

### Filter Composition (AND logic)
All active filters combine with AND. If you pick Status=red AND Detailer=Jackie AND Due=Next 7 Days, you get only units that match ALL three.

### Filter Persistence
Filters are NOT persisted across sessions by default (clean slate each launch). The `list_filters` config key is optional — if present, restore them; if absent, default to "All."

### COM Search
- Substring match on both `com_number` and `job_name`
- Case-insensitive
- Real-time filtering (fires on every keystroke via `textChanged`)
- Debounce: 150ms timer so it doesn't re-filter on every single keystroke

### Date Presets
| Preset | Logic |
|--------|-------|
| All | No date filter |
| Overdue | `detailing_due_date < today` |
| Today | `detailing_due_date == today` |
| Next 3 Days | `today <= due <= today+3` |
| Next 7 Days | `today <= due <= today+7` |
| Next 30 Days | `today <= due <= today+30` |
| This Month | Same month/year as today |
| Next Month | Calendar next month |
| Past 30 Days | `today-30 <= due <= today` |

### Status Filter
Uses the 6-level color system. "All" shows everything. Otherwise filters to exact `status_color` match.

### Detailer Filter
Dynamically populated from the actual data. Shows all unique `detailer` values found in the loaded units. "All" shows everything.

---

## Sorting Behavior

| Column | Sort Type | Default Direction |
|--------|-----------|-------------------|
| COM | Alphanumeric | Ascending |
| Due Date | Chronological | Ascending (soonest first) |
| Job Name | Alphabetical | Ascending |
| Detailer | Alphabetical | Ascending |
| Status | Severity (red→green) | Red first |
| % Complete | Numeric | Ascending |
| Hours columns | Numeric | Ascending |

Click a column header to sort by it. Click again to toggle direction. The header shows ▲ or ▼ to indicate current sort.

---

## Execution Plan

### Step 1: Create `gui/list_panel.py`
**Effort: ~0.5 day**

- `UnitListModel` class with filtering and sorting
- `ListPanel` widget with filter bar + table
- `unit_selected(Unit)` signal
- Column chooser dialog
- Status label at bottom

### Step 2: Integrate into `gui/main_window.py`
**Effort: ~0.5 day**

- Add view toggle buttons
- Replace direct `calendar_panel` reference with `QStackedWidget`
- Connect both panels' `unit_selected` signals
- Update `_refresh_data()` to populate both panels
- Load/save view preference from config

### Step 3: Config + Persistence
**Effort: ~0.25 day**

- Add `ui` section to `config.yaml`
- Save/restore visible columns, sort state, and last view
- Optional: restore last filter state

### Step 4: Polish + Edge Cases
**Effort: ~0.25 day**

- Debounce the COM search (150ms timer)
- Handle empty filter results ("No units match your filters")
- Keyboard navigation: Up/Down arrows move selection, Enter activates
- Double-click a row to select (in addition to single-click)
- Ensure the selected unit is preserved across filter changes if still visible

### Step 5: PyInstaller + Test
**Effort: ~0.25 day**

- Rebuild `.exe`
- Test view toggle
- Test all filter combinations
- Test sort on every column
- Test column chooser
- Test that edit form and timeline work identically from both views
- Test config persistence (close app, reopen, verify view + columns restored)

---

## Testing Checklist

- [ ] View toggle switches between calendar and list without losing selection
- [ ] List loads with all units, sorted by due date ascending
- [ ] Clicking a list row updates timeline and edit form
- [ ] Status filter works for all 6 colors + All
- [ ] Detailer filter populates from data
- [ ] Date presets work correctly (verify boundary dates)
- [ ] COM search filters in real-time (substring, case-insensitive)
- [ ] COM search matches both COM number and job name
- [ ] Clear All Filters resets everything
- [ ] Column sort toggles on header click (▲/▼ indicator)
- [ ] Status sort orders by severity (red first, green last)
- [ ] Overdue dates show in red bold in the table
- [ ] Column chooser shows/hides columns, order persists
- [ ] View preference persists across app restart
- [ ] Empty filter results show "No units match your filters"
- [ ] Keyboard Up/Down moves selection in list
- [ ] Double-click selects (same as single-click)
- [ ] After save + refresh, list updates and selection is preserved if unit still visible
- [ ] .exe rebuilds and runs correctly

---

*Estimated total: 1.5–2.5 days*
*Generated: 2026-05-30*
