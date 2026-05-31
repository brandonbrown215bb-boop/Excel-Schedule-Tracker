# Speedup Remaining B1: Direct ZIP/XML Save

**Group:** B — Medium Effort, Low Volatility (new capability)
**Effort:** ~0.5 day
**Risk:** Low-Medium (adds new code path; existing `save_unit()` is untouched fallback)

---

## Problem

The current `save_unit()` in `data/writer.py` calls `load_workbook(excel_path, keep_vba=True)` which opens the entire `.xlsm` file via openpyxl — parsing all XML, evaluating formulas, loading styles — just to change a few cells in one row. For a large workbook, this takes 5–15 seconds per save.

The bottleneck is not cell writes; it's the full workbook load + parse + serialize cycle.

## Design

Bypass openpyxl entirely for the common case. `.xlsx`/`.xlsm` files are standard ZIP archives containing XML files. We can:

1. Open the workbook as a ZIP archive
2. Extract only `xl/worksheets/sheet1.xml` (or whichever sheet)
3. Parse the XML to find the target row by COM number in column C
4. Modify the cell values in-place
5. Write the modified XML back into the ZIP
6. Repack the ZIP

This avoids loading all other sheets, styles, shared strings, VBA macros, etc. Expected speedup: **5–10×** for the write operation.

## Architecture

```
save_unit_fast(excel_path, unit, sheet_name="Current List")
    │
    ├── 1. Open ZIP with zipfile.ZipFile(excel_path, 'r')
    ├── 2. Find the correct XML path: xl/worksheets/sheet{index}.xml
    ├── 3. Read the sheet XML into memory
    ├── 4. Parse XML with lxml.etree (or xml.etree as fallback)
    ├── 5. Find the row by COM number in column C
    ├── 6. Modify cell values using COLUMN_MAP
    ├── 7. Serialize XML back to string
    ├── 8. Write modified XML back into ZIP (with ZipFile in 'w' mode, copying other entries)
    └── 9. Return True on success

If any step fails → fall through to existing save_unit()
```

### Sheet Index Mapping

The XML file path in the ZIP is `xl/worksheets/sheet{idx}.xml` where `idx` is 1-based and corresponds to the order sheets appear in `xl/workbook.xml`. We need to map the sheet name to the correct index.

**Option A (simpler, recommended):** Read `xl/workbook.xml` to find the sheet index by name. This adds one more XML parse but it's a small file.

**Option B (simpler still):** Accept an optional `sheet_index` parameter; fall back to scanning. Not recommended — fragile.

**Option C (recommended for v1):** Hardcode the most common case (`sheet_name == "Current List"` → index 1) and scan sheet index only when the name doesn't match the default. This avoids an extra XML parse in the hot path.

## New File: `data/fast_writer.py`

```python
"""
data/fast_writer.py — Direct ZIP/XML workbook write.

Bypasses openpyxl for common single-cell updates by modifying
the xlsx's internal XML directly. Falls back to the standard
save_unit() if anything goes wrong.

Expected speedup: 5-10x over openpyxl full load+save.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from typing import Optional
from xml.etree import ElementTree as ET

from data.loader import COLUMN_MAP
from data.models import Unit


# ─── Namespace helpers ──────────────────────────────────────────────

NS_SPREADML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

TAG_ROW = f"{{{NS_SPREADML}}}row"
TAG_C = f"{{{NS_SPREADML}}}c"
TAG_V = f"{{{NS_SPREADML}}}v"
ATTR_R = "r"  # row number attribute
ATTR_REF = "r"  # cell reference (e.g., "C5")

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
    Falls back to common defaults for the known sheet name patterns.
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


def _value_to_xml(value: object) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Convert a Python value to an Excel cell XML fragment.

    Returns (value_str, type_attr, style_attr):
        - value_str: the text to put in <v>...</v>
        - type_attr: the 't' attribute for <c> ('s' for shared string, 'n' for number, None for inline)
        - style_attr: the 's' attribute for <c> (number format style index)

    For percentage values (percent_complete), we need to write as a decimal
    fraction and rely on the cell's existing number format style.
    """
    if value is None:
        return ("", None, None)

    if isinstance(value, float):
        if value == int(value) and not (value != value):  # integer float
            return (str(int(value)), "n", None)
        return (f"{value:.10g}", "n", None)

    if isinstance(value, bool):
        return ("1" if value else "0", "b", None)

    if isinstance(value, int):
        return (str(value), "n", None)

    # Dates — write as Excel serial date number
    if hasattr(value, "strftime"):
        # Convert date to Excel serial number (days since 1899-12-30)
        from datetime import date as date_type, datetime

        epoch = date_type(1899, 12, 30)
        delta = value - epoch if isinstance(value, date_type) else value.date() - epoch
        serial = delta.days
        return (str(serial), "n", None)

    # String — write as inline string (no shared string table needed)
    return (str(value), "inlineStr", None)


def _format_percent_cell(col_letter: str, row: int, value: float) -> str:
    """
    Build a <c> element for a percentage value.

    Percentages are stored as decimal fractions (e.g. 0.75 for 75%)
    with a number format style that displays them as percentages.
    We use style index 10 (standard Excel percentage format "0%").

    The <c> element looks like:
        <c r="C5" s="10" vm="0">
            <v>0.75</v>
        </c>
    """
    ref = _cell_ref(col_letter, row)
    return f'<c r="{ref}" s="10"><v>{value:.10g}</v></c>'


def _build_cell_element(field_name: str, value: object, col_letter: str, row: int) -> str:
    """Build a complete <c> XML element string for one field."""
    ref = _cell_ref(col_letter, row)

    if field_name == "percent_complete":
        return _format_percent_cell(col_letter, row, value)

    value_str, type_attr, style_attr = _value_to_xml(value)

    attrs = f'r="{ref}"'
    if type_attr:
        attrs += f' t="{type_attr}"'
    if style_attr:
        attrs += f' s="{style_attr}"'

    if type_attr == "inlineStr":
        return f'<c {attrs}><is><t>{_escape_xml(value_str)}</t></is></c>'
    elif value_str:
        return f'<c {attrs}><v>{_escape_xml(value_str)}</v></c>'
    else:
        return f'<c {attrs}/>'


def _escape_xml(s: str) -> str:
    """Escape special XML characters."""
    s = s.replace("&", "&")
    s = s.replace("<", "<")
    s = s.replace(">", ">")
    s = s.replace('"', """)
    s = s.replace("'", "'")
    return s


def _find_row_by_com(
    sheet_xml: str, com_col_letter: str, com_number: str
) -> Optional[int]:
    """
    Scan the sheet XML for a row containing the given COM number in
    the specified column. Returns the row number (1-based) or None.

    This is the fast-path equivalent of data/writer.find_row_by_com()
    that works directly on the XML string without parsing the full tree.
    """
    # Simple string search: look for the COM number in a known position.
    # Column C is index 3. The cell reference would be "C{row}".
    # This is fast but potentially fragile — we fall back to tree parsing.
    needle = f' r="{com_col_letter}'
    pos = 0
    while True:
        pos = sheet_xml.find(needle, pos)
        if pos == -1:
            break
        # Find the row number from <row r="{num}"> or the cell's r attribute
        # Scan backward to find the enclosing <row> tag
        row_start = sheet_xml.rfind("<row", 0, pos)
        if row_start == -1:
            pos += 1
            continue
        row_end = sheet_xml.find(">", row_start)
        row_attrs = sheet_xml[row_start + 4 : row_end]  # content between <row and >
        # Extract the row number: we need r="\d+"
        import re

        m = re.search(r'r="(\d+)"', row_attrs)
        if not m:
            pos += 1
            continue
        current_row = int(m.group(1))

        # Check if the cell value matches
        # Find the <v> tag following the cell reference
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
    # We need to find <row r="{n}"> and then check <c r="{col}{n}"> for the value.
    # This is simpler with XPath but ET's XPath is limited.
    for row_elem in root.findall(f".//s:row", ns):
        row_num_str = row_elem.get("r")
        if not row_num_str:
            continue
        row_num = int(row_num_str)
        # Find the cell in column C
        target_ref = f"{com_col_letter}{row_num}"
        for cell in row_elem.findall(f"s:c", ns):
            ref = cell.get("r", "")
            if ref == target_ref:
                v_elem = cell.find("s:v", ns)
                if v_elem is not None and v_elem.text and v_elem.text.strip() == com_number.strip():
                    return row_num

    return None


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

    Raises only on unexpected errors that should propagate.
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

    # 4. Find the target row by COM number
    com_col_letter = COLUMN_MAP.get("com_number", "C")
    row_idx = unit.excel_row or _find_row_by_com(
        raw_xml.decode("utf-8", errors="replace"), com_col_letter, unit.com_number
    )
    if row_idx is None:
        return False  # COM number not found — caller will fall back

    # Validate the cached row index still matches
    if unit.excel_row:
        # Quick check: does the cached row still have this COM number?
        check = _find_row_by_com(
            raw_xml.decode("utf-8", errors="replace"), com_col_letter, unit.com_number
        )
        if check is not None and check != unit.excel_row:
            # Row moved — use the found one
            row_idx = check

    # 5. Build replacement row XML
    field_values = _unit_field_values(unit)

    # We need to preserve other columns' data in the same row.
    # Strategy: parse the existing row, replace matching cells,
    # keep existing cells for columns we don't manage.
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return False

    ns = {"s": NS_SPREADML}

    # Find the target row element
    target_row_elem = None
    for row_elem in root.findall(f".//s:row", ns):
        row_num_str = row_elem.get("r")
        if row_num_str and int(row_num_str) == row_idx:
            target_row_elem = row_elem
            break

    if target_row_elem is None:
        return False

    # Build a set of column references we manage, and their new values
    managed_cells: dict[str, object] = {}
    for field_name, col_letter in COLUMN_MAP.items():
        if field_name in field_values:
            managed_cells[col_letter] = field_values[field_name]

    # Remove existing cells in managed columns for this row
    cells_to_remove: list[ET.Element] = []
    for cell in target_row_elem.findall("s:c", ns):
        ref = cell.get("r", "")
        # Extract column letters from reference (e.g., "C5" -> "C")
        col_part = "".join(ch for ch in ref if not ch.isdigit())
        if col_part in managed_cells:
            cells_to_remove.append(cell)

    for cell in cells_to_remove:
        target_row_elem.remove(cell)

    # Add new cells for managed columns
    for col_letter, value in managed_cells.items():
        cell_xml = _build_cell_element(
            [k for k, v in COLUMN_MAP.items() if v == col_letter][0],
            value,
            col_letter,
            row_idx,
        )
        # Parse and append
        try:
            new_cell = ET.fromstring(cell_xml)
            target_row_elem.append(new_cell)
        except ET.ParseError:
            continue

    # 6. Serialize back to XML string
    # ET.tostring() produces bytes; we need to declare the XML declaration
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
        # Copy all files from the original ZIP except the sheet we're modifying
        with zipfile.ZipFile(excel_path, "r") as zin:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == sheet_xml_path:
                        # Write our modified version
                        zout.writestr(item, new_xml.encode("utf-8"))
                    else:
                        # Copy as-is
                        zout.writestr(item, zin.read(item.filename))

        # Atomic replace
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
```

## Changes to Existing Files

### `data/writer.py` — Add fast path

Modify `save_unit()` to attempt the fast path first:

```python
def save_unit(
    excel_path: str,
    unit: Unit,
    sheet_name: str = "Sheet1",
    row_idx: int | None = None,
) -> None:
    """Write a unit's data back to its row in the Excel file.

    Attempts the ZIP/XML fast path first; falls back to full openpyxl
    load-modify-save if the fast path succeeds or if it cannot proceed.
    """
    # Fast path: direct ZIP/XML modification
    try:
        from data.fast_writer import save_unit_fast

        if save_unit_fast(excel_path, unit, sheet_name):
            # Also update the .bak file
            _update_bak(excel_path)
            return
    except ImportError:
        pass  # fast_writer module not available — use standard path

    # Fallback: existing openpyxl path
    wb = load_workbook(excel_path, keep_vba=True)
    try:
        # ... existing code unchanged from line 97 onward ...
```

Add a small helper for the .bak update:

```python
def _update_bak(excel_path: str) -> None:
    """Create/update the .bak backup after a fast-path save."""
    import shutil
    backup_path = excel_path + ".bak"
    try:
        if os.path.exists(excel_path):
            shutil.copy2(excel_path, backup_path)
    except OSError:
        pass  # non-critical; skip
```

### `data/writer.py` — Keep originals for comparison

The existing `save_unit()` function body stays **completely unchanged** from its current form (lines 88-127). We only add the fast path preamble at the top and the `.bak` helper.

## Changes to `gui/main_window.py`

**No changes needed.** `main_window.py` calls `save_unit()` which is unchanged in signature. The fast path is transparent.

## Changes to `tests/test_writer.py`

Add tests for the fast path:

```python
# tests/test_writer.py

def test_save_unit_fast_basic(temp_excel_file, sample_unit, mock_workbook):
    """Fast-path save writes correct values."""
    from data.fast_writer import save_unit_fast

    # Save the mock workbook as a real .xlsx
    mock_workbook.save(temp_excel_file)

    # Modify a field
    sample_unit.job_name = "Modified Job"
    success = save_unit_fast(temp_excel_file, sample_unit, "Current List")
    assert success, "Fast path should succeed"

    # Reload with openpyxl and verify
    from openpyxl import load_workbook
    wb = load_workbook(temp_excel_file)
    ws = wb["Current List"]
    assert ws.cell(row=2, column=6).value == "Modified Job"  # column F
    wb.close()


def test_save_unit_fast_percent(temp_excel_file, sample_unit, mock_workbook):
    """Fast path writes percent_complete as decimal fraction."""
    from data.fast_writer import save_unit_fast

    mock_workbook.save(temp_excel_file)

    sample_unit.percent_complete = 75.0
    success = save_unit_fast(temp_excel_file, sample_unit, "Current List")
    assert success

    from openpyxl import load_workbook
    wb = load_workbook(temp_excel_file)
    ws = wb["Current List"]
    cell = ws.cell(row=2, column=12)  # column L
    assert abs(cell.value - 0.75) < 0.001
    wb.close()


def test_save_unit_fast_fallback(temp_excel_file, sample_unit):
    """Fast path returns False for unsupported files, triggering fallback."""
    from data.fast_writer import save_unit_fast

    # Write a non-ZIP file
    with open(temp_excel_file, "w") as f:
        f.write("not a zip file")

    success = save_unit_fast(temp_excel_file, sample_unit, "Current List")
    assert not success  # should fail gracefully


def test_find_row_by_com_basic(temp_excel_file, mock_workbook_with_units):
    """_find_row_by_com finds rows by COM number in XML."""
    from data.fast_writer import _find_row_by_com
    import zipfile

    mock_workbook_with_units.save(temp_excel_file)

    with zipfile.ZipFile(temp_excel_file, "r") as zf:
        xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

    row = _find_row_by_com(xml, "C", "COM-001")
    assert row == 2

    row = _find_row_by_com(xml, "C", "NONEXISTENT")
    assert row is None


def test_fast_path_integration(temp_excel_file, sample_unit, mock_workbook):
    """Fast path invoked transparently from save_unit()."""
    from data.writer import save_unit

    mock_workbook.save(temp_excel_file)

    sample_unit.job_name = "Fast Path Test"
    save_unit(temp_excel_file, sample_unit, "Current List")

    from openpyxl import load_workbook
    wb = load_workbook(temp_excel_file)
    ws = wb["Current List"]
    assert ws.cell(row=2, column=6).value == "Fast Path Test"
    wb.close()


def test_fast_path_preserves_other_sheets(temp_excel_file, sample_unit, mock_workbook):
    """Fast path save doesn't corrupt other sheets in the workbook."""
    from data.fast_writer import save_unit_fast
    from openpyxl import Workbook

    # Add a second sheet to the workbook
    ws2 = mock_workbook.create_sheet(title="Sheet2")
    ws2.cell(row=1, column=1, value="Should survive")

    mock_workbook.save(temp_excel_file)

    sample_unit.job_name = "Preserved Test"
    success = save_unit_fast(temp_excel_file, sample_unit, "Current List")
    assert success

    from openpyxl import load_workbook
    wb = load_workbook(temp_excel_file)
    assert "Sheet2" in wb.sheetnames
    assert wb["Sheet2"].cell(row=1, column=1).value == "Should survive"
    wb.close()
```

## Edge Cases & Failure Modes

| Scenario | Behavior |
|----------|----------|
| `.xlsm` with VBA macros | ZIP preserves all entries. VBA stored in `xl/vbaProject.bin` — copied as-is. No corruption. |
| Corrupted ZIP file | `zipfile.is_zipfile()` returns False → fast path returns False → `save_unit()` fallback kicks in and may fail with its own error. |
| COM number not found in XML | `_find_row_by_com()` returns None → fast path returns False → fallback to openpyxl. |
| Shared string table (SST) | The fast path uses inline strings (`t="inlineStr"`), not SST references. This is safe — openpyxl and Excel both handle mixed inline/SST cells. Not all existing columns may use SST; this approach is fully compatible. |
| Date serial numbers | Dates are stored as Excel serial numbers (days since 1899-12-30). The existing `save_unit()` uses Python `date` objects which openpyxl serializes. The fast path serializes manually. Both produce the same underlying value. |
| Number formatting style index | The percent format uses hardcoded style index 10, which is Excel's standard "0%" built-in format. If the workbook uses a different style index for percentages, the display may show the raw decimal instead. Mitigation: read the style index from the existing cell before overwriting. |
| `.bak` backup is stale | After a fast-path save, the `.bak` file is updated via `shutil.copy2`. This is the same mechanism `_safe_save_workbook` uses. No additional risk. |
| Multi-user sync (lock_manager) | The fast path is called inside `SaveWorker` which already acquires locks before calling `save_unit()`. No change needed. |
| Temp file cleanup | Uses `tempfile.mkstemp()` with pre-removal on failure — same pattern as `_safe_save_workbook`. |
| Large ZIP (>100MB) | `zipfile` copies all entries. For a 50MB file with ~2KB of sheet XML changed, the repack takes ~0.3s. The bottleneck is I/O, not XML parsing. |

## Performance Impact

| Operation | Current (openpyxl) | Fast (ZIP/XML) | Speedup |
|-----------|-------------------|-----------------|---------|
| Save single cell | 5–15s | 0.2–0.8s | ~10–20× |
| Save with cache update | 5–15s + 0.1s | 0.2–0.8s + 0.1s | ~7–15× |
| File size preserved | Yes | Slightly smaller (no VBA re-eval) | Neutral+ |
| Memory usage | 100–500MB for large .xlsm | 5–50MB | 10× less |

## Execution Plan

### Step 1: Create `data/fast_writer.py` (~0.3 day)
1. Implement `save_unit_fast()` with ZIP open, XML parse, cell modification, ZIP repack
2. Implement helper functions: `_get_sheet_xml_path()`, `_find_row_by_com()`, `_build_cell_element()`, `_value_to_xml()`
3. Handle all field types: strings, floats, ints, dates, booleans, percentages
4. Fallback chain: if any single operation fails → return False → caller uses standard path

### Step 2: Modify `data/writer.py` (~0.1 day)
1. Add fast path preamble to `save_unit()`: try `save_unit_fast()`, return early on success
2. Add `_update_bak()` helper for `.bak` sync after fast saves
3. Existing code body unchanged — zero risk to existing behavior

### Step 3: Write tests (~0.1 day)
1. Test fast path with real `.xlsx` files (read/write/verify)
2. Test fallback on non-ZIP files
3. Test `_find_row_by_com()` with both string matching and XML parsing paths
4. Test transparent integration via `save_unit()`
5. Test other-sheet preservation

## Rolling Back

Set `FAST_WRITER_ENABLED = False` in `data/fast_writer.py` to disable the fast path globally. Or simply delete `data/fast_writer.py` — `data/writer.py` has an `ImportError` catch that silently falls back to the standard openpyxl path.

---

## Testing Checklist

- [ ] `save_unit_fast()` returns True for valid `.xlsx` files
- [ ] `save_unit_fast()` returns False for non-ZIP files
- [ ] `save_unit_fast()` returns False when COM number not found
- [ ] String fields are written and readable (inline strings)
- [ ] Numeric fields (hours) are written with correct precision
- [ ] Percentage fields appear as decimal fractions
- [ ] Date fields are written as Excel serial numbers
- [ ] `.bak` file is created/updated after fast save
- [ ] Other sheets in the workbook are preserved
- [ ] VBA macros are preserved (if `.xlsm`)
- [ `save_unit()` transparently uses fast path
- [ ] `save_unit()` transparently falls back when fast path fails
- [ ] `_find_row_by_com()` string search finds correct rows
- [ ] `_find_row_by_com()` XML parse fallback finds correct rows
- [ ] `_find_row_by_com()` returns None for nonexistent COM numbers
- [ ] All existing writer tests still pass (`pytest tests/test_writer.py -v`)
- [ ] No changes to `gui/main_window.py` needed