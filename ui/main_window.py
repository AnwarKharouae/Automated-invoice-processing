import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QSplitter, QTabWidget,
    QLabel, QFileDialog, QMessageBox, QProgressBar ,  QMenu , QDialog  , QToolButton
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QAction, QMovie, QShortcut, QKeySequence, QBrush,QPalette, QColor

from ui.image_viewer import ImageViewer
from ui.review_table import ReviewTable
from core.worker import BatchWorker
from core.ollama_manager import OllamaManager
from core.sound import get_player
from core.preferences import load_preferences, save_preferences
from core.session import save_session, load_session, delete_session
from PySide6.QtWidgets import QApplication


PHASE_ORDER = ["preprocess", "ocr", "structure", "spotting", "drawing"]
PHASE_LABELS = {
    "preprocess": "🧹 Preprocessing",
    "ocr":        "🔍 DeepSeek OCR",
    "structure":  "🧠 Llama structure",
    "spotting":   "📐 PaddleOCR-VL",
    "drawing":    "✏️ Drawing boxes",
}
PHASE_WEIGHTS = {"preprocess": 5, "ocr": 40, "structure": 15, "spotting": 35, "drawing": 5}
LIGHT_STYLE = """
QMainWindow, QWidget { background-color: #f5f5f7; color: #1e1e1e; }
QToolBar { background: #e8e8ec; border: none; spacing: 4px; }
QToolButton { color: #1e1e1e; padding: 4px 8px; }
QToolButton:hover { background: #d8d8dc; }
QStatusBar { background: #e8e8ec; color: #1e1e1e; }
QListWidget {
    background: #ffffff; color: #1e1e1e;
    border: 1px solid #c8c8cc;
}
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background: #3a5a8a; color: white; }
QTabWidget::pane { border: 1px solid #c8c8cc; }
QTabBar::tab {
    background: #e8e8ec; color: #4a4a4a;
    padding: 6px 14px; border: 1px solid #c8c8cc;
}
QTabBar::tab:selected { background: #3a5a8a; color: white; }
QTableWidget {
    background: #ffffff; color: #1e1e1e;
    gridline-color: #e0e0e4;
    border: 1px solid #c8c8cc;
}
QHeaderView::section {
    background: #e8e8ec; color: #1e1e1e;
    border: 1px solid #c8c8cc; padding: 4px;
}
QTableWidget::item:selected { background: #3a5a8a; color: white; }
QLineEdit, QPlainTextEdit, QTextEdit {
    background: #ffffff; color: #1e1e1e;
    border: 1px solid #c8c8cc;
}
QMenu { background: #ffffff; color: #1e1e1e; border: 1px solid #c8c8cc; }
QMenu::item:selected { background: #3a5a8a; color: white; }
QPushButton {
    background: #e8e8ec; color: #1e1e1e;
    border: 1px solid #c8c8cc; padding: 4px 10px;
}
QPushButton:hover { background: #d8d8dc; }
QLabel { color: #1e1e1e; }
QMessageBox { background: #f5f5f7; color: #1e1e1e; }
QDialog { background: #f5f5f7; color: #1e1e1e; }
QDialog QWidget { background: #f5f5f7; color: #1e1e1e; }
"""
DARK_STYLE = """
QMainWindow, QWidget { background-color: #1e1e22; color: #e0e0e0; }
QToolBar { background: #2a2a2e; border: none; spacing: 4px; }
QToolButton { color: #e0e0e0; padding: 4px 8px; }
QToolButton:hover { background: #3a3a3e; }
QStatusBar { background: #2a2a2e; color: #e0e0e0; }
QListWidget {
    background: #26262a; color: #e0e0e0;
    border: 1px solid #3a3a3e;
}
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background: #3a5a8a; color: white; }
QTabWidget::pane { border: 1px solid #3a3a3e; }
QTabBar::tab {
    background: #2a2a2e; color: #c0c0c0;
    padding: 6px 14px; border: 1px solid #3a3a3e;
}
QTabBar::tab:selected { background: #3a5a8a; color: white; }
QTableWidget {
    background: #26262a; color: #e0e0e0;
    gridline-color: #3a3a3e;
    border: 1px solid #3a3a3e;
}
QHeaderView::section {
    background: #2a2a2e; color: #e0e0e0;
    border: 1px solid #3a3a3e; padding: 4px;
}
QTableWidget::item:selected { background: #3a5a8a; color: white; }
QLineEdit, QPlainTextEdit, QTextEdit {
    background: #26262a; color: #e0e0e0;
    border: 1px solid #3a3a3e;
}
QMenu { background: #2a2a2e; color: #e0e0e0; }
QMenu::item:selected { background: #3a5a8a; }
QPushButton {
    background: #2a2a2e; color: #e0e0e0;
    border: 1px solid #3a3a3e; padding: 4px 10px;
}
QPushButton:hover { background: #3a3a3e; }
QLabel { color: #e0e0e0; }
QMessageBox { background: #1e1e22; color: #e0e0e0; }
QDialog { background: #1e1e22; color: #e0e0e0; }
QDialog QWidget { background: #1e1e22; color: #e0e0e0; }
"""

class PreloadWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, mgr):
        super().__init__()
        self.mgr = mgr
    
    def run(self):
        if not self.mgr.check_ollama():
            self.done.emit(False, "Ollama not running. Start it and restart the app.")
            return
        ok = self.mgr.load_deepseek()
        self.done.emit(ok, "DeepSeek ready. Upload invoices to begin."
                       if ok else "Failed to load DeepSeek.")


class LoadingOverlay(QWidget):
    FALLBACK_EMOJI = {
        "preprocess": "🧹",
        "ocr":        "🔍",
        "structure":  "🧠",
        "spotting":   "📐",
        "drawing":    "✏️",
        "done":       "✅",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.paths import resource_path
        self.GIFS = {
            "preprocess": resource_path("characters", "preprocess.gif"),
            "ocr":        resource_path("characters", "ocr.gif"),
            "structure":  resource_path("characters", "structure.gif"),
            "spotting":   resource_path("characters", "spotting.gif"),
            "drawing":    resource_path("characters", "drawing.gif"),
            "done":       resource_path("characters", "done.gif"),
        }
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(20, 20, 24, 235);")

        self._movie = None  # keep ref or Qt kills the animation

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(28)

        self.character = QLabel()
        self.character.setAlignment(Qt.AlignCenter)
        self.character.setStyleSheet("background: transparent; font-size: 120px;")
        self.character.setFixedSize(240, 240)
        layout.addWidget(self.character, alignment=Qt.AlignCenter)

        self.title = QLabel("Loading...")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(
            "color: white; font-size: 22px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(self.title, alignment=Qt.AlignCenter)

        self.bar = QProgressBar()
        self.bar.setFixedSize(520, 26)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 13px;
                background-color: #2a2a2e;
            }
            QProgressBar::chunk {
                background-color: #29b6f6;
                border-radius: 11px;
            }
        """)
        layout.addWidget(self.bar, alignment=Qt.AlignCenter)

    # ---------------------------------------------------------------
    def set_phase_gif(self, phase_key):
        path = self.GIFS.get(phase_key)

        if path and os.path.exists(path):
            if self._movie:
                self._movie.stop()
                self._movie.deleteLater()
                self._movie = None

            self._movie = QMovie(path)
            self._movie.setCacheMode(QMovie.CacheAll)

            # 🔑 Set a fixed scaled size BEFORE start — never changes on loop
            from PySide6.QtCore import QSize
            self._movie.setScaledSize(QSize(240, 240))

            self.character.setMovie(self._movie)
            self._movie.start()
        else:
            if self._movie:
                self._movie.stop()
                self._movie.deleteLater()
                self._movie = None
            self.character.setMovie(None)
            self.character.setText(self.FALLBACK_EMOJI.get(phase_key, "✍️"))

    def set_progress(self, value):
        self.bar.setValue(max(0, min(100, int(value))))

    def set_text(self, text):
        self.title.setText(text)



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mgr = OllamaManager(log=print)
        self.setWindowTitle("Invoice Reviewer")
        self.resize(1600, 900)

        self.invoice_files = []
        self.current_index = -1
        self.review_data = {}
        self.worker = None
        self._current_phase = None
        self._current_file = None

        self.prefs = load_preferences()
        self._loaded_session_zip = None
        self._loaded_session_folder = None
        self._loaded_session_name = None

        self._build_toolbar()
        self._build_layout()
        self._build_statusbar()
        self._build_shortcuts()
        QApplication.instance().setStyleSheet(LIGHT_STYLE)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f5f5f7"))
        palette.setColor(QPalette.WindowText, QColor("#1e1e1e"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.Text, QColor("#1e1e1e"))
        palette.setColor(QPalette.Button, QColor("#e8e8ec"))
        palette.setColor(QPalette.ButtonText, QColor("#1e1e1e"))
        palette.setColor(QPalette.Highlight, QColor("#3a5a8a"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        QApplication.instance().setPalette(palette)
        QTimer.singleShot(500, self._preload_deepseek)

    # ---------------------------------------------------------------
    def _build_toolbar(self):
        tb = self.addToolBar("Main")

        upload = QAction("📂 Upload Invoices", self)
        upload.triggered.connect(self.upload_invoices)
        tb.addAction(upload)

        load_sess = QAction("📁 Load Session", self)
        load_sess.triggered.connect(self.load_session_action)
        tb.addAction(load_sess)

        # Save Session with dropdown (Save / Save As…)
        save_btn = QToolButton()
        save_btn.setText("💾 Save Session")
        save_btn.setPopupMode(QToolButton.MenuButtonPopup)
        save_menu = QMenu(save_btn)
        save_menu.addAction("Save", self._save_session)
        save_menu.addAction("Save As…", self._save_session_as)
        save_btn.setMenu(save_menu)
        save_btn.clicked.connect(self._save_session)
        tb.addWidget(save_btn)
        tb.addSeparator()

        prefs_action = QAction("⚙️ Preferences", self)
        prefs_action.triggered.connect(self.open_preferences)
        tb.addAction(prefs_action)

        self.dark_action = QAction("🌙 Dark", self)
        self.dark_action.setCheckable(True)
        self.dark_action.triggered.connect(self._toggle_dark_mode)
        tb.addAction(self.dark_action)

        tb.addSeparator()

        process = QAction("▶️ Process", self)
        process.triggered.connect(self.process_invoices)
        tb.addAction(process)

        approve = QAction("✅ Approve Batch & Save", self)
        approve.triggered.connect(self.approve_batch)
        tb.addAction(approve)
    # ---------------------------------------------------------------
    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_current)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo_current)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self._redo_current)

    def _undo_current(self):
        if self.tabs.currentIndex() == 0:
            self.details_table.undo()
        else:
            self.items_table.undo()

    def _redo_current(self):
        if self.tabs.currentIndex() == 0:
            self.details_table.redo()
        else:
            self.items_table.redo()
    # ---------------------------------------------------------------
    def _build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(260)
        self.sidebar.currentRowChanged.connect(self.on_invoice_selected)
        self.sidebar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sidebar.customContextMenuRequested.connect(self._sidebar_menu)
        root.addWidget(self.sidebar)

        splitter = QSplitter(Qt.Horizontal)

        self.image_viewer = ImageViewer()
        splitter.addWidget(self.image_viewer)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.tabs = QTabWidget()

        self.details_table = ReviewTable()
        self.items_table = ReviewTable()

        # Hook up the changed signal so edits get saved per invoice


        self.tabs.addTab(self.details_table, "Details")
        self.tabs.addTab(self.items_table, "Items")
        right_layout.addWidget(self.tabs)

        splitter.addWidget(right)
        splitter.setSizes([900, 700])
        root.addWidget(splitter)

        # Loading overlay — covers the whole central area when visible
        self.overlay = LoadingOverlay(central)
        self.overlay.setGeometry(central.rect())
        self.overlay.hide()

    # ---------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay") and self.centralWidget():
            self.overlay.setGeometry(self.centralWidget().rect())

    # ---------------------------------------------------------------
    def _build_statusbar(self):
        self.status_label = QLabel("Starting up...")
        self.statusBar().addWidget(self.status_label)

        legend = QLabel("☐ new  ✏️ edited  ❓ empty  ⚠ failed  ✓ approved")
        legend.setStyleSheet("color: #888; padding-right: 8px;")
        self.statusBar().addPermanentWidget(legend)

    # ---------------------------------------------------------------
    def _preload_deepseek(self):
        self.status_label.setText("⏳ Loading DeepSeek-OCR in background...")
        self._preload_worker = PreloadWorker(self.mgr)
        self._preload_worker.done.connect(self._on_preload_done)
        self._preload_worker.start()

    def _on_preload_done(self, ok, msg):
        self.status_label.setText("✅ " + msg if ok else "❌ " + msg)
        if ok:
            get_player().play("deepseek_ready.mp3")
        else:
            QMessageBox.critical(self, "Startup failed", msg)

    # ---------------------------------------------------------------
    def upload_invoices(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select invoice images", "invoices",
            "Images (*.png *.jpg *.jpeg)"
        )
        if not files:
            return

        existing = {os.path.basename(p) for p in self.invoice_files}
        new_files = [f for f in files if os.path.basename(f) not in existing]
        if not new_files:
            QMessageBox.information(self, "No new files",
                                    "All selected files are already in the list.")
            return

        self.invoice_files.extend(new_files)

        self.sidebar.blockSignals(True)
        for f in new_files:
            self._add_sidebar_item(os.path.basename(f), icon="☐")
        self.sidebar.blockSignals(False)

        self.status_label.setText(
            f"📂 Added {len(new_files)}. Total: {len(self.invoice_files)}. Click ▶️ Process."
        )

    # ---------------------------------------------------------------
    # ------------------- session save / load -------------------

    def _current_schema_text(self):
        from core.paths import resource_path
        path = resource_path("default_schema.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _save_session(self):

        """Overwrite current session. If none loaded, behaves like Save As."""
        if not self.review_data:
            QMessageBox.information(self, "Nothing to save",
                                    "There's no batch to save yet.")
            return

        if self._loaded_session_zip:
            self._write_session_to(self._loaded_session_zip)
        else:
            self._save_session_as()

    def _save_session_as(self):
        """Prompt for name + location. Timestamp appended to suggested name."""
        if not self.review_data:
            QMessageBox.information(self, "Nothing to save",
                                    "There's no batch to save yet.")
            return

        from PySide6.QtWidgets import QInputDialog
        from datetime import datetime

        # suggest base name from the previously loaded session (strip its timestamp)
        default_base = "session"
        if self._loaded_session_name:
            parts = self._loaded_session_name.rsplit("_", 2)
            if len(parts) >= 3:
                default_base = "_".join(parts[:-2]) or "session"

        name, ok = QInputDialog.getText(
            self, "Save Session As",
            "Name this session (date/time will be added to the suggested filename):",
            text=default_base,
        )
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "_")

        stamp = datetime.now().strftime("%d-%m-%Y_%H%M")
        filename = f"{name}_{stamp}.zip"

        default_dir = self.prefs.get("session_save_dir") or os.path.expanduser("~")
        default_path = os.path.join(default_dir, filename)

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session As", default_path, "Session files (*.zip)"
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"

        self._write_session_to(path)

        # one-time hint about the difference between Save and Save As
        if not self.prefs.get("save_hint_shown"):
            QMessageBox.information(
                self, "About saving",
                "• Save → overwrites the current session file\n"
                "• Save As… → creates a new file\n\n"
                "Use Save As… at milestones (before sending to ERP, after a "
                "big correction pass) to keep versioned snapshots.\n\n"
                "You can delete old session files from the session folder "
                "whenever you want."
            )
            self.prefs["save_hint_shown"] = True
            save_preferences(self.prefs)

    def _write_session_to(self, path):
        existed = os.path.exists(path)
        try:
            save_session(
                review_data=self.review_data,
                invoice_files=self.invoice_files,
                schema_text=self._current_schema_text(),
                output_zip=path,
            )
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return

        self._loaded_session_zip = path
        self._loaded_session_folder = None
        self._loaded_session_name = os.path.splitext(os.path.basename(path))[0]
        verb = "Overwrote" if existed else "Saved"
        self.status_label.setText(f"💾 {verb} → {os.path.basename(path)}")

        QMessageBox.information(
            self,
            "Session saved",
            f"💾 {verb} session\n\n{os.path.basename(path)}\n\nFull path:\n{path}"
        )


 
    def load_session_action(self):
        if self.review_data:
            reply = QMessageBox.question(
                self, "Replace current batch?",
                "Loading a session will replace your current batch.\n\n"
                "Any unsaved work in the current batch will be lost. Continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        default_dir = self.prefs.get("session_save_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", default_dir, "Session files (*.zip)"
        )
        if not path:
            return

        try:
            loaded = load_session(path)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))
            return

        # replace state
        self.review_data = loaded["review_data"]
        self.invoice_files = loaded["invoice_files"]
        self._loaded_session_zip = path
        self._loaded_session_folder = loaded["folder"]
        self._loaded_session_name = loaded["name"]

        # rebuild sidebar
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        for fname in self.review_data.keys():
            icon = self._sidebar_icon_for(fname)
            red = bool(self.review_data[fname].get("failed"))
            self._add_sidebar_item(fname, icon=icon, red=red)
        self.sidebar.blockSignals(False)

        # select first invoice if any
        if self.sidebar.count() > 0:
            self.sidebar.setCurrentRow(0)
        else:
            self.details_table.load_rows([], [])
            self.items_table.load_rows([], [])
            self.image_viewer.load_image("")

        self.status_label.setText(
            f"📁 Session loaded: {loaded['name']} ({self.sidebar.count()} invoices)"
        )

    def open_preferences(self):
        from ui.preferences_dialog import PreferencesDialog
        dlg = PreferencesDialog(self.prefs, self)
        if dlg.exec() == QDialog.Accepted:
            save_preferences(self.prefs)
            self.status_label.setText("⚙️ Preferences saved.")
    # ---------------------------------------------------------------
    def process_invoices(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Still finishing",
                "The previous batch is still cleaning up. Try again in a few seconds."
            )
            return
        if not self.invoice_files:
            QMessageBox.information(self, "No invoices", "Upload invoices first.")
            return

        from core.paths import resource_path, work_path
        schema_path = resource_path("default_schema.txt")
        if not os.path.exists(schema_path):
            QMessageBox.critical(self, "Missing schema",
                                 "resources/default_schema.txt not found.")
            return

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_prompt = f.read()

        # Only process files we haven't processed yet
        to_process = [p for p in self.invoice_files
                      if os.path.basename(p) not in self.review_data]
        if not to_process:
            QMessageBox.information(self, "Nothing to process",
                                    "All loaded invoices have already been processed.")
            return

        self._current_phase = None
        self.overlay.set_progress(0)
        self.overlay.set_text("Starting...")
        self.overlay.setGeometry(self.centralWidget().rect())
        self.overlay.show()
        self.overlay.raise_()

        self.worker = BatchWorker(to_process, schema_prompt,
                                  work_path("annotated_batch"), self.mgr)
        self.worker.phase.connect(self._on_worker_phase)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.one_done.connect(self._on_worker_one_done)
        self.worker.one_failed.connect(self._on_worker_one_failed)
        self.worker.finished_.connect(self._on_worker_finished)
        self.worker.deepseek_reloaded.connect(self._on_deepseek_reloaded)
        self.worker.start()
    # ---------------------------------------------------------------
    def _on_deepseek_reloaded(self):
        # Only play after the FIRST batch — the startup tuturu already covers launch
        if getattr(self, "_batches_done", 0) > 0:
            get_player().play("deepseek_back.mp3")
    # ---------------------------------------------------------------
    def _on_worker_phase(self, name):
        self._current_phase = name
        self.overlay.set_phase_gif(name)

    def _on_worker_progress(self, current, total, filename):
        idx = PHASE_ORDER.index(self._current_phase) if self._current_phase in PHASE_ORDER else 0
        base = sum(PHASE_WEIGHTS[p] for p in PHASE_ORDER[:idx])
        within = (current / total) * PHASE_WEIGHTS.get(self._current_phase, 0) if total else 0
        self.overlay.set_progress(base + within)
        label = PHASE_LABELS.get(self._current_phase, "")
        self.overlay.set_text(f"{label} — {filename}")


    def _is_empty_result(self, result):
        details = result.get("details") or {}
        items = result.get("items") or []

        def has_content(v):
            return v is not None and str(v).strip() != ""

        details_empty = not any(has_content(v) for v in details.values())

        items_empty = True
        for it in items:
            if isinstance(it, dict) and any(has_content(v) for v in it.values()):
                items_empty = False
                break

        return details_empty and items_empty




    def _on_worker_one_done(self, filename, result):
        self.review_data[filename] = result
        result["empty"] = self._is_empty_result(result)
        self._ensure_default_tables(filename, result)
        self.sidebar.blockSignals(True)
        self._add_sidebar_item(filename, icon=self._sidebar_icon_for(filename),
                               replace=True)
        self.sidebar.blockSignals(False)

    def _on_worker_one_failed(self, filename, err):
        print(f"[FAILED] {filename}: {err}")
        data = self.review_data.setdefault(filename, {})
        data["failed"] = True
        self._ensure_default_tables(filename, data)
        self.sidebar.blockSignals(True)
        self._add_sidebar_item(filename, icon="⚠", replace=True, red=True)
        self.sidebar.blockSignals(False)

    def _on_worker_finished(self):
        self.overlay.set_progress(100)
        self.overlay.set_phase_gif("done")
        self.overlay.set_text("✅ Done!")
        self.status_label.setText("✅ Batch complete. Review each invoice, then Approve.")
        get_player().play("batch_done.mp3")
        QTimer.singleShot(1200, self.overlay.hide)
        self._batches_done = getattr(self, "_batches_done", 0) + 1 
      # ---------------------------------------------------------------
    def _flags_for_details(self, data):
        """2D list [row][col] of state strings (None | 'pink')."""
        located = data["located"].get("details", {})
        flags = []
        for field, val in data["details"].items():
            entry = located.get(field, {}) if isinstance(located, dict) else {}
            bbox = entry.get("bbox") if isinstance(entry, dict) else None
            unmatched = (val is not None) and (bbox is None)
            flags.append([None, "pink" if unmatched else None])
        return flags

    def _flags_for_items(self, data):
        """2D list [row][col] of state strings."""
        cols = ["product_name", "product_code", "quantity", "unit_price", "total"]
        located_items = data["located"].get("items", [])
        flags = []
        for i, item in enumerate(data["items"]):
            row_flags = [None] * len(cols)
            entry = located_items[i] if i < len(located_items) else {}
            if not isinstance(entry, dict):
                flags.append(row_flags)
                continue
            for c, field in enumerate(cols):
                sub = entry.get(field)
                if not isinstance(sub, dict):
                    continue
                val = item.get(field)
                if val is None:
                    continue
                if sub.get("bbox") is None:
                    row_flags[c] = "pink"
            flags.append(row_flags)
        return flags

    # ---------------------------------------------------------------
    def on_invoice_selected(self, row):
        if row < 0 or row >= self.sidebar.count():
            return

        filename = self._filename_from_sidebar(row)
        if not filename:
            return

        # 1) Save the OUTGOING invoice's state + icon
        if self._current_file and self._current_file != filename:
            old = self.review_data.get(self._current_file)
            if old:
                old["details_state"] = self.details_table.get_state()
                old["items_state"] = self.items_table.get_state()
                self._refresh_sidebar_icon(self._current_file)

        self.current_index = row
        data = self.review_data.get(filename)

        if data:
            self._current_file = filename

            # Use annotated image if present; fall back to original for failed invoices
            img_path = data.get("annotated_path")
            if not img_path:
                for p in self.invoice_files:
                    if os.path.basename(p) == filename:
                        img_path = p
                        break
            if img_path:
                self.image_viewer.load_image(img_path)

            # Details
            edited_details = (data.get("details_state", {}).get("index", 0) > 0)
            if "details_state" in data and edited_details:
                self.details_table.set_state(data["details_state"])
            else:
                details_rows = [[k, "" if v is None else str(v)]
                                for k, v in data["details"].items()]
                flags = self._flags_for_details(data)
                self.details_table.load_rows(["field", "value"], details_rows, flags=flags)
                data["details_state"] = self.details_table.get_state()

            # Items
            edited_items = (data.get("items_state", {}).get("index", 0) > 0)
            if "items_state" in data and edited_items:
                self.items_table.set_state(data["items_state"])
            else:
                cols = ["product_name", "product_code", "quantity", "unit_price", "total"]
                item_rows = []
                for it in data["items"]:
                    item_rows.append(["" if it.get(c) is None else str(it.get(c))
                                      for c in cols])
                flags = self._flags_for_items(data)
                self.items_table.load_rows(cols, item_rows, flags=flags)
                data["items_state"] = self.items_table.get_state()

            self.status_label.setText(f"Viewing: {filename}")
        else:
            self._current_file = None
            for path in self.invoice_files:
                if os.path.basename(path) == filename:
                    self.image_viewer.load_image(path)
                    break
            self.details_table.load_rows([], [])
            self.items_table.load_rows([], [])
            self.status_label.setText(f"Viewing (unprocessed): {filename}")
    # ---------------------------------------------------------------
    def approve_batch(self):
        if not self.review_data:
            QMessageBox.information(self, "Nothing to save",
                                    "Process some invoices first.")
            return

        exportable = [f for f, d in self.review_data.items()
                      if not (d.get("failed") and not d.get("details_state"))]
        if not exportable:
            QMessageBox.warning(
                self, "Nothing to export",
                "No invoices have been processed (or filled in manually)."
            )
            return

        from ui.export_dialog import ExportDialog
        dlg = ExportDialog(self.review_data, self)
        if dlg.exec() != QDialog.Accepted:
            return

        selected = dlg.selected
        if not selected:
            return

        # ask about deleting the loaded session after successful export
        delete_after = False
        if self._loaded_session_zip:
            reply = QMessageBox.question(
                self, "Delete session after export?",
                f"This batch was loaded from:\n{self._loaded_session_zip}\n\n"
                "If the export succeeds, the session .zip and its extracted folder "
                "will be deleted.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            delete_after = (reply == QMessageBox.Yes)

        # file dialog
        from datetime import datetime
        default_name = f"invoices_{datetime.now().strftime('%Y-%m-%d_%H%M')}.xlsx"
        default_dir = self.prefs.get("excel_export_dir") or os.path.expanduser("~")
        default_path = os.path.join(default_dir, default_name)

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel file", default_path,
            "Excel files (*.xlsx)"
        )
        if not save_path:
            return

        try:
            from core.excel_export import export_batch
            export_batch(self.review_data, selected, save_path)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return

        QMessageBox.information(
            self, "Export complete",
            f"Exported {len(selected)} invoice(s) →\n{save_path}"
        )

        # delete session only on successful export AND user said yes
        if delete_after and self._loaded_session_zip:
            delete_session(self._loaded_session_zip, self._loaded_session_folder)

        self._cleanup_after_export()

    # ---------------------------------------------------------------

    def _cleanup_after_export(self):
        import shutil
        from core.paths import work_path
        ann_dir = work_path("annotated_batch")
        if os.path.exists(ann_dir):
            try:
                shutil.rmtree(ann_dir)
            except Exception as e:
                print(f"[cleanup] could not delete annotated_batch: {e}")

        # wipe session pointers
        self._loaded_session_zip = None
        self._loaded_session_folder = None
        self._loaded_session_name = None

        # wipe session
        self.review_data = {}
        self.invoice_files = []
        self._current_file = None
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        self.sidebar.blockSignals(False)
        self.details_table.load_rows([], [])
        self.items_table.load_rows([], [])
        self.image_viewer.load_image("")
        self.status_label.setText("✅ Export complete. Ready for a new batch.")

    # ---------------------------------------------------------------
    def closeEvent(self, event):
        try:
            if self.worker and self.worker.isRunning():
                self.worker.cancel()
                self.worker.wait(3000)
            self.mgr.kill_all()
        finally:
            event.accept()

    def _add_sidebar_item(self, filename, icon="☐", replace=False, red=False):
        """Add or update a sidebar row. The raw filename is stored in UserRole."""
        if replace:
            for i in range(self.sidebar.count()):
                it = self.sidebar.item(i)
                if it.data(Qt.UserRole) == filename:
                    it.setText(f"{icon} {filename}")
                    if red:
                        it.setForeground(Qt.red)
                    else:
                        it.setForeground(QBrush())   # reset to default
                    return

        it = QListWidgetItem(f"{icon} {filename}")
        it.setData(Qt.UserRole, filename)
        if red:
            it.setForeground(Qt.red)
        self.sidebar.addItem(it)
# ---------------------------------------------------------------
    def _set_sidebar_icon(self, filename, icon, red=False):
        self.sidebar.blockSignals(True)
        self._add_sidebar_item(filename, icon=icon, replace=True, red=red)
        self.sidebar.blockSignals(False)
# ---------------------------------------------------------------
    def _filename_from_sidebar(self, row):
        it = self.sidebar.item(row)
        if not it:
            return None
        return it.data(Qt.UserRole) or it.text().strip()

    def _sidebar_menu(self, pos):
        item = self.sidebar.itemAt(pos)
        menu = QMenu(self)

        if item:
            filename = item.data(Qt.UserRole) or item.text().strip()
            data = self.review_data.get(filename, {})

            if data.get("approved"):
                menu.addAction("↩ Unapprove", lambda: self._toggle_approve(filename))
            else:
                menu.addAction("✓ Approve", lambda: self._toggle_approve(filename))

            menu.addSeparator()
            menu.addAction("🗑 Remove from list", lambda: self._remove_invoice(filename))
            menu.addSeparator()

        menu.addAction("📂 Add invoices...", self.upload_invoices)
        menu.exec(self.sidebar.mapToGlobal(pos))

    def _remove_invoice(self, filename):
        reply = QMessageBox.question(
            self, "Remove invoice",
            f"Remove {filename} from the list?\n\nEdits and history for this invoice will be lost.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # sidebar
        self.sidebar.blockSignals(True)
        for i in range(self.sidebar.count()):
            it = self.sidebar.item(i)
            if it.data(Qt.UserRole) == filename:
                self.sidebar.takeItem(i)
                break
        self.sidebar.blockSignals(False)

        # data
        self.review_data.pop(filename, None)
        self.invoice_files = [p for p in self.invoice_files
                              if os.path.basename(p) != filename]

        # clear view if we removed the current one
        if self._current_file == filename:
            self._current_file = None
            self.image_viewer.load_image("")
            self.details_table.load_rows([], [])
            self.items_table.load_rows([], [])
            self.status_label.setText("Invoice removed.")

    def _sidebar_icon_for(self, filename):
        data = self.review_data.get(filename)
        if not data:
            return "☐"
        if data.get("failed"):
            return "⚠"

        edited = (data.get("details_state", {}).get("index", 0) > 0 or
                  data.get("items_state", {}).get("index", 0) > 0)

        if data.get("empty") and not edited:
            return "❓"
        if data.get("approved"):
            return "✓"
        return "✏️" if edited else "☐"

    def _refresh_sidebar_icon(self, filename):
        data = self.review_data.get(filename, {})
        icon = self._sidebar_icon_for(filename)
        red = bool(data.get("failed"))
        self._set_sidebar_icon(filename, icon, red=red)

    def _toggle_approve(self, filename):
        data = self.review_data.get(filename)
        if not data:
            return
        data["approved"] = not data.get("approved", False)
        self._refresh_sidebar_icon(filename)
        state = "approved ✓" if data["approved"] else "unapproved"
        self.status_label.setText(f"{filename}: {state}")
    def _toggle_dark_mode(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor

        app = QApplication.instance()
        dark = self.dark_action.isChecked()

        if dark:
            app.setStyleSheet(DARK_STYLE)
            self.dark_action.setText("☀️ Light")
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor("#1e1e22"))
            palette.setColor(QPalette.WindowText, QColor("#e0e0e0"))
            palette.setColor(QPalette.Base, QColor("#26262a"))
            palette.setColor(QPalette.AlternateBase, QColor("#2a2a2e"))
            palette.setColor(QPalette.Text, QColor("#e0e0e0"))
            palette.setColor(QPalette.Button, QColor("#2a2a2e"))
            palette.setColor(QPalette.ButtonText, QColor("#e0e0e0"))
            palette.setColor(QPalette.Highlight, QColor("#3a5a8a"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
            app.setPalette(palette)
        else:
            app.setStyleSheet(LIGHT_STYLE)
            self.dark_action.setText("🌙 Dark")
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor("#f5f5f7"))
            palette.setColor(QPalette.WindowText, QColor("#1e1e1e"))
            palette.setColor(QPalette.Base, QColor("#ffffff"))
            palette.setColor(QPalette.AlternateBase, QColor("#e8e8ec"))
            palette.setColor(QPalette.Text, QColor("#1e1e1e"))
            palette.setColor(QPalette.Button, QColor("#e8e8ec"))
            palette.setColor(QPalette.ButtonText, QColor("#1e1e1e"))
            palette.setColor(QPalette.Highlight, QColor("#3a5a8a"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
            app.setPalette(palette)



    def _ensure_default_tables(self, filename, data):
        """Give an invoice an editable table if it doesn't have one yet.
        Uses whatever the pipeline extracted; if nothing, starts empty."""
        if data.get("details_state") and data.get("items_state"):
            return

        details_fields = [
            "invoice_number", "date", "consignee_name", "consignee_address",
            "consignee_phone", "consignee_email", "port_of_loading",
            "port_of_discharge", "vessel_airline", "shipment_date",
            "bank_name", "account_number", "routing_number", "payment_method",
            "total_quantity", "total_value",
        ]
        items_cols = ["product_name", "product_code", "quantity", "unit_price", "total"]

        if not data.get("details_state"):
            raw_details = data.get("details", {}) or {}
            if raw_details and any(
                v is not None and str(v).strip() != "" for v in raw_details.values()
            ):
                details_rows = [[(k, None), (str(v) if v is not None else "", None)]
                                for k, v in raw_details.items()]
            else:
                details_rows = [[(f, None), ("", None)] for f in details_fields]
            data["details_state"] = {
                "history": [{"columns": ["field", "value"], "rows": details_rows}],
                "index": 0,
            }

        if not data.get("items_state"):
            raw_items = data.get("items", []) or []
            real_items = [
                it for it in raw_items
                if isinstance(it, dict) and any(
                    v is not None and str(v).strip() != "" for v in it.values()
                )
            ]
            if real_items:
                items_rows = []
                for it in real_items:
                    items_rows.append([
                        (str(it.get(c)) if it.get(c) is not None else "", None)
                        for c in items_cols
                    ])
            else:
                items_rows = [[("", None) for _ in items_cols]]
            data["items_state"] = {
                "history": [{"columns": items_cols, "rows": items_rows}],
                "index": 0,
            }