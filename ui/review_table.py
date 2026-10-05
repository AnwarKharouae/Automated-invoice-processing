from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QMenu, QInputDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor

PINK_HEX = "#FFC8C8"
EDITED_HEX = "#81C784"

class ReviewTable(QTableWidget):
    """
    Editable table with per-invoice undo history.
    - Double-click to edit
    - Right-click: add/remove row, add/rename/delete column
    - Ctrl+Z / Ctrl+Y walk the history (keyboard shortcuts live in MainWindow)
    """

    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.horizontalHeader().setStretchLastSection(True)

        self._loading = False
        self._history = []
        self._history_index = -1
        self._current_flags = []

        self.itemChanged.connect(self._on_item_edited)
        self.model().rowsInserted.connect(self._on_any_change)
        self.model().rowsRemoved.connect(self._on_any_change)
        self.model().columnsInserted.connect(self._on_any_change)
        self.model().columnsRemoved.connect(self._on_any_change)

    # ---------- loading ----------
    def load_rows(self, columns, rows, reset_history=True, flags=None):
        self._loading = True
        try:
            self.setRowCount(0)
            self.setColumnCount(0)
            if columns:
                self.setColumnCount(len(columns))
                self.setHorizontalHeaderLabels(list(columns))
                self.setRowCount(len(rows))
                for r, row in enumerate(rows):
                    for c, val in enumerate(row):
                        text = "" if val is None else str(val)
                        item = QTableWidgetItem(text)
                        state = None
                        if flags and r < len(flags) and c < len(flags[r]):
                            state = flags[r][c]
                        self._paint_cell(item, state)
                        self.setItem(r, c, item)
                self.resizeColumnsToContents()
        finally:
            self._loading = False

        if reset_history:
            self._history = [self.snapshot()]
            self._history_index = 0
# ---------- ----------

# ---------- ----------
    def _apply(self, snap):
        self._loading = True
        try:
            self.setRowCount(0)
            self.setColumnCount(0)
            cols = snap["columns"]
            rows = snap["rows"]
            if cols:
                self.setColumnCount(len(cols))
                self.setHorizontalHeaderLabels(list(cols))
                self.setRowCount(len(rows))
                for r, row in enumerate(rows):
                    for c, cell in enumerate(row):
                        if isinstance(cell, tuple):
                            text, state = cell
                        else:
                            text, state = cell, None
                        item = QTableWidgetItem("" if text is None else str(text))
                        self._paint_cell(item, state)
                        self.setItem(r, c, item)
                self.resizeColumnsToContents()
        finally:
            self._loading = False


    def to_rows(self):
        return [
            [(self.item(r, c).text() if self.item(r, c) else "")
             for c in range(self.columnCount())]
            for r in range(self.rowCount())
        ]

    def to_dicts(self):
        headers = [self.horizontalHeaderItem(c).text() for c in range(self.columnCount())]
        out = []
        for r in range(self.rowCount()):
            d = {}
            for c, h in enumerate(headers):
                it = self.item(r, c)
                d[h] = it.text() if it else ""
            out.append(d)
        return out

    # ---------- snapshots + history ----------
    def snapshot(self):
        columns = [self.horizontalHeaderItem(c).text()
                   for c in range(self.columnCount())]
        rows = []
        for r in range(self.rowCount()):
            row = []
            for c in range(self.columnCount()):
                it = self.item(r, c)
                text = it.text() if it else ""
                state = self._cell_state(it)
                row.append((text, state))
            rows.append(row)
        return {"columns": columns, "rows": rows}

    def restore(self, snap):
        self.load_rows(snap["columns"], snap["rows"], reset_history=False)

    def _on_item_edited(self, item):
        if self._loading:
            return
        self._loading = True
        try:
            item.setBackground(QBrush(QColor(EDITED_HEX)))
            item.setForeground(QBrush(QColor("000000")))
        finally:
            self._loading = False
        self._on_any_change()

    def _cell_state(self, item):
        if item is None:
            return None
        c = item.background().color()
        if c == QColor(PINK_HEX):
            return "pink"
        if c == QColor(EDITED_HEX):
            return "edited"
        return None

    def _paint_cell(self, item, state):
        if state == "pink":
            item.setBackground(QBrush(QColor(PINK_HEX)))
            item.setForeground(QBrush(QColor("000000")))
        elif state == "edited":
            item.setBackground(QBrush(QColor(EDITED_HEX)))
            item.setForeground(QBrush(QColor("000000")))

    def _on_any_change(self, *args):
        if self._loading:
            return
        snap = self.snapshot()
        # Drop any redo-future after a new edit
        self._history = self._history[: self._history_index + 1]
        self._history.append(snap)
        self._history_index = len(self._history) - 1
        self.changed.emit()

    def undo(self):
        if self._history_index > 0:
            self._history_index -= 1
            self._apply(self._history[self._history_index])

    def redo(self):
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._apply(self._history[self._history_index])

    def can_undo(self):
        return self._history_index > 0

    def can_redo(self):
        return self._history_index < len(self._history) - 1

    def get_state(self):
        return {"history": list(self._history), "index": self._history_index}

    def set_state(self, state):
        self._history = list(state.get("history", []))
        self._history_index = state.get("index", -1)
        if 0 <= self._history_index < len(self._history):
            self._apply(self._history[self._history_index])

    # ---------- context menu ----------
    def _context_menu(self, pos):
        item = self.itemAt(pos)
        row = item.row() if item else self.rowCount() - 1
        col = item.column() if item else self.columnCount() - 1

        menu = QMenu(self)
        menu.addAction("Insert row below",   lambda: self._insert_row(row + 1))
        menu.addAction("Delete this row",    lambda: self._delete_row(row))
        menu.addSeparator()
        menu.addAction("Add column",         lambda: self._add_column())
        menu.addAction("Rename this column", lambda: self._rename_column(col))
        menu.addAction("Delete this column", lambda: self._delete_column(col))
        menu.exec(self.viewport().mapToGlobal(pos))

    def _insert_row(self, at):
        self.insertRow(at)
        for c in range(self.columnCount()):
            self.setItem(at, c, QTableWidgetItem(""))

    def _delete_row(self, at):
        if self.rowCount() > 0:
            self.removeRow(at)

    def _add_column(self):
        name, ok = QInputDialog.getText(self, "New column", "Column name:")
        if not ok or not name.strip():
            return
        c = self.columnCount()
        self.insertColumn(c)
        self.setHorizontalHeaderItem(c, QTableWidgetItem(name.strip()))
        for r in range(self.rowCount()):
            self.setItem(r, c, QTableWidgetItem(""))

    def _rename_column(self, c):
        if c < 0 or c >= self.columnCount():
            return
        current = self.horizontalHeaderItem(c).text()
        name, ok = QInputDialog.getText(self, "Rename column", "New name:", text=current)
        if ok and name.strip():
            self.setHorizontalHeaderItem(c, QTableWidgetItem(name.strip()))

    def _delete_column(self, c):
        if 0 <= c < self.columnCount():
            self.removeColumn(c)