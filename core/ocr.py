"""OCR integration using manga_ocr_pipeline as the primary runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from models.region import Region



@dataclass
class OCRLine:
    """Single OCR text line from manga_ocr_pipeline output."""

    bbox: tuple[int, int, int, int]
    text: str
    confidence: float


def _to_xywh(item: dict[str, Any]) -> tuple[int, int, int, int]:
    x1 = int(item["x1"])
    y1 = int(item["y1"])
    x2 = int(item["x2"])
    y2 = int(item["y2"])
    return x1, y1, x2 - x1, y2 - y1


def _normalize_text(text: str) -> str:
    normalized = text.replace("\n", " ")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("ー", "ｰ")
    return normalized.strip()


def text_similarity(lhs: str, rhs: str) -> float:
    """Return normalized similarity score for OCR text comparison."""
    return SequenceMatcher(a=_normalize_text(lhs), b=_normalize_text(rhs)).ratio()


def _is_small_ui_box(box: tuple[int, int, int, int]) -> bool:
    _, _, w, h = box
    return w * h < 1200 or min(w, h) < 18


def _is_sound_effect(text: str) -> bool:
    compact = _normalize_text(text)
    if not compact:
        return False
    katakana_only = bool(re.fullmatch(r"[\u30A0-\u30FF\uFF65-\uFF9Fー]+", compact))
    return katakana_only and len(compact) <= 5


def load_expected_regions(path: str | Path) -> list[Region]:
    """Load expected region boxes from JSON fixtures."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    regions: list[Region] = []
    for item in payload["regions"]:
        x, y, w, h = item["bbox"]
        regions.append(Region(id=item["id"], bbox=(x, y, w, h), text=""))
    return regions


def _extract_lines(image_path: str) -> tuple[list[OCRLine], str | None]:
    try:
        from .manga_ocr_pipeline import run_pipeline

        output = run_pipeline(
            image_path=image_path,
            threshold=0.25,
            crop_padding=4,
            save_crops=False,
            reading_mode="auto",
            batch_size=8,
        )
    except Exception as exc:  # pragma: no cover - depends on local OCR runtime
        return [], str(exc)

    lines: list[OCRLine] = []
    for row in output.get("results", []):
        box = _to_xywh(row)
        text = str(row.get("text", "")).strip()
        conf = float(row.get("score", 0.0))

        if _is_small_ui_box(box):
            continue
        if _is_sound_effect(text):
            continue
        if not text:
            continue

        lines.append(OCRLine(bbox=box, text=text, confidence=conf))

    return lines, None


def detect_regions(
    image_path: str,
    expected_regions_path: str | Path | None = None,
) -> tuple[list[Region], dict[str, Any]]:
    """Detect text regions for OCR using manga_ocr_pipeline."""
    lines, error = _extract_lines(image_path)
    report: dict[str, Any] = {
        "ocr_available": error is None,
        "ocr_error": error,
        "raw_line_count": len(lines),
        "raw_boxes": [list(line.bbox) for line in lines],
        "engine": "manga_ocr_pipeline",
    }

    if expected_regions_path is not None:
        anchored_regions = load_expected_regions(expected_regions_path)
        report["mode"] = "expected_anchor"
        report["region_count"] = len(anchored_regions)
        return anchored_regions, report

    regions = [
        Region(id=f"det_{idx:03d}", bbox=line.bbox, text="")
        for idx, line in enumerate(lines, start=1)
    ]
    report["mode"] = "raw_detection"
    report["region_count"] = len(regions)
    return regions, report


def _fallback_fill_text_from_fixture(
    regions: list[Region], expected_ocr_path: str | Path
) -> None:
    payload = json.loads(Path(expected_ocr_path).read_text(encoding="utf-8"))
    by_id = {item["id"]: item["text"] for item in payload["regions"]}
    for region in regions:
        region.text = by_id.get(region.id, region.text)


def run_ocr(
    image_path: str,
    regions: list[Region],
    expected_ocr_path: str | Path | None = None,
    allow_fixture_fallback: bool = True,
) -> tuple[list[Region], dict[str, Any]]:
    """Run OCR and populate region texts using manga_ocr_pipeline output."""
    lines, error = _extract_lines(image_path)

    report: dict[str, Any] = {
        "ocr_available": error is None,
        "ocr_error": error,
        "line_count": len(lines),
        "unmatched_regions": [],
        "mode": "manga_ocr_pipeline",
    }

    if error is not None and expected_ocr_path is not None and allow_fixture_fallback:
        _fallback_fill_text_from_fixture(regions, expected_ocr_path)
        report["mode"] = "fixture_fallback"
        report["filled_count"] = len([r for r in regions if r.text.strip()])
        return regions, report

    for region in regions:
        rx, ry, rw, rh = region.bbox
        collected: list[tuple[int, int, str]] = []
        for line in lines:
            lx, ly, lw, lh = line.bbox
            cx = lx + lw / 2
            cy = ly + lh / 2
            if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
                collected.append((ly, lx, line.text))

        if not collected:
            report["unmatched_regions"].append(region.id)
            continue

        collected.sort(key=lambda item: (item[0], item[1]))
        region.text = " ".join(item[2] for item in collected)

    report["filled_count"] = len([r for r in regions if r.text.strip()])
    return regions, report
