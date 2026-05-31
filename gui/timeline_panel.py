# gui/timeline_panel.py
from datetime import date, timedelta

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from data.models import Unit


class TimelineWidget(QWidget):
    """Renders a horizontal milestone timeline bar with readable labels."""

    BAR_HEIGHT = 36
    BAR_Y = 55
    MARKER_AREA_TOP = None  # computed at paint time
    ROW_HEIGHT = 22
    LEFT_MARGIN = 16
    RIGHT_MARGIN = 16
    FONT_FAMILY = "Segoe UI"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.unit: Unit | None = None
        self.setMinimumHeight(220)
        self._theme_name = "light"
        self._cvd_mode = "none"

    def _font(self, size: int, bold: bool = False) -> QFont:
        weight = QFont.Bold if bold else QFont.Normal
        f = QFont(self.FONT_FAMILY, size, weight)
        f.setStyleStrategy(QFont.PreferAntialias)
        return f

    def set_unit(self, unit: Unit | None):
        self.unit = unit
        # Dynamically resize to fit content
        if unit:
            milestones = [(n, d) for n, d in unit.milestones if d is not None]
            n_rows = max(len(milestones), 1)
            needed = self.BAR_Y + self.BAR_HEIGHT + 20 + n_rows * self.ROW_HEIGHT + 50
            self.setMinimumHeight(max(needed, 220))
            self.setMaximumHeight(max(needed, 220))
        else:
            self.setMinimumHeight(220)
            self.setMaximumHeight(220)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # --- Background ---
        painter.fillRect(self.rect(), QBrush(QColor(252, 252, 255)))

        if self.unit is None:
            painter.setPen(QPen(QColor(140, 140, 140)))
            painter.setFont(self._font(11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Select a unit to view its timeline")  # type: ignore[reportAttributeAccessIssue]
            painter.end()
            return

        milestones = [(name, d) for name, d in self.unit.milestones if d is not None]
        if not milestones:
            painter.setPen(QPen(QColor(140, 140, 140)))
            painter.setFont(self._font(11))
            painter.drawText(self.rect(), Qt.AlignCenter, "No milestone dates available")  # type: ignore[reportAttributeAccessIssue]
            painter.end()
            return

        # --- Determine date range ---
        dates = [d for _, d in milestones]
        min_date = min(dates)
        max_date = max(dates)

        # Pad so short timelines don't look broken (at least 30 days)
        date_range = (max_date - min_date).days
        if date_range < 30:
            padding = (30 - date_range) // 2 + 1
            min_date -= timedelta(days=padding)
            max_date += timedelta(days=padding)

        total_days = max((max_date - min_date).days, 1)

        # --- Layout geometry ---
        width = self.width()
        bar_x = self.LEFT_MARGIN
        bar_width = width - self.LEFT_MARGIN - self.RIGHT_MARGIN
        bar_y = self.BAR_Y

        # --- Status color bar ---
        from gui.theme import get_status_colors, STATUS_SHAPES
        colors = get_status_colors(self._theme_name, self._cvd_mode)
        bar_color = QColor(colors.get(self.unit.calculated_status_color, colors["gray"]))

        # Add icon to bar text
        icon = STATUS_SHAPES.get(self.unit.calculated_status_color, "")

        # Bar border
        painter.setPen(QPen(QColor(160, 160, 160), 1))
        painter.setBrush(QBrush(bar_color))
        painter.drawRoundedRect(bar_x, bar_y, bar_width, self.BAR_HEIGHT, 4, 4)

        # Status text on the bar
        painter.setPen(QPen(QColor(30, 30, 30)))
        painter.setFont(self._font(9, bold=True))
        status_text = f"{icon} {self.unit.percent_complete:.0f}%  —  {self.unit.checking_status}"
        painter.drawText(
            bar_x + 10,
            bar_y + 2,
            bar_width - 20,
            self.BAR_HEIGHT - 4,
            Qt.AlignVCenter | Qt.AlignLeft,
            status_text,  # type: ignore[reportAttributeAccessIssue]
        )

        # --- Draw thin horizontal grid lines behind milestones ---
        marker_area_top = bar_y + self.BAR_HEIGHT + 12
        marker_area_bottom = marker_area_top + len(milestones) * self.ROW_HEIGHT

        # --- Milestone rows ---
        painter.setFont(self._font(9))

        for i, (name, d) in enumerate(milestones):
            row_y = marker_area_top + i * self.ROW_HEIGHT

            # Alternating row background for readability
            if i % 2 == 0:
                painter.fillRect(
                    bar_x, row_y, bar_width, self.ROW_HEIGHT, QBrush(QColor(237, 240, 248))
                )

            # Position along bar
            offset_days = (d - min_date).days
            x = bar_x + int((offset_days / total_days) * bar_width)
            x = max(bar_x + 2, min(x, bar_x + bar_width - 2))  # clamp

            # Vertical guide line (faint)
            painter.setPen(QPen(QColor(200, 200, 210), 1, Qt.DotLine))  # type: ignore[reportAttributeAccessIssue]
            painter.drawLine(x, bar_y + self.BAR_HEIGHT, x, row_y + self.ROW_HEIGHT)

            # Tick from bar to row
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawLine(x, bar_y + self.BAR_HEIGHT, x, row_y + 2)

            # Milestone dot (larger, more visible)
            dot_r = 5
            painter.setBrush(QBrush(QColor(50, 90, 190)))
            painter.setPen(QPen(QColor(30, 60, 150), 1))
            painter.drawEllipse(
                x - dot_r, row_y + self.ROW_HEIGHT // 2 - dot_r, dot_r * 2, dot_r * 2
            )

            # Milestone name (left-aligned after the dot)
            painter.setPen(QPen(QColor(20, 20, 20)))
            painter.setFont(self._font(9))
            label_x = bar_x + 14
            label_w = bar_width - 30
            painter.drawText(
                label_x,
                row_y,
                label_w,
                self.ROW_HEIGHT,
                Qt.AlignVCenter | Qt.AlignLeft,
                name,  # type: ignore[reportAttributeAccessIssue]
            )

            # Date label (right-aligned)
            painter.setPen(QPen(QColor(80, 80, 100)))
            painter.setFont(self._font(8))
            date_str = d.strftime("%b %d, %Y")
            painter.drawText(
                bar_x,
                row_y,
                bar_width - 10,
                self.ROW_HEIGHT,
                Qt.AlignVCenter | Qt.AlignRight,
                date_str,  # type: ignore[reportAttributeAccessIssue]
            )

        # --- Axis / range labels at the bottom ---
        axis_y = marker_area_bottom + 12
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.setFont(self._font(8))

        # Axis line
        painter.drawLine(bar_x, axis_y, bar_x + bar_width, axis_y)

        # Tick marks along the axis (roughly monthly)
        self._draw_date_axis(painter, min_date, max_date, total_days, bar_x, bar_width, axis_y)

        # --- Today line ---
        today = date.today()
        if min_date <= today <= max_date:
            today_offset = (today - min_date).days
            today_x = bar_x + int((today_offset / total_days) * bar_width)

            painter.setPen(QPen(QColor(210, 40, 40), 2, Qt.DashLine))  # type: ignore[reportAttributeAccessIssue]
            painter.drawLine(today_x, bar_y - 4, today_x, axis_y)

            # "TODAY" label
            painter.setPen(QPen(QColor(210, 40, 40)))
            painter.setFont(self._font(7, bold=True))
            painter.drawText(
                today_x + 4,
                bar_y - 6,
                40,
                12,
                Qt.AlignLeft | Qt.AlignVCenter,
                "TODAY",  # type: ignore[reportAttributeAccessIssue]
            )

        painter.end()

    def _draw_date_axis(
        self,
        painter: QPainter,
        min_date: date,
        max_date: date,
        total_days: int,
        bar_x: int,
        bar_width: int,
        axis_y: int,
    ) -> None:
        """Draw month-start tick marks and labels along the bottom axis."""
        current = min_date.replace(day=1)
        if current < min_date:
            # Advance to next month start
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)

        painter.setFont(self._font(7))
        painter.setPen(QPen(QColor(100, 100, 100)))

        while current <= max_date:
            offset_days = (current - min_date).days
            x = bar_x + int((offset_days / total_days) * bar_width)

            # Tick
            painter.drawLine(x, axis_y, x, axis_y + 5)

            # Label
            label = current.strftime("%b %Y")
            painter.drawText(x - 30, axis_y + 7, 60, 14, Qt.AlignCenter, label)  # type: ignore[reportAttributeAccessIssue]

            # Next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)


class TimelinePanel(QWidget):
    """Wrapper panel that holds the header + timeline widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("timeline_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._theme_name = "light"
        self._cvd_mode = "none"

        self.header_label = QLabel("<b>Unit Timeline</b>")
        self.header_label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.header_label)

        self.timeline = TimelineWidget()
        layout.addWidget(self.timeline)

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode = cvd_mode
        self.timeline._theme_name = theme_name
        self.timeline._cvd_mode = cvd_mode
        self.timeline.update()

    def set_unit(self, unit: Unit | None):
        if unit:
            self.header_label.setText(
                f"<b>Unit Timeline</b> — COM {unit.com_number} — {unit.job_name}"
            )
        else:
            self.header_label.setText("<b>Unit Timeline</b>")
        self.timeline.set_unit(unit)
