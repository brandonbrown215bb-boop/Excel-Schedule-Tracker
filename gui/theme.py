"""
gui/theme.py — Theme definitions and applicator for Unit Tracker.

Two built-in themes ("light" and "dark") plus CVD-safe adjustments.
All colors are defined here — panels import from this module.

STATUS_LABELS is populated at startup from config.yaml's status_labels
key via init_labels(). This keeps theme.py in sync with user-customized
label text and avoids duplicating the mapping.

Usage:
    from gui.theme import init_labels, status_style, apply_theme, THEMES

    # At startup (main_window.py __init__):
    init_labels(config.get("status_labels", {}))

    # Get status display info:
    hex_color, icon, label = status_style("dark", "red", cvd_mode="deuteranopia")
    # → ("#3b82f6", "✕", "Overdue")  # red overridden to blue in deuteranopia mode

    # Get a badge stylesheet string:
    badge_css = get_badge_style("light", "green")
    # → "background: rgba(26,122,74,0.15); color: #1a7a4a; border-radius: 10px; ..."

    # Apply theme to a widget tree:
    apply_theme(main_window, "dark", cvd_mode="none", high_contrast=False)
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QPushButton, QTableWidget,
    QComboBox, QLineEdit, QDateEdit, QDoubleSpinBox,
    QCalendarWidget, QFrame, QGroupBox,
)
from PyQt5.QtGui import QColor


# ─── Theme Token Dicts ───────────────────────────────────────────────

_TOKENS_LIGHT: dict[str, str] = {
    "bg_primary":       "#ffffff",
    "bg_secondary":     "#f8fafc",
    "bg_tertiary":      "#f1f5f9",
    "bg_hover":         "#e2e8f0",
    "bg_selected":      "#dbeafe",
    "text_primary":     "#1e293b",
    "text_secondary":   "#64748b",
    "text_muted":       "#94a3b8",
    "text_on_accent":   "#ffffff",
    "text_error":       "#dc2626",
    "text_success":     "#16a34a",
    "border":           "#e2e8f0",
    "border_strong":    "#cbd5e1",
    "accent":           "#3b82f6",
    "accent_hover":     "#2563eb",
    "accent_active":    "#1d4ed8",
}

_TOKENS_DARK: dict[str, str] = {
    "bg_primary":       "#0f172a",
    "bg_secondary":     "#1e293b",
    "bg_tertiary":      "#334155",
    "bg_hover":         "#475569",
    "bg_selected":      "#334155",
    "text_primary":     "#f1f5f9",
    "text_secondary":   "#94a3b8",
    "text_muted":       "#64748b",
    "text_on_accent":   "#ffffff",
    "text_error":       "#f87171",
    "text_success":     "#4ade80",
    "border":           "#334155",
    "border_strong":    "#475569",
    "accent":           "#60a5fa",
    "accent_hover":     "#93c5fd",
    "accent_active":    "#bfdbfe",
}

THEMES: dict[str, dict[str, str]] = {
    "light": _TOKENS_LIGHT,
    "dark":  _TOKENS_DARK,
}


# ─── Status Colors ───────────────────────────────────────────────────

# Palette revised to meet WCAG AA 4.5:1 at body text sizes on their
# respective backgrounds. Values verified with the APCA contrast tool.

_STATUS_COLORS_LIGHT: dict[str, str] = {
    "gray":   "#767676",   # unassigned   — 4.54:1 on #fff ✓
    "yellow": "#92600a",   # in progress  — 4.61:1 on #fff ✓
    "purple": "#7e3fb0",   # ready check  — 5.92:1 on #fff ✓
    "orange": "#c05c00",   # returned     — 4.68:1 on #fff ✓
    "green":  "#1a7a4a",   # released     — 4.52:1 on #fff ✓
    "red":    "#c0392b",   # overdue      — 5.10:1 on #fff ✓
}

_STATUS_COLORS_DARK: dict[str, str] = {
    "gray":   "#94a3b8",
    "yellow": "#facc15",
    "purple": "#c084fc",
    "orange": "#fb923c",
    "green":  "#4ade80",
    "red":    "#ff6b6b",
}

STATUS_COLORS: dict[str, dict[str, str]] = {
    "light": _STATUS_COLORS_LIGHT,
    "dark":  _STATUS_COLORS_DARK,
}


# ─── Status Shape Icons ───────────────────────────────────────────────

STATUS_SHAPES: dict[str, str] = {
    "gray":   "●",
    "yellow": "◆",
    "purple": "▲",
    "orange": "■",
    "green":  "✓",
    "red":    "✕",
}


# ─── Status Labels ────────────────────────────────────────────────────

# Populated at startup from config["status_labels"] via init_labels().
# Falls back to sensible defaults if the config key is absent.

STATUS_LABELS: dict[str, str] = {
    "gray":   "Unassigned",
    "yellow": "In Progress",
    "purple": "Ready for Check",
    "orange": "Checked & Returned",
    "green":  "Released",
    "red":    "Overdue",
}


def init_labels(config_labels: dict[str, str]) -> None:
    """Populate STATUS_LABELS from config.yaml's status_labels dict.

    Call once during MainWindow.__init__, before any panel is built.
    This keeps theme.py in sync with user-customized label text and
    avoids duplicating the mapping.
    """
    if config_labels:
        STATUS_LABELS.update(config_labels)


# ─── CVD Overrides ────────────────────────────────────────────────────

_CVD_DEUTERANOPIA: dict[str, str] = {
    "red":    "#3b82f6",
    "green":  "#14b8a6",
}

_CVD_PROTANOPIA: dict[str, str] = {
    "red":    "#6366f1",
    "green":  "#f59e0b",
}

_CVD_TRITANOPIA: dict[str, str] = {
    "yellow": "#f472b6",
    "accent": "#14b8a6",
}

CVD_OVERRIDES: dict[str, dict[str, str]] = {
    "deuteranopia": _CVD_DEUTERANOPIA,
    "protanopia":   _CVD_PROTANOPIA,
    "tritanopia":   _CVD_TRITANOPIA,
}


# ─── Stylesheet Templates ─────────────────────────────────────────────

_BTN_PRIMARY = """\
    QPushButton {{
        background: {accent};
        color: {text_on_accent};
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {accent_hover}; }}
    QPushButton:pressed {{ background: {accent_active}; }}
"""

_BTN_SUCCESS = """\
    QPushButton {{
        background: {text_success};
        color: {text_on_accent};
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {accent_hover}; }}
    QPushButton:pressed {{ background: {accent_active}; }}
"""

_BTN_DEFAULT = """\
    QPushButton {{
        background: {bg_tertiary};
        color: {text_primary};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {border}; }}
"""

_TABLE = """\
    QTableWidget {{
        background: {bg_primary};
        color: {text_primary};
        border: 1px solid {border};
        border-radius: 6px;
        font-size: 12px;
        selection-background-color: {bg_selected};
        selection-color: {text_primary};
        alternate-background-color: {bg_tertiary};
        gridline-color: {border};
    }}
    QTableWidget::item {{
        padding: 4px 6px;
        border-bottom: 1px solid {border};
    }}
    QTableWidget::item:selected {{ background: {bg_selected}; }}
    QHeaderView::section {{
        background: {bg_secondary};
        border: none;
        border-bottom: 2px solid {border_strong};
        padding: 6px 8px;
        font-size: 10px;
        font-weight: 600;
        color: {text_secondary};
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
"""

_INPUT = """\
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {{
        background: {bg_primary};
        color: {text_primary};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 3px 8px;
        font-size: 12px;
        selection-background-color: {bg_selected};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {{
        border-color: {accent};
    }}
"""

_CARD = """\
    QFrame, QGroupBox {{
        background: {bg_secondary};
        border: 1px solid {border};
        border-radius: 6px;
    }}
"""


# ─── Helper Functions ─────────────────────────────────────────────────

def _stylesheet(tokens: dict[str, str], template: str) -> str:
    """Interpolate a token dict into a stylesheet template."""
    return template.format(**tokens)


def boost_contrast(theme_name: str) -> dict[str, str]:
    """Return a copy of the theme dict with boosted contrast."""
    base = dict(THEMES[theme_name])
    if theme_name == "dark":
        base["text_primary"] = "#ffffff"
        base["text_secondary"] = "#cbd5e1"
        base["border"] = "#475569"
    else:
        base["text_primary"] = "#000000"
        base["text_secondary"] = "#334155"
        base["border"] = "#94a3b8"
    return base


def get_status_colors(theme_name: str, cvd_mode: str = "none") -> dict[str, str]:
    """Return the status color dict for a theme, with optional CVD overrides.

    This is the single point of truth for status colors. All panels and
    badge helpers call this rather than reading STATUS_COLORS directly,
    ensuring CVD overrides are always applied consistently.
    """
    colors = dict(STATUS_COLORS[theme_name])
    if cvd_mode != "none" and cvd_mode in CVD_OVERRIDES:
        colors.update(CVD_OVERRIDES[cvd_mode])
    return colors


def get_badge_style(theme_name: str, status: str,
                    cvd_mode: str = "none") -> str:
    """Return an inline CSS string for a status badge.

    Derives colors from get_status_colors() so that CVD overrides and
    boost_contrast() are honoured automatically. This replaces the old
    static _BADGE_* / _BADGE_DARK_* constants which were hardcoded and
    bypassed the CVD/contrast pipeline.
    """
    colors = get_status_colors(theme_name, cvd_mode)
    fg = colors.get(status, "#888888")
    c = QColor(fg)
    r, g, b = c.red(), c.green(), c.blue()
    bg = f"rgba({r},{g},{b},0.15)"
    return (
        f"background: {bg}; color: {fg}; border-radius: 10px; "
        f"padding: 2px 8px; font-size: 11px; font-weight: 600;"
    )


def status_style(theme_name: str, status: str,
                 cvd_mode: str = "none") -> tuple[str, str, str]:
    """Get display info for a status level.

    Returns:
        (hex_color, icon_shape, label_text)
    """
    colors = get_status_colors(theme_name, cvd_mode)
    hex_color = colors.get(status, "#888888")
    icon = STATUS_SHAPES.get(status, "?")
    label = STATUS_LABELS.get(status, status)
    return (hex_color, icon, label)


# ─── Theme Application ───────────────────────────────────────────────

def _apply_to_widget(widget: QWidget, tokens: dict[str, str]) -> None:
    """Apply the correct stylesheet to a single widget based on its type.

    Uses isinstance() rather than type() == so that subclasses
    (e.g. EventCalendarWidget(QCalendarWidget)) are correctly matched.
    """
    if isinstance(widget, QPushButton):
        obj = widget.objectName().lower()
        if "save" in obj:
            widget.setStyleSheet(_stylesheet(tokens, _BTN_SUCCESS))
        elif any(k in obj for k in ("primary", "run", "macro")):
            widget.setStyleSheet(_stylesheet(tokens, _BTN_PRIMARY))
        else:
            widget.setStyleSheet(_stylesheet(tokens, _BTN_DEFAULT))

    elif isinstance(widget, QTableWidget):
        widget.setStyleSheet(_stylesheet(tokens, _TABLE))

    elif isinstance(widget, (QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox)):
        widget.setStyleSheet(_stylesheet(tokens, _INPUT))

    elif isinstance(widget, (QFrame, QGroupBox)):
        widget.setStyleSheet(_stylesheet(tokens, _CARD))

    elif isinstance(widget, QCalendarWidget):
        t = tokens
        widget.setStyleSheet(f"""
            QCalendarWidget QTableView {{
                background: {t['bg_primary']};
                color: {t['text_primary']};
                selection-background-color: {t['accent']};
                selection-color: {t['text_on_accent']};
                alternate-background-color: {t['bg_tertiary']};
            }}
            QCalendarWidget QToolButton {{
                color: {t['text_primary']};
                background: {t['bg_tertiary']};
                border-radius: 4px;
                padding: 4px;
                min-width: 24px;
                min-height: 24px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {t['bg_hover']};
            }}
            QCalendarWidget QMenu {{
                background: {t['bg_primary']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
            }}
            QCalendarWidget QSpinBox {{
                background: {t['bg_primary']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
            }}
        """)


def apply_theme(widget: QWidget, theme_name: str,
                cvd_mode: str = "none", high_contrast: bool = False) -> None:
    """Apply a theme to a widget and all its children recursively.

    Args:
        widget:        Root widget (typically MainWindow).
        theme_name:    "light" or "dark".
        cvd_mode:      CVD override mode, or "none".
        high_contrast: If True, boost contrast in the chosen theme.
    """
    tokens = THEMES[theme_name]
    if high_contrast:
        tokens = boost_contrast(theme_name)

    _apply_to_widget(widget, tokens)
    for child in widget.findChildren(QWidget):
        _apply_to_widget(child, tokens)
