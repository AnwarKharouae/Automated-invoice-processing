from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem,
    QWidget, QButtonGroup
)
from PySide6.QtCore import Qt


class ExportDialog(QDialog):
    """
    Three-step export dialog:
      Page 1 — choose: export all vs pick
      Page 2 — if pick, checklist of invoices
      Page 3 — confirm + pink warning

    After accept(), read .selected (list of filenames).
    """

    def __init__(self, review_data, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QDialog { background-color: #2a2a2e; color: #e0e0e0; }
            QWidget { background-color: #2a2a2e; color: #e0e0e0; }
            QLabel { color: #e0e0e0; background: transparent; }
            QRadioButton { color: #e0e0e0; background: transparent; }
            QCheckBox { color: #e0e0e0; background: transparent; }
            QListWidget {
                background-color: #1e1e22; color: #e0e0e0;
                border: 1px solid #3a3a3e;
            }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background: #3a5a8a; color: white; }
            QPushButton {
                background-color: #2a2a2e; color: #e0e0e0;
                border: 1px solid #3a3a3e; padding: 4px 10px;
            }
            QPushButton:hover { background-color: #3a3a3e; }
        """)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("Export Invoices")
        self.setMinimumSize(560, 500)
        self.review_data = review_data
        self.selected = []

        # state
        self.mode = "all"

        root = QVBoxLayout(self)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.page1 = self._build_page1()
        self.page2 = self._build_page2()
        self.page3 = self._build_page3()
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        self.stack.setCurrentIndex(0)

    # ---------------- page 1 ----------------

    def _build_page1(self):
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h3>How do you want to export?</h3>"))

        self.radio_all = QRadioButton(
            "Export all processed invoices (with approval status shown)"
        )
        self.radio_pick = QRadioButton(
            "Let me pick which invoices to export"
        )
        self.radio_all.setChecked(True)

        group = QButtonGroup(self)
        group.addButton(self.radio_all)
        group.addButton(self.radio_pick)

        v.addWidget(self.radio_all)
        v.addWidget(self.radio_pick)
        v.addStretch()

        bar = QHBoxLayout()
        bar.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        nxt = QPushButton("Next →")
        nxt.clicked.connect(self._page1_next)
        bar.addWidget(cancel)
        bar.addWidget(nxt)
        v.addLayout(bar)
        return w

    def _page1_next(self):
        if self.radio_pick.isChecked():
            self.mode = "pick"
            self._refresh_page2()
            self.stack.setCurrentIndex(1)
        else:
            self.mode = "all"
            self.selected = self._all_exportable()
            self._refresh_page3()
            self.stack.setCurrentIndex(2)

    # ---------------- page 2 ----------------

    def _build_page2(self):
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h3>Pick invoices to export</h3>"))
        v.addWidget(QLabel("(failed invoices without a manual table are disabled)"))

        self.list_widget = QListWidget()
        v.addWidget(self.list_widget, 1)

        bar = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        nxt = QPushButton("Next →")
        nxt.clicked.connect(self._page2_next)
        bar.addWidget(back)
        bar.addStretch()
        bar.addWidget(nxt)
        v.addLayout(bar)
        return w

    def _refresh_page2(self):
        self.list_widget.clear()
        for fname, data in self.review_data.items():
            label = fname
            if data.get("failed"):
                label = f"⚠ {fname} (failed)"
            if data.get("approved"):
                label = f"✓ {fname}"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, fname)

            # disabled: failed AND no manual table
            failed = data.get("failed")
            has_table = bool(data.get("details_state"))
            if failed and not has_table:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setToolTip("Failed processing and never filled in manually")
            else:
                # default-check approved
                if data.get("approved"):
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            self.list_widget.addItem(item)

    def _page2_next(self):
        self.selected = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it.flags() & Qt.ItemIsEnabled and it.checkState() == Qt.Checked:
                self.selected.append(it.data(Qt.UserRole))
        if not self.selected:
            return
        self._refresh_page3()
        self.stack.setCurrentIndex(2)

    # ---------------- page 3 ----------------

    def _build_page3(self):
        w = QWidget()
        w.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<h3>Confirm export</h3>"))

        self.confirm_label = QLabel("")
        self.confirm_label.setWordWrap(True)
        v.addWidget(self.confirm_label)

        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #b00020; font-weight: 600;")
        v.addWidget(self.warn_label)

        v.addStretch()

        bar = QHBoxLayout()
        back = QPushButton("← Back")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        do_export = QPushButton("Export")
        do_export.clicked.connect(self.accept)
        bar.addWidget(back)
        bar.addStretch()
        bar.addWidget(do_export)
        v.addLayout(bar)
        return w

    def _refresh_page3(self):
        n = len(self.selected)
        self.confirm_label.setText(f"Ready to export <b>{n}</b> invoice(s).")

        # count pink-bearing invoices
        pink_count = 0
        for fname in self.selected:
            data = self.review_data.get(fname, {})
            d_state = data.get("details_state", {})
            i_state = data.get("items_state", {})
            if self._has_unresolved_pink(d_state) or self._has_unresolved_pink(i_state):
                pink_count += 1

        if pink_count:
            self.warn_label.setText(
                f"⚠ {pink_count} of {n} invoices still have unresolved flags (pink cells)."
            )
        else:
            self.warn_label.setText("")

    def _has_unresolved_pink(self, state):
        history = state.get("history", [])
        idx = state.get("index", -1)
        if not history:
            return False
        initial = history[0]
        current = history[idx] if 0 <= idx < len(history) else history[-1]

        c_rows = current.get("rows", [])
        i_rows = initial.get("rows", [])
        for r, row in enumerate(c_rows):
            for c, cell in enumerate(row):
                flag = cell[1] if isinstance(cell, tuple) else False
                if not flag:
                    continue
                if r < len(i_rows) and c < len(i_rows[r]):
                    init_text = i_rows[r][c][0] if isinstance(i_rows[r][c], tuple) else i_rows[r][c]
                    cur_text = cell[0] if isinstance(cell, tuple) else cell
                    if str(init_text) == str(cur_text):
                        return True
        return False

    def _all_exportable(self):
        out = []
        for fname, data in self.review_data.items():
            failed = data.get("failed")
            has_table = bool(data.get("details_state"))
            if failed and not has_table:
                continue
            out.append(fname)
        return out