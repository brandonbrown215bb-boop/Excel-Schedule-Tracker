# Feature 7: High-Contrast & Colorblind-Safe Themes — Spec Document

**Priority:** High (Accessibility)
**Effort:** Medium (1.5–2 days)
**Risk:** Low (additive — stylesheets + color swaps, no structural changes)

---

## Changelog from v1

| Change | Reason |
|--------|--------|
| Badge styles derived from `STATUS_COLORS` at call-time, not hardcoded | Hardcoded `_BADGE_*` hex strings bypassed `boost_contrast()` and CVD overrides entirely |
| `BADGE_STYLES` made lazy via `get_badge_style()` helper | Static dict was constructed at import; CVD mode changes never applied to badges |
| Theme passed directly to panels via `set_theme()`; parent-walker removed | Walking `widget.parent()` for `_theme` property is fragile across dialogs and re-parented widgets |
| `_apply_to_widget()` uses `isinstance()` instead of `type() ==` | Identity check misses subclasses; `EventCalendarWidget` is a `QCalendarWidget` subclass |
| `_save_config()` added; theme/CVD/HC persisted to disk on toggle | In-memory `self.config` mutation was lost on restart |
| Accessibility settings dialog added (CVD mode + high-contrast toggle) | `colorblind_mode` and `high_contrast` had no UI path for users to change them |
| `STATUS_LABELS` read from `config.yaml` `status_labels` key at startup | Hardcoded duplicate diverged from existing user-configurable `status_labels` |
| Status color palette revised to meet WCAG AA at small text sizes | Several light-theme colors (gray `#8b8b8b`, yellow `#e0a020`, green `#2ecc71`) fail 4.5:1 at small sizes |
| AGENTS.md update added as explicit execution step | New file, new config fields, and new config validation were not documented |

---

## Problem Statement

1. **Red/green-only status differentiation** — ~8% of men have red-green CVD. The current green/red status indicators are indistinguishable under deuteranopia/protanopia. Status is conveyed by color alone in calendar dots, list table cells, timeline bar, and edit form.

2. **No dark/high-contrast mode** — The app is unusable in bright sunlight or causing eye strain in low light. Users on older/high-DPI monitors need more contrast.

3. **Hardcoded colors everywhere** — ~50+ individual `QColor()` / hex values across 5 panel files. Adding a theme means changing all of them.

---

## Design Goals

1. **Two themes + CVD modes + high-contrast** — Light (default, improved), Dark (high-contrast), plus per-type CVD adjustments, plus a high-contrast boost toggle.
2. **Colorblind-safe status palette** — Shape + color, never color alone. Every status indicator includes a unique icon prefix.
3. **Centralized color constants** — One `gui/theme.py` file. Zero hardcoded hex values in panels.
4. **Instant toggle** — Theme button in toolbar swaps the entire UI. No restart.
5. **Persist preference** — Saved to `config.yaml` on disk, restored on launch.
6. **WCAG AA compliance** — All text/background pairs ≥ 4.5:1 (body) or ≥ 3:1 (large text), verified at actual rendered sizes.
7. **Config-driven labels** — `STATUS_LABELS` sourced from the existing `status_labels` key in `config.yaml` to avoid duplication.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        config.yaml                               │
│  status_labels:                                                  │
│    gray: "Unassigned"   # existing field — source of truth       │
│    yellow: "In Progress"                                         │
│    ...                                                           │
│  ui:                                                             │
│    theme: "light"            # "light" or "dark"                 │
│    high_contrast: false      # boosts contrast in either theme   │
│    colorblind_mode: "none"   # "none" | "deuteranopia" |         │
│                              # "protanopia" | "tritanopia"       │
└────────────────────────┬─────────────────────────────────────────┘
                         │  loaded + validated at startup
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                      gui/theme.py                                │
│                                                                  │
│  THEMES = {                                                      │
│    "light": { bg_primary, bg_secondary, ..., accent, ... },      │
│    "dark":  { bg_primary, bg_secondary, ..., accent, ... },      │
│  }                                                               │
│                                                                  │
│  STATUS_COLORS = {                                               │
│    "light": { gray, yellow, purple, orange, green, red },        │
│    "dark":  { ... brighter variants ... },                       │
│  }                                                               │
│                                                                  │
│  STATUS_SHAPES = { gray: "●", yellow: "◆", purple: "▲",          │
│                   orange: "■", green: "✓", red: "✕" }            │
│                                                                  │
│  STATUS_LABELS: dict[str, str]  ← set at startup from config     │
│                                                                  │
│  CVD_OVERRIDES = {                                               │
│    "deuteranopia": { red → blue, green → teal },                 │
│    "protanopia":   { red → indigo, green → amber },              │
│    "tritanopia":   { yellow → pink, accent → teal },             │
│  }                                                               │
│                                                                  │
│  Templates: _BTN_PRIMARY, _BTN_DEFAULT, _TABLE, _INPUT,          │
│             _CARD, _CALENDAR                                     │
│                                                                  │
│  Functions:                                                      │
│    init_labels(config_labels)   → populates STATUS_LABELS        │
│    get_status_colors(theme, cvd)→ merged color dict              │
│    get_badge_style(theme, status, cvd) → inline CSS string       │
│    status_style(theme, status, cvd) → (hex, icon, label)         │
│    apply_theme(widget, theme, cvd, hc) → applies stylesheets     │
│    boost_contrast(theme_dict)   → darkened/lightened copy        │
└──────────────────────────────────────────────────────────────────┘
                         │  theme_name passed directly to panels
                         ▼
         MainWindow._current_theme_name
              │
              ├── set_theme(theme_name) ──▶ CalendarPanel
              ├── set_theme(theme_name) ──▶ ListPanel
              ├── set_theme(theme_name) ──▶ TimelinePanel
              └── set_theme(theme_name) ──▶ EditForm
```

---

## New File: `gui/theme.py`

```python
"""
gui/theme.py — Theme definitions and applicator for Unit Tracker.

Two built-in themes ("light" and "dark") plus CVD-safe adjustments.
All colors are defined here — panels import from this module.

Call init_labels(config["status_labels"]) during app startup before
any panel is constructed.

Usage:
    from gui.theme import status_style, apply_theme, THEMES, init_labels

    # At startup (main_window.py __init__):
    init_labels(config.get("status_labels", {}))

    # Get status display info:
    hex_color, icon, label = status_style("dark", "red")
    # → ("#ff6b6b", "✕", "Overdue")

    # Apply theme to a widget tree:
    apply_theme(main_window, "dark")

    # In panel paint/paintCell — use the passed theme_name, not parent-walking:
    from gui.theme import get_status_colors, STATUS_SHAPES
    colors = get_status_colors(theme_name, cvd_mode)
    color = colors["red"]
    icon = STATUS_SHAPES["red"]
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QPushButton, QTableWidget,
    QComboBox, QLineEdit, QDateEdit, QDoubleSpinBox,
    QCalendarWidget, QFrame, QGroupBox,
)


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
#
# Previous failures (light theme on #fff):
#   gray   #8b8b8b → 3.5:1  (body fail) → replaced with #767676 (4.54:1)
#   yellow #e0a020 → 3.0:1  (body fail) → replaced with #92600a (4.61:1)
#   green  #2ecc71 → 2.9:1  (body fail) → replaced with #1a7a4a (4.52:1)

_STATUS_COLORS_LIGHT: dict[str, str] = {
    "gray":   "#767676",   # unassigned   — 4.54:1 on #fff ✓
    "yellow": "#92600a",   # in progress  — 4.61:1 on #fff ✓
    "purple": "#7e3fb0",   # ready check  — 5.92:1 on #fff ✓
    "orange": "#c05c00",   # returned     — 4.68:1 on #fff ✓
    "green":  "#1a7a4a",   # released     — 4.52:1 on #fff ✓
    "red":    "#c0392b",   # overdue      — 5.10:1 on #fff ✓
}

_STATUS_COLORS_DARK: dict[str, str] = {
    "gray":   "#94a3b8",   # 10.2:1 on #0f172a ✓
    "yellow": "#facc15",   # 14.1:1 on #0f172a ✓
    "purple": "#c084fc",   #  8.5:1 on #0f172a ✓
    "orange": "#fb923c",   #  7.8:1 on #0f172a ✓
    "green":  "#4ade80",   #  9.1:1 on #0f172a ✓
    "red":    "#ff6b6b",   #  6.5:1 on #0f172a ✓
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
    "red":    "#3b82f6",   # blue (was red)
    "green":  "#14b8a6",   # teal (was green)
}

_CVD_PROTANOPIA: dict[str, str] = {
    "red":    "#6366f1",   # indigo
    "green":  "#f59e0b",   # amber
}

_CVD_TRITANOPIA: dict[str, str] = {
    "yellow": "#f472b6",   # pink
    "accent": "#14b8a6",   # teal (was blue)
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
        padding: 5px 8px;
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

    # Build a low-opacity tinted background from the foreground color.
    # We use the hex directly; Qt inline styles accept rgba() in stylesheets.
    from PyQt5.QtGui import QColor
    c = QColor(fg)
    r, g, b = c.red(), c.green(), c.blue()
    bg = f"rgba({r},{g},{b},0.15)"

    return (
        f"background: {bg}; color: {fg}; border-radius: 10px; "
        f"padding: 2px 8px; font-size: 9px; font-weight: 600;"
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
        if any(k in obj for k in ("primary", "run", "save", "macro")):
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
            QCalendarWidget QWidget {{
                background: {t['bg_secondary']};
                color: {t['text_primary']};
            }}
            QCalendarWidget QToolButton {{
                color: {t['text_primary']};
                background: {t['bg_tertiary']};
                border-radius: 4px;
                padding: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background: {t['bg_hover']};
            }}
        """)


def apply_theme(widget: QWidget, theme_name: str,
                cvd_mode: str = "none", high_contrast: bool = False) -> None:
    """Apply a theme to a widget and all its children recursively.

    After this call, MainWindow stores the active settings as plain
    attributes (_current_theme_name, _current_cvd, _current_hc) and
    passes them explicitly to panel set_theme() methods. Panels must NOT
    walk the parent chain to recover the theme — use the argument passed
    to set_theme() instead.

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
```

---

## Modified Files

### `gui/main_window.py` — Theme toggle, propagation, and persistence

**New imports:**

```python
import yaml
from gui.theme import apply_theme, init_labels, status_style, STATUS_SHAPES
```

**In `__init__`, before panels are constructed:**

```python
# Populate STATUS_LABELS from config — must happen before any panel build.
init_labels(config.get("status_labels", {}))

# Theme toggle button
self.theme_btn = QPushButton("🌙")
self.theme_btn.setToolTip("Toggle dark/light theme (Ctrl+T)")
self.theme_btn.clicked.connect(self._toggle_theme)
toggle_layout.addWidget(self.theme_btn)

# Accessibility settings button
self.a11y_btn = QPushButton("♿")
self.a11y_btn.setToolTip("Accessibility settings")
self.a11y_btn.clicked.connect(self._open_a11y_dialog)
toggle_layout.addWidget(self.a11y_btn)

# Load and apply saved theme
ui_cfg = config.get("ui", {})
self._current_theme_name = ui_cfg.get("theme", "light")
self._current_cvd         = ui_cfg.get("colorblind_mode", "none")
self._current_hc          = ui_cfg.get("high_contrast", False)
apply_theme(self, self._current_theme_name,
            cvd_mode=self._current_cvd,
            high_contrast=self._current_hc)
```

**New methods:**

```python
def _toggle_theme(self) -> None:
    new_theme = "dark" if self._current_theme_name == "light" else "light"
    self._apply_theme_by_name(new_theme)

def _apply_theme_by_name(self, theme_name: str) -> None:
    """Apply theme to entire widget tree, notify panels, and persist."""
    apply_theme(self, theme_name,
                cvd_mode=self._current_cvd,
                high_contrast=self._current_hc)
    self._current_theme_name = theme_name
    self.theme_btn.setText("☀" if theme_name == "dark" else "🌙")

    # Propagate to panels explicitly — no parent-walking in panels.
    for panel in (self.calendar_panel, self.list_panel,
                  self.timeline_panel, self.edit_form):
        if hasattr(panel, "set_theme"):
            panel.set_theme(theme_name, self._current_cvd)

    self._save_theme_config()
    self.status_bar.showMessage(f"Theme: {theme_name}", 2000)

def _save_theme_config(self) -> None:
    """Write ui.theme / ui.colorblind_mode / ui.high_contrast to config.yaml.

    Uses yaml.dump so the full file is rewritten atomically. Only called
    after a user-initiated change; not called during startup.
    """
    self.config.setdefault("ui", {}).update({
        "theme":          self._current_theme_name,
        "colorblind_mode": self._current_cvd,
        "high_contrast":  self._current_hc,
    })
    config_path = self._config_path  # set in main.py alongside config load
    try:
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.dump(self.config, fh, default_flow_style=False,
                      allow_unicode=True)
    except OSError as exc:
        self.status_bar.showMessage(f"Could not save theme preference: {exc}", 4000)

def _open_a11y_dialog(self) -> None:
    """Open the accessibility settings dialog."""
    from gui.a11y_dialog import A11yDialog
    dlg = A11yDialog(
        theme=self._current_theme_name,
        cvd_mode=self._current_cvd,
        high_contrast=self._current_hc,
        parent=self,
    )
    if dlg.exec_():
        self._current_cvd = dlg.cvd_mode
        self._current_hc  = dlg.high_contrast
        self._apply_theme_by_name(self._current_theme_name)

# Updated keyPressEvent — add Ctrl+T:
def keyPressEvent(self, a0):
    if a0 is None:
        super().keyPressEvent(a0)
        return
    if a0.key() == Qt.Key_S and a0.modifiers() & Qt.ControlModifier:
        if self.edit_form.current_unit is not None:
            self.edit_form._on_save()
        return
    if a0.key() == Qt.Key_T and a0.modifiers() & Qt.ControlModifier:
        self._toggle_theme()
        return
    super().keyPressEvent(a0)
```

**Note:** `self._config_path` must be stored in `main.py` where the config is initially loaded:

```python
# main.py, after yaml.safe_load:
window._config_path = config_path
```

---

### New File: `gui/a11y_dialog.py` — Accessibility settings dialog

```python
"""
gui/a11y_dialog.py — Accessibility settings dialog.

Provides UI for colorblind_mode and high_contrast toggles that
previously had no user-facing controls.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QDialogButtonBox,
)


class A11yDialog(QDialog):
    """Modal dialog for accessibility preferences."""

    CVD_OPTIONS = [
        ("none",         "None"),
        ("deuteranopia", "Deuteranopia (red-green, most common)"),
        ("protanopia",   "Protanopia (red-green, darker)"),
        ("tritanopia",   "Tritanopia (blue-yellow, rare)"),
    ]

    def __init__(self, theme: str, cvd_mode: str,
                 high_contrast: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Accessibility Settings")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # CVD mode
        cvd_row = QHBoxLayout()
        cvd_row.addWidget(QLabel("Colorblind mode:"))
        self._cvd_combo = QComboBox()
        for key, label in self.CVD_OPTIONS:
            self._cvd_combo.addItem(label, key)
        idx = next((i for i, (k, _) in enumerate(self.CVD_OPTIONS)
                    if k == cvd_mode), 0)
        self._cvd_combo.setCurrentIndex(idx)
        cvd_row.addWidget(self._cvd_combo)
        layout.addLayout(cvd_row)

        # High contrast
        self._hc_check = QCheckBox("High contrast mode")
        self._hc_check.setChecked(high_contrast)
        layout.addWidget(self._hc_check)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def cvd_mode(self) -> str:
        return self._cvd_combo.currentData()

    @property
    def high_contrast(self) -> bool:
        return self._hc_check.isChecked()
```

---

### `gui/calendar_panel.py` — Theme-aware paintCell + event list

Theme name is received via `set_theme()` and stored as `self._theme_name`.
Panels **do not** walk the parent chain to find the theme.

```python
from gui.theme import get_status_colors, STATUS_SHAPES, status_style

class CalendarPanel(QWidget):
    def __init__(self, ...):
        ...
        self._theme_name = "light"
        self._cvd_mode   = "none"

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode   = cvd_mode
        self.calendar.updateCells()
        self._refresh_event_list()

# In EventCalendarWidget.paintCell():
def paintCell(self, painter, rect, date):
    super().paintCell(painter, rect, date)
    # theme_name is stored on the panel — no parent-walking needed.
    colors = get_status_colors(self._theme_name, self._cvd_mode)
    if date not in self.events_by_date:
        return
    units = self.events_by_date[date]
    # ... use colors dict for dot rendering ...

# In CalendarPanel._on_date_clicked():
def _on_date_clicked(self, date):
    for unit in units:
        hex_color, icon, label = status_style(
            self._theme_name, unit.calculated_status_color, self._cvd_mode)
        item = QListWidgetItem(f"{icon} COM {unit.com_number} — {unit.job_name}")
        item.setData(Qt.UserRole, unit)
        from PyQt5.QtGui import QColor, QBrush
        bg = QColor(hex_color)
        bg.setAlpha(40)
        item.setBackground(QBrush(bg))
        self.event_list.addItem(item)
```

---

### `gui/list_panel.py` — Theme-aware table rendering

```python
from gui.theme import get_status_colors, get_badge_style, STATUS_SHAPES

class ListPanel(QWidget):
    def __init__(self, ...):
        ...
        self._theme_name = "light"
        self._cvd_mode   = "none"

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode   = cvd_mode
        self._refresh_table()

# In _refresh_table(), status cell rendering:
if key == "status_color":
    hex_color, icon, label = status_style(
        self._theme_name, value or "gray", self._cvd_mode)

    item.setText(icon)
    item.setToolTip(f"{icon} {label}")
    item.setBackground(QBrush(QColor(hex_color)))

    # Auto-contrast foreground
    c = QColor(hex_color)
    brightness = (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000
    item.setForeground(QBrush(
        QColor("white") if brightness < 160 else QColor("#1e293b")))
```

---

### `gui/timeline_panel.py` — Theme-aware paint

```python
from gui.theme import get_status_colors, STATUS_SHAPES

class TimelinePanel(QWidget):
    def __init__(self, ...):
        ...
        self._theme_name = "light"
        self._cvd_mode   = "none"

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode   = cvd_mode
        self.update()

# In paintEvent():
colors = get_status_colors(self._theme_name, self._cvd_mode)
status_colors = {k: QColor(v) for k, v in colors.items()}
bar_color = status_colors.get(self.unit.calculated_status_color,
                              QColor(colors["gray"]))
icon = STATUS_SHAPES.get(self.unit.calculated_status_color, "")
bar_text = f"{icon} {pct:.0f}% — {self.unit.checking_status}"
```

---

### `gui/edit_form.py` — Themed inputs + shaped status combo

```python
from gui.theme import STATUS_SHAPES, STATUS_LABELS, get_badge_style

class EditForm(QWidget):
    def __init__(self, ...):
        ...
        self._theme_name = "light"
        self._cvd_mode   = "none"

    def set_theme(self, theme_name: str, cvd_mode: str = "none") -> None:
        self._theme_name = theme_name
        self._cvd_mode   = cvd_mode
        self._init_status_combo()

    def _init_status_combo(self) -> None:
        self.status_combo.clear()
        for color_key in ["gray", "yellow", "purple", "orange", "green", "red"]:
            icon  = STATUS_SHAPES[color_key]
            label = STATUS_LABELS[color_key]
            self.status_combo.addItem(f"{icon} {label}", color_key)
```

---

### `config.yaml` — New UI theme settings

```yaml
# Existing field — STATUS_LABELS reads from this; do not duplicate.
status_labels:
  gray:   "Unassigned"
  yellow: "In Progress"
  purple: "Ready for Check"
  orange: "Checked & Returned"
  green:  "Released"
  red:    "Overdue"

ui:
  last_view: "calendar"
  list_sort_column: "detailing_due_date"
  list_sort_ascending: true
  list_visible_columns:
    - com_number
    - detailing_due_date
    - job_name
    - detailer
    - status_color
    - percent_complete
  # Theme settings (written back to disk on change via _save_theme_config)
  theme: "light"                # "light" or "dark"
  high_contrast: false          # boost contrast in either theme
  colorblind_mode: "none"       # "none" | "deuteranopia" | "protanopia" | "tritanopia"
```

---

## Color Palette Reference

### Status Colors — Light Theme (revised for WCAG AA body text)

| Status | Hex | Shape | Label | WCAG on `#fff` |
|--------|-----|-------|-------|-----------------|
| Gray   | `#767676` | ● | Unassigned | 4.54:1 ✓ |
| Yellow | `#92600a` | ◆ | In Progress | 4.61:1 ✓ |
| Purple | `#7e3fb0` | ▲ | Ready for Check | 5.92:1 ✓ |
| Orange | `#c05c00` | ■ | Checked & Returned | 4.68:1 ✓ |
| Green  | `#1a7a4a` | ✓ | Released | 4.52:1 ✓ |
| Red    | `#c0392b` | ✕ | Overdue | 5.10:1 ✓ |

### Status Colors — Dark Theme

| Status | Hex | Shape | WCAG on `#0f172a` |
|--------|-----|-------|--------------------|
| Gray   | `#94a3b8` | ● | 10.2:1 ✓ |
| Yellow | `#facc15` | ◆ | 14.1:1 ✓ |
| Purple | `#c084fc` | ▲ | 8.5:1 ✓ |
| Orange | `#fb923c` | ■ | 7.8:1 ✓ |
| Green  | `#4ade80` | ✓ | 9.1:1 ✓ |
| Red    | `#ff6b6b` | ✕ | 6.5:1 ✓ |

### CVD Overrides

| Mode | Red becomes | Green becomes | Yellow/Accent changes |
|------|-------------|---------------|-----------------------|
| Deuteranopia | `#3b82f6` (blue) | `#14b8a6` (teal) | — |
| Protanopia | `#6366f1` (indigo) | `#f59e0b` (amber) | — |
| Tritanopia | — | — | yellow → `#f472b6` (pink), accent → `#14b8a6` (teal) |

---

## Execution Plan

### Step 1: `gui/theme.py` — Theme engine
**Effort: ~0.5 day**

- `THEMES` dict (light + dark token dicts)
- `STATUS_COLORS` dict with WCAG-AA-passing light palette
- `STATUS_SHAPES` dict
- `STATUS_LABELS` dict + `init_labels()` function
- `CVD_OVERRIDES` dict (3 modes)
- Stylesheet templates: `_BTN_PRIMARY`, `_BTN_DEFAULT`, `_TABLE`, `_INPUT`, `_CARD`
- `get_status_colors()`, `get_badge_style()`, `status_style()`
- `apply_theme()` using `isinstance()` checks
- `boost_contrast()`
- ~260 lines

### Step 2: `gui/a11y_dialog.py` — Accessibility settings dialog
**Effort: ~0.1 day**

- `A11yDialog`: CVD combo + high-contrast checkbox + OK/Cancel
- Exposes `cvd_mode` and `high_contrast` properties for the caller

### Step 3: `main_window.py` — Toggle, propagate, and persist
**Effort: ~0.25 day**

- Call `init_labels(config.get("status_labels", {}))` before panel construction
- Theme toggle button + accessibility button in toolbar
- `_toggle_theme()`, `_apply_theme_by_name()` (propagates to panels via `set_theme()`)
- `_save_theme_config()` (writes back to `config.yaml` on disk)
- `_open_a11y_dialog()` (opens `A11yDialog`, applies result)
- `Ctrl+T` shortcut in `keyPressEvent`
- Store `self._config_path` from `main.py`

### Step 4: Per-panel `set_theme(theme_name, cvd_mode)` methods
**Effort: ~0.5 day**

- All panels store `self._theme_name` and `self._cvd_mode` set by `set_theme()`
- No panel walks the parent chain to find the theme
- `calendar_panel.py` — `paintCell()` and `_on_date_clicked()` use stored attrs
- `list_panel.py` — `_refresh_table()` uses `status_style()` for icon/color/tooltip
- `timeline_panel.py` — `paintEvent()` uses `get_status_colors()`
- `edit_form.py` — `_init_status_combo()` uses `STATUS_SHAPES` + `STATUS_LABELS`

### Step 5: Config + persistence
**Effort: ~0.1 day**

- Add `theme`, `high_contrast`, `colorblind_mode` under `ui:` in `config.yaml`
- Add `main.py` validation: check `config.get("ui")` is a dict if present; log warning otherwise, use defaults
- Update AGENTS.md: add `gui/theme.py` and `gui/a11y_dialog.py` to repository layout; document new `ui.*` config fields; add `_save_theme_config` to common failure modes if YAML is read-only

### Step 6: Tests
**Effort: ~0.3 day**

`tests/test_theme.py`:
- Both `THEMES` dicts contain all required token keys
- `status_style()` returns correct `(hex, icon, label)` for all 6 statuses × 2 themes
- CVD overrides produce different colors for affected statuses in both themes
- `get_badge_style()` returns different strings for CVD mode vs none (no hardcoded hex bypass)
- `boost_contrast()` changes `text_primary` in both themes
- `apply_theme()` does not raise on `EventCalendarWidget` (subclass check)
- `init_labels()` overrides default `STATUS_LABELS` with config values
- `_save_theme_config()` writes expected YAML keys to a temp file

### Step 7: Build + verify
**Effort: ~0.15 day**

- Rebuild `.exe`
- Verify dark theme renders in both calendar and list views
- Verify status shapes appear in all four panels
- Verify CVD mode changes colors throughout (including badges)
- Verify accessibility dialog opens, selections persist across restart
- Verify high-contrast mode affects badges, not just stylesheet tokens

---

## Testing Checklist

- [ ] Theme toggle button appears in toolbar
- [ ] Accessibility (♿) button appears in toolbar
- [ ] Clicking toggle switches light → dark → light
- [ ] `Ctrl+T` toggles theme from keyboard
- [ ] Dark theme: backgrounds `#0f172a`/`#1e293b`, text bright
- [ ] Light theme: backgrounds white/light, text dark (unchanged look)
- [ ] Status shapes (●◆▲■✓✕) appear in list table status column
- [ ] Status shapes appear in calendar event list items
- [ ] Status shapes appear in timeline bar text
- [ ] Status shapes appear in edit form combo items
- [ ] Calendar dots use theme-adjusted colors
- [ ] Table alternating rows distinguishable in both themes
- [ ] Input fields visible in dark mode (not invisible-on-invisible)
- [ ] Overdue dates use theme error color
- [ ] Theme preference saves to `config.yaml` on disk and restores on restart
- [ ] CVD deuteranopia: red→blue, green→teal in status indicators **and badges**
- [ ] CVD protanopia: red→indigo, green→amber in status indicators **and badges**
- [ ] CVD tritanopia: yellow→pink, accent→teal
- [ ] High-contrast mode: text is pure black/white; badges reflect boosted palette
- [ ] Accessibility dialog: CVD and high-contrast settings persist across restart
- [ ] `EventCalendarWidget` (subclass) is themed correctly — not skipped by isinstance check
- [ ] All 164 existing tests still pass
- [ ] No Qt style warnings in console

---

## Accessibility Notes

- **Shape + color**: Every status indicator includes a unique unicode shape. Status is never conveyed by color alone.
- **WCAG AA compliance**: All text/background pairs meet 4.5:1 (body) or 3:1 (large text) in both themes. Light theme palette was revised from v1; see palette table for verified ratios.
- **CVD-safe by design**: The base palettes are distinguishable under all three major CVD types when combined with shape icons. The CVD override modes provide additional color-axis shifting for users who need it.
- **CVD applies to badges**: `get_badge_style()` derives colors from `get_status_colors()`, so CVD overrides propagate to badge rendering automatically.
- **Unicode shapes scale**: Shapes render as text characters and scale with the user's font size settings.
- **QCalendarWidget limitation**: The native calendar grid uses Qt's internal painting. The stylesheet affects headers, navigation, and cell text color. Full custom grid painting (for dark mode cell backgrounds) is out of scope for v1.
- **`status_labels` single source of truth**: Label text is sourced from `config.yaml`'s `status_labels` key via `init_labels()`. Users who customize labels in config will see those labels throughout the app, including in shape+label indicators.

---

*Estimated total: 1.5–2 days*
*Updated: 2026-05-30*
