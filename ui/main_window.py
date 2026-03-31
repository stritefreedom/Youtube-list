"""Main window for MVP image loading workflow."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.image_loader import load_image


class ImageScrollArea(QScrollArea):
    """Scroll area with wheel zoom and drag-to-pan behavior."""

    def __init__(self, image_label: QLabel) -> None:
        super().__init__()
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWidget(image_label)

        self._zoom_factor = 1.0
        self._zoom_min = 0.2
        self._zoom_max = 5.0
        self._pan_start: QPoint | None = None
        self._base_pixmap: QPixmap | None = None

    def set_base_pixmap(self, pixmap: QPixmap) -> None:
        """Store the original pixmap and reset zoom state."""
        self._base_pixmap = pixmap
        self._zoom_factor = 1.0
        self._apply_zoom()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Use Ctrl + wheel to zoom image in/out."""
        if self._base_pixmap is None:
            super().wheelEvent(event)
            return

        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            super().wheelEvent(event)
            return

        step = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom_factor = max(self._zoom_min, min(self._zoom_max, self._zoom_factor * step))
        self._apply_zoom()
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start = event.pos()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._pan_start is not None:
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _apply_zoom(self) -> None:
        if self._base_pixmap is None:
            return

        scaled = self._base_pixmap.scaled(
            self._base_pixmap.size() * self._zoom_factor,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_label = self.widget()
        if isinstance(image_label, QLabel):
            image_label.setPixmap(scaled)
            image_label.resize(scaled.size())


class MainWindow(QMainWindow):
    """Primary desktop window for phase-1 MVP."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Manga Translator Studio")
        self.resize(1000, 700)

        self.image_label = QLabel("請先載入 PNG / JPG 圖片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setScaledContents(False)

        self.scroll_area = ImageScrollArea(self.image_label)

        self.open_button = QPushButton("開啟圖片")
        self.open_button.clicked.connect(self.open_image)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        open_action = QAction("開啟圖片", self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.open_button)
        layout.addWidget(self.scroll_area)
        self.setCentralWidget(container)

        self.statusBar().showMessage("就緒（Ctrl + 滾輪縮放，左鍵拖曳平移）")

    def open_image(self) -> None:
        """Open a local image file and display it."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇圖片",
            "",
            "Image Files (*.png *.jpg *.jpeg)",
        )

        if not file_path:
            self.statusBar().showMessage("已取消選擇圖片")
            return

        try:
            pixmap = load_image(file_path)
        except ValueError as error:
            self.statusBar().showMessage(str(error))
            return

        self.scroll_area.set_base_pixmap(pixmap)
        self.statusBar().showMessage(f"已載入：{file_path}（Ctrl + 滾輪縮放，左鍵拖曳平移）")
