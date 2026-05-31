"""
data/fast_writer.py — Direct ZIP/XML workbook write.

Bypasses openpyxl for common single-cell updates by modifying
the xlsx's internal XML directly. Falls back to the standard
save_unit() if anything goes wrong.

Expected speedup: 5-10x over openpyxl full load+save.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from datetime import date as date_type, datetime
from typing import Optional
from xml.etree import ElementTree as ET

from data.loader import COLUMN_MAP
from data.models import Unit


# ─── Namespace helpers ──────────────────────────────────────────────

NS_SPREADML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Column letter → index cache (A=1, B=2, ...)
_COL_INDEX_CACHE: dict[str, int] = {}


def _col_index(col_letter: str) -> int:
    """Convert column letter to 1-based index (A=1, Z=26, AA=27)."""
    if col_letter not in _COL_INDEX_CACHE:
        result = 0
        for ch in col_letter.upper():
            result = result * 26 + (ord(ch) - ord("A") + 1)
        _COL_INDEX_CACHE[col_letter] = result
    return _COL_INDEX_CACHE[col_letter]


def _cell_ref(col_letter: str, row: int) -> str:
    """Build an Excel cell reference string, e.g. 'C5'."""
    return f"{col_letter}{row}"


def _get_sheet_xml_path(zf: zipfile.ZipFile, sheet_name: str) -> Optional[str]:
    """
    Find the sheet XML path inside the xlsx ZIP for a given sheet name.

    Reads xl/workbook.xml to map sheet names to their XML file paths.
    Falls back to common defaults for known sheet name patterns.
    """
    # Fast path for known names
    KNOWN_SHEETS: dict[str, str] = {
        "Current List": "xl/worksheets/sheet1.xml",
        "Unedited Report": "xl/worksheets/sheet2.xml",
        "SCHDetailingReport": "xl/worksheets/sheet3.xml",
    }
    if sheet_name in KNOWN_SHEETS:
        path = KNOWN_SHEETS[sheet_name]
        if path in zf.namelist():
            return path

    # Slow path: parse xl/workbook.xml to find the sheet index
    try:
        with zf.open("xl/workbook.xml") as f:
            tree = ET.parse(f)
        root = tree.getroot()
        ns = {"s": NS_SPREADML, "r": NS_R}
        sheets = root.findall(".//s:sheet", ns)
        for i, sheet_elem in enumerate(sheets, start=1):
            name = sheet_elem.get("name", "")
            if name and name.strip() == sheet_name:
                return f"xl/worksheets/sheet{i}.xml"
    except (KeyError, ET.ParseError, zipfile.BadZipFile):
        pass

    return None


def _escape_xml(s: str) -> str:
    """Escape special XML characters."""
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("'", "&apos;")
    return s


def _value_to_xml(value: object) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Convert a Python value to an Excel cell XML fragment.

    Returns (value_str, type_attr, style_attr).
    """
    if value is None:
        return ("", None, None)

    if isinstance(value, bool):
        return ("1" if value else "0", "b", None)

    if isinstance(value, int):
        return (str(value), "n", None)

    if isinstance(value, float):
        return (f"{value:.10g}", "n", None)

    # Dates — write as Excel serial date number
    if isinstance(value, (date_type, datetime)):
        epoch = date_type(1899, 12, 30)
        if isinstance(value, datetime):
            value = value.date()
        delta = value - epoch
        serial = delta.days
        return (str(serial), "n", None)

    # String — write as inline string
    return (_escape_xml(str(value)), "inlineStr", None)


def _build_cell_element(field_name: str, value: object, col_letter: str, row: int) -> str:
    """Build a complete <c> XML element string for one field."""
    ref = _cell_ref(col_letter, row)

    if field_name == "percent_complete":
        return f'<c r="{ref}" s="10"><v>{value:.10g}</v></c>'

    value_str, type_attr, style_attr = _value_to_xml(value)

    attrs = f'r="{ref}"'
    if type_attr:
        attrs += f' t="{type_attr}"'
    if style_attr:
        attrs += f' s="{style_attr}"'

    if type_attr == "inlineStr":
        return f'<c {attrs}><is><t>{value_str}</t></is></c>'
    elif value_str:
        return f'<c {attrs}><v>{value_str}</v></c>'
    else:
        return f'<c {attrs}/>'


def _find_row_by_com(
    sheet_xml: str, com_col_letter: str, com_number: str
) -> Optional[int]:
    """
    Scan the sheet XML for a row containing the given COM number in
    the specified column. Returns the row number (1-based) or None.
    """
    needle = f' r="{com_col_letter}'
    pos = 0
    while True:
        pos = sheet_xml.find(needle, pos)
        if pos == -1:
            break
        # Scan backward to find the enclosing <row> tag
        row_start = sheet_xml.rfind("<row", 0, pos)
        if row_start == -1:
            pos += 1
            continue
        row_end = sheet_xml.find(">", row_start)
        row_attrs = sheet_xml[row_start + 4 : row_end]
        m = re.search(r'r="(\d+)"', row_attrs)
        if not m:
            pos += 1
            continue
        current_row = int(m.group(1))

        # Check if the cell value matches
        cell_start = sheet_xml.find("<v>", pos)
        cell_end = sheet_xml.find("</v>", cell_start) if cell_start != -1 else -1
        if cell_start != -1 and cell_end != -1:
            cell_val = sheet_xml[cell_start + 3 : cell_end]
            if cell_val.strip() == str(com_number).strip():
                return current_row
        pos += 1

    # Fallback: use proper XML parsing
    try:
        root = ET.fromstring(sheet_xml)
    except ET.ParseError:
        return None

    ns = {"s": NS_SPREADML}
    for row_elem in root.findall(".//s:row", ns):
        row_num_str = row_elem.get("r")
        if not row_num_str:
            continue
        row_num = int(row_num_str)
        target_ref = f"{com_col_letter}{row_num}"
        for cell in row_elem.findall("s:c", ns):
            ref = cell.get("r", "")
            if ref == target_ref:
                v_elem = cell.find("s:v", ns)
                if v_elem is not None and v_elem.text and v_elem.text.strip() == com_number.strip():
                    return row_num
    return None


def _unit_field_values(unit: Unit) -> dict[str, object]:
    """Map Unit fields to XML-ready values (same as writer.py)."""
    return {
        "com_number": unit.com_number,
        "job_name": unit.job_name,
        "contract_number": unit.contract_number,
        "description": unit.description,
        "detailer": unit.detailer,
        "checking_status": unit.checking_status,
        "department_hours": unit.department_hours,
        "actual_hours": unit.actual_hours,
        "target_department_hours": unit.target_department_hours,
        "iec_internal_hours": unit.iec_internal_hours,
        "percent_complete": unit.percent_complete / 100.0,
        "unit_detailing_start_date": unit.unit_detailing_start_date,
        "unit_moved_to_checking_date": unit.unit_moved_to_checking_date,
        "unit_detailing_completion_date": unit.unit_detailing_completion_date,
        "dept_due_date_previous": unit.dept_due_date_previous,
        "detailing_due_date": unit.detailing_due_date,
        "build_date": unit.build_date,
    }


def save_unit_fast(
    excel_path: str,
    unit: Unit,
    sheet_name: str = "Current List",
) -> bool:
    """
    Write one unit's data to the Excel file by directly modifying the
    sheet XML inside the ZIP archive.

    Returns True if the fast path succeeded. Returns False (no exception)
    if it cannot proceed — the caller should fall back to save_unit().
    """
    if not zipfile.is_zipfile(excel_path):
        return False

    # 1. Open the ZIP
    try:
        zf = zipfile.ZipFile(excel_path, "r")
    except (zipfile.BadZipFile, OSError):
        return False

    # 2. Find the sheet XML path
    try:
        sheet_xml_path = _get_sheet_xml_path(zf, sheet_name)
        if sheet_xml_path is None:
            return False
        # 3. Read the sheet XML
        raw_xml = zf.read(sheet_xml_path)
    except (KeyError, zipfile.BadZipFile, OSError):
        return False
    finally:
        zf.close()

    xml_str = raw_xml.decode("utf-8", errors="replace")

    # 4. Find the target row by COM number
    com_col_letter = COLUMN_MAP.get("com_number", "C")
    row_idx = unit.excel_row or _find_row_by_com(xml_str, com_col_letter, unit.com_number)
    if row_idx is None:
        return False

    # Validate the cached row index still matches
    if unit.excel_row:
        check = _find_row_by_com(xml_str, com_col_letter, unit.com_number)
        if check is not None and check != unit.excel_row:
            row_idx = check

    # 5. Parse XML and modify the target row
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return False

    ns = {"s": NS_SPREADML}

    # Find the target row element
    target_row_elem = None
    for row_elem in root.findall(".//s:row", ns):
        row_num_str = row_elem.get("r")
        if row_num_str and int(row_num_str) == row_idx:
            target_row_elem = row_elem
            break

    if target_row_elem is None:
        return False

    # Build a set of column references we manage, and their new values
    field_values = _unit_field_values(unit)
    managed_cells: dict[str, object] = {}
    for field_name, col_letter in COLUMN_MAP.items():
        if field_name in field_values:
            managed_cells[col_letter] = field_values[field_name]

    # Remove existing cells in managed columns for this row
    cells_to_remove: list[ET.Element] = []
    for cell in target_row_elem.findall("s:c", ns):
        ref = cell.get("r", "")
        col_part = "".join(ch for ch in ref if not ch.isdigit())
        if col_part in managed_cells:
            cells_to_remove.append(cell)

    for cell in cells_to_remove:
        target_row_elem.remove(cell)

    # Add new cells for managed columns
    for col_letter, value in managed_cells.items():
        field_name_candidates = [k for k, v in COLUMN_MAP.items() if v == col_letter]
        if not field_name_candidates:
            continue
        cell_xml = _build_cell_element(field_name_candidates[0], value, col_letter, row_idx)
        try:
            new_cell = ET.fromstring(cell_xml)
            target_row_elem.append(new_cell)
        except ET.ParseError:
            continue

    # 6. Serialize back to XML string
    try:
        new_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    except Exception:
        return False

    # 7. Write the modified ZIP
    directory = os.path.dirname(os.path.abspath(excel_path)) or "."
    suffix = os.path.splitext(excel_path)[1] or ".xlsm"
    fd, temp_path = tempfile.mkstemp(prefix=".unittracker-fast-", suffix=suffix, dir=directory)
    os.close(fd)

    try:
        with zipfile.ZipFile(excel_path, "r") as zin:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == sheet_xml_path:
                        zout.writestr(item, new_xml.encode("utf-8"))
                    else:
                        zout.writestr(item, zin.read(item.filename))

        backup_path = excel_path + ".bak"
        if os.path.exists(excel_path):
            shutil.copy2(excel_path, backup_path)
        os.replace(temp_path, excel_path)

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

    if os.path.exists(temp_path):
        os.remove(temp_path)

    return True
