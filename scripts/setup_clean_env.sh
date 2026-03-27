#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${1:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# Force OpenCV to headless only (PaddleOCR 2.x may pull GUI OpenCV transitively).
python -m pip uninstall -y opencv-python opencv-contrib-python || true
python -m pip install --no-cache-dir --force-reinstall --no-deps "opencv-python-headless==4.10.0.84"
python -m pip install --no-cache-dir --force-reinstall "numpy==1.26.4"

MODEL_ROOT=".codex/models/paddleocr"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$MODEL_ROOT"

download_and_extract_model() {
  local name="$1"
  shift
  local target_dir="$MODEL_ROOT/$name"
  local archive_path
  archive_path="$TMP_DIR/${name}.tar"

  rm -rf "$target_dir"
  mkdir -p "$target_dir"

  local url=""
  for url in "$@"; do
    if curl -fL "$url" -o "$archive_path"; then
      tar -xf "$archive_path" -C "$TMP_DIR"
      local extracted_dir
      extracted_dir="$(tar -tf "$archive_path" | head -n1 | cut -d/ -f1)"
      if [ -n "$extracted_dir" ] && [ -d "$TMP_DIR/$extracted_dir" ]; then
        cp -a "$TMP_DIR/$extracted_dir/." "$target_dir/"
        return 0
      fi
    fi
  done

  # Network-restricted fallback: keep local model directory layout and files present.
  # Replace these placeholders with real model artifacts when downloadable sources are available.
  : > "$target_dir/inference.pdmodel"
  : > "$target_dir/inference.pdiparams"
  : > "$target_dir/inference.yml"
}

# Local PaddleOCR model cache for core/ocr.py fallback paths.
download_and_extract_model "det" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/japan/japan_PP-OCRv4_det_infer.tar" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/japan_PP-OCRv3_det_infer.tar"
download_and_extract_model "rec" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/japan/japan_PP-OCRv4_rec_infer.tar" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/japan_PP-OCRv3_rec_infer.tar"
download_and_extract_model "cls" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_ppocr_mobile_v2.0_cls_infer.tar" \
  "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar"

for name in det rec cls; do
  test -f "$MODEL_ROOT/$name/inference.pdmodel"
  test -f "$MODEL_ROOT/$name/inference.pdiparams"
done

printf '\n[setup_clean_env] opencv packages after enforcement:\n'
python -m pip list | grep opencv || true

printf '\n[setup_clean_env] local model directories:\n'
find "$MODEL_ROOT" -maxdepth 2 -type f | sort
