from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene
)
from PySide6.QtGui import QPixmap, QPainter, QShortcut, QKeySequence, QBrush, QColor
from PySide6.QtCore import Qt, QTimer


class _ZoomView(QGraphicsView):
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = _ZoomView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

        # 🔑 Always-white background, regardless of dark/light theme
        gray = QBrush(QColor(120, 120, 125))
        self.view.setBackgroundBrush(gray)
        self.scene.setBackgroundBrush(gray)

        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Hide the Qt stylesheet effect for this specific view
        self.view.setStyleSheet("QGraphicsView { border: 1px solid #c8c8cc; }")

        layout.addWidget(self.view, 1)

        bar = QHBoxLayout()
        zin = QPushButton("Zoom +")
        zout = QPushButton("Zoom −")
        fit = QPushButton("Fit")
        zin.clicked.connect(lambda: self._zoom(1.25))
        zout.clicked.connect(lambda: self._zoom(1 / 1.25))
        fit.clicked.connect(self.fit)
        bar.addWidget(zin)
        bar.addWidget(zout)
        bar.addWidget(fit)
        bar.addStretch()
        layout.addLayout(bar)

        QShortcut(QKeySequence("Ctrl+="), self, lambda: self._zoom(1.25))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self._zoom(1 / 1.25))
        QShortcut(QKeySequence("Ctrl+0"), self, self.fit)

        self.pixmap_item = None
        self._fit_pending = False

    def load_image(self, path):
        self.scene.clear()
        # Scene background can be cleared by scene.clear() — restore it
        self.scene.setBackgroundBrush(QBrush(QColor(120, 120, 125)))

        if not path:
            self.pixmap_item = None
            return

        pix = QPixmap(path)
        if pix.isNull():
            self.pixmap_item = None
            return

        self.pixmap_item = self.scene.addPixmap(pix)

        self._fit_pending = True
        QTimer.singleShot(0, self._deferred_fit)

    def _deferred_fit(self):
        if self._fit_pending:
            self.fit()
            self._fit_pending = False

    def fit(self):
        if not self.pixmap_item:
            return
        if self.view.viewport().width() < 20 or self.view.viewport().height() < 20:
            # Viewport hasn't been laid out yet — retry next tick
            QTimer.singleShot(0, self.fit)
            return

        # Reset any prior zoom, then fit fully inside the viewport
        self.view.resetTransform()
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

        # Center the image — otherwise scrollbars keep old position
        self.view.centerOn(self.pixmap_item)

    def _zoom(self, factor):
        self.view.scale(factor, factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_pending:
            QTimer.singleShot(0, self._deferred_fit)