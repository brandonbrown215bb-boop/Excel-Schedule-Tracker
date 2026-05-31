## Performance Brainstorm: Loading / Saving / Refreshing

### Current Bottleneck Analysis

1. **CSV cache load** (`_load_units_from_csv`): Opens CSV → iterates rows → parses dates/floats → creates `Unit` objects → computes `calculated_status_color` for every unit. Even though it's "fast path", this is still Python object creation + date parsing + status calculation for potentially thousands of units.
2. **Excel load** (`load_units` slow path): `openpyxl.load_workbook(..., data_only=True)` on a large `.xlsm` file is inherently slow — it parses the entire XML, evaluates formulas via cached values, and iterates every row.
3. **Save** (`save_unit`): Opens the full workbook again (`load_workbook`), finds the row, writes cells, saves the whole file. This is the biggest bottleneck — a full read-modify-write cycle on a large `.xlsm`.
4. **Refresh** (`_refresh_data`): Forces the slow Excel path, then rebuilds the entire UI.

---

### Strategy 1: Faster CSV Cache Format

**Problem:** CSV parsing in Python is slow — `csv.DictReader` + per-field `parse_date()` / `parse_float()` calls for every row.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **Parquet cache** | Replace CSV with Apache Parquet (via `pyarrow` or `fastparquet`). Columnar, binary, typed — no parsing needed. | 5-20x faster cache load |
| **Pickle cache** | Use Python's `pickle` to serialize the `Unit` list directly. Zero parsing. | 3-10x faster cache load |
| **SQLite cache** | Write to a local SQLite file. Supports typed columns and partial queries. | 2-5x faster + enables partial loading |
| **orjson cache** | Use `orjson` (fastest Python JSON library) instead of CSV. | 2-3x faster |

---

### Strategy 2: Avoid Full Workbook Load on Save

**Problem:** `save_unit()` calls `load_workbook(excel_path)` which reads the entire `.xlsm` file just to change a few cells.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **Direct ZIP/XML manipulation** | `.xlsx`/`.xlsm` files are ZIP archives. Use `zipfile` + `lxml` to extract only `xl/worksheets/sheet1.xml`, modify cells, and repack. Bypasses openpyxl entirely. | 5-10x faster save |
| **xlwings / COM on Windows** | Connect to a running Excel instance and write cells directly. Near-instant. | 10-50x faster save |
| **Append-only delta file** | Write changes to a small delta file. Apply deltas on load. Never touch Excel for saves. | Near-instant save |
| **openpyxl read-only + write-only** | Use `read_only=True` to find row, then `write_only=True` to write. | 2-3x faster save |

---

### Strategy 3: Incremental / Partial Loading

**Problem:** All units are loaded at startup, even though the user only sees a few at a time.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **Lazy loading with SQLite** | Only query units needed for the current calendar view. Load more as user scrolls. | 5-10x faster startup |
| **Two-tier cache** | Keep a "light" cache (COM number + due date + status) for calendar, load full details on selection. | 3-5x faster startup |
| **Background loading** | Load UI immediately with skeleton state. Populate units in background thread. | Perceived instant startup |
| **Pagination** | Load units in pages (e.g., 100 at a time) based on selected date range. | 2-5x faster startup |

---

### Strategy 4: Parallelize / Async Operations

**Problem:** All operations are blocking — UI freezes during load/save.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **QThread for loading** | Move `load_units()` to a `QThread`. Show loading spinner. | Perceived instant |
| **QThread for saving** | Move `save_unit()` to background thread. Queue multiple saves. | Perceived instant |
| **Pre-compute status colors** | Use `pandas`/`numpy` vectorized operations instead of per-unit Python loops. | 2-5x faster for large datasets |

---

### Strategy 5: Reduce Excel File Size

**Problem:** The `.xlsm` file is large due to VBA, multiple sheets, and formatting.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **Separate data from presentation** | Keep a "data-only" `.xlsx` for the app, separate "report" `.xlsm` for humans. | 5-10x faster load |
| **Strip unused styles** | Copy only data to a clean `.xlsx` file. | 2-5x faster load |
| **Compress the cache** | Use `lz4` compression on the cache file. GB/s decompression. | 1.5-2x faster cache load |

---

### Strategy 6: Smarter Refresh Logic

**Problem:** `_refresh_data()` always forces a full Excel reload, even if nothing changed.

| Method | Description | Expected Speedup |
|--------|-------------|------------------|
| **File watcher** | Use `QFileSystemWatcher` to detect when Excel file changes. Only reload on change. | Eliminates unnecessary reloads |
| **Checksum comparison** | Fast checksum (xxhash) of file before reload. Skip if unchanged. | Eliminates unnecessary reloads |
| **Scheduled auto-refresh** | Auto-refresh every N minutes in background. User never waits. | Perceived instant |

---

### Recommended Priority Order

| Priority | Strategy | Effort | Impact |
|----------|----------|--------|--------|
| 1 | **QThread for loading/saving** | Low | High (perceived) |
| 2 | **Parquet or Pickle cache** | Low | High (5-20x cache load) |
| 3 | **Direct ZIP/XML save** | Medium | High (5-10x save) |
| 4 | **File watcher for refresh** | Low | Medium |
| 5 | **Two-tier cache (light + full)** | Medium | High (startup) |
| 6 | **Separate data from presentation** | High | Very High (long-term) |
| 7 | **SQLite for partial loading** | High | Very High (scalability) |

---

### Quick Wins (Implemented Today)

1. **Replace CSV with Pickle** — 3 lines of code change, 3-10x faster cache load.
2. **Move `load_units()` to QThread** — UI shows immediately, data loads in background.
3. **Move `save_unit()` to QThread** — UI doesn't freeze on save.
4. **Add `QFileSystemWatcher`** — Auto-refresh only when file changes.