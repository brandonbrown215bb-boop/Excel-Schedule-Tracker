# tests/test_loader.py
"""Tests for data/loader.py — COLUMN_MAP, parse_date, parse_float, caching."""

from __future__ import annotations

import csv
import os
import pickle
import time
from datetime import date, datetime

from data.loader import (
    COLUMN_MAP,
    _cache_is_fresh,
    _cache_path,
    _csv_cache_path,
    _date_to_str,
    _save_csv_cache,
    _save_pickle_cache,
    parse_date,
    parse_float,
    save_csv_cache,
)

# ── COLUMN_MAP ────────────────────────────────────────────────────


class TestColumnMap:
    def test_all_expected_fields_present(self):
        expected = {
            "detailing_due_date",
            "dept_due_date_previous",
            "com_number",
            "detailer",
            "job_name",
            "contract_number",
            "description",
            "build_date",
            "department_hours",
            "percent_complete",
            "actual_hours",
            "checking_status",
            "target_department_hours",
            "iec_internal_hours",
            "unit_detailing_start_date",
            "unit_moved_to_checking_date",
            "unit_detailing_completion_date",
        }
        assert set(COLUMN_MAP.keys()) == expected

    def test_all_values_are_column_letters(self):
        for field, col in COLUMN_MAP.items():
            assert len(col) == 1, f"{field}: expected single letter, got {col!r}"
            assert col.isalpha(), f"{field}: expected letter, got {col!r}"
            assert col.isupper(), f"{field}: expected uppercase, got {col!r}"

    def test_com_number_is_column_c(self):
        assert COLUMN_MAP["com_number"] == "C"

    def test_detailer_is_column_e(self):
        assert COLUMN_MAP["detailer"] == "E"


# ── parse_date ────────────────────────────────────────────────────


class TestParseDate:
    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_date_object(self):
        d = date(2025, 6, 15)
        assert parse_date(d) == d

    def test_datetime_object(self):
        dt = datetime(2025, 6, 15, 10, 30, 0)
        assert parse_date(dt) == date(2025, 6, 15)

    def test_string_slash_format(self):
        assert parse_date("06/15/2025") == date(2025, 6, 15)

    def test_string_iso_format(self):
        assert parse_date("2025-06-15") == date(2025, 6, 15)

    def test_string_dash_short_year(self):
        assert parse_date("06-15-25") == date(2025, 6, 15)

    def test_string_unparseable(self):
        assert parse_date("not a date") is None

    def test_integer_zero(self):
        assert parse_date(0) is None

    def test_small_integer(self):
        """Excel serial date for 1900-01-02 is excluded by bound check (must be > 1)."""
        result = parse_date(1)
        assert result is None

    def test_serial_2(self):
        """Excel serial 2 = valid date."""
        result = parse_date(2)
        assert result is not None

    def test_large_serial_date(self):
        """Excel serial 45000 ≈ 2023-03-27."""
        result = parse_date(45000)
        assert result is not None
        assert isinstance(result, date)

    def test_float_serial_date(self):
        result = parse_date(45000.0)
        assert result is not None
        assert isinstance(result, date)

    def test_string_with_whitespace(self):
        assert parse_date("  06/15/2025  ") == date(2025, 6, 15)


# ── parse_float ───────────────────────────────────────────────────


class TestParseFloat:
    def test_none_returns_zero(self):
        assert parse_float(None) == 0.0

    def test_integer(self):
        assert parse_float(42) == 42.0

    def test_float(self):
        assert parse_float(3.14) == 3.14

    def test_string_number(self):
        assert parse_float("99.5") == 99.5

    def test_string_with_whitespace(self):
        assert parse_float("  10.0  ") == 10.0

    def test_empty_string(self):
        assert parse_float("") == 0.0

    def test_invalid_string(self):
        assert parse_float("abc") == 0.0

    def test_zero(self):
        assert parse_float(0) == 0.0

    def test_zero_float(self):
        assert parse_float(0.0) == 0.0


# ── _date_to_str ─────────────────────────────────────────────────


class TestDateToStr:
    def test_none(self):
        assert _date_to_str(None) == ""

    def test_valid_date(self):
        assert _date_to_str(date(2025, 6, 15)) == "2025-06-15"

    def test_end_of_year(self):
        assert _date_to_str(date(2025, 12, 31)) == "2025-12-31"


# ── cache path helpers ────────────────────────────────────────────


class TestCachePaths:
    def test_pickle_cache_path(self):
        result = _cache_path("/some/path/workbook.xlsx")
        assert result == "/some/path/workbook_cache.pkl"

    def test_csv_cache_path(self):
        result = _csv_cache_path("/some/path/workbook.xlsx")
        assert result == "/some/path/workbook_cache.csv"

    def test_no_extension(self):
        result = _cache_path("/path/file")
        assert result == "/path/file_cache.pkl"


# ── _cache_is_fresh ───────────────────────────────────────────────


class TestCacheIsFresh:
    def test_no_cache_returns_false(self, tmp_path):
        excel_file = tmp_path / "workbook.xlsx"
        excel_file.write_bytes(b"fake")
        assert _cache_is_fresh(str(excel_file)) is False

    def test_fresh_pickle_cache(self, tmp_path):
        excel_file = tmp_path / "workbook.xlsx"
        excel_file.write_bytes(b"excel content")
        time.sleep(0.01)
        cache_file = tmp_path / "workbook_cache.pkl"
        cache_file.write_bytes(pickle.dumps([]))
        assert _cache_is_fresh(str(excel_file)) is True

    def test_stale_pickle_cache(self, tmp_path):
        cache_file = tmp_path / "workbook_cache.pkl"
        cache_file.write_bytes(pickle.dumps([]))
        time.sleep(0.01)
        excel_file = tmp_path / "workbook.xlsx"
        excel_file.write_bytes(b"excel content")
        assert _cache_is_fresh(str(excel_file)) is False


# ── pickle cache save/load ────────────────────────────────────────


class TestPickleCache:
    def test_save_and_reload(self, tmp_path):
        units = ["unit1", "unit2"]
        excel_path = str(tmp_path / "workbook.xlsx")
        # Create a fake Excel file so the path exists for consistency
        (tmp_path / "workbook.xlsx").write_bytes(b"fake")

        _save_pickle_cache(excel_path, units)
        cache_path = _cache_path(excel_path)
        with open(cache_path, "rb") as f:
            loaded = pickle.load(f)
        assert loaded == units

    def test_cache_file_has_pkl_extension(self, tmp_path):
        excel_path = str(tmp_path / "data.xlsx")
        (tmp_path / "data.xlsx").write_bytes(b"fake")
        _save_pickle_cache(excel_path, [])
        assert os.path.exists(str(tmp_path / "data_cache.pkl"))


# ── csv cache save ────────────────────────────────────────────────


class TestCsvCache:
    def test_save_csv_has_all_columns(self, tmp_path):
        from data.models import Unit

        excel_path = str(tmp_path / "workbook.xlsx")
        (tmp_path / "workbook.xlsx").write_bytes(b"fake")

        unit = Unit(
            com_number="C001",
            job_name="J",
            contract_number="CT",
            description="D",
            detailer="DT",
            checking_status="CS",
            unit_detailing_start_date=date(2025, 1, 1),
            detailing_due_date=date(2025, 6, 1),
            build_date=date(2025, 7, 1),
        )
        _save_csv_cache(excel_path, [unit])

        csv_path = _csv_cache_path(excel_path)
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["com_number"] == "C001"
        assert rows[0]["unit_detailing_start_date"] == "2025-01-01"

    def test_save_csv_empty_dates(self, tmp_path):
        from data.models import Unit

        excel_path = str(tmp_path / "workbook.xlsx")
        (tmp_path / "workbook.xlsx").write_bytes(b"fake")

        unit = Unit(
            com_number="C001",
            job_name="",
            contract_number="",
            description="",
            detailer="",
            checking_status="",
        )
        _save_csv_cache(excel_path, [unit])

        csv_path = _csv_cache_path(excel_path)
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["unit_detailing_start_date"] == ""
        assert rows[0]["detailing_due_date"] == ""


# ── save_csv_cache (public wrapper) ───────────────────────────────


class TestSaveCsvCache:
    def test_creates_both_caches(self, tmp_path):
        from data.models import Unit

        excel_path = str(tmp_path / "workbook.xlsx")
        (tmp_path / "workbook.xlsx").write_bytes(b"fake")

        unit = Unit(
            com_number="C001",
            job_name="",
            contract_number="",
            description="",
            detailer="",
            checking_status="",
        )
        save_csv_cache(excel_path, [unit])

        assert os.path.exists(_cache_path(excel_path))
        assert os.path.exists(_csv_cache_path(excel_path))
