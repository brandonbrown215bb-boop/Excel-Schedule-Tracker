# automation/vba_runner.py
"""
Python implementation of VBA macro runner — replaces COM/win32com.

Uses the native Python implementations from vba_native.py.
"""

from .vba_native import apply_formulas, backup, coms_into_list, save_master

# Map macro names to their Python implementations
MACRO_DISPATCH = {
    "COMs_into_List": coms_into_list,
    "Backup": backup,
    "Save": save_master,
    "ApplyFormulas": apply_formulas,
}


def run_macro(excel_path: str, macro_name: str):
    """
    Run a named macro using the native Python implementation.

    This replaces the COM-based VBA runner for cross-platform support.
    Falls back to a simple no-op for unknown macros.
    """
    func = MACRO_DISPATCH.get(macro_name)
    if func is None:
        # Macro not implemented in Python — log and skip
        print(f"VBA runner: {macro_name} not implemented in native Python")
        return

    # Call the native implementation
    func(excel_path)
