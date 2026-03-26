"""Data models used by the desktop app."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Region:
    """Basic region model placeholder for future OCR/text boxes."""

    id: str
    bbox: tuple[int, int, int, int]
    text: str = ""
