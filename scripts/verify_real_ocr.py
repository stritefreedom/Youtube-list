"""Verify manga_ocr_pipeline runtime availability through core.ocr."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.ocr import detect_regions, run_ocr


def main() -> int:
    image_path = REPO_ROOT / "sample_data" / "page001.jpg"
    expected_regions_path = REPO_ROOT / "expected_regions.json"
    expected_ocr_path = REPO_ROOT / "expected_ocr.json"

    print("=== OCR runtime check (manga_ocr_pipeline) ===")
    print(f"image_path={image_path}")

    try:
        regions, det_report = detect_regions(
            str(image_path),
            expected_regions_path=expected_regions_path,
        )
        print("\n[Detection Report]")
        print(json.dumps(det_report, ensure_ascii=False, indent=2))

        ocr_regions, ocr_report = run_ocr(
            str(image_path),
            regions,
            expected_ocr_path=expected_ocr_path,
            allow_fixture_fallback=False,
        )
        print("\n[OCR Report]")
        print(json.dumps(ocr_report, ensure_ascii=False, indent=2))

        preview = [
            {"id": region.id, "text": region.text}
            for region in ocr_regions[:5]
        ]
        print("\n[OCR Preview (first 5)]")
        print(json.dumps(preview, ensure_ascii=False, indent=2))

        return 0 if ocr_report.get("ocr_available", False) else 1
    except Exception as exc:
        print("runtime_ok=False")
        print(f"runtime_error={exc!r}")
        print("\n=== Full traceback ===")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
