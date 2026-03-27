"""Verify local PaddleOCR model paths and runtime availability."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.ocr import _create_ocr_engine, build_ocr_init_attempts, inspect_paddleocr_model_dirs


def main() -> int:
    diagnostics = inspect_paddleocr_model_dirs()
    print("=== PaddleOCR model directory diagnostics ===")
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    attempts, force_local_only = build_ocr_init_attempts()
    print("\n=== Planned PaddleOCR init kwargs ===")
    print(f"force_local_only={force_local_only}")
    for idx, kwargs in enumerate(attempts, start=1):
        print(f"[attempt {idx}] {json.dumps(kwargs, ensure_ascii=False, sort_keys=True)}")

    print("\n=== PaddleOCR initialization check ===")
    try:
        _create_ocr_engine()
        print("init_ok=True")
        return 0
    except Exception as exc:
        print("init_ok=False")
        print(f"init_error={exc!r}")
        print("\n=== Full traceback ===")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
