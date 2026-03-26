"""Image loading utilities for local files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def load_image(file_path: str) -> QPixmap:
    """Load a local image file as QPixmap.

    Raises:
        ValueError: if file extension is unsupported or image cannot be loaded.
    """
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("Unsupported image format. Please use PNG or JPG.")

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        raise ValueError("Failed to load image. The file may be corrupted.")

    return pixmap
