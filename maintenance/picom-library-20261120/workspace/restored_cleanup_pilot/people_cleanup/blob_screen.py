#!/usr/bin/env python3
"""Read-only, one-worker screen for possible thick near-white components.

This reports queue candidates only. It makes no semantic classifications and
grants no cleanup authority. It reads original WebP bytes and writes only JSON
checkpoints/reports; it never writes or re-encodes an image.
"""

import os

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
WORKSPACE = PILOT.parent
LIBRARY = Path("/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library")
OUT = HERE / "blob_screen"
EXPECTED_CENSUS = 10891
PROGRESS_CALIBRATION = 100
PROGRESS_CENSUS = 500


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(path, record, *, sync=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()
        if sync:
            os.fsync(f.fileno())


def checkpoint_index(path):
    records = {}
    if not Path(path).exists():
        return records
    with Path(path).open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") == "ok":
                records[(row["source"], row["source_sha256"])] = row
    return records


def calibration_items():
    refs_by_source = defaultdict(list)
    for cohort in ("development", "validation"):
        path = PILOT / cohort / "selection.json"
        for row in load_json(path)["images"]:
            refs_by_source[row["source"]].append({"cohort": cohort, "id": row["id"], "style_id": row["style_id"], "style": row["style"], "concept": row.get("concept")})
    inv_path = HERE / "inventory.json"
    for row in load_json(inv_path)["images"]:
        refs_by_source[row["source"]].append({"cohort": "people_inventory", "id": row["id"], "style_id": row["style_id"], "style": row["style"], "concept": row.get("concept")})
    return [
        {"source": source, "refs": refs}
        for source, refs in sorted(refs_by_source.items())
    ]


def census_items():
    inventory = load_json(HERE / "inventory.json")["images"]
    styles_by_id = {r["style_id"]: r["style"] for r in inventory}
    if len(styles_by_id) != 16:
        raise RuntimeError(f"expected 16 styles in People inventory; found {len(styles_by_id)}")
    items = []
    for style_id, style in sorted(styles_by_id.items()):
        style_root = LIBRARY / style
        if not style_root.is_dir():
            raise FileNotFoundError(f"missing style directory from inventory: {style_root}")
        category_root = style_root / "People & Relationships"
        if not category_root.is_dir():
            raise FileNotFoundError(f"missing category folder: {category_root}")
        for source in sorted(category_root.rglob("*.webp")):
            rel_parent = source.parent.relative_to(style_root).as_posix()
            items.append({"source": str(source), "refs": [{"cohort": "people_relationships_census", "style_id": style_id, "style": style, "subfolder": rel_parent}]})
    if len(items) != EXPECTED_CENSUS:
        raise RuntimeError(f"expected exactly {EXPECTED_CENSUS} People & Relationships WebPs; found {len(items)}. No census started.")
    return items


def screen_bytes(raw, source, refs, np, ndi, Image):
    digest = sha256(raw)
    try:
        with Image.open(BytesIO(raw)) as im:
            rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    except Exception as exc:
        raise RuntimeError(f"corrupt or undecodable image: {source}: {type(exc).__name__}: {exc}") from exc
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise RuntimeError(f"decoded image is not RGBA: {source}")
    h, w = rgba.shape[:2]
    scale = max(h, w) / 512.0
    rgb = rgba[:, :, :3]
    low, high = rgb.min(axis=2), rgb.max(axis=2)
    spread = high - low
    alpha = rgba[:, :, 3]

    broad = (low >= 230) & (spread <= 30) & (alpha >= 128)
    labels, label_count = ndi.label(broad, structure=np.ones((3, 3), dtype=np.uint8))
    # One distance transform for the image; aggregate max distance per label.
    distance = ndi.distance_transform_edt(broad)
    areas = np.bincount(labels.ravel(), minlength=label_count + 1)
    max_distance = np.zeros(label_count + 1, dtype=np.float32)
    np.maximum.at(max_distance, labels.ravel(), distance.ravel())
    broad_area_min = 64.0 * scale * scale
    focused_area_min = 128.0 * scale * scale
    broad_depth_min = 2.0 * scale
    focused_depth_min = 3.0 * scale
    ids = np.arange(1, label_count + 1)
    broad_ids = ids[(areas[1:] >= broad_area_min) & (max_distance[1:] >= broad_depth_min)]
    focused_ids = ids[(areas[1:] >= focused_area_min) & (max_distance[1:] >= focused_depth_min)]

    # Original strict-white core is a separate raw count, not either queue rule.
    strict = (low >= 240) & (spread <= 20) & (alpha >= 128)
    strict_labels, strict_count = ndi.label(strict, structure=np.ones((3, 3), dtype=np.uint8))
    strict_areas = np.bincount(strict_labels.ravel(), minlength=strict_count + 1)
    strict_pixels = int(strict.sum())

    selected = set(map(int, broad_ids))
    boxes = []
    for lab in sorted(selected):
        yy, xx = np.nonzero(labels == lab)
        boxes.append({
            "component": lab,
            "area_px": int(areas[lab]),
            "area_at_512": round(float(areas[lab]) / (scale * scale), 3),
            "max_edge_distance_px": round(float(max_distance[lab]), 3),
            "max_edge_distance_at_512": round(float(max_distance[lab] / scale), 3),
            "bbox_xyxy": [int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1],
            "focused_candidate": bool(lab in set(map(int, focused_ids))),
        })
    style_id = refs[0].get("style_id") if refs else None
    style = refs[0].get("style") if refs else None
    subfolder = refs[0].get("subfolder")
    return {
        "status": "ok",
        "source": str(source),
        "source_sha256": digest,
        "source_bytes": len(raw),
        "dimensions": [w, h],
        "scale_from_512": scale,
        "refs": refs,
        "style_id": style_id,
        "style": style,
        "subfolder": subfolder,
        "broad_nearwhite_pixel_count": int(broad.sum()),
        "broad_component_count": int(label_count),
        "broad_candidate_component_count": int(len(broad_ids)),
        "focused_candidate_component_count": int(len(focused_ids)),
        "candidate_image_broad": bool(len(broad_ids)),
        "candidate_image_focused": bool(len(focused_ids)),
        "candidate_components": boxes,
        "strict_white_core_pixel_count": strict_pixels,
        "strict_white_core_component_count": int(strict_count),
        "strict_white_core_component_area_ge_8_at_512_count": int(np.sum(strict_areas[1:] >= max(1, round(8 * scale * scale)))),
        "rules": {
            "broad": {"rgb_min": 230, "max_channel_range": 30, "min_alpha": 128, "connectivity": 8, "min_area_at_512": 64, "min_max_edge_distance_at_512": 2},
            "focused": {"same_color_mask": "broad", "connectivity": 8, "min_area_at_512": 128, "min_max_edge_distance_at_512": 3},
            "strict_core_count": {"rgb_min": 240, "max_channel_range": 20, "min_alpha": 128},
        },
    }


def apply_item_context(row, item, phase):
    row = dict(row)
    new_refs = item.get("refs", [])
    if phase.startswith("people_relationships_census") and new_refs:
        # A cached calibration row may contain stale/empty grouping fields.
        # The census item supplies the authoritative style/subfolder context.
        old_refs = [r for r in row.get("refs", []) if r.get("cohort") != "people_relationships_census"]
        row["refs"] = old_refs + new_refs
        row["style_id"] = new_refs[0].get("style_id")
        row["style"] = new_refs[0].get("style")
        row["subfolder"] = new_refs[0].get("subfolder")
        row["census_context_source"] = "inventory_style_root_and_source_relative_parent"
    else:
        row["refs"] = new_refs
    return row


def summarize(records, phase, started, errors):
    by_style = defaultdict(lambda: {"images": 0, "broad_candidate_images": 0, "focused_candidate_images": 0, "broad_candidate_components": 0, "focused_candidate_components": 0, "strict_core_pixels": 0})
    by_subfolder = defaultdict(lambda: {"images": 0, "broad_candidate_images": 0, "focused_candidate_images": 0, "broad_candidate_components": 0, "focused_candidate_components": 0, "strict_core_pixels": 0})
    for row in records:
        if row.get("status") != "ok":
            continue
        style_key = f"{row.get('style_id')}:{row.get('style')}"
        sub_key = f"{style_key}/{row.get('subfolder') or 'pilot_selection'}"
        for key, bucket in ((style_key, by_style), (sub_key, by_subfolder)):
            agg = bucket[key]
            agg["images"] += 1
            agg["broad_candidate_images"] += int(row["candidate_image_broad"])
            agg["focused_candidate_images"] += int(row["candidate_image_focused"])
            agg["broad_candidate_components"] += row["broad_candidate_component_count"]
            agg["focused_candidate_components"] += row["focused_candidate_component_count"]
            agg["strict_core_pixels"] += row["strict_white_core_pixel_count"]
    broad_rows = [r for r in records if r.get("status") == "ok" and r["candidate_image_broad"]]
    focused_rows = [r for r in records if r.get("status") == "ok" and r["candidate_image_focused"]]
    return {
        "phase": phase,
        "images_screened": sum(r.get("status") == "ok" for r in records),
        "exception_count": len(errors),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "broad_candidate_image_count": len(broad_rows),
        "focused_candidate_image_count": len(focused_rows),
        "broad_candidate_ids": [{"source": r["source"], "source_sha256": r["source_sha256"], "refs": r.get("refs", []), "component_count": r["broad_candidate_component_count"]} for r in broad_rows],
        "focused_candidate_ids": [{"source": r["source"], "source_sha256": r["source_sha256"], "refs": r.get("refs", []), "component_count": r["focused_candidate_component_count"]} for r in focused_rows],
        "counts_by_style": dict(sorted(by_style.items())),
        "counts_by_style_subfolder": dict(sorted(by_subfolder.items())),
        "errors": errors,
    }


def run_phase(phase, items, checkpoint_path, summary_path, progress_every, *, reusable=None):
    import numpy as np
    from scipy import ndimage as ndi
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    existing = checkpoint_index(checkpoint_path)
    reusable = reusable or {}
    started = time.monotonic()
    records = []
    errors = []
    n_total = len(items)
    reuse_count = 0
    for idx, item in enumerate(items, 1):
        source = Path(item["source"]).expanduser().resolve(strict=True)
        refs = item.get("refs", [])
        raw = source.read_bytes()
        digest = sha256(raw)
        key = (str(source), digest)
        if key in existing:
            row = apply_item_context(existing[key], item, phase)
            records.append(row)
            reuse_count += 1
        elif key in reusable:
            row = apply_item_context(reusable[key], item, phase)
            records.append(row)
            append_jsonl(checkpoint_path, row, sync=(idx % 100 == 0))
            reuse_count += 1
        else:
            t0 = time.monotonic()
            try:
                row = screen_bytes(raw, source, refs, np, ndi, Image)
                row = apply_item_context(row, item, phase)
                row["file_elapsed_seconds"] = round(time.monotonic() - t0, 4)
                append_jsonl(checkpoint_path, row, sync=(idx % 100 == 0 or idx == n_total))
                records.append(row)
            except Exception as exc:
                error = {"status": "exception", "source": str(source), "source_sha256": digest, "error": f"{type(exc).__name__}: {exc}"}
                errors.append(error)
                append_jsonl(checkpoint_path, error, sync=True)
                atomic_json(summary_path, summarize(records, phase, started, errors))
                raise RuntimeError(f"screen halted on exception; not silently skipped: {error}") from exc
        if idx % progress_every == 0 or idx == n_total:
            elapsed = time.monotonic() - started
            done = idx
            cand = sum(r.get("status") == "ok" and r["candidate_image_broad"] for r in records)
            focused = sum(r.get("status") == "ok" and r["candidate_image_focused"] for r in records)
            print(f"{phase}: {done}/{n_total} images; broad candidates={cand}, focused={focused}, reused={reuse_count}; elapsed={elapsed:.1f}s", flush=True)
            atomic_json(summary_path, summarize(records, phase, started, errors))
    report = summarize(records, phase, started, errors)
    report["reused_from_checkpoint_or_prior_phase"] = reuse_count
    report["expected_total"] = n_total
    atomic_json(summary_path, report)
    return report, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("calibration", "census"))
    args = parser.parse_args()
    if args.phase == "calibration":
        items = calibration_items()
        checkpoint = OUT / "calibration_checkpoint.jsonl"
        summary = OUT / "calibration_summary.json"
        report, _ = run_phase("calibration_680_plus_48", items, checkpoint, summary, PROGRESS_CALIBRATION)
        print(f"CALIBRATION DONE: rows={len(items)} broad={report['broad_candidate_image_count']} focused={report['focused_candidate_image_count']} elapsed={report['elapsed_seconds']:.1f}s", flush=True)
    else:
        items = census_items()
        cal_path = OUT / "calibration_checkpoint.jsonl"
        reusable = checkpoint_index(cal_path)
        checkpoint = OUT / "census_checkpoint.jsonl"
        summary = OUT / "census_summary.json"
        report, _ = run_phase("people_relationships_census_10891", items, checkpoint, summary, PROGRESS_CENSUS, reusable=reusable)
        print(f"CENSUS DONE: rows={len(items)} broad={report['broad_candidate_image_count']} focused={report['focused_candidate_image_count']} elapsed={report['elapsed_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
