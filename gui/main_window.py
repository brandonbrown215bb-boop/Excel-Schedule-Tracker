# gui/main_window.py
import os
import time

from PyQt5.QtCore import QFileSystemWatcher, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QKeyEvent  # type: ignore[reportMissingImports]
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSplitter,  # Added for adjustable main layout
    QVBoxLayout,
    QWidget,
)

from data.loader import load_units, save_csv_cache, unit_fingerprint
from data.models import Unit
from data.writer import save_unit
from gui.calendar_panel import CalendarPanel
from gui.conflict_dialog import ConflictDialog
from gui.edit_form import EditForm
from gui.list_panel import ListPanel
from gui.loading_overlay import LoadingOverlay
from gui.onboarding import should_show_onboarding, show_onboarding
from gui.timeline_panel import TimelinePanel
from sync.revision_store import RevisionConflictError

# Lazy imports (inside methods):
#   automation.csv_sync.pull_and_sync  (in _pull_csv)
#   sync.lock_manager.LockManager      (in _setup_multi_user_sync)
#   sync.revision_store.RevisionStore  (in _setup_multi_user_sync)
#   sync.session_registry.SessionRegistry (in _setup_multi_user_sync)
#   sync.shared_cache.SharedCache      (in _setup_multi_user_sync)


class LoadWorker(QThread):
    """Background worker for loading units."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self, excel_path: str, sheet_name: str, detailer_schedules: dict, force_reload: bool = False
    ):
        super().__init__()
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.detailer_schedules = detailer_schedules
        self.force_reload = force_reload

    def run(self):
        try:
            units = load_units(
                self.excel_path,
                self.sheet_name,
                detailer_schedules=self.detailer_schedules,
                force_reload=self.force_reload,
            )
            self.finished.emit(units)
        except Exception as e:
            self.error.emit(str(e))


class SaveWorker(QThread):
    """Background worker for saving units.

    Emits ``finished`` on success, ``error(str)`` on generic errors, and
    ``conflict(RevisionConflictError)`` when a revision conflict is detected.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)
    conflict = pyqtSignal(object)  # RevisionConflictError

    def __init__(
        self,
        excel_path: str,
        sheet_name: str,
        unit: Unit,
        all_units: list[Unit],
        lock_manager=None,
        revision_store=None,
        owner_id: str = "local",
        force: bool = False,
    ):
        super().__init__()
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.unit = unit
        self.all_units = all_units
        self.lock_manager = lock_manager
        self.revision_store = revision_store
        self.owner_id = owner_id
        self.force = force

    def run(self):
        try:
            if self.lock_manager and self.revision_store:
                with self.lock_manager.commit_lock():
                    if not self.force:
                        base_revision = self.unit.base_revision or self.revision_store.baseline(
                            self.unit.com_number
                        )
                    else:
                        base_revision = self.revision_store.baseline(self.unit.com_number)
                    with self.lock_manager.write_lock():
                        save_unit(
                            self.excel_path, self.unit, self.sheet_name,
                            force=self.force,
                        )
                        revision = self.revision_store.commit(
                            self.unit.com_number,
                            base_revision,
                            unit_fingerprint(self.unit),
                            self.owner_id,
                            unit=self.unit,
                        )
                        self.unit.base_revision = revision.revision
            elif self.lock_manager:
                with self.lock_manager.write_lock():
                    save_unit(self.excel_path, self.unit, self.sheet_name)
            else:
                save_unit(self.excel_path, self.unit, self.sheet_name)
            save_csv_cache(self.excel_path, self.all_units)
            self.finished.emit()
        except RevisionConflictError as e:
            self.conflict.emit(e)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, config: dict, config_path: str | None = None):
        super().__init__()
        self.config = config
        self.units: list[Unit] = []
        self.current_unit: Unit | None = None
        self._load_worker: LoadWorker | None = None
        self._save_worker: SaveWorker | None = None
        self.lock_manager = None
        self.revision_store = None
        self.owner_id = "local"
        self._sync_save_blocked = False
        self._pending_excel_sync: dict[str, Unit] = {}
        self._debounce_flush_timer: QTimer | None = None
        self._shared_cache = None
        self._session_registry = None
        self._presence_label: QLabel | None = None
        self._presence_poll_timer: QTimer | None = None
        self._retired_save_workers: list[SaveWorker] = []
        self._save_worker_errors: dict[SaveWorker, str] = {}
        self._file_poll_timer: QTimer | None = None
        self._auto_refresh_timer: QTimer | None = None
        self._form_dirty = False

        # ── Theme initialization (before any panel is built) ──
        from gui.theme import init_labels, apply_theme
        init_labels(config.get("status_labels", {}))
        ui_cfg = config.get("ui", {})
        self._current_theme_name = ui_cfg.get("theme", "light")
        self._current_cvd: str = ui_cfg.get("colorblind_mode", "none")
        self._current_hc: bool = ui_cfg.get("high_contrast", False)
        apply_theme(self, self._current_theme_name,
                    cvd_mode=self._current_cvd,
                    high_contrast=self._current_hc)
        self._config_path = config_path  # Passed from main(); not injected into config dict

        self.setWindowTitle("Unit Tracker")
        self.setMinimumSize(1200, 700)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("status_bar")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Loading...")
        print("MainWindow: Initializing status bar...")

        # Build UI first (with empty data)
        print("MainWindow: Building UI components...")
        central = QWidget()
        self.setCentralWidget(central)
        # Use QSplitter for adjustable main layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout = QHBoxLayout(central)  # Use QHBoxLayout as parent for splitter
        main_layout.addWidget(self.main_splitter)

        print("MainWindow: Central widget and main layout created.")

        # ── Left: view toggle + stacked panel ──
        left_widget = QWidget()
        left_container = QVBoxLayout(left_widget)

        # View toggle buttons
        toggle_layout = QHBoxLayout()
        self.calendar_view_btn = QPushButton("📅 Calendar")

        self.list_view_btn = QPushButton("\U0001f4cb List")
        self.list_view_btn.setObjectName("list_view_btn")
        self.calendar_view_btn.setCheckable(True)
        self.list_view_btn.setCheckable(True)
        self.calendar_view_btn.setChecked(True)
        self.calendar_view_btn.clicked.connect(lambda: self._switch_view("calendar"))
        self.list_view_btn.clicked.connect(lambda: self._switch_view("list"))
        toggle_layout.addWidget(self.calendar_view_btn)
        toggle_layout.addWidget(self.list_view_btn)
        toggle_layout.addStretch()

        # Theme toggle button
        self.theme_btn = QPushButton("☀" if self._current_theme_name == "dark" else "🌙")
        self.theme_btn.setObjectName("theme_btn")
        self.theme_btn.setToolTip("Toggle dark/light theme (Ctrl+T)")
        self.theme_btn.clicked.connect(self._toggle_theme)
        toggle_layout.addWidget(self.theme_btn)

        # Accessibility settings button
        self.a11y_btn = QPushButton("♿")
        self.a11y_btn.setObjectName("a11y_btn")
        self.a11y_btn.setToolTip("Accessibility settings")
        self.a11y_btn.clicked.connect(self._open_a11y_dialog)
        toggle_layout.addWidget(self.a11y_btn)

        left_container.addLayout(toggle_layout)

        # Stacked widget: calendar at index 0, list at index 1
        self.view_stack = QStackedWidget()
        self.view_stack.setObjectName("view_stack")

        print("MainWindow: Creating CalendarPanel...")
        self.calendar_panel = CalendarPanel(self.units)
        self.calendar_panel.unit_selected.connect(self.on_unit_selected)
        self.view_stack.addWidget(self.calendar_panel)  # index 0
        print("MainWindow: CalendarPanel created and added to stack.")

        print("MainWindow: Creating ListPanel...")
        self.list_panel = ListPanel(self.units)
        self.list_panel.unit_selected.connect(self.on_unit_selected)
        self.view_stack.addWidget(self.list_panel)  # index 1
        print("MainWindow: ListPanel created and added to stack.")

        left_container.addWidget(self.view_stack)
        self.main_splitter.addWidget(left_widget)  # Add left widget to splitter

        # Restore saved view preference
        saved_view = self.config.get("ui", {}).get("last_view", "calendar")
        if saved_view == "list":
            self._switch_view("list")
        print("MainWindow: Left panel (stacked) added to main layout.")

        # Right: Timeline + Edit Form + Buttons
        right_widget = QWidget()
        right_panel = QVBoxLayout(right_widget)
        print("MainWindow: Right panel layout created.")

        print("MainWindow: Creating TimelinePanel...")
        self.timeline_panel = TimelinePanel()
        right_panel.addWidget(self.timeline_panel)
        print("MainWindow: TimelinePanel created and added.")

        print("MainWindow: Creating EditForm...")
        self.edit_form = EditForm(default_detailers=self.config.get("default_detailers", []))
        self.edit_form.saved.connect(self.on_save_unit)
        self.edit_form.dirty_changed.connect(self._on_dirty_changed)
        right_panel.addWidget(self.edit_form, 1)
        print("MainWindow: EditForm created and added.")

        # Automation buttons
        print("MainWindow: Building automation bar...")
        auto_bar = self._build_automation_bar()
        right_panel.addLayout(auto_bar)
        print("MainWindow: Automation bar built and added.")

        self.main_splitter.addWidget(right_widget) # Add right widget to splitter
        print("MainWindow: Right panel added to main layout.")

        # Restore splitter sizes
        saved_sizes = self.config.get("ui", {}).get("splitter_sizes")
        if saved_sizes:
            self.main_splitter.setSizes(saved_sizes)
        else:
            # Default split: 1/3 for left, 2/3 for right
            self.main_splitter.setSizes([self.width() // 3, 2 * self.width() // 3])

        # Loading overlay (A2)
        self.loading_overlay = LoadingOverlay(central)

        # Setup file watcher for auto-refresh
        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.fileChanged.connect(self._on_file_changed)
        self._setup_file_watcher()
        self._setup_multi_user_sync()

        # Setup auto-refresh timer (A1)
        self._setup_auto_refresh()

        # Build Help menu (with Show Walkthrough action)
        self._build_help_menu()

        # Show onboarding on first launch (after UI is ready)
        if should_show_onboarding(self.config):
            # Delay 500ms so the window is fully painted first
            QTimer.singleShot(500, lambda: show_onboarding(self, self.config))

        # Load data in background
        print("MainWindow: Starting background load...")
        self._load_data_async(force_reload=False)

    # ── Help menu ──────────────────────────────────────────────────────

    def _build_help_menu(self):
        """Build the Help menu with walkthrough and about actions."""
        menubar = self.menuBar()
        help_menu = menubar.addMenu("&Help")

        # Show Walkthrough
        walkthrough_action = help_menu.addAction("&Show Walkthrough")
        walkthrough_action.setToolTip("Show the onboarding walkthrough")
        walkthrough_action.triggered.connect(
            lambda: show_onboarding(self, self.config)
        )

        help_menu.addSeparator()

        # About
        about_action = help_menu.addAction("&About Unit Tracker")
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Unit Tracker",
            "<b>Unit Tracker</b><br><br>"
            "A desktop viewer/editor for detailing schedules.<br>"
            f"Python {__import__('sys').version.split()[0]} | "
            f"PyQt5 | openpyxl<br><br>"
            "© 2026",
        )

    # ── View switching ─────────────────────────────────────────────────

    def _switch_view(self, view_name: str) -> None:
        """Swap between calendar and list views."""
        if view_name == "calendar":
            self.view_stack.setCurrentIndex(0)
            self.calendar_view_btn.setChecked(True)
            self.list_view_btn.setChecked(False)
        elif view_name == "list":
            self.view_stack.setCurrentIndex(1)
            self.calendar_view_btn.setChecked(False)
            self.list_view_btn.setChecked(True)
            # Populate list panel if it has no data yet
            if self.units and self.list_panel._model is None:
                self.list_panel.set_units(self.units)

        # Save preference
        self.config.setdefault("ui", {})["last_view"] = view_name
        print(f"MainWindow: Switched to {view_name} view.")

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._form_dirty = dirty

    def _confirm_discard(self) -> bool:
        """Return True if it's safe to discard unsaved changes."""
        if not getattr(self, "_form_dirty", False):
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    # ── Selection + Save ───────────────────────────────────────────────

    def on_unit_selected(self, unit: Unit | None):
        if not self._confirm_discard():
            return
        self.current_unit = unit
        self.timeline_panel.set_unit(unit)
        self.edit_form.set_unit(unit)
        if unit is not None:
            self.status_bar.showMessage(f"Selected: COM {unit.com_number} — {unit.job_name}")
        else:
            self.status_bar.showMessage("No unit selected")

    def on_save_unit(self, unit: Unit):
        """Save unit — commit to memory and cache immediately,
        then debounce the Excel write."""
        if self._sync_save_blocked:
            QMessageBox.warning(
                self,
                "Save Disabled",
                "Multi-user sync is configured to block saves when locking is unavailable.",
            )
            return
        self._commit_unit_to_memory(unit)
        save_csv_cache(self.config["excel_path"], self.units)
        self.calendar_panel.refresh(self.units)
        self.list_panel.refresh(self.units)
        self.timeline_panel.set_unit(unit)
        self.edit_form.current_unit = unit
        self.status_bar.showMessage(
            f"✓ Saved COM {unit.com_number} locally — queuing Excel sync...", 3000
        )

        # Queue for debounced background flush
        self._pending_excel_sync[unit.com_number] = unit
        self._restart_debounce_flush()

    def _restart_debounce_flush(self) -> None:
        """Start or restart the debounce timer that triggers the batch flush."""
        DEBOUNCE_MS = 5000  # 5 seconds
        self._stop_debounce_flush()
        self._debounce_flush_timer = QTimer(self)
        self._debounce_flush_timer.setSingleShot(True)
        self._debounce_flush_timer.setInterval(DEBOUNCE_MS)
        self._debounce_flush_timer.timeout.connect(self._flush_pending_syncs)
        self._debounce_flush_timer.start()

    def _stop_debounce_flush(self) -> None:
        timer = self._debounce_flush_timer
        self._debounce_flush_timer = None
        if timer is None:
            return
        try:
            timer.stop()
            timer.deleteLater()
        except RuntimeError:
            pass

    def _flush_pending_syncs(self) -> None:
        """Batch flush all queued saves to Excel in one background worker."""
        if not self._pending_excel_sync:
            return
        if self._active_save_worker_running():
            # Worker still running — restart debounce and retry later
            self._restart_debounce_flush()
            return

        # Grab the first pending unit for the worker (worker processes one unit)
        com_number, unit = self._pending_excel_sync.popitem(last=False)
        self.status_bar.showMessage(
            f"Flushing COM {com_number} to Excel ({len(self._pending_excel_sync)} queued)..."
        )
        self._start_excel_sync(unit)

    def _start_excel_sync(self, unit: Unit, force: bool = False) -> None:
        """Start the background workbook write for an already-committed unit."""
        worker = SaveWorker(
            self.config["excel_path"],
            self.config.get("sheet_name", "Sheet1"),
            unit,
            self.units,
            self.lock_manager,
            self.revision_store,
            self.owner_id,
            force=force,
        )
        self._save_worker = worker
        worker.finished.connect(
            lambda worker=worker, unit=unit: self._on_save_finished(unit, worker)
        )
        worker.error.connect(
            lambda error_msg, worker=worker: self._on_save_error(error_msg, worker)
        )
        worker.conflict.connect(
            lambda exc, worker=worker: self._on_save_conflict(exc, worker)
        )
        worker.destroyed.connect(lambda _=None, worker=worker: self._release_save_worker(worker))
        worker.start()

    def _on_save_finished(self, unit: Unit, worker: SaveWorker):
        """Handle successful excel sync.

        After we write to Excel, the Pickle cache is already fresh.
        The in-memory list is already updated. We just need to refresh the UI.
        Do NOT trigger a file-watcher reload — that would re-parse Excel (57s).
        """
        self._retire_save_worker(worker)
        if worker in self._save_worker_errors:
            return
        if self._pending_excel_sync:
            # Flush next queued unit
            com_number, next_unit = self._pending_excel_sync.popitem(last=False)
            self.status_bar.showMessage(
                f"Flushing COM {com_number} to Excel ({len(self._pending_excel_sync)} queued)..."
            )
            self._start_excel_sync(next_unit)
            return
        self.status_bar.showMessage(f"✓ Synced COM {unit.com_number} to Excel", 5000)

    def _on_save_error(self, error_msg: str, worker: SaveWorker | None = None):
        """Handle save error."""
        if worker is not None:
            self._save_worker_errors[worker] = error_msg
        QMessageBox.warning(
            self,
            "Excel Sync Error",
            f"Your changes were saved in the local cache, but Excel sync failed:\n{error_msg}\n\n"
            f"Make sure the Excel file is not open in another program, then save again.",
        )

    def _on_save_conflict(self, exc: RevisionConflictError, worker: SaveWorker):
        """Handle a revision conflict by showing the conflict dialog."""
        self._retire_save_worker(worker)

        # Build local values dict from the unit we tried to save
        local_values = self._unit_to_dict(worker.unit)

        com = exc.latest.com_number
        modified_by = exc.latest.modified_by
        modified_at = exc.latest.modified_at
        remote_values = exc.remote_values

        dlg = ConflictDialog(
            com_number=com,
            local_values=local_values,
            remote_values=remote_values or {},
            modified_by=modified_by,
            modified_at=modified_at,
            parent=self,
        )
        result = dlg.exec_()

        if dlg.overwrite:
            # Force-save ignoring conflict
            self.status_bar.showMessage(f"Overwriting COM {com} (ignoring conflict)...")
            self._start_excel_sync(worker.unit, force=True)
        elif dlg.reload:
            # Discard local changes — re-run the load to get remote version
            self.status_bar.showMessage(f"Reloading COM {com} from shared workbook...")
            self._load_data_async(force_reload=False)

    @staticmethod
    def _unit_to_dict(unit: Unit) -> dict:
        """Extract a dict of field_name -> value for conflict display."""
        return {
            "com_number": unit.com_number,
            "job_name": unit.job_name,
            "contract_number": unit.contract_number,
            "description": unit.description,
            "detailer": unit.detailer,
            "checking_status": unit.checking_status,
            "department_hours": unit.department_hours,
            "target_department_hours": unit.target_department_hours,
            "iec_internal_hours": unit.iec_internal_hours,
            "percent_complete": unit.percent_complete,
            "actual_hours": unit.actual_hours,
            "unit_detailing_start_date": (
                unit.unit_detailing_start_date.isoformat()
                if unit.unit_detailing_start_date else None
            ),
            "unit_moved_to_checking_date": (
                unit.unit_moved_to_checking_date.isoformat()
                if unit.unit_moved_to_checking_date else None
            ),
            "unit_detailing_completion_date": (
                unit.unit_detailing_completion_date.isoformat()
                if unit.unit_detailing_completion_date else None
            ),
            "dept_due_date_previous": (
                unit.dept_due_date_previous.isoformat()
                if unit.dept_due_date_previous else None
            ),
            "detailing_due_date": (
                unit.detailing_due_date.isoformat()
                if unit.detailing_due_date else None
            ),
            "build_date": (
                unit.build_date.isoformat() if unit.build_date else None
            ),
        }

    def _active_save_worker_running(self) -> bool:
        """Return True while the active worker's thread is still alive."""
        worker = self._save_worker
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def _retire_save_worker(self, worker: SaveWorker) -> None:
        """Keep a finished worker referenced until Qt safely deletes it."""
        if self._save_worker is worker:
            self._save_worker = None
        if worker not in self._retired_save_workers:
            self._retired_save_workers.append(worker)
            worker.deleteLater()

    def _release_save_worker(self, worker: SaveWorker) -> None:
        """Drop references after Qt destroys the QThread object."""
        if worker in self._retired_save_workers:
            self._retired_save_workers.remove(worker)
        self._save_worker_errors.pop(worker, None)

    def _commit_unit_to_memory(self, unit: Unit) -> None:
        """Replace the selected unit immediately so navigation shows current edits."""
        unit.status_color = unit.calculated_status_color
        for i, existing in enumerate(self.units):
            if existing.com_number == unit.com_number:
                unit.excel_row = unit.excel_row or existing.excel_row
                unit.fingerprint = unit.fingerprint or existing.fingerprint
                unit.base_revision = unit.base_revision or existing.base_revision
                self.units[i] = unit
                break
        else:
            self.units.append(unit)
        self.current_unit = unit

    # ── Data loading ───────────────────────────────────────────────────

    def _load_data_async(self, force_reload: bool = False):
        """Load data in background thread."""
        # Guard: don't start a new load if one is already in flight
        if getattr(self, "_io_busy", False):
            print("MainWindow: Load requested but I/O already in progress — skipping")
            self.status_bar.showMessage("Please wait — operation in progress...", 2000)
            return
        self.status_bar.showMessage("Loading..." if not force_reload else "Refreshing...")

        # Show loading overlay (A2)
        msg = "Reloading from Excel..." if force_reload else "Loading..."
        self.loading_overlay.show_with_message(msg)

        self._set_io_busy(True)
        self._load_worker = LoadWorker(
            self.config["excel_path"],
            self.config.get("sheet_name", "Sheet1"),
            self.config.get("detailer_schedules", {}),
            force_reload=force_reload,
        )
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_load_finished(self, units: list[Unit]):
        """Handle successful load."""
        self.loading_overlay.hide()
        self._set_io_busy(False)
        self.units = units
        if self.revision_store is not None:
            for unit in self.units:
                unit.base_revision = self.revision_store.baseline(unit.com_number)
        self.calendar_panel.refresh(self.units)
        self.list_panel.set_units(self.units)
        self.status_bar.showMessage(
            f"Loaded {len(self.units)} units from {self.config['excel_path']}"
        )
        print(f"MainWindow: Loaded {len(self.units)} units.")

    def _on_load_error(self, error_msg: str):
        """Handle load error."""
        self.loading_overlay.hide()
        self._set_io_busy(False)
        print(f"MainWindow: Error loading Excel file: {error_msg}")
        QMessageBox.critical(
            self,
            "Load Error",
            f"Failed to load Excel file:\n{error_msg}\n\n"
            f"Check config.yaml — excel_path must point to a valid .xlsx/.xlsm file.",
        )
        self.units = []

    # ── Refresh / VBA / Pull ────────────────────────────────────────────

    def _refresh_data(self):
        """Refresh data from Excel (async)."""
        self._apply_refresh_cooldown()
        self._load_data_async(force_reload=False)

    def _reload_from_excel(self):
        """Force a full Excel parse, bypassing cache."""
        self._apply_refresh_cooldown()
        self._load_data_async(force_reload=True)

    # ── File watcher ───────────────────────────────────────────────────

    def _setup_file_watcher(self):
        """Setup file watcher to auto-refresh when Excel file changes."""
        excel_path = self.config.get("excel_path", "")
        if excel_path and os.path.exists(excel_path):
            self._file_watcher.addPath(excel_path)
            print(f"MainWindow: Watching file {excel_path} for changes")

    def _on_file_changed(self, path: str):
        """Handle file change notification from QFileSystemWatcher.

        Excel (and other editors) lock the file while saving. We must:
        1. Ignore events while we ourselves are mid-load or mid-save
        2. Coalesce rapid duplicate watcher events
        3. Wait (non-blocking) for the file to be fully written before loading
        """
        print(f"MainWindow: Detected change in {path}")

        # Ignore if we're currently loading or saving (prevents save→load→save loops)
        if getattr(self, "_io_busy", False):
            print("MainWindow: Ignoring file change — I/O in progress")
            return
        if self._active_save_worker_running():
            print("MainWindow: Ignoring file change — Excel sync in progress")
            return

        # Coalesce: ignore duplicate events within 5 seconds
        now = time.monotonic()
        if now - getattr(self, "_last_file_change", 0) < 5.0:
            print("MainWindow: Ignoring duplicate file change event (coalesced)")
            return
        self._last_file_change = now

        # Schedule non-blocking file readiness check via QTimer
        self._file_change_path = path
        self._file_deadline = now + 8.0
        self._stop_file_poll_timer()
        self._file_poll_timer = QTimer(self)
        self._file_poll_timer.setSingleShot(False)
        self._file_poll_timer.setInterval(500)  # check every 500ms
        self._file_poll_timer.timeout.connect(self._check_file_ready)
        self._file_poll_timer.start()
        self.status_bar.showMessage("File changed — waiting...", 2000)

    def _check_file_ready(self):
        """Non-blocking check if the changed file is ready to read."""
        import os
        path = self._file_change_path
        deadline = self._file_deadline

        if time.monotonic() > deadline:
            print("MainWindow: File not ready after timeout, skipping reload")
            self._stop_file_poll_timer()
            return

        try:
            if not os.path.exists(path):
                return  # still not ready, wait for next tick
            size = os.path.getsize(path)
            if size < 100:
                return
            with open(path, "rb") as f:
                header = f.read(4)
                if header != b"PK\x03\x04":  # not a valid ZIP/xlsx
                    return
            # File is ready — stop polling
            self._stop_file_poll_timer()

            # Check: is our Pickle cache fresher than this Excel file?
            # If we just saved, the cache is already up-to-date and we
            # should NOT re-parse Excel (which takes ~57s).
            self._load_data_async(force_reload=False)
        except OSError:
            return  # file still locked, wait for next tick

    def _stop_file_poll_timer(self):
        """Stop and clear the file poll timer even if Qt already deleted it."""
        timer = self._file_poll_timer
        self._file_poll_timer = None
        if timer is None:
            return
        try:
            timer.stop()
            timer.deleteLater()
        except RuntimeError:
            pass

    def _set_io_busy(self, busy: bool):
        """Mark I/O as in-progress (prevents watcher from re-triggering)."""
        self._io_busy = busy

    # ── A1: Auto-refresh timer ─────────────────────────────────────────

    def _setup_auto_refresh(self) -> None:
        """Start a periodic background refresh timer (configurable interval)."""
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

    def _on_auto_refresh(self) -> None:
        """Called by auto-refresh timer. Skips if I/O is busy or a save is pending."""
        if getattr(self, "_io_busy", False):
            return
        if self._active_save_worker_running():
            return
        # Cache-first reload — don't force a full Excel parse
        self._load_data_async(force_reload=False)

    # ── A3: Refresh cooldown ───────────────────────────────────────────

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
        remaining = [COOLDOWN]

        def tick():
            remaining[0] -= 1
            if remaining[0] > 0:
                for btn in buttons:
                    btn.setToolTip(f"Refresh ready in {remaining[0]}s...")
            else:
                timer.stop()
                for btn in buttons:
                    btn.setEnabled(True)
                    if btn.objectName() == "refresh_btn":
                        btn.setToolTip("Reload data from Excel file")
                    else:
                        btn.setToolTip("Force a full reload from the Excel workbook")

        timer = QTimer(self)
        timer.setInterval(1000)
        timer.timeout.connect(tick)
        timer.start()
        tick()  # immediate first update

    # ── Automation bar ─────────────────────────────────────────────────

    def _build_automation_bar(self):
        outer = QVBoxLayout()
        outer.setSpacing(4)

        # Row 1: Macro selector + Run
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("VBA Macro:"))

        self.macro_combo = QComboBox()
        self.macro_combo.setObjectName("macro_combo")
        self.macro_combo.setEditable(True)
        self.macro_combo.setMinimumWidth(160)
        self.macro_combo.addItems(self.config.get("macros", []))
        row1.addWidget(self.macro_combo, 1)

        run_macro_btn = QPushButton("\u25b6 Run")
        run_macro_btn.setObjectName("run_btn")
        run_macro_btn.setToolTip("Run the selected VBA macro in the Excel workbook")
        run_macro_btn.clicked.connect(self._run_vba)
        row1.addWidget(run_macro_btn)
        outer.addLayout(row1)

        # Row 2: Action buttons
        row2 = QHBoxLayout()
        pull_csv_btn = QPushButton("\U0001f4e5 Pull CSV")
        pull_csv_btn.setObjectName("pull_csv_btn")
        pull_csv_btn.setToolTip("Download latest CSV and save to configured output directory")
        pull_csv_btn.clicked.connect(self._pull_csv)
        row2.addWidget(pull_csv_btn)

        refresh_btn = QPushButton("\U0001f504 Refresh")
        refresh_btn.setObjectName("refresh_btn")
        refresh_btn.setToolTip("Reload data from Excel file")
        refresh_btn.clicked.connect(self._refresh_data)
        row2.addWidget(refresh_btn)

        reload_btn = QPushButton("Reload Excel")
        reload_btn.setObjectName("reload_btn")
        reload_btn.setToolTip("Force a full reload from the Excel workbook")
        reload_btn.clicked.connect(self._reload_from_excel)
        row2.addWidget(reload_btn)
        outer.addLayout(row2)

        return outer

    def _setup_multi_user_sync(self):
        """Initialize optional cache-first multi-user sync helpers.

        Sets up:
          - LockManager (file-level locks)
          - RevisionStore (per-COM optimistic revisions)
          - SharedCache (per-COM remote field values for conflict diffs)
          - SessionRegistry (heartbeat + presence)
          - Presence label in status bar
        """
        settings = self.config.get("multi_user", {})
        if not settings.get("enabled", False):
            return
        try:
            import getpass
            import socket

            from sync.lock_manager import LockManager
            from sync.revision_store import RevisionStore
            from sync.shared_cache import SharedCache
            from sync.session_registry import SessionRegistry

            username = settings.get("username") or os.environ.get("USERNAME") or getpass.getuser()
            machine = settings.get("machine") or os.environ.get("COMPUTERNAME") or socket.gethostname()
            self.owner_id = f"{username}@{machine}"
            excel_path = self.config["excel_path"]

            # Core sync infrastructure
            self.lock_manager = LockManager(excel_path, username, machine)
            self.revision_store = RevisionStore(excel_path)
            self._shared_cache = SharedCache(excel_path)

            # Wire shared cache into revision store so commits auto-update it
            self.revision_store.set_shared_cache(self._shared_cache)

            # Session heartbeat
            self._session_registry = SessionRegistry(excel_path, self.owner_id)
            self._session_registry.start(parent=self)

            # Presence display (status bar label)
            self._presence_label = QLabel()
            self._presence_label.setObjectName("presence_label")
            self._presence_label.setToolTip("Click to see who else is online")
            self._presence_label.setCursor(Qt.PointingHandCursor)
            self._presence_label.mousePressEvent = lambda _: self._show_presence_tooltip()
            self.status_bar.addPermanentWidget(self._presence_label)

            # Presence polling timer (every 60 seconds)
            self._presence_poll_timer = QTimer(self)
            self._presence_poll_timer.setInterval(60_000)
            self._presence_poll_timer.timeout.connect(self._update_presence_display)
            self._presence_poll_timer.start()

            # Initial presence update
            self._update_presence_display()

            print(f"MainWindow: Multi-user sync enabled for {self.owner_id}")
        except Exception as e:
            mode = settings.get("fallback_mode", "block")
            print(f"MainWindow: Multi-user sync unavailable: {e}")
            if mode == "block":
                self._sync_save_blocked = True
                QMessageBox.warning(
                    self,
                    "Sync Unavailable",
                    "Multi-user sync could not be initialized. Saves are disabled until "
                    "sync is available or multi_user.enabled is false.",
                )

    def _update_presence_display(self) -> None:
        """Update the presence label in the status bar."""
        if self._presence_label is None:
            return
        try:
            from sync.session_registry import SessionRegistry
            sessions = SessionRegistry.list_active(self.config["excel_path"])
            # Filter out our own session
            others = [s for s in sessions if s.owner != self.owner_id]
            if not others:
                self._presence_label.setText("")
                self._presence_label.setToolTip("No other users online")
            else:
                names = ", ".join(s.owner for s in others)
                self._presence_label.setText(f"👤 {len(others)} other{'s' if len(others) > 1 else ''} online")
                self._presence_label.setToolTip(f"Online: {names}")
        except Exception:
            self._presence_label.setText("")

    def _show_presence_tooltip(self) -> None:
        """Show a detailed popup listing active sessions."""
        try:
            from sync.session_registry import SessionRegistry
            sessions = SessionRegistry.list_active(self.config["excel_path"])
            if not sessions:
                QMessageBox.information(self, "Sessions", "No other users online.")
                return
            lines = ["Active sessions:"]
            for s in sessions:
                age = s.age_seconds
                ago = f"{age}s ago" if age < 120 else f"{age // 60}m ago"
                lines.append(f"  • {s.owner} (started {ago})")
            QMessageBox.information(self, "Active Sessions", "\n".join(lines))
        except Exception as e:
            self.status_bar.showMessage(f"Could not read sessions: {e}", 3000)

    def _run_vba(self):
        macro_name = self.macro_combo.currentText().strip()
        if not macro_name:
            QMessageBox.information(self, "No Macro", "Select or type a macro name first.")
            return

        try:
            from automation.vba_runner import run_macro

            if self.lock_manager:
                with self.lock_manager.write_lock(purpose=f"vba-{macro_name}"):
                    run_macro(self.config["excel_path"], macro_name)
            else:
                run_macro(self.config["excel_path"], macro_name)
            self.status_bar.showMessage(f"\u2713 Ran macro: {macro_name}", 5000)
        except ImportError:
            QMessageBox.warning(
                self,
                "VBA Error",
                "pywin32 is not installed or not available.\nRun: pip install pywin32",
            )
        except Exception as e:
            QMessageBox.warning(self, "VBA Error", f"Failed to run macro '{macro_name}': {e}")

    def _pull_csv(self):
        # Lazy import to avoid win32com dependency on non-Windows platforms
        from automation.csv_sync import pull_and_sync

        # Step 1: File dialog — user picks the source file
        source_dir = self.config.get(
            "unedited_reports_dir", "P:/Detailing Schedule 2019/Unedited Reports"
        )
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Unedited Report",
            source_dir,
            "Excel Files (*.xlsx *.xlsm *.csv);;All Files (*)",
        )
        if not source_path:
            return  # user cancelled

        # Step 2: Confirm
        target_path = self.config["excel_path"]
        macros = self.config.get("pull_macros", ["COMs_into_List", "Backup", "Save"])

        reply = QMessageBox.question(
            self,
            "Confirm Pull",
            f"Pull data from:\n{source_path}\n\n"
            f"Into:\n{target_path}\n\n"
            f"Then run macros: {', '.join(macros)}\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Step 3: Run the pipeline (wrapped in excel.lock when multi-user enabled)
        self.status_bar.showMessage("Pulling data...")
        try:
            if self.lock_manager:
                with self.lock_manager.write_lock(purpose="pull-csv"):
                    row_count = pull_and_sync(source_path, target_path, macros)
            else:
                row_count = pull_and_sync(source_path, target_path, macros)
            self.status_bar.showMessage(
                f"\u2713 Pulled {row_count} rows and ran macros successfully", 8000
            )
            # Reload data so the calendar reflects the update
            self._refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Pull Error", f"Failed:\n{e}")
            self.status_bar.showMessage("Pull failed", 5000)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is None:
            super().keyPressEvent(a0)
            return
        # Ctrl+S — save
        if a0.key() == Qt.Key_S and a0.modifiers() & Qt.ControlModifier:  # type: ignore[attr-defined]
            if self.edit_form.current_unit is not None:
                self.edit_form._on_save()
            return
        # Ctrl+T — toggle theme
        if a0.key() == Qt.Key_T and a0.modifiers() & Qt.ControlModifier:  # type: ignore[attr-defined]
            self._toggle_theme()
            return
        # F5 — refresh
        if a0.key() == Qt.Key_F5:  # type: ignore[attr-defined]
            self._refresh_data()
            return
        # Ctrl+F — focus search
        if a0.key() == Qt.Key_F and a0.modifiers() & Qt.ControlModifier:  # type: ignore[attr-defined]
            if hasattr(self.list_panel, 'com_search'):
                self.list_panel.com_search.setFocus()
                self.list_panel.com_search.selectAll()
            return
        # Escape — clear selection
        if a0.key() == Qt.Key_Escape:  # type: ignore[attr-defined]
            self.on_unit_selected(None)
            return
        super().keyPressEvent(a0)

    # ── Theme ────────────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        new_theme = "dark" if self._current_theme_name == "light" else "light"
        self._apply_theme_by_name(new_theme)

    def _apply_theme_by_name(self, theme_name: str) -> None:
        """Apply theme to entire widget tree, notify panels, persist."""
        from gui.theme import apply_theme
        apply_theme(self, theme_name,
                    cvd_mode=self._current_cvd,
                    high_contrast=self._current_hc)
        self._current_theme_name = theme_name
        self.theme_btn.setText("☀" if theme_name == "dark" else "🌙")
        # Propagate to panels — no parent-walking needed
        for panel in (self.calendar_panel, self.list_panel,
                      self.timeline_panel, self.edit_form):
            if hasattr(panel, "set_theme"):
                panel.set_theme(theme_name, self._current_cvd)
        self._save_ui_config()
        self.status_bar.showMessage(f"Theme: {theme_name}", 2000)

    def _save_ui_config(self) -> None:
        """Write ui.theme / ui.colorblind_mode / ui.high_contrast / ui.splitter_sizes to config.yaml."""
        import yaml
        import os
        self.config.setdefault("ui", {}).update({
            "theme": self._current_theme_name,
            "colorblind_mode": self._current_cvd,
            "high_contrast": self._current_hc,
            "splitter_sizes": self.main_splitter.sizes(),
        })
        # Remove runtime-only keys that should not be persisted to YAML
        save_config = {k: v for k, v in self.config.items() if k != "config_path"}
        config_path = getattr(self, "_config_path", None)
        if config_path and os.path.exists(os.path.dirname(config_path)):
            try:
                with open(config_path, "w", encoding="utf-8") as fh:
                    yaml.safe_dump(save_config, fh, default_flow_style=False,
                                   allow_unicode=True)
            except OSError as exc:
                self.status_bar.showMessage(
                    f"Could not save theme preference: {exc}", 4000)

    def _open_a11y_dialog(self) -> None:
        """Open the accessibility settings dialog."""
        from gui.a11y_dialog import A11yDialog
        dlg = A11yDialog(
            theme=self._current_theme_name,
            cvd_mode=self._current_cvd,
            high_contrast=self._current_hc,
            parent=self,
        )
        if dlg.exec_():
            self._current_cvd = dlg.cvd_mode
            self._current_hc = dlg.high_contrast
            self._apply_theme_by_name(self._current_theme_name)

    def closeEvent(self, a0) -> None:
        """Save UI preferences, stop session heartbeat, flush pending syncs."""
        # Stop session heartbeat
        if self._session_registry is not None:
            try:
                self._session_registry.stop()
            except Exception:
                pass

        # Stop presence polling
        if self._presence_poll_timer is not None:
            try:
                self._presence_poll_timer.stop()
            except RuntimeError:
                pass

        # Stop debounce flush timer
        self._stop_debounce_flush()

        # Flush any pending Excel syncs synchronously (best-effort)
        if self._pending_excel_sync:
            print(f"MainWindow: Flushing {len(self._pending_excel_sync)} pending syncs on close...")
            for com_number, unit in list(self._pending_excel_sync.items()):
                try:
                    if self.lock_manager and self.revision_store:
                        with self.lock_manager.write_lock(timeout=5.0):
                            save_unit(
                                self.config["excel_path"], unit,
                                self.config.get("sheet_name", "Sheet1"),
                                force=True,
                            )
                    else:
                        save_unit(
                            self.config["excel_path"], unit,
                            self.config.get("sheet_name", "Sheet1"),
                        )
                except Exception as exc:
                    print(f"MainWindow: Failed to flush COM {com_number} on close: {exc}")
                del self._pending_excel_sync[com_number]

        self._save_ui_config()
        super().closeEvent(a0)
