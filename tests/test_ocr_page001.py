from __future__ import annotations

import json
from pathlib import Path

from core.ocr import detect_regions, run_ocr, text_similarity

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = ROOT / "sample_data" / "page001.jpg"
EXPECTED_REGIONS_PATH = ROOT / "expected_regions.json"
EXPECTED_OCR_PATH = ROOT / "expected_ocr.json"


def _load_expected_ocr() -> dict:
    return json.loads(EXPECTED_OCR_PATH.read_text(encoding="utf-8"))


def test_page001_ocr_similarity_report() -> None:
    expected = _load_expected_ocr()

    regions, det_report = detect_regions(
        str(IMAGE_PATH),
        expected_regions_path=EXPECTED_REGIONS_PATH,
    )
    ocr_regions, ocr_report = run_ocr(
        str(IMAGE_PATH),
        regions,
        expected_ocr_path=EXPECTED_OCR_PATH,
        allow_fixture_fallback=False,
    )

    print("\n[OCR Detection Report]")
    print(json.dumps(det_report, ensure_ascii=False, indent=2))
    print("\n[OCR Text Report]")
    print(json.dumps(ocr_report, ensure_ascii=False, indent=2))

    if not ocr_report["ocr_available"]:
        import pytest

        pytest.skip(f"Real OCR unavailable: {ocr_report['ocr_error']}")

    assert ocr_report["mode"] == "manga_ocr_pipeline"
    assert len(ocr_regions) == expected["expected_count"]

    expected_by_id = {item["id"]: item["text"] for item in expected["regions"]}

    similarity_rows: list[dict[str, float | str]] = []
    for region in ocr_regions:
        target = expected_by_id[region.id]
        score = text_similarity(region.text, target)
        similarity_rows.append(
            {
                "id": region.id,
                "actual": region.text,
                "expected": target,
                "similarity": round(score, 4),
            }
        )

    print("\n[OCR Similarity Report]")
    print(json.dumps(similarity_rows, ensure_ascii=False, indent=2))

    below_threshold = [row for row in similarity_rows if row["similarity"] < 0.85]
    assert not below_threshold, f"OCR similarity below threshold: {below_threshold}"


def test_page001_ocr_fixture_fallback_report() -> None:
    expected = _load_expected_ocr()

    regions, _ = detect_regions(
        str(IMAGE_PATH),
        expected_regions_path=EXPECTED_REGIONS_PATH,
    )
    ocr_regions, ocr_report = run_ocr(
        str(IMAGE_PATH),
        regions,
        expected_ocr_path=EXPECTED_OCR_PATH,
        allow_fixture_fallback=True,
    )

    print("\n[OCR Fallback Report]")
    print(json.dumps(ocr_report, ensure_ascii=False, indent=2))

    if ocr_report["ocr_available"]:
        import pytest

        pytest.xfail("OCR runtime is available; fallback mode is not expected.")

    assert ocr_report["mode"] == "fixture_fallback"
    assert len(ocr_regions) == expected["expected_count"]

    expected_by_id = {item["id"]: item["text"] for item in expected["regions"]}
    for region in ocr_regions:
        assert region.text == expected_by_id[region.id]
