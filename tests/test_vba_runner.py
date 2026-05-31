# tests/test_vba_runner.py
"""Tests for automation/vba_runner.py — MACRO_DISPATCH, run_macro."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from automation.vba_runner import MACRO_DISPATCH, run_macro


class TestMacroDispatch:
    def test_all_expected_macros_registered(self):
        expected = {"COMs_into_List", "Backup", "Save", "ApplyFormulas"}
        assert set(MACRO_DISPATCH.keys()) == expected

    def test_coms_into_list_is_callable(self):
        assert callable(MACRO_DISPATCH["COMs_into_List"])

    def test_backup_is_callable(self):
        assert callable(MACRO_DISPATCH["Backup"])

    def test_save_is_callable(self):
        assert callable(MACRO_DISPATCH["Save"])

    def test_apply_formulas_is_callable(self):
        assert callable(MACRO_DISPATCH["ApplyFormulas"])


class TestRunMacro:
    def test_calls_backup_implementation(self):
        """run_macro dispatches Backup via MACRO_DISPATCH dict."""
        with patch.dict(MACRO_DISPATCH, {"Backup": lambda p: None}):
            from unittest.mock import MagicMock

            mock_backup = MagicMock()
            MACRO_DISPATCH["Backup"] = mock_backup
            try:
                run_macro("src.xlsx", "Backup")
                mock_backup.assert_called_once_with("src.xlsx")
            finally:
                # Restore real function
                from automation.vba_native import backup

                MACRO_DISPATCH["Backup"] = backup

    def test_calls_coms_into_list_implementation(self):
        mock_func = MagicMock()
        MACRO_DISPATCH["COMs_into_List"] = mock_func
        try:
            run_macro("src.xlsx", "COMs_into_List")
            mock_func.assert_called_once_with("src.xlsx")
        finally:
            from automation.vba_native import coms_into_list

            MACRO_DISPATCH["COMs_into_List"] = coms_into_list

    def test_calls_save_implementation(self):
        mock_func = MagicMock()
        MACRO_DISPATCH["Save"] = mock_func
        try:
            run_macro("src.xlsx", "Save")
            mock_func.assert_called_once_with("src.xlsx")
        finally:
            from automation.vba_native import save_master

            MACRO_DISPATCH["Save"] = save_master

    def test_unknown_macro_does_not_raise(self):
        """Unknown macro name should print a message, not raise."""
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            run_macro("/some/path.xlsx", "NonExistentMacro")
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "NonExistentMacro" in output
        assert "not implemented" in output

    def test_unknown_macro_returns_none(self):
        result = run_macro("/some/path.xlsx", "BogusMacro")
        assert result is None

    def test_dispatch_table_is_dict(self):
        assert isinstance(MACRO_DISPATCH, dict)

    def test_dispatch_values_are_functions(self):
        for name, func in MACRO_DISPATCH.items():
            assert callable(func), f"{name} is not callable"


class TestPullAndSync:
    def test_pull_and_sync_calls_move_data_in(self):
        with patch("automation.csv_sync.move_data_in", return_value=42) as mock_move:
            import automation.csv_sync as cs

            result = cs.pull_and_sync("src.xlsx", "tgt.xlsx")
            assert result == 42
            mock_move.assert_called_once_with("src.xlsx", "tgt.xlsx")

    def test_pull_and_sync_passes_macros_none(self):
        """macros parameter defaults to None and is not used (csv_sync just delegates)."""
        with patch("automation.csv_sync.move_data_in", return_value=0):
            import automation.csv_sync as cs

            # Should not raise even with macros=None
            cs.pull_and_sync("a.xlsx", "b.xlsx")
