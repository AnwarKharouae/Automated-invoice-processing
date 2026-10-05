import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit,
    QMessageBox
)
from PySide6.QtCore import Qt
from core.paths import resource_path

SCHEMA_FILE = resource_path("default_schema.txt")
BACKUP_FILE = resource_path("save my ass.txt")


class PreferencesDialog(QDialog):
    def __init__(self, prefs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(760, 620)
        self.prefs = prefs

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        tabs.addTab(self._build_folders_tab(), "Folders")
        tabs.addTab(self._build_schema_tab(), "Schema")

        bar = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        bar.addStretch()
        bar.addWidget(cancel)
        bar.addWidget(save)
        root.addLayout(bar)

    def _build_folders_tab(self):
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(w)

        v.addWidget(QLabel("<b>Excel export folder</b>"))
        v.addWidget(QLabel("Where 'Approve Batch & Save' suggests saving .xlsx files."))
        row1 = QHBoxLayout()
        self.excel_dir = QLineEdit(self.prefs.get("excel_export_dir", ""))
        b1 = QPushButton("Browse…")
        b1.clicked.connect(lambda: self._pick_dir(self.excel_dir))
        row1.addWidget(self.excel_dir, 1)
        row1.addWidget(b1)
        v.addLayout(row1)

        v.addSpacing(20)

        v.addWidget(QLabel("<b>Session save folder</b>"))
        v.addWidget(QLabel("Where 'Save Session' suggests saving .zip files."))
        row2 = QHBoxLayout()
        self.session_dir = QLineEdit(self.prefs.get("session_save_dir", ""))
        b2 = QPushButton("Browse…")
        b2.clicked.connect(lambda: self._pick_dir(self.session_dir))
        row2.addWidget(self.session_dir, 1)
        row2.addWidget(b2)
        v.addLayout(row2)

        v.addStretch()
        return w

    def _pick_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(
            self, "Pick folder",
            line_edit.text() or os.path.expanduser("~")
        )
        if d:
            line_edit.setText(d)

    def _build_schema_tab(self):
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Edit the Llama extraction prompt. Saved for future batches."))

        self.schema_editor = QPlainTextEdit()
        self.schema_editor.setPlainText(self._load_schema())
        v.addWidget(self.schema_editor, 1)

        row = QHBoxLayout()
        restore = QPushButton("Restore backup")
        restore.clicked.connect(self._restore_backup)
        row.addWidget(restore)
        row.addStretch()
        v.addLayout(row)
        return w

    def _load_schema(self):
        if os.path.exists(SCHEMA_FILE):
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _restore_backup(self):
        if not os.path.exists(BACKUP_FILE):
            QMessageBox.warning(self, "No backup", "Backup file not found.")
            return
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            self.schema_editor.setPlainText(f.read())
        QMessageBox.information(self, "Restored", "Backup loaded. Click Save to apply.")

    def _save(self):
        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            f.write(self.schema_editor.toPlainText())

        self.prefs["excel_export_dir"] = self.excel_dir.text().strip()
        self.prefs["session_save_dir"] = self.session_dir.text().strip()
        self.accept()