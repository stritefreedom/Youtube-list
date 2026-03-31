"""Main window for MVP image loading workflow."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.image_loader import load_image
from core.ocr import detect_regions, run_ocr


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
        self.current_image_path: str | None = None

        self.image_label = QLabel("請先載入 PNG / JPG 圖片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setScaledContents(False)

        self.scroll_area = ImageScrollArea(self.image_label)

        self.open_button = QPushButton("開啟圖片")
        self.open_button.clicked.connect(self.open_image)

        self.ocr_button = QPushButton("執行 OCR")
        self.ocr_button.clicked.connect(self.run_ocr_for_current_image)
        self.ocr_button.setEnabled(False)

        self.ocr_text_view = QTextEdit()
        self.ocr_text_view.setReadOnly(True)
        self.ocr_text_view.setPlaceholderText("OCR 結果會顯示在這裡。")

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        open_action = QAction("開啟圖片", self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)
        ocr_action = QAction("執行 OCR", self)
        ocr_action.triggered.connect(self.run_ocr_for_current_image)
        toolbar.addAction(ocr_action)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.open_button)
        layout.addWidget(self.ocr_button)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.ocr_text_view)
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
        self.current_image_path = file_path
        self.ocr_button.setEnabled(True)
        self.ocr_text_view.clear()
        self.statusBar().showMessage(f"已載入：{file_path}（Ctrl + 滾輪縮放，左鍵拖曳平移）")

    def run_ocr_for_current_image(self) -> None:
        """Run OCR for current image and show recognized text in a text panel."""
        if not self.current_image_path:
            QMessageBox.information(self, "尚未載入圖片", "請先載入圖片再執行 OCR。")
            return

        self.statusBar().showMessage("OCR 執行中，請稍候...")
        self.ocr_text_view.setPlainText("OCR 執行中...")
        self.repaint()

        regions, det_report = detect_regions(self.current_image_path)
        ocr_regions, ocr_report = run_ocr(self.current_image_path, regions)

        if not ocr_report.get("ocr_available", False):
            err = ocr_report.get("ocr_error") or "未知錯誤"
            self.ocr_text_view.setPlainText(f"OCR 不可用：{err}")
            self.statusBar().showMessage("OCR 失敗：請確認本機 OCR 依賴與模型環境")
            return

        rows: list[str] = []
        for index, region in enumerate(ocr_regions, start=1):
            text = region.text.strip()
            if not text:
                continue
            rows.append(f"[{index:03d}] {text}")

        if not rows:
            rows.append("未偵測到可用文字。")

        report_summary = [
            "=== OCR 執行摘要 ===",
            f"engine: {det_report.get('engine', 'unknown')}",
            f"偵測框數量: {det_report.get('region_count', 0)}",
            f"填入文字區數量: {ocr_report.get('filled_count', 0)}",
            "",
            "=== OCR 文字 ===",
            *rows,
        ]
        self.ocr_text_view.setPlainText("\n".join(report_summary))
        self.statusBar().showMessage("OCR 完成")
