"""Main window for MVP image loading workflow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
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

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

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

        self.statusBar().showMessage("就緒")

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

        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())
        self.statusBar().showMessage(f"已載入：{file_path}")
