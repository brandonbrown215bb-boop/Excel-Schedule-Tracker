# automation/csv_sync.py
"""
CSV sync pipeline — now uses pure-Python macro implementations
instead of COM/VBA.  No keep_vba=True needed.
"""

from .vba_native import move_data_in


def pull_and_sync(source_path: str, target_path: str, macros: list[str] | None = None) -> int:
    """
    Full pipeline (pure Python, no COM required):
    1. Read data from source file's SCHDetailingReport sheet
    2. Write to target file's Unedited Report sheet
    3. Run COMs_into_List merge, ApplyFormulas, Backup — all in Python
    """
    return move_data_in(source_path, target_path)
