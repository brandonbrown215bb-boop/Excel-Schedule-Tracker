# gui/calendar_panel.py
from collections import defaultdict

from PyQt5.QtCore import QDate, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter
from PyQt5.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from data.models import Unit


class EventCalendarWidget(QCalendarWidget):
    """Calendar that paints colored dots on dates that have COM events."""

    date_clicked = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events_by_date: dict[QDate, list[Unit]] = defaultdict(list)
        self.setGridVisible(True)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.clicked.connect(self._emit_date_clicked)
        self._theme_name = "light"
        self._cvd_mode = "none"

    def _emit_date_clicked(self, date: QDate):
        if date in self.events_by_date:
            self.date_clicked.emit(date)

    def set_events(self, units: list[Unit]):
        """Build the date→units map — only the detailing due date."""
        self.events_by_date.clear()
        for unit in units:
            if unit.detailing_due_date is not None:
                qdate = QDate(
                    unit.detailing_due_date.year,
                    unit.detailing_due_date.month,
                    unit.detailing_due_date.day,
                )
                self.events_by_date[qdate].append(unit)
        self.updateCells()

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode = cvd_mode
        self.updateCells()

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate) -> None:
        super().paintCell(painter, rect, date)

        try:
            if date not in self.events_by_date:
                return

            units = self.events_by_date[date]

            from gui.theme import get_status_colors
            status_colors = get_status_colors(self._theme_name, self._cvd_mode)
            hex_to_qcolor = {k: QColor(v) for k, v in status_colors.items()}

            # If multiple units on this date, color by worst status
            statuses = {u.calculated_status_color for u in units}
            severity = {"red": 0, "orange": 1, "purple": 2, "yellow": 3, "gray": 4, "green": 5}
            worst = min(statuses, key=lambda s: severity.get(s, 99))
            dot_color = hex_to_qcolor.get(worst, QColor(150, 150, 150))

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(dot_color))
            painter.setPen(Qt.NoPen)  # type: ignore[reportAttributeAccessIssue]

            dot_radius = 4
            dot_diameter = dot_radius * 2
            spacing = 2
            start_x = rect.right() - dot_diameter - spacing
            start_y = rect.top() + spacing + 2
            positions = [
                (start_x, start_y),
                (start_x - dot_diameter - spacing, start_y),
                (start_x - 2 * (dot_diameter + spacing), start_y),
                (start_x, start_y + dot_diameter + spacing),
                (start_x - dot_diameter - spacing, start_y + dot_diameter + spacing),
                (start_x - 2 * (dot_diameter + spacing), start_y + dot_diameter + spacing),
            ]
            for i in range(min(len(units), len(positions))):
                painter.drawEllipse(
                    int(positions[i][0]), int(positions[i][1]), dot_diameter, dot_diameter
                )
            painter.restore()
        except Exception:
            pass  # Defensive: don't crash on paint errors


class CalendarPanel(QWidget):
    """Left panel: calendar + event list for selected date."""

    unit_selected = pyqtSignal(Unit)

    def __init__(self, units: list[Unit], parent=None):
        super().__init__(parent)
        self.setObjectName("calendar_panel")
        self.units = units
        self.selected_date: QDate | None = None
        self._theme_name = "light"
        self._cvd_mode = "none"

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Calendar</b>"))
        header.addStretch()
        self.today_btn = QPushButton("Today")
        self.today_btn.clicked.connect(self._go_today)
        header.addWidget(self.today_btn)
        layout.addLayout(header)

        self.calendar = EventCalendarWidget()
        self.calendar.set_events(units)
        self.calendar.date_clicked.connect(self._on_date_clicked)
        layout.addWidget(self.calendar)

        layout.addWidget(QLabel("<b>Events on date:</b>"))
        self.event_list = QListWidget()
        self.event_list.itemClicked.connect(self._on_event_clicked)
        layout.addWidget(self.event_list)

        show_all_btn = QPushButton("Show All Units")
        show_all_btn.clicked.connect(self._show_all_units)
        layout.addWidget(show_all_btn)

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode = cvd_mode
        self.calendar.set_theme(theme_name, cvd_mode)
        self._refresh_event_list()

    def _refresh_event_list(self) -> None:
        """Rebuild the event list with current theme colors."""
        if self.selected_date is None:
            return
        self.event_list.clear()
        for unit in self.calendar.events_by_date.get(self.selected_date, []):
            self._add_event_item(unit)

    def _add_event_item(self, unit: Unit) -> None:
        from gui.theme import status_style
        hex_color, icon, label = status_style(
            self._theme_name, unit.calculated_status_color, self._cvd_mode)
        item = QListWidgetItem(f"{icon} COM {unit.com_number} — {unit.job_name}")
        item.setData(Qt.UserRole, unit)
        bg = QColor(hex_color)
        bg.setAlpha(80)
        item.setBackground(QBrush(bg))
        self.event_list.addItem(item)

    def refresh(self, units: list[Unit]):
        """Reload data."""
        self.units = units
        self.calendar.set_events(units)

    def _on_date_clicked(self, date: QDate) -> None:
        self.selected_date = date
        self.event_list.clear()
        for unit in self.calendar.events_by_date.get(date, []):
            self._add_event_item(unit)

    def _on_event_clicked(self, item: QListWidgetItem):
        unit = item.data(Qt.UserRole)  # type: ignore[reportAttributeAccessIssue]
        if unit:
            self.unit_selected.emit(unit)

    def _show_all_units(self):
        self.event_list.clear()
        for unit in self.units:
            has_dates = any(d is not None for _, d in unit.milestones)
            if has_dates:
                self._add_event_item(unit)

    def _go_today(self):
        self.calendar.setSelectedDate(QDate.currentDate())
