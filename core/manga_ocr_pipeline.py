"""Manga OCR pipeline built around RT-DETR-v2 detector + manga-ocr-base recognizer.

This module keeps the original pipeline behavior (`run_pipeline(image_path) -> dict`) while
refactoring OCR into configurable preprocessing, fallback ranking, batching, and reading-order
sorting for manga pages.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

import cv2
import jaconv
import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageDraw
from transformers import (
    AutoImageProcessor,
    AutoModelForObjectDetection,
    AutoTokenizer,
    ViTImageProcessor,
    VisionEncoderDecoderModel,
)

LOGGER = logging.getLogger(__name__)

PreprocessMode = Literal[
    "none",
    "grayscale",
    "contrast",
    "adaptive_thresh",
    "denoise",
    "resize_up",
]
ReadingMode = Literal["ltr", "rtl", "vertical_jp", "auto"]


@dataclass(slots=True)
class PipelineConfig:
    """Runtime config for the manga OCR pipeline."""

    detector_id: str = "ogkalu/comic-text-and-bubble-detector"
    ocr_id: str = "kha-white/manga-ocr-base"
    output_dir: str = "/content/output"
    detection_threshold: float = 0.25
    ocr_max_length: int = 300
    crop_padding: int = 4
    sort_row_tol: int = 24
    preprocess_mode: tuple[PreprocessMode, ...] = (
        "none",
        "grayscale",
        "contrast",
        "adaptive_thresh",
        "denoise",
        "resize_up",
    )
    reading_mode: ReadingMode = "auto"
    ocr_batch_size: int = 8
    ocr_labels: tuple[str, ...] = ("text_bubble", "text_free")
    min_box_side_for_resize: int = 28
    resize_scale_for_small: float = 2.0
    preprocess_padding: int = 6
    retry_single_on_oom: bool = True
    enable_debug: bool = False


@dataclass(slots=True)
class LoadedModels:
    """Loaded detector/OCR models and processors."""

    det_processor: Any
    det_model: Any
    ocr_processor: Any
    ocr_tokenizer: Any
    ocr_model: Any
    device: str
    dtype: torch.dtype


@dataclass(slots=True)
class OcrCandidate:
    """OCR candidate hypothesis for one crop."""

    name: str
    image: Image.Image
    text: str = ""
    score: float = -1.0


_MODEL_CACHE: LoadedModels | None = None


def manga_ocr_post_process(text: str) -> str:
    """Normalize OCR output into a cleaner text form."""
    text = "".join(text.split())
    text = text.replace("…", "...")
    text = re.sub(r"[・.]{2,}", lambda m: "." * (m.end() - m.start()), text)
    return jaconv.h2z(text, ascii=True, digit=True)


def load_models(config: PipelineConfig) -> LoadedModels:
    """Load detector + OCR models with dtype/device safety to avoid mismatch bugs."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    LOGGER.info("Loading models on device=%s dtype=%s", device, dtype)

    det_processor = AutoImageProcessor.from_pretrained(config.detector_id)
    det_model = AutoModelForObjectDetection.from_pretrained(
        config.detector_id,
        torch_dtype=dtype if device == "cuda" else torch.float32,
    ).to(device)
    det_model.eval()

    ocr_processor = ViTImageProcessor.from_pretrained(config.ocr_id)
    ocr_tokenizer = AutoTokenizer.from_pretrained(config.ocr_id)
    ocr_model = VisionEncoderDecoderModel.from_pretrained(
        config.ocr_id,
        torch_dtype=dtype if device == "cuda" else torch.float32,
    ).to(device)
    ocr_model.eval()

    _MODEL_CACHE = LoadedModels(
        det_processor=det_processor,
        det_model=det_model,
        ocr_processor=ocr_processor,
        ocr_tokenizer=ocr_tokenizer,
        ocr_model=ocr_model,
        device=device,
        dtype=dtype,
    )
    return _MODEL_CACHE


def load_image(image_path: str) -> Image.Image:
    """Read RGB image from disk."""
    return Image.open(image_path).convert("RGB")


def clamp_box(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> tuple[int, int, int, int]:
    """Clamp box to valid image coordinates."""
    cx1 = max(0, min(int(round(x1)), w - 1))
    cy1 = max(0, min(int(round(y1)), h - 1))
    cx2 = max(0, min(int(round(x2)), w - 1))
    cy2 = max(0, min(int(round(y2)), h - 1))
    if cx2 <= cx1:
        cx2 = min(w - 1, cx1 + 1)
    if cy2 <= cy1:
        cy2 = min(h - 1, cy1 + 1)
    return cx1, cy1, cx2, cy2


def expand_box(box: tuple[int, int, int, int], pad: int, w: int, h: int) -> tuple[int, int, int, int]:
    """Add fixed padding around a box and clamp."""
    x1, y1, x2, y2 = box
    return clamp_box(x1 - pad, y1 - pad, x2 + pad, y2 + pad, w, h)


@torch.inference_mode()
def detect_regions(image: Image.Image, models: LoadedModels, threshold: float) -> list[dict[str, Any]]:
    """Run RT-DETR-v2 detection and keep all labels for downstream filtering."""
    inputs = models.det_processor(images=image, return_tensors="pt")
    inputs = {k: v.to(models.device) for k, v in inputs.items()}
    for key, value in list(inputs.items()):
        if torch.is_floating_point(value):
            inputs[key] = value.to(dtype=models.dtype if models.device == "cuda" else torch.float32)

    outputs = models.det_model(**inputs)
    target_sizes = torch.tensor([image.size[::-1]], device=models.device)
    results = models.det_processor.post_process_object_detection(
        outputs,
        threshold=threshold,
        target_sizes=target_sizes,
    )[0]

    w, h = image.size
    id2label = models.det_model.config.id2label
    detections: list[dict[str, Any]] = []
    for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
        x1, y1, x2, y2 = clamp_box(*box.tolist(), w, h)
        detections.append(
            {
                "label_id": int(label.item()),
                "label": id2label[int(label.item())],
                "score": float(score.item()),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": x2 - x1,
                "height": y2 - y1,
            }
        )
    return detections


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _bgr_to_pil(image: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def preprocess_crop(
    crop: Image.Image,
    mode: PreprocessMode,
    config: PipelineConfig,
) -> Image.Image:
    """Apply one preprocessing mode to a crop and return RGB image."""
    bgr = _pil_to_bgr(crop)
    h, w = bgr.shape[:2]

    if mode == "none":
        pass
    elif mode == "grayscale":
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    elif mode == "contrast":
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        bgr = cv2.cvtColor(cv2.merge((l2, a, b)), cv2.COLOR_LAB2BGR)
    elif mode == "adaptive_thresh":
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        th = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            8,
        )
        bgr = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
    elif mode == "denoise":
        bgr = cv2.fastNlMeansDenoisingColored(bgr, None, 4, 4, 7, 21)
    elif mode == "resize_up":
        scale = config.resize_scale_for_small if min(w, h) < config.min_box_side_for_resize else 1.25
        bgr = cv2.resize(
            bgr,
            dsize=(max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_CUBIC,
        )
    else:
        raise ValueError(f"Unsupported preprocess mode: {mode}")

    if config.preprocess_padding > 0:
        bgr = cv2.copyMakeBorder(
            bgr,
            config.preprocess_padding,
            config.preprocess_padding,
            config.preprocess_padding,
            config.preprocess_padding,
            borderType=cv2.BORDER_REPLICATE,
        )

    return _bgr_to_pil(bgr)


def _is_japanese_char(char: str) -> bool:
    code = ord(char)
    return (
        0x3040 <= code <= 0x309F  # Hiragana
        or 0x30A0 <= code <= 0x30FF  # Katakana
        or 0x3400 <= code <= 0x4DBF  # CJK Ext A
        or 0x4E00 <= code <= 0x9FFF  # CJK Unified
        or 0xFF66 <= code <= 0xFF9D  # half-width katakana
    )


def score_text(text: str) -> float:
    """Heuristic score for OCR text quality (higher is better)."""
    if not text:
        return -10.0
    cleaned = text.strip()
    if not cleaned:
        return -10.0

    length = len(cleaned)
    score = 0.0
    if 1 <= length <= 120:
        score += 1.5
    if 2 <= length <= 60:
        score += 1.0

    jp_count = sum(1 for c in cleaned if _is_japanese_char(c))
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    punct_count = sum(1 for c in cleaned if not c.isalnum() and not c.isspace())

    valid_chars = max(1, len(cleaned))
    jp_ratio = jp_count / valid_chars
    alnum_ratio = alnum_count / valid_chars
    punct_ratio = punct_count / valid_chars

    score += jp_ratio * 2.5
    score += alnum_ratio * 1.0
    score -= punct_ratio * 1.5

    if re.fullmatch(r"[\W_]+", cleaned):
        score -= 3.0

    garble_like = len(re.findall(r"[�□◇◆※☆★]+", cleaned))
    score -= garble_like * 0.5
    return score


def _decode_generated(models: LoadedModels, generated: torch.Tensor) -> list[str]:
    texts = models.ocr_tokenizer.batch_decode(generated, skip_special_tokens=True)
    return [manga_ocr_post_process(t) for t in texts]


@torch.inference_mode()
def ocr_batch(
    crops: list[Image.Image],
    models: LoadedModels,
    config: PipelineConfig,
) -> list[str]:
    """Run batched OCR inference with GPU OOM fallback to single-image mode."""
    if not crops:
        return []

    all_texts: list[str] = []
    for start in range(0, len(crops), config.ocr_batch_size):
        part = crops[start : start + config.ocr_batch_size]
        try:
            pixel_values = models.ocr_processor(images=part, return_tensors="pt").pixel_values.to(models.device)
            if models.device == "cuda":
                pixel_values = pixel_values.to(dtype=models.dtype)

            generated = models.ocr_model.generate(
                pixel_values,
                max_length=config.ocr_max_length,
                num_beams=1,
            )
            all_texts.extend(_decode_generated(models, generated))
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower() and config.retry_single_on_oom:
                LOGGER.warning("Batch OCR OOM, fallback to single mode for %d crops", len(part))
                if models.device == "cuda":
                    torch.cuda.empty_cache()
                for img in part:
                    all_texts.append(ocr_one(img, models=models, config=config))
            else:
                raise

    return all_texts


def rank_ocr(candidates: Iterable[OcrCandidate]) -> OcrCandidate:
    """Pick best OCR candidate by score_text."""
    best = OcrCandidate(name="none", image=Image.new("RGB", (1, 1)), text="", score=-10.0)
    for candidate in candidates:
        cand_score = score_text(candidate.text)
        candidate.score = cand_score
        if cand_score > best.score:
            best = candidate
    return best


def _candidate_images(crop: Image.Image, config: PipelineConfig) -> list[OcrCandidate]:
    raw = crop.convert("RGB")
    padded = preprocess_crop(raw, "none", config)
    resized = preprocess_crop(raw, "resize_up", config)
    threshold = preprocess_crop(raw, "adaptive_thresh", config)
    return [
        OcrCandidate(name="raw_crop", image=raw),
        OcrCandidate(name="padded_crop", image=padded),
        OcrCandidate(name="resized_crop", image=resized),
        OcrCandidate(name="threshold_crop", image=threshold),
    ]


def ocr_one(crop: Image.Image, models: LoadedModels, config: PipelineConfig) -> str:
    """Run OCR fallback candidates for a single crop and return best text."""
    candidates = _candidate_images(crop, config)
    texts = ocr_batch([c.image for c in candidates], models=models, config=config)
    for candidate, text in zip(candidates, texts):
        candidate.text = text
    return rank_ocr(candidates).text


def _group_rows(items: list[dict[str, Any]], row_tol: int) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for item in items:
        cy = (item["y1"] + item["y2"]) / 2.0
        placed = False
        for row in rows:
            row_cy = float(np.mean([(r["y1"] + r["y2"]) / 2.0 for r in row]))
            if abs(cy - row_cy) <= row_tol:
                row.append(item)
                placed = True
                break
        if not placed:
            rows.append([item])
    return rows


def sort_boxes(
    items: list[dict[str, Any]],
    reading_mode: ReadingMode,
    row_tol: int,
) -> list[dict[str, Any]]:
    """Sort boxes by reading order with manga-friendly modes."""
    if not items:
        return items

    mode = reading_mode
    if mode == "auto":
        widths = np.array([it["x2"] - it["x1"] for it in items], dtype=np.float32)
        heights = np.array([it["y2"] - it["y1"] for it in items], dtype=np.float32)
        vertical_ratio = float(np.mean((heights + 1e-6) / (widths + 1e-6) > 1.35))
        mode = "vertical_jp" if vertical_ratio >= 0.45 else "rtl"

    sorted_items: list[dict[str, Any]]
    if mode == "vertical_jp":
        columns = sorted(items, key=lambda d: ((d["x1"] + d["x2"]) / 2.0), reverse=True)
        col_groups = _group_rows(columns, row_tol=row_tol)
        sorted_items = []
        for col in col_groups:
            col.sort(key=lambda d: d["y1"])
            sorted_items.extend(col)
    else:
        base = sorted(items, key=lambda d: ((d["y1"] + d["y2"]) / 2.0, d["x1"]))
        rows = _group_rows(base, row_tol=row_tol)
        sorted_items = []
        for row in rows:
            reverse = mode == "rtl"
            row.sort(key=lambda d: d["x1"], reverse=reverse)
            sorted_items.extend(row)

    for idx, item in enumerate(sorted_items, start=1):
        item["order"] = idx
    return sorted_items


def draw_detections(image: Image.Image, detections: list[dict[str, Any]], show_label: bool = True) -> Image.Image:
    """Draw OCR region boxes for preview outputs."""
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    color_map = {
        "bubble": (0, 180, 255),
        "text_bubble": (0, 220, 0),
        "text_free": (255, 140, 0),
    }
    for det in detections:
        x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
        label = det["label"]
        color = color_map.get(label, (255, 0, 0))
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        if show_label:
            text = f'{det.get("order", "?")} | {label} | {det["score"]:.2f}'
            tx = x1
            ty = max(0, y1 - 18)
            draw.rectangle([tx, ty, tx + 8 * len(text), ty + 16], fill=color)
            draw.text((tx + 2, ty), text, fill=(0, 0, 0))
    return canvas


def render_outputs(
    image: Image.Image,
    text_regions: list[dict[str, Any]],
    results: list[dict[str, Any]],
    output_dir: str,
    base_name: str,
) -> dict[str, str]:
    """Save visualization and JSON/CSV/TXT outputs with original schema preserved."""
    vis = draw_detections(image, text_regions, show_label=True)
    vis_path = os.path.join(output_dir, f"{base_name}_detections.png")
    vis.save(vis_path)

    json_path = os.path.join(output_dir, f"{base_name}_ocr.json")
    csv_path = os.path.join(output_dir, f"{base_name}_ocr.csv")
    txt_path = os.path.join(output_dir, f"{base_name}_ocr.txt")

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)
    pd.DataFrame(results).to_csv(csv_path, index=False, encoding="utf-8-sig")
    with open(txt_path, "w", encoding="utf-8") as file:
        for row in results:
            file.write(f"[{row['order']:03d}] {row['text']}\n")

    return {
        "visualized_path": vis_path,
        "json_path": json_path,
        "csv_path": csv_path,
        "txt_path": txt_path,
    }


def run_pipeline(
    image_path: str,
    threshold: float = 0.25,
    crop_padding: int = 4,
    ocr_labels: tuple[str, ...] = ("text_bubble", "text_free"),
    save_crops: bool = True,
    reading_mode: ReadingMode = "auto",
    batch_size: int = 8,
    config: PipelineConfig | None = None,
) -> dict[str, Any]:
    """Run detector + OCR pipeline and return the original output dictionary contract."""
    base_cfg = config or PipelineConfig()
    cfg_dict = asdict(base_cfg)
    cfg_dict.update(
        {
            "detection_threshold": threshold,
            "crop_padding": crop_padding,
            "ocr_labels": ocr_labels,
            "reading_mode": reading_mode,
            "ocr_batch_size": batch_size,
        }
    )
    cfg = PipelineConfig(**cfg_dict)

    os.makedirs(cfg.output_dir, exist_ok=True)
    models = load_models(cfg)
    image = load_image(image_path)
    w, h = image.size

    detections = detect_regions(image=image, models=models, threshold=cfg.detection_threshold)
    text_regions = [d for d in detections if d["label"] in cfg.ocr_labels]
    text_regions = sort_boxes(text_regions, reading_mode=cfg.reading_mode, row_tol=cfg.sort_row_tol)

    results: list[dict[str, Any]] = []
    base_name = Path(image_path).stem
    crop_dir = os.path.join(cfg.output_dir, f"{base_name}_crops")
    os.makedirs(crop_dir, exist_ok=True)

    crop_images: list[Image.Image] = []
    crop_meta: list[tuple[dict[str, Any], tuple[int, int, int, int]]] = []
    for item in text_regions:
        box = (item["x1"], item["y1"], item["x2"], item["y2"])
        ex_box = expand_box(box, cfg.crop_padding, w, h)
        crop = image.crop(ex_box)
        crop_images.append(crop)
        crop_meta.append((item, ex_box))

    recognized_texts: list[str] = []
    for crop in crop_images:
        recognized_texts.append(ocr_one(crop, models=models, config=cfg))

    for (item, ex_box), text, crop in zip(crop_meta, recognized_texts, crop_images):
        out = {
            "order": item["order"],
            "label": item["label"],
            "score": round(item["score"], 6),
            "x1": ex_box[0],
            "y1": ex_box[1],
            "x2": ex_box[2],
            "y2": ex_box[3],
            "width": ex_box[2] - ex_box[0],
            "height": ex_box[3] - ex_box[1],
            "text": text,
        }
        if save_crops:
            crop_path = os.path.join(crop_dir, f"{item['order']:03d}_{item['label']}.png")
            crop.save(crop_path)
            out["crop_path"] = crop_path
        results.append(out)

    output_paths = render_outputs(
        image=image,
        text_regions=text_regions,
        results=results,
        output_dir=cfg.output_dir,
        base_name=base_name,
    )

    visualized_image = Image.open(output_paths["visualized_path"]).copy()
    return {
        "image": image,
        "visualized_image": visualized_image,
        "visualized_path": output_paths["visualized_path"],
        "json_path": output_paths["json_path"],
        "csv_path": output_paths["csv_path"],
        "txt_path": output_paths["txt_path"],
        "results": results,
        "all_detections": detections,
    }


__all__ = [
    "PipelineConfig",
    "LoadedModels",
    "detect_regions",
    "load_models",
    "ocr_batch",
    "ocr_one",
    "preprocess_crop",
    "rank_ocr",
    "render_outputs",
    "run_pipeline",
    "score_text",
    "sort_boxes",
]
