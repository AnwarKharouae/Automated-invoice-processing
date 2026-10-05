from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QMessageBox, QLabel
)

from core.paths import resource_path

SCHEMA_FILE = resource_path("default_schema.txt")
BACKUP_FILE = resource_path("save my ass.txt")


class SchemaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Llama Extraction Schema")
        self.resize(800, 700)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Edit the Llama prompt. This is saved and used for all future batches."))

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(self._load_schema())
        layout.addWidget(self.editor)

        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        restore = QPushButton("Restore backup")
        restore.clicked.connect(self.restore_backup)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)

        btns.addWidget(restore)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _load_schema(self):
        if os.path.exists(SCHEMA_FILE):
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save(self):
        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        QMessageBox.information(self, "Saved", "Schema saved.")
        self.accept()

    def restore_backup(self):
        if not os.path.exists(BACKUP_FILE):
            QMessageBox.warning(self, "No backup", "Backup file not found.")
            return
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            self.editor.setPlainText(f.read())
        QMessageBox.information(self, "Restored", "Backup loaded into editor. Click Save to apply.")