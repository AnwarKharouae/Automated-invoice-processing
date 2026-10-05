"""
The extraction pipeline: image → structured data + boxes.

Ported from the notebook. No Qt here — this is pure Python.
"""

import io
import os
import re
import json
import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageStat, ImageDraw
from rapidfuzz import fuzz
import ollama


# ============================================================
# 1. PREPROCESSING
# ============================================================

def _estimate_text_height(im):
    gray = im.convert("L")
    arr = np.array(gray)
    binary = arr < 128
    row_has_ink = binary.any(axis=1)
    heights = []
    in_run, start = False, 0
    for i, val in enumerate(row_has_ink):
        if val and not in_run:
            start, in_run = i, True
        elif not val and in_run:
            heights.append(i - start)
            in_run = False
    return np.median(heights) if heights else None



def _resize_for_text_height(im, target_line_height=30, max_upscale=2.0):
    h = _estimate_text_height(im)
    if not h or h <= 0:
        return im
    scale = min(max(target_line_height / h, 0.3), max_upscale)
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)


def _dynamic_contrast(im, target_std=60):
    stat = ImageStat.Stat(im.convert("L"))
    s = stat.stddev[0]
    if s >= target_std or s == 0:
        return im
    return ImageEnhance.Contrast(im).enhance(min(target_std / s, 2.0))


def preprocess_invoice(img_path):
    """Return processed image bytes (JPEG)."""
    with Image.open(img_path) as im:
        im = im.convert("RGB")
        im = _dynamic_contrast(im)
        im = _resize_for_text_height(im)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=95)
        return buf.getvalue()


# ============================================================
# 2. DEEPSEEK-OCR
# ============================================================

def run_deepseek_ocr(image_bytes, model="deepseek-ocr"):
    resp = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": "Free OCR.", "images": [image_bytes]}],
        keep_alive=-1,
    )
    return resp["message"]["content"]


# ============================================================
# 3. LLAMA STRUCTURING
# ============================================================

def structure_with_llama(raw_text, schema_prompt, model="llama3.2:3b"):
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": schema_prompt},
            {"role": "user",   "content": f"Raw text:\n{raw_text}"},
        ],
        format="json",
        options={"temperature": 0.0, "num_predict": 1024},
        keep_alive=-1,
    )
    try:
        return json.loads(resp["message"]["content"])
    except json.JSONDecodeError:
        return {"details": {}, "items": []}


def normalize_extraction(parsed):
    """Force details=dict, items=list-of-dicts, whatever the model returned."""
    details = parsed.get("details", {})
    if isinstance(details, list):
        merged = {}
        for d in details:
            if isinstance(d, dict):
                merged.update(d)
        details = merged
    if not isinstance(details, dict):
        details = {}

    items = parsed.get("items", [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        items = []
    items = [i for i in items if isinstance(i, dict)]

    return {"details": details, "items": items}


# ============================================================
# 4. PADDLEOCR-VL SPOTTING
# ============================================================

LOC_PATTERN = re.compile(
    r"^(.*?)"
    r"<\|LOC_(\d+)\|><\|LOC_(\d+)\|>"
    r"<\|LOC_(\d+)\|><\|LOC_(\d+)\|>"
    r"<\|LOC_(\d+)\|><\|LOC_(\d+)\|>"
    r"<\|LOC_(\d+)\|><\|LOC_(\d+)\|>$"
)


def run_paddle_spotting(image_bytes, model="seriouswebby/paddleocr-vl-1.6:spotting"):
    resp = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": "Spotting:", "images": [image_bytes]}],
        options={"num_ctx": 8196},
        keep_alive=-1,
    )
    return resp["message"]["content"]


def parse_paddle_spotting(raw_text, img_width, img_height):
    """Raw spotting text → [{'text': str, 'box': [x1,y1,x2,y2]}]"""
    lines = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = LOC_PATTERN.match(line)
        if not m:
            continue
        text = m.group(1).strip()
        coords = [int(m.group(i)) for i in range(2, 10)]
        xs = [coords[0], coords[2], coords[4], coords[6]]
        ys = [coords[1], coords[3], coords[5], coords[7]]
        lines.append({
            "text": text,
            "box": [
                int(min(xs) / 1000 * img_width),
                int(min(ys) / 1000 * img_height),
                int(max(xs) / 1000 * img_width),
                int(max(ys) / 1000 * img_height),
            ],
        })
    return lines


# ============================================================
# 5. MATCHING HELPERS
# ============================================================

def _clean_basic(x):
    """Strip commas, $, whitespace. Used for details matching (matches Woof)."""
    return str(x).replace(",", "").replace("$", "").strip()


def _clean_money(x):
    """Strip commas, $, USD, whitespace. Used for item fields (matches Woof)."""
    return str(x).replace(",", "").replace("$", "").replace("USD", "").strip()


def find_value_in_lines(value, lines, threshold=70):
    target = _clean_basic(value).lower()
    if not target:
        return None
    best_score, best_box = 0, None
    for line in lines:
        s = fuzz.partial_ratio(target, _clean_basic(line["text"]).lower())
        if s > best_score:
            best_score, best_box = s, line["box"]
    return best_box if best_score >= threshold else None


def find_row_lines(anchor_text, lines, tolerance_factor=0.8):
    anchor_line, best_score = None, 0
    target = anchor_text.lower()
    for line in lines:
        text = line["text"].lower()
        p = fuzz.partial_ratio(target, text)
        r = fuzz.ratio(target, text)
        if p >= 85 and r >= 40 and p > best_score:
            best_score, anchor_line = p, line
    if not anchor_line:
        return []

    cy = (anchor_line["box"][1] + anchor_line["box"][3]) / 2
    h  = anchor_line["box"][3] - anchor_line["box"][1]
    tol = max(h * tolerance_factor, 8)

    row = [l for l in lines
           if abs((l["box"][1] + l["box"][3]) / 2 - cy) <= tol]
    row.sort(key=lambda l: l["box"][0])
    return row


# ============================================================
# 6. LOCATE (details + items)
# ============================================================

def locate_values(details, items, lines):
    """
    Returns:
        {
          "details": {field_name: {"value": str, "bbox": [...] or None}},
          "items": [
             {field_name: {"value": str, "bbox": [...] or None}, ...},
             ...
          ]
        }
    A bbox of None means "not found on the image" (so we can flag it).
    """
    details_out = {}
    for field, val in details.items():
        if val is None or (isinstance(val, float) and pd.isna(val)):
            details_out[field] = {"value": None, "bbox": None}
            continue
        box = find_value_in_lines(val, lines)
        details_out[field] = {"value": str(val), "bbox": box}

    items_out = []
    for item in items:
        entry = {}
        name = item.get("product_name")
        if not name:
            items_out.append(entry)
            continue

        row = find_row_lines(name, lines)
        if not row:
            entry["product_name"] = {"value": name, "bbox": None}
        else:
            anchor_line, s = None, 0
            for l in row:
                sc = fuzz.partial_ratio(name.lower(), l["text"].lower())
                if sc > s:
                    s, anchor_line = sc, l
            anchor_line = anchor_line or row[0]
            entry["product_name"] = {"value": name, "bbox": anchor_line["box"]}

            used = {tuple(anchor_line["box"])}
            for field in ["quantity", "unit_price", "total"]:
                tv = item.get(field)
                if tv is None or (isinstance(tv, float) and pd.isna(tv)):
                    continue
                target = _clean_money(tv)
                if not target:
                    entry[field] = {"value": str(tv), "bbox": None}
                    continue
                best_s, best_box = 0, None
                for l in row:
                    if tuple(l["box"]) in used:
                        continue
                    lc = _clean_money(l["text"])
                    if target == lc:
                        sc = 100
                    elif target in lc:
                        sc = 95
                    else:
                        sc = fuzz.partial_ratio(target, lc)
                    if sc > best_s:
                        best_s, best_box = sc, l["box"]
                if best_s >= 60 and best_box:
                    used.add(tuple(best_box))
                    entry[field] = {"value": str(tv), "bbox": best_box}
                else:
                    entry[field] = {"value": str(tv), "bbox": None}

        items_out.append(entry)

    return {"details": details_out, "items": items_out}

# ============================================================
# 7. DRAW
# ============================================================

def draw_boxes(img_path, located, out_path, padding=4):
    with Image.open(img_path) as im:
        im = im.convert("RGB")
        W, H = im.size
        draw = ImageDraw.Draw(im)

        # Details — yellow
        for field, entry in located.get("details", {}).items():
            box = entry.get("bbox")
            if not box:
                continue
            x1, y1, x2, y2 = box
            draw.rectangle(
                [max(0, x1 - padding), max(0, y1 - padding),
                 min(W, x2 + padding), min(H, y2 + padding)],
                outline="yellow", width=3,
            )

        # Items — green
        for item in located.get("items", []):
            for field, entry in item.items():
                box = entry.get("bbox")
                if not box:
                    continue
                x1, y1, x2, y2 = box
                draw.rectangle(
                    [max(0, x1 - padding), max(0, y1 - padding),
                     min(W, x2 + padding), min(H, y2 + padding)],
                    outline="green", width=3,
                )

        im.save(out_path)
        return out_path


# ============================================================
# 8. Bactch invoice processing (end-to-end)
# ============================================================

def preprocess_all(image_paths):
    """Phase 1: preprocess every image. Returns {filename: bytes}."""
    out = {}
    for path in image_paths:
        out[os.path.basename(path)] = preprocess_invoice(path)
    return out


def deepseek_ocr_all(preprocessed):
    """Phase 2: OCR every invoice with DeepSeek. Returns {filename: raw_text}."""
    out = {}
    for filename, img_bytes in preprocessed.items():
        out[filename] = run_deepseek_ocr(img_bytes)
    return out


def structure_all(ocr_results, schema_prompt):
    """Phase 3: Llama structures each OCR result. Returns {filename: {'details':..., 'items':...}}."""
    out = {}
    for filename, raw_text in ocr_results.items():
        parsed = structure_with_llama(raw_text, schema_prompt)
        out[filename] = normalize_extraction(parsed)
    return out


def paddle_spot_all(preprocessed, image_paths):
    """Phase 4: PaddleOCR-VL spots on every invoice. Returns {filename: [lines]}."""
    out = {}
    by_name = {os.path.basename(p): p for p in image_paths}
    for filename, img_bytes in preprocessed.items():
        raw = run_paddle_spotting(img_bytes)
        with Image.open(by_name[filename]) as im:
            W, H = im.size
        out[filename] = parse_paddle_spotting(raw, W, H)
    return out


def locate_and_draw_all(structured, spotting, image_paths, out_folder):
    """Phase 5: locate values + draw boxes per invoice."""
    os.makedirs(out_folder, exist_ok=True)
    by_name = {os.path.basename(p): p for p in image_paths}
    results = {}
    for filename, data in structured.items():
        lines = spotting.get(filename, [])
        located = locate_values(data["details"], data["items"], lines)
        annotated_path = os.path.join(out_folder, f"annotated_{filename}")
        draw_boxes(by_name[filename], located, annotated_path)
        results[filename] = {
            "file": filename,
            "path": by_name[filename],
            "annotated_path": annotated_path,
            "details": data["details"],
            "items": data["items"],
            "located": located,
        }
    return results