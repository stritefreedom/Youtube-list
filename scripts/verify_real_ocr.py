"""Verify local PaddleOCR model paths and runtime availability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.ocr import _create_ocr_engine, inspect_paddleocr_model_dirs


def main() -> int:
    diagnostics = inspect_paddleocr_model_dirs()
    print("=== PaddleOCR model directory diagnostics ===")
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    print("\n=== PaddleOCR initialization check ===")
    try:
        _create_ocr_engine()
        print("init_ok=True")
        return 0
    except Exception as exc:
        print("init_ok=False")
        print(f"init_error={exc!r}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
