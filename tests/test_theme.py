"""
tests/test_theme.py — Tests for gui/theme.py

Covers: palette completeness, CVD overrides, status_style(), 
get_badge_style(), boost_contrast(), init_labels(), apply_theme().
"""

from __future__ import annotations

import pytest

from gui.theme import (
    THEMES, STATUS_COLORS, STATUS_SHAPES, STATUS_LABELS,
    CVD_OVERRIDES, init_labels, get_status_colors, get_badge_style,
    status_style, boost_contrast, apply_theme, _apply_to_widget,
)

# ── Palette completeness ──

class TestPalettes:
    def test_light_theme_has_all_tokens(self):
        required = [
            "bg_primary", "bg_secondary", "bg_tertiary", "bg_hover",
            "bg_selected", "text_primary", "text_secondary", "text_muted",
            "text_on_accent", "text_error", "text_success",
            "border", "border_strong",
            "accent", "accent_hover", "accent_active",
        ]
        for key in required:
            assert key in THEMES["light"], f"Missing light token: {key}"

    def test_dark_theme_has_all_tokens(self):
        required = [
            "bg_primary", "bg_secondary", "bg_tertiary", "bg_hover",
            "bg_selected", "text_primary", "text_secondary", "text_muted",
            "text_on_accent", "text_error", "text_success",
            "border", "border_strong",
            "accent", "accent_hover", "accent_active",
        ]
        for key in required:
            assert key in THEMES["dark"], f"Missing dark token: {key}"

    def test_both_themes_have_same_keys(self):
        assert set(THEMES["light"].keys()) == set(THEMES["dark"].keys())

    def test_status_colors_both_themes(self):
        for theme in ("light", "dark"):
            for status in ("gray", "yellow", "purple", "orange", "green", "red"):
                assert status in STATUS_COLORS[theme], f"Missing {status} in {theme}"

    def test_status_shapes_complete(self):
        for status in ("gray", "yellow", "purple", "orange", "green", "red"):
            assert status in STATUS_SHAPES

    def test_status_labels_complete(self):
        for status in ("gray", "yellow", "purple", "orange", "green", "red"):
            assert status in STATUS_LABELS


# ── init_labels ──

class TestInitLabels:
    def test_init_labels_defaults_preserved(self):
        """STATUS_LABELS starts with sensible defaults."""
        assert STATUS_LABELS["red"] == "Overdue"
        assert STATUS_LABELS["green"] == "Released"

    def test_init_labels_overrides(self):
        init_labels({"red": "LATE", "green": "DONE"})
        assert STATUS_LABELS["red"] == "LATE"
        assert STATUS_LABELS["green"] == "DONE"
        # Restore defaults
        init_labels({"red": "Overdue", "green": "Released"})

    def test_init_labels_empty_dict_is_noop(self):
        before = dict(STATUS_LABELS)
        init_labels({})
        assert STATUS_LABELS == before


# ── CVD overrides ──

class TestCVD:
    def test_deuteranopia_changes_red_and_green(self):
        colors = get_status_colors("light", "deuteranopia")
        assert colors["red"] == "#3b82f6"     # blue
        assert colors["green"] == "#14b8a6"   # teal
        # Unchanged
        assert colors["yellow"] == STATUS_COLORS["light"]["yellow"]

    def test_protanopia_changes_red_and_green(self):
        colors = get_status_colors("light", "protanopia")
        assert colors["red"] == "#6366f1"     # indigo
        assert colors["green"] == "#f59e0b"   # amber

    def test_tritanopia_changes_yellow_and_accent(self):
        colors = get_status_colors("dark", "tritanopia")
        assert colors["yellow"] == "#f472b6"  # pink

    def test_cvd_none_is_passthrough(self):
        colors = get_status_colors("light", "none")
        assert colors == STATUS_COLORS["light"]

    def test_cvd_mode_different_from_none(self):
        """status_style returns different hex for CVD mode vs none."""
        hex_normal, _, _ = status_style("light", "red", "none")
        hex_cvd, _, _ = status_style("light", "red", "deuteranopia")
        assert hex_normal != hex_cvd


# ── status_style ──

class TestStatusStyle:
    def test_returns_tuple_of_3(self):
        result = status_style("light", "red")
        assert len(result) == 3
        hex_color, icon, label = result
        assert isinstance(hex_color, str)
        assert isinstance(icon, str)
        assert isinstance(label, str)

    def test_all_statuses_both_themes(self):
        for theme in ("light", "dark"):
            for status in ("gray", "yellow", "purple", "orange", "green", "red"):
                hex_color, icon, label = status_style(theme, status)
                assert hex_color.startswith("#")
                assert len(hex_color) == 7
                assert icon == STATUS_SHAPES[status]
                assert label == STATUS_LABELS[status]


# ── get_badge_style ──

class TestBadgeStyle:
    def test_returns_css_string(self):
        css = get_badge_style("light", "red")
        assert "background:" in css
        assert "color:" in css
        assert "border-radius: 10px" in css

    def test_badge_style_different_for_cvd(self):
        """Badge style should differ between CVD modes (not hardcoded hex)."""
        normal = get_badge_style("light", "red", "none")
        cvd = get_badge_style("light", "red", "deuteranopia")
        assert normal != cvd

    def test_badge_style_both_themes(self):
        for theme in ("light", "dark"):
            for status in ("gray", "yellow", "green"):
                css = get_badge_style(theme, status)
                assert "rgba(" in css


# ── boost_contrast ──

class TestBoostContrast:
    def test_light_boost_changes_text_primary(self):
        boosted = boost_contrast("light")
        assert boosted["text_primary"] == "#000000"
        assert boosted["text_secondary"] == "#334155"

    def test_dark_boost_changes_text_primary(self):
        boosted = boost_contrast("dark")
        assert boosted["text_primary"] == "#ffffff"
        assert boosted["text_secondary"] == "#cbd5e1"

    def test_boost_preserves_other_tokens(self):
        boosted = boost_contrast("light")
        assert boosted["bg_primary"] == THEMES["light"]["bg_primary"]
        assert boosted["accent"] == THEMES["light"]["accent"]


# ── apply_theme ──

class TestApplyTheme:
    def test_apply_does_not_raise(self):
        from PyQt5.QtWidgets import QWidget, QPushButton, QTableWidget
        w = QWidget()
        QPushButton("test", w)
        QTableWidget(w)
        apply_theme(w, "dark")
        apply_theme(w, "light")

    def test_subclass_widget_is_themed(self):
        """isinstance() check should theme EventCalendarWidget (subclass)."""
        from PyQt5.QtWidgets import QCalendarWidget
        cal = QCalendarWidget()
        apply_theme(cal, "dark")
        assert cal.styleSheet() != ""
