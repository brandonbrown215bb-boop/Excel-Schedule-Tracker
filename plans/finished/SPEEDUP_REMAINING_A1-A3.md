# Speedup Remaining A1-A3: Auto-Refresh, Loading Spinner, Refresh Cooldown

**Group:** A — Low Effort, Low Volatility (safe wins)
**Total Effort:** ~0.6 day
**Risk:** Low

---

## A1. Scheduled Auto-Refresh

**Effort:** ~0.25 day | **Risk:** Low

### Problem

Users must manually click Refresh (or Reload Excel) to see changes made externally. The file watcher handles this when the Excel file changes on disk, but there's no periodic background refresh for cases where the file watcher misses an event (network drive flakiness, rapid succession of saves, file replaced by a different inode).

### Design

Add a `QTimer` in `MainWindow` that periodically calls `_load_data_async(force_reload=False)` (cache-first reload). The interval is configurable via `config.yaml`. The timer pauses while I/O is in progress to avoid stacking loads.

### Current Context

- `MainWindow.__init__` starts a `LoadWorker` at line 265: `self._load_data_async(force_reload=False)`
- `_load_data_async(force_reload)` at line 428: guarded by `_io_busy` flag, spawns `LoadWorker` QThread
- `_refresh_data()` at line 475: calls `_load_data_async(force_reload=False)`
- `_reload_from_excel()` at line 479: calls `_load_data_async(force_reload=True)`
- File watcher (`_on_file_changed` line 492) already has coalesce logic and IO-busy guard

### Changes to `gui/main_window.py`

**New attributes in `__init__`:**
```python
# After self._file_poll_timer = None (line 128)
self._auto_refresh_timer: QTimer | None = None
```

**New method — start the auto-refresh timer (call at end of `__init__`):**
```python
def _setup_auto_refresh(self) -> None:
    """Start a periodic background refresh timer."""
    interval_min = self.config.get("ui", {}).get("auto_refresh_minutes", 0)
    if interval_min <= 0:
        return  # disabled

    interval_ms = interval_min * 60 * 1000
    self._auto_refresh_timer = QTimer(self)
    self._auto_refresh_timer.setInterval(interval_ms)
    self._auto_refresh_timer.timeout.connect(self._on_auto_refresh)
    self._auto_refresh_timer.start()
    print(f"MainWindow: Auto-refresh every {interval_min} minute(s)")
    self.status_bar.showMessage(f"Auto-refresh: {interval_min}min", 3000)
```

**New method — auto-refresh tick:**
```python
def _on_auto_refresh(self) -> None:
    """Called by auto-refresh timer. Skips if I/O is busy or a save is pending."""
    if getattr(self, "_io_busy", False):
        return
    if self._active_save_worker_running():
        return
    # Cache-first reload — don't force a full Excel parse
    self._load_data_async(force_reload=False)
```

**Modify `_on_file_changed` to reset the auto-refresh timer** (so the auto-refresh doesn't fire immediately after a manual/external refresh):
```python
# At end of _check_file_ready(), after successful load:
def _on_auto_refresh_reset(self) -> None:
    """Reset the auto-refresh timer after a manual/external refresh."""
    if self._auto_refresh_timer and self._auto_refresh_timer.isActive():
        self._auto_refresh_timer.start()  # restart the interval
```

But this is unnecessary complexity — auto-refresh is harmless after a manual refresh since `_io_busy` guard prevents stacking. Keep it simple.

**Integration point:** Add `self._setup_auto_refresh()` at the very end of `__init__`, after `self._load_data_async(force_reload=False)` at line 265.

### Changes to `config.yaml`

```yaml
ui:
  # ... existing fields ...
  auto_refresh_minutes: 5    # 0 = disabled, any positive int = interval in minutes
```

### Changes to `AGENTS.md`

Add `auto_refresh_minutes` to the config table:
```
| `ui.auto_refresh_minutes` | Auto-refresh interval in minutes (0 = disabled) |
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| auto_refresh_minutes: 0 | Timer never created. No auto-refresh. |
| auto_refresh_minutes: 1 | Refreshes every 60 seconds. Safe because cache-first. |
| Excel file locked during auto-refresh | `_load_data_async` → `LoadWorker` → `load_units()` → cache-hit → returns instantly. If cache is stale, falls back to CSV/Excel parse; if file locked, rescue path uses stale cache. No crash. |
| User clicks Refresh while auto-refresh fires | `_io_busy` guard in `_load_data_async` returns early. Auto-refresh tick is silently dropped. |
| Auto-refresh fires while save is in progress | `_active_save_worker_running()` check returns True → auto-refresh skips. |
| User changes config and restarts | New interval applies on restart. No hot-reload (out of scope). |

### Test Plan

1. Set `auto_refresh_minutes: 1` in config → launch app → verify load occurs ~60s after startup
2. Set `auto_refresh_minutes: 0` → verify no timer created (check logs for absence of "Auto-refresh" message)
3. Trigger a manual refresh while auto-refresh fires → verify no stacked loads (check `_io_busy` guard in logs)
4. Start a save, verify auto-refresh tick doesn't interrupt it

---

## A2. Loading Spinner / Skeleton State

**Effort:** ~0.25 day | **Risk:** Low

### Problem

When data loads for the first time or during a force-reload (which can take 57+ seconds for the slow Excel path), the UI shows a brief "Loading..." in the status bar but otherwise appears frozen. Users don't know whether the app is doing work or stuck.

### Design

Add a visual loading overlay that appears while `_io_busy` is True and disappears when loading finishes. The overlay is a semi-transparent QWidget placed over the central widget with a spinner animation and message text. No changes to the existing load/save flow — just UI polish.

### Current Context

- `_io_busy` flag is set/cleared via `_set_io_busy(True/False)` at lines 436 and 571
- `_on_load_finished` (line 447) sets `_io_busy = False`
- `_on_load_error` (line 461) sets `_io_busy = False`
- Save operations do NOT set `_io_busy` — only `_load_data_async` does
- The status bar message "Loading..." is set at line 435

### New File: `gui/loading_overlay.py`

```python
"""
gui/loading_overlay.py — Semi-transparent loading spinner overlay.

Appears over the central widget while I/O is in progress.
Disappears when loading finishes or errors.

Usage (in MainWindow):
    self.loading_overlay = LoadingOverlay(self.centralWidget())
    self.loading_overlay.show_with_message("Loading units...")
    # ... async load ...
    self.loading_overlay.hide()

Uses QTimer-based spinner animation — no threading needed.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy


class LoadingOverlay(QWidget):
    """Semi-transparent overlay with a spinning indicator and message."""

    SPINNER_RADIUS = 16
    SPINNER_WIDTH = 4
    SPINNER_SEGMENTS = 8  # number of arc positions

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setVisible(False)

        # Block mouse events to the underlying widgets while loading
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Center layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Message label
        self._label = QLabel("Loading...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                color: #3b82f6;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
                padding: 4px 12px;
            }
        """)
        layout.addWidget(self._label)

        # Spinner animation state
        self._angle: float = 0.0  # current rotation in degrees
        self._spinner_timer: QTimer | None = None

    def show_with_message(self, message: str = "Loading...") -> None:
        """Show the overlay and start the spinner animation."""
        self._label.setText(message)
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

        # Start spinner animation (30fps)
        if self._spinner_timer is None:
            self._spinner_timer = QTimer(self)
            self._spinner_timer.setInterval(33)  # ~30fps
            self._spinner_timer.timeout.connect(self._advance_spinner)
        self._angle = 0.0
        self._spinner_timer.start()

    def hide(self) -> None:
        """Hide the overlay and stop the spinner."""
        if self._spinner_timer and self._spinner_timer.isActive():
            self._spinner_timer.stop()
        super().hide()

    def _advance_spinner(self) -> None:
        """Advance the spinner by one frame."""
        self._angle = (self._angle + 30) % 360  # 30° per frame = 360° in ~0.33s
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Semi-transparent dark backdrop
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Draw spinner
        center = self.rect().center()
        cx, cy = center.x(), center.y() - 20  # slightly above label

        for i in range(self.SPINNER_SEGMENTS):
            segment_angle = self._angle + (360.0 / self.SPINNER_SEGMENTS) * i
            alpha = int(255 * (i / self.SPINNER_SEGMENTS))  # fade towards end
            painter.setPen(QPen(QColor(59, 130, 246, alpha), self.SPINNER_WIDTH))
            painter.setBrush(Qt.NoBrush)

            # Draw an arc for this segment
            start_angle = int(segment_angle * 16)  # Qt uses 1/16th degrees
            span_angle = int((360.0 / self.SPINNER_SEGMENTS) * 16)
            painter.drawArc(
                cx - self.SPINNER_RADIUS,
                cy - self.SPINNER_RADIUS,
                self.SPINNER_RADIUS * 2,
                self.SPINNER_RADIUS * 2,
                start_angle,
                span_angle,
            )

        painter.end()

    def resizeEvent(self, event) -> None:
        """Re-cover the parent when resized."""
        super().resizeEvent(event)
        self.setGeometry(self.parent().rect())
```

### Changes to `gui/main_window.py`

**New import:**
```python
from gui.loading_overlay import LoadingOverlay
```

**New attribute in `__init__` (after building central widget, before `_load_data_async`):**
```python
# Loading overlay
self.loading_overlay = LoadingOverlay(central)
```

**Modify `_load_data_async` to show overlay:**
```python
def _load_data_async(self, force_reload: bool = False):
    if getattr(self, "_io_busy", False):
        print("MainWindow: Load requested but I/O already in progress — skipping")
        self.status_bar.showMessage("Please wait — operation in progress...", 2000)
        return
    self.status_bar.showMessage("Loading..." if not force_reload else "Refreshing...")

    # Show overlay
    msg = "Reloading from Excel..." if force_reload else "Loading..."
    self.loading_overlay.show_with_message(msg)

    self._set_io_busy(True)
    self._load_worker = LoadWorker(...)
    ...
```

**Modify `_on_load_finished` to hide overlay:**
```python
def _on_load_finished(self, units: list[Unit]):
    self.loading_overlay.hide()
    self._set_io_busy(False)
    ...
```

**Modify `_on_load_error` to hide overlay:**
```python
def _on_load_error(self, error_msg: str):
    self.loading_overlay.hide()
    self._set_io_busy(False)
    ...
```

### Theme Integration

The overlay draws a fixed `#3b82f6` blue spinner and a dark `rgba(0,0,0,100)` backdrop. These are hardcoded for simplicity — the overlay is temporary during load. If the app uses dark theme, the dark backdrop is slightly less jarring, and the blue spinner is the same accent color used in theme tokens. No theme-awareness needed for this v1.

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Fast load (<100ms from cache) | Overlay appears and disappears instantly — may flicker. Mitigation: if load finishes in <200ms, skip showing the overlay entirely. |
| Load error | Overlay hidden in `_on_load_error`. Error message box shown afterward. |
| App resized during load | Overlay `resizeEvent` re-covers parent. |
| Force reload takes 57s | Overlay stays visible throughout. Label says "Reloading from Excel...". |
| Multiple rapid refreshes | Guarded by `_io_busy` — second call is dropped. Overlay stays up from first call. |
| Dark theme | Dark backdrop is invisible-on-dark; overlay still covers UI elements. Acceptable for v1. |

### Flicker Mitigation

Add a minimum display time to avoid flashing for fast loads:

```python
def __init__(self, parent):
    ...
    self._show_timestamp: float = 0.0
    self._MIN_VISIBLE_MS = 200  # minimum 200ms visible

def show_with_message(self, message: str) -> None:
    import time
    self._show_timestamp = time.monotonic()
    ...

def hide(self) -> None:
    import time
    elapsed_ms = (time.monotonic() - self._show_timestamp) * 1000
    if elapsed_ms < self._MIN_VISIBLE_MS:
        # Delay hide via timer so the overlay is visible long enough
        QTimer.singleShot(int(self._MIN_VISIBLE_MS - elapsed_ms), self._do_hide)
    else:
        self._do_hide()

def _do_hide(self) -> None:
    if self._spinner_timer and self._spinner_timer.isActive():
        self._spinner_timer.stop()
    super().hide()
```

### Unit Tests (`tests/test_loading_overlay.py`)

```python
import pytest
from PyQt5.QtWidgets import QWidget, QApplication
from gui.loading_overlay import LoadingOverlay


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_create_and_show(qapp):
    parent = QWidget()
    overlay = LoadingOverlay(parent)
    overlay.show_with_message("Testing...")
    assert overlay.isVisible()
    assert overlay._label.text() == "Testing..."
    overlay.hide()
    assert not overlay.isVisible()


def test_hide_stops_timer(qapp):
    parent = QWidget()
    overlay = LoadingOverlay(parent)
    overlay.show_with_message("Test")
    assert overlay._spinner_timer is not None
    assert overlay._spinner_timer.isActive()
    overlay.hide()
    assert not overlay._spinner_timer.isActive()
```

### Test Plan

1. Launch app → verify overlay appears briefly, then disappears when data loads
2. Click "Reload Excel" → verify overlay shows "Reloading from Excel..." for the duration
3. Simulate load error → verify overlay hides and error dialog appears
4. Resize window during load → verify overlay covers the expanded area
5. Rapid clicks on Refresh → verify only one load starts, overlay stays visible
6. Fast cache load (<200ms) → verify overlay doesn't flicker (minimum display time)

---

## A3. Refresh Cooldown / Debounce

**Effort:** ~0.1 day | **Risk:** Low

### Problem

Users can click the Refresh button or Reload Excel button rapidly, stacking multiple `_load_data_async` calls. Currently, the `_io_busy` guard in `_load_data_async` prevents the second call from starting, but the button still appears clickable. This creates a dead-click UX: user clicks Refresh, nothing seems to happen (because it's ignored), clicks again, still nothing, assumes the app is broken.

### Design

Disable the Refresh and Reload Excel buttons for a cooldown period after each click. Show a countdown tooltip to give visual feedback. The cooldown only applies to user-initiated refreshes — the file watcher and auto-refresh timer are unaffected.

### Current Context

- Refresh button at line 606-609: `QPushButton("🔄 Refresh")`, `_refresh_data` connected
- Reload Excel button at line 612-616: `QPushButton("Reload Excel")`, `_reload_from_excel` connected
- `_refresh_data()` (line 475) calls `_load_data_async(force_reload=False)`
- `_reload_from_excel()` (line 479) calls `_load_data_async(force_reload=True)`
- `_io_busy` guard at line 431 prevents stacked loads
- `_build_automation_bar()` at line 577 creates both buttons with object names `refresh_btn` and `reload_btn`

### Changes to `gui/main_window.py`

**New method — apply cooldown to both refresh buttons:**
```python
def _apply_refresh_cooldown(self) -> None:
    """Disable refresh buttons for COOLDOWN seconds, with countdown tooltip."""
    COOLDOWN = 3  # seconds

    buttons: list[QPushButton] = []
    for name in ("refresh_btn", "reload_btn"):
        btn = self.findChild(QPushButton, name)
        if btn:
            buttons.append(btn)

    for btn in buttons:
        btn.setEnabled(False)

    # Countdown timer — update tooltip every second
    remaining = [COOLDOWN]  # mutable for closure

    def tick():
        remaining[0] -= 1
        if remaining[0] > 0:
            for btn in buttons:
                btn.setToolTip(f"Refresh ready in {remaining[0]}s...")
        else:
            timer.stop()
            for btn in buttons:
                btn.setEnabled(True)
                btn.setToolTip(btn.objectName() == "refresh_btn" and
                               "Reload data from Excel file" or
                               "Force a full reload from the Excel workbook")

    timer = QTimer(self)
    timer.setInterval(1000)
    timer.timeout.connect(tick)
    timer.start()
    tick()  # immediate first update
```

**Modify `_refresh_data` to apply cooldown:**
```python
def _refresh_data(self):
    """Refresh data from Excel (async)."""
    self._apply_refresh_cooldown()
    self._load_data_async(force_reload=False)
```

**Modify `_reload_from_excel` to apply cooldown:**
```python
def _reload_from_excel(self):
    """Force a full Excel parse, bypassing cache."""
    self._apply_refresh_cooldown()
    self._load_data_async(force_reload=True)
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User clicks Refresh, then immediately clicks again | Second click is a no-op (button is disabled). Tooltip shows "Refresh ready in 2s..." |
| User clicks Reload Excel during cooldown | Button is disabled — only affects the clicked button's cooldown path. Both buttons share the same cooldown. |
| File watcher fires during cooldown | Watcher calls `_on_file_changed` → `_check_file_ready` → `_load_data_async` directly (not through `_refresh_data`). Not affected by button cooldown. |
| Auto-refresh fires during cooldown | Timer calls `_on_auto_refresh` → `_load_data_async` directly. Not affected by button cooldown. |
| App closed during countdown | Timer is parented to `self` (MainWindow), auto-deleted when MainWindow is destroyed. No resource leak. |
| Cooldown expires while another load is in progress | `_io_busy` guard in `_load_data_async` still prevents stacked loads. Button becomes enabled but click is silently dropped. Safe. |

### Test Plan

1. Click Refresh → verify button is disabled for 3 seconds with countdown tooltip
2. Rapidly click Refresh 5 times → verify only one `_load_data_async` call (check logs for "skipping")
3. Click Refresh, wait 3 seconds → verify button re-enables with original tooltip
4. Click Reload Excel during Refresh cooldown → verify button is also disabled (shared cooldown)
5. Verify file watcher still works during cooldown (not affected by button state)
6. Verify auto-refresh timer still works during cooldown (not affected by button state)

---

## Execution Plan

### Step 1: A3 — Refresh Cooldown (~0.1 day)
1. Add `_apply_refresh_cooldown()` method to `MainWindow`
2. Modify `_refresh_data()` and `_reload_from_excel()` to call it
3. Test: click refresh, verify button disables for 3s
4. *File:* `gui/main_window.py` only

### Step 2: A2 — Loading Overlay (~0.25 day)
1. Create `gui/loading_overlay.py`
2. Wire into `MainWindow` — create overlay, show/hide around `_load_data_async`
3. Add flicker mitigation (minimum 200ms visible)
4. Unit test in `tests/test_loading_overlay.py`
5. Test: verify overlay appears on slow loads, hides on finish/error

### Step 3: A1 — Auto-Refresh Timer (~0.15 day)
1. Add `_setup_auto_refresh()` to `MainWindow.__init__`
2. Add `_on_auto_refresh()` timer callback
3. Add `auto_refresh_minutes` to `config.yaml`
4. Test: set 1-minute interval, verify refresh occurs after 60s
5. *Files:* `gui/main_window.py`, `config.yaml`

### Step 4: Documentation (~0.05 day)
1. Add `auto_refresh_minutes` to config table in `AGENTS.md`
2. Add `gui/loading_overlay.py` to repository layout in `AGENTS.md`

---

## Files Changed Summary

| File | Change | Lines |
|------|--------|-------|
| `gui/main_window.py` | Add A1 timer + A2 overlay show/hide + A3 cooldown | ~40 new lines |
| `gui/loading_overlay.py` | **New file** — LoadingOverlay QWidget | ~130 lines |
| `tests/test_loading_overlay.py` | **New file** — tests for overlay | ~30 lines |
| `config.yaml` | Add `auto_refresh_minutes` under `ui:` | 1 line |
| `AGENTS.md` | Document new config field + new file | ~5 lines |

---

## Testing Checklist

- [ ] Auto-refresh fires at configured interval (A1)
- [ ] Auto-refresh disabled when interval = 0 (A1)
- [ ] Auto-refresh skips when I/O busy (A1)
- [ ] Loading overlay appears during `_load_data_async` (A2)
- [ ] Loading overlay hides on `_on_load_finished` (A2)
- [ ] Loading overlay hides on `_on_load_error` (A2)
- [ ] Fast cache loads (<200ms) don't flicker the overlay (A2)
- [ ] Overlay resizes with main window (A2)
- [ ] Overlay blocks clicks to underlying widgets (A2)
- [ ] Refresh button disabled for 3s after click (A3)
- [ ] Reload Excel button shares the same cooldown (A3)
- [ ] Countdown tooltip updates every second (A3)
- [ ] File watcher works during button cooldown (A3)
- [ ] Auto-refresh fires during button cooldown (A3)
- [ ] `config.yaml` accepts `auto_refresh_minutes: 0` gracefully (A1)
- [ ] All existing tests still pass (`pytest`)