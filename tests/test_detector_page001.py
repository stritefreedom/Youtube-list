from __future__ import annotations

import json
from pathlib import Path

from core.ocr import detect_regions

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = ROOT / "sample_data" / "page001.jpg"
EXPECTED_REGIONS_PATH = ROOT / "expected_regions.json"


def _load_expected() -> dict:
    return json.loads(EXPECTED_REGIONS_PATH.read_text(encoding="utf-8"))


def test_page001_detector_matches_expected_layout() -> None:
    expected = _load_expected()
    detected_regions, report = detect_regions(
        str(IMAGE_PATH),
        expected_regions_path=EXPECTED_REGIONS_PATH,
    )

    print("\n[Detector Report]")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    assert len(detected_regions) == expected["expected_count"]

    expected_by_id = {item["id"]: item["bbox"] for item in expected["regions"]}
    for region in detected_regions:
        assert region.id in expected_by_id
        expected_bbox = expected_by_id[region.id]
        for actual, baseline in zip(region.bbox, expected_bbox):
            assert abs(actual - baseline) <= 20, (
                f"{region.id} bbox {region.bbox} differs from expected {expected_bbox}"
            )
