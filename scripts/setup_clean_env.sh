#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${1:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

"$VENV_PIP" install --upgrade pip setuptools wheel
"$VENV_PIP" install -r requirements.txt

# Force OpenCV to headless only (PaddleOCR 2.x may pull GUI OpenCV transitively).
"$VENV_PIP" uninstall -y opencv-python opencv-contrib-python || true
"$VENV_PIP" install --no-cache-dir --force-reinstall --no-deps "opencv-python-headless==4.10.0.84"
"$VENV_PIP" install --no-cache-dir --force-reinstall "numpy==1.26.4"

MODEL_ROOT=".codex/models/paddleocr"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$MODEL_ROOT"

download_and_extract_model() {
  local name="$1"
  shift
  local target_dir="$MODEL_ROOT/$name"
  local archive_path="$TMP_DIR/${name}.tar"
  local extract_base="$TMP_DIR/extract_${name}"
  local staged_dir="$TMP_DIR/staged_${name}"
  rm -rf "$extract_base" "$staged_dir"
  mkdir -p "$extract_base" "$staged_dir"

  local url=""
  for url in "$@"; do
    echo "[setup_clean_env] downloading ${name} model from: $url"
    if curl -fL "$url" -o "$archive_path"; then
      tar -xf "$archive_path" -C "$extract_base"
      local extracted_dir=""
      extracted_dir="$(find "$extract_base" -mindepth 1 -maxdepth 1 -type d | head -n1 || true)"
      if [ -n "$extracted_dir" ] && [ -d "$extracted_dir" ]; then
        cp -a "$extracted_dir/." "$staged_dir/"
        rm -rf "$target_dir"
        mkdir -p "$target_dir"
        cp -a "$staged_dir/." "$target_dir/"
        echo "[setup_clean_env] ${name} model ready: $target_dir"
        return 0
      fi
    fi
  done

  echo "[setup_clean_env] ERROR: missing real OCR models for '$name'" >&2
  return 1
}

validate_model_file() {
  local file_path="$1"
  if [ ! -s "$file_path" ]; then
    echo "[setup_clean_env] INVALID MODEL FILE: $file_path (missing or zero bytes)" >&2
    return 1
  fi
  return 0
}

# Local PaddleOCR model cache for core/ocr.py fallback paths.
download_failed=0
download_and_extract_model "det" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/japan/japan_PP-OCRv4_det_infer.tar" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/japan_PP-OCRv3_det_infer.tar" || download_failed=1
download_and_extract_model "rec" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/japan/japan_PP-OCRv4_rec_infer.tar" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/japan_PP-OCRv3_rec_infer.tar" || download_failed=1
download_and_extract_model "cls" \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_ppocr_mobile_v2.0_cls_infer.tar" \
  "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar" || download_failed=1

invalid_models=0
for name in det rec cls; do
  validate_model_file "$MODEL_ROOT/$name/inference.pdmodel" || invalid_models=1
  validate_model_file "$MODEL_ROOT/$name/inference.pdiparams" || invalid_models=1
done

printf '\n[setup_clean_env] opencv packages after enforcement:\n'
"$VENV_PIP" list | grep opencv || true

printf '\n[setup_clean_env] local model directories:\n'
find "$MODEL_ROOT" -maxdepth 2 -type f | sort

if [ "$invalid_models" -ne 0 ]; then
  echo "[setup_clean_env] ERROR: missing real OCR models" >&2
  exit 1
fi

if [ "$download_failed" -ne 0 ]; then
  echo "[setup_clean_env] ERROR: missing real OCR models" >&2
  exit 1
fi
