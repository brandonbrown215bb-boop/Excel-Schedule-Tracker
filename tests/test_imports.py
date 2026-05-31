# tests/test_imports.py
"""Verify all module imports work correctly — catches missing deps and renamed files."""


class TestImports:
    def test_data_models(self):
        from data.models import Unit, _working_days_between

        assert Unit is not None
        assert _working_days_between is not None

    def test_data_loader(self):
        from data.loader import COLUMN_MAP

        assert isinstance(COLUMN_MAP, dict)
        assert len(COLUMN_MAP) > 0

    def test_data_writer(self):
        from data.writer import find_row_by_com, save_unit

        assert callable(find_row_by_com)
        assert callable(save_unit)

    def test_automation_vba_runner(self):
        from automation.vba_runner import MACRO_DISPATCH, run_macro

        assert "Backup" in MACRO_DISPATCH
        assert callable(run_macro)

    def test_automation_csv_sync(self):
        from automation.csv_sync import pull_and_sync

        assert callable(pull_and_sync)

    def test_automation_vba_native(self):
        from automation.vba_native import (
            apply_formulas,
            backup,
            coms_into_list,
            move_data_in,
            save_master,
        )

        assert callable(apply_formulas)
        assert callable(backup)
        assert callable(coms_into_list)
        assert callable(move_data_in)
        assert callable(save_master)

    def test_gui_imports(self):
        """GUI imports require PyQt5 — verify it's importable."""
        from PyQt5.QtCore import QDate
        from PyQt5.QtWidgets import QApplication

        assert QApplication is not None
        assert QDate is not None

    def test_gui_list_panel(self):
        from gui.list_panel import ListPanel, UnitListModel

        assert callable(ListPanel)
        assert callable(UnitListModel)

    def test_main_import(self):
        import main

        assert hasattr(main, "main")
