#!/usr/bin/env python3
"""Select and render one random, grouped source-review batch from the blob screen.

Reads originals only; emits a manifest plus source/contact/overlay PNGs. It does
not clean images, change ROIs, encode WebP, or modify Library files.
"""

import os

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
SCREEN_DIR = HERE / "blob_screen"
OUT = HERE / "batch002"
SEED = 20261104
TARGET_CANDIDATE_VERSIONS = 100
MAX_CANDIDATE_VERSIONS = 115
REFERENCE_STYLE_PREFERENCE = (6, 2, 12)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def normalized_stem(source):
    stem = Path(source).stem.casefold()
    # Collapse only whitespace, hyphen, and underscore. Parenthetical variants
    # such as "(1)" remain in the key and are never merged with the base name.
    return re.sub(r"[\s_-]+", "", stem)


def group_key(row):
    return f"{row['subfolder']}::{normalized_stem(row['source'])}"


def read_records(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_census_rows():
    rows = read_records(SCREEN_DIR / "census_checkpoint.jsonl")
    if len(rows) != 10891 or any(r.get("status") != "ok" for r in rows):
        raise RuntimeError("batch002 requires the complete, exception-free 10,891-image census")
    inventory = json.loads((HERE / "inventory.json").read_text())
    styles = {r["style_id"]: r["style"] for r in inventory["images"]}
    style_ids = {name: sid for sid, name in styles.items()}
    for row in rows:
        source = Path(row["source"]).resolve()
        try:
            rel = source.relative_to(Path("/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library").resolve())
        except ValueError as exc:
            raise ValueError(f"census source escaped Library: {source}") from exc
        if not rel.parts or rel.parts[0] not in style_ids:
            raise ValueError(f"cannot resolve census style from source path: {source}")
        style = rel.parts[0]
        sid = style_ids[style]
        if len(rel.parts) < 3 or rel.parts[1] != "People & Relationships":
            raise ValueError(f"census file is outside People & Relationships: {source}")
        subfolder = Path(*rel.parts[1:-1]).as_posix()
        row["style_id"], row["style"], row["subfolder"] = sid, style, subfolder
        row["census_context_source"] = "source_path_relative_to_library_style_root"
        row["refs"] = [r for r in row.get("refs", []) if r.get("cohort") != "people_relationships_census"] + [{
            "cohort": "people_relationships_census", "style_id": sid, "style": style, "subfolder": subfolder,
        }]
    return rows


def build_groups(rows):
    grouped = {}
    for row in rows:
        key = group_key(row)
        grouped.setdefault(key, []).append(row)
    for versions in grouped.values():
        versions.sort(key=lambda r: (r["style_id"], r["source"].casefold()))
    return grouped


def choose_groups(grouped):
    eligible = []
    excluded_too_large = []
    for key, versions in grouped.items():
        n_candidates = sum(bool(r["candidate_image_focused"]) for r in versions)
        if not n_candidates:
            continue
        entry = {"key": key, "versions": versions, "candidate_versions": n_candidates}
        if n_candidates > MAX_CANDIDATE_VERSIONS:
            excluded_too_large.append({"key": key, "candidate_versions": n_candidates})
        else:
            eligible.append(entry)
    eligible.sort(key=lambda g: g["key"])
    rng = random.Random(SEED)
    rng.shuffle(eligible)
    chosen = []
    skipped_capacity = []
    total = 0
    for rank, group in enumerate(eligible, 1):
        group["shuffle_rank"] = rank
        n = group["candidate_versions"]
        if total >= TARGET_CANDIDATE_VERSIONS:
            break
        if total + n > MAX_CANDIDATE_VERSIONS:
            skipped_capacity.append({"key": group["key"], "candidate_versions": n, "candidate_versions_if_added": total + n, "shuffle_rank": rank})
            continue
        chosen.append(group)
        total += n
    if not (TARGET_CANDIDATE_VERSIONS <= total <= MAX_CANDIDATE_VERSIONS):
        raise RuntimeError(f"could not choose a whole-group batch in the 100–115 range; got {total}")
    return chosen, {
        "seed": SEED,
        "eligible_group_count": len(eligible),
        "eligible_groups_exceeding_115_excluded": excluded_too_large,
        "groups_skipped_to_stay_at_or_below_115": skipped_capacity,
        "random_group_order": [g["key"] for g in eligible],
    }


def assign_roles(group):
    versions = group["versions"]
    candidates = [r for r in versions if r["candidate_image_focused"]]
    nonbroad = [r for r in versions if not r["candidate_image_broad"]]
    if nonbroad:
        preferred = [r for sid in REFERENCE_STYLE_PREFERENCE for r in nonbroad if r["style_id"] == sid]
        reference = preferred[0] if preferred else nonbroad[0]
    else:
        reference = None
    role_by_source = {r["source"]: "noncandidate_unchanged_no_visual_review" for r in versions}
    for r in candidates:
        role_by_source[r["source"]] = "candidate_pending_visual_source_review"
    if reference:
        role_by_source[reference["source"]] = "reference_pending_pose_comparison"
    return candidates, reference, role_by_source


def make_plan(grouped, chosen, selection_stats, census_sha):
    planned = []
    candidate_total = 0
    for index, group in enumerate(chosen, 1):
        candidates, reference, roles = assign_roles(group)
        candidate_total += len(candidates)
        group_id = f"g{index:03d}"
        all_versions = []
        for row in group["versions"]:
            role = roles[row["source"]]
            if role == "noncandidate_unchanged_no_visual_review" and row["candidate_image_broad"]:
                role = "broad_only_nonselected_unchanged_no_visual_review"
            all_versions.append({
                "batch_id": f"b02_s{row['style_id']:02d}_{Path(row['source']).stem}",
                "style_id": row["style_id"],
                "style": row["style"],
                "source": row["source"],
                "source_sha256": row["source_sha256"],
                "source_bytes": row["source_bytes"],
                "dimensions": row["dimensions"],
                "normalized_subfolder": row["subfolder"],
                "normalized_stem": normalized_stem(row["source"]),
                "broad_candidate": row["candidate_image_broad"],
                "focused_candidate": row["candidate_image_focused"],
                "broad_candidate_component_count": row["broad_candidate_component_count"],
                "focused_candidate_component_count": row["focused_candidate_component_count"],
                "strict_white_core_pixel_count": row["strict_white_core_pixel_count"],
                "candidate_components": row["candidate_components"],
                "role": role,
                "reference_is_not_automatic_pose_equivalence": role == "reference_pending_pose_comparison",
            })
        planned.append({
            "group_id": group_id,
            "group_key": group["key"],
            "subfolder_exact": group["versions"][0]["subfolder"],
            "normalized_stem": normalized_stem(group["versions"][0]["source"]),
            "random_shuffle_rank": group["shuffle_rank"],
            "available_style_versions": len(group["versions"]),
            "candidate_versions": len(candidates),
            "reference_id": None if reference is None else f"b02_s{reference['style_id']:02d}_{Path(reference['source']).stem}",
            "reference_selection_note": "first screened broad-negative version in preferred style order" if reference else "no broad-negative noncandidate reference available",
            "versions": all_versions,
        })
    return {
        "batch_id": "batch002",
        "schema_version": 1,
        "status": "source_visual_review_pending",
        "filter_version": "blob-screen-v1",
        "census_summary_sha256": census_sha,
        "random_seed": SEED,
        "random_selection": selection_stats,
        "selection_probability_caveat": "Whole concept groups were selected by a seeded random permutation until the candidate-version count first reached 100–115. This is cluster sampling, not equal-probability sampling per image; some groups larger than 115 were excluded by the fixed cap. Candidate flags do not mean a human-confirmed background blob.",
        "target_candidate_versions": TARGET_CANDIDATE_VERSIONS,
        "maximum_candidate_versions": MAX_CANDIDATE_VERSIONS,
        "selected_candidate_versions": candidate_total,
        "selected_group_count": len(planned),
        "groups": planned,
    }


def save_group_previews(group, final_dir, np, Image, ImageDraw):
    if final_dir.exists():
        marker = final_dir / "checkpoint.json"
        if not marker.exists():
            raise FileExistsError(f"partial group directory lacks checkpoint: {final_dir}")
        checkpoint = json.loads(marker.read_text())
        for item in checkpoint["outputs"]:
            file = final_dir / item["file"]
            if not file.is_file() or sha_file(file) != item["sha256"]:
                raise ValueError(f"saved group preview hash mismatch: {file}")
        return checkpoint

    temp_dir = final_dir.with_name(f".{final_dir.name}.stage-{os.getpid()}")
    temp_dir.mkdir(parents=True, exist_ok=False)
    outputs = []
    contact_items = []
    try:
        for version in group["versions"]:
            if version["role"] not in ("candidate_pending_visual_source_review", "reference_pending_pose_comparison"):
                continue
            source_path = Path(version["source"])
            raw = source_path.read_bytes()
            if sha256(raw) != version["source_sha256"]:
                raise ValueError(f"source changed after census: {source_path}")
            with Image.open(source_path) as im:
                rgba = im.convert("RGBA")
                if list(rgba.size) != version["dimensions"]:
                    raise ValueError(f"dimension change after census: {source_path}")
                bg = Image.new("RGBA", rgba.size, (86, 67, 118, 255))
                bg.alpha_composite(rgba)
                source_rgb = bg.convert("RGB")
            file_id = version["batch_id"]
            source_file = f"{file_id}_source.png"
            source_rgb.save(temp_dir / source_file, format="PNG", optimize=False)
            outputs.append({"file": source_file, "sha256": sha_file(temp_dir / source_file), "role": version["role"], "source_sha256": version["source_sha256"]})
            if version["role"] == "candidate_pending_visual_source_review":
                overlay = source_rgb.copy()
                draw = ImageDraw.Draw(overlay)
                line = max(1, round(max(rgba.size) / 512))
                for comp in version["candidate_components"]:
                    if not comp.get("focused_candidate"):
                        continue
                    x0, y0, x1, y1 = comp["bbox_xyxy"]
                    # Outlines only; raw source PNG remains beside this overlay.
                    draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 40, 190), width=line)
                overlay_file = f"{file_id}_bbox_overlay.png"
                overlay.save(temp_dir / overlay_file, format="PNG", optimize=False)
                outputs.append({"file": overlay_file, "sha256": sha_file(temp_dir / overlay_file), "role": "bbox_overlay", "source_sha256": version["source_sha256"]})
            if version["dimensions"] == [512, 512]:
                contact_items.append((file_id, source_rgb))

        # Native512 2×2 sheets, four tiles per page; no symbol resampling.
        for page_no, start in enumerate(range(0, len(contact_items), 4), 1):
            part = contact_items[start:start + 4]
            tile_w, tile_h, gutter, label_h = 512, 512, 12, 28
            sheet = Image.new("RGB", (2 * tile_w + 3 * gutter, 2 * (tile_h + label_h) + 3 * gutter), (86, 67, 118))
            draw = ImageDraw.Draw(sheet)
            for k, (file_id, image) in enumerate(part):
                col, row = k % 2, k // 2
                x = gutter + col * (tile_w + gutter)
                y = gutter + row * (tile_h + label_h + gutter)
                draw.text((x, y), file_id, fill=(255, 255, 255))
                sheet.paste(image, (x, y + label_h))
            filename = f"contact_512_page_{page_no:02d}.png"
            sheet.save(temp_dir / filename, format="PNG", optimize=False)
            outputs.append({"file": filename, "sha256": sha_file(temp_dir / filename), "role": "native512_contact_sheet"})
        checkpoint = {
            "group_id": group["group_id"],
            "group_key": group["group_key"],
            "completed_utc": utc_now(),
            "outputs": outputs,
        }
        atomic_json(temp_dir / "checkpoint.json", checkpoint)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_dir, final_dir)
        return checkpoint
    except Exception:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def main():
    # Heavy image modules are delayed until after thread limits are installed.
    import numpy as np
    from PIL import Image, ImageDraw

    prep_start = utc_now()
    t0 = time.monotonic()
    census_path = SCREEN_DIR / "census_summary.json"
    census = json.loads(census_path.read_text())
    census_sha = sha_file(census_path)
    if census.get("phase") != "people_relationships_census_10891" or census.get("images_screened") != 10891 or census.get("exception_count") != 0:
        raise RuntimeError("batch002 requires the completed, clean 10,891-image census summary")
    rows = load_census_rows()
    grouped = build_groups(rows)
    chosen, stats = choose_groups(grouped)
    plan = make_plan(grouped, chosen, stats, census_sha)
    plan["prep_started_utc"] = prep_start
    plan["checkpoint_policy"] = "atomic per group; source SHA rechecked before every preview"
    plan_path = OUT / "selection_plan.json"
    OUT.mkdir(parents=True, exist_ok=True)
    if plan_path.exists():
        previous = json.loads(plan_path.read_text())
        if previous.get("random_seed") != SEED or previous.get("census_summary_sha256") != census_sha or previous.get("selected_candidate_versions") != plan["selected_candidate_versions"]:
            raise ValueError("existing batch002 plan differs; refusing to overwrite")
        plan = previous
    else:
        atomic_json(plan_path, plan)

    # One sequential image worker; resume only from hash-verified group checkpoints.
    for index, group in enumerate(plan["groups"], 1):
        final_dir = OUT / "previews" / "groups" / group["group_id"]
        checkpoint = save_group_previews(group, final_dir, np, Image, ImageDraw)
        group["preview_checkpoint_sha256"] = sha_file(final_dir / "checkpoint.json")
        group["preview_files"] = [f"previews/groups/{group['group_id']}/{x['file']}" for x in checkpoint["outputs"]]
        atomic_json(plan_path, plan)
        print(f"batch002 preview group {index}/{len(plan['groups'])}: {group['group_id']} {group['group_key']} candidate_versions={group['candidate_versions']}", flush=True)

    plan["prep_finished_utc"] = utc_now()
    plan["prep_elapsed_seconds"] = round(time.monotonic() - t0, 3)
    plan["status"] = "source_visual_review_pending"
    atomic_json(OUT / "manifest.json", plan)
    atomic_json(plan_path, plan)
    print(f"BATCH002 READY: groups={plan['selected_group_count']} candidate_versions={plan['selected_candidate_versions']} prep_seconds={plan['prep_elapsed_seconds']}", flush=True)


if __name__ == "__main__":
    main()
