#!/usr/bin/env python3
"""Run only the production candidates with reviewer-selected, root-authorized source ROIs.

Outputs use the frozen cleaner's strict white-core component mask only. Every
selected pixel must satisfy RGB min>=240, channel range<=20, alpha>=128; only
its alpha is set to zero. Unchanged and uncertain candidates keep source bytes
in place and get no duplicate image output. This script never reads beyond the
frozen manifest and creates no Q80 files.
"""

import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "manifest.json"
BATCH = HERE
APPROVALS = HERE / "approved_decisions.json"
STATE = HERE / "selected_run_state.json"
OUT = HERE / "selected_outputs"
PROTOCOL = HERE / "protocol.json"
CLEANER = ROOT / "scripts" / "cleaner.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def approved_candidates(manifest, approvals, manifest_sha):
    if approvals.get("batch_id") != manifest.get("batch_id") or approvals.get("manifest_sha256") != manifest_sha:
        raise ValueError("approval does not bind the current production manifest")
    root = approvals.get("root_approval", {})
    if root.get("approved") is not True or root.get("approved_by") != "root":
        raise ValueError("root approval is required before processing")
    versions = [v for g in manifest.get("groups", []) for v in g.get("versions", [])]
    ids = [v.get("batch_id") for v in versions]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", i) or Path(i).name != i or "/" in i or "\\" in i or "\x00" in i for i in ids):
        raise ValueError("manifest IDs must be unique and path-safe")
    candidates = versions
    if not candidates:
        raise ValueError("empty all-variant manifest")
    decisions = approvals.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("approved_decisions.json needs a decisions array")
    by_id = {d.get("id"): d for d in decisions}
    expected = {v["batch_id"] for v in candidates}
    if len(by_id) != len(decisions) or set(by_id) != expected:
        raise ValueError("approved decisions must cover every batch source exactly once")
    for v in candidates:
        d = by_id[v["batch_id"]]
        if d.get("source_sha256") != v.get("source_sha256") or d.get("dimensions") != v.get("dimensions"):
            raise ValueError(f"{v['batch_id']}: decision source binding differs from manifest")
        if not isinstance(d.get("reviewer"), str) or not d["reviewer"].strip():
            raise ValueError(f"{v['batch_id']}: source reviewer is required")
        if d.get("decision") not in ("cleanup", "unchanged", "uncertain"):
            raise ValueError(f"{v['batch_id']}: invalid decision")
        regions = d.get("regions", [])
        if not isinstance(regions, list) or (d["decision"] == "cleanup" and not regions) or (d["decision"] != "cleanup" and regions):
            raise ValueError(f"{v['batch_id']}: cleanup needs ROIs; retained decisions must have none")
        w, h = v["dimensions"]
        for r in regions:
            roi = r.get("roi", [])
            if len(roi) != 4 or not all(isinstance(q, int) for q in roi):
                raise ValueError(f"{v['batch_id']}: ROI must be integer [x0,y0,x1,y1]")
            x0, y0, x1, y1 = roi
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise ValueError(f"{v['batch_id']}: ROI outside native bounds")
            if r.get("transparent_seed") is not None or r.get("core_labels") or not r.get("core_seeds"):
                raise ValueError(f"{v['batch_id']}: only explicit white-core seeds are supported")
            for x, y in r["core_seeds"]:
                if not (isinstance(x, int) and isinstance(y, int) and x0 <= x < x1 and y0 <= y < y1):
                    raise ValueError(f"{v['batch_id']}: seed outside approved ROI")
    return candidates, by_id


def image_stack(protocol, expected_cleaner_sha):
    if protocol.get("rule_version") != "people-white-core-v1" or sha_file(CLEANER) != expected_cleaner_sha:
        raise RuntimeError("pinned people-white-core-v1 cleaner hash mismatch")
    sys.path.insert(0, str(CLEANER.parent))
    import numpy as np
    from PIL import Image
    from cleaner import cleanup
    return np, Image, cleanup


def save_image(Image, image, path, **kwargs):
    tmp = Path(path).with_name(Path(path).name + f".tmp-{os.getpid()}")
    image.save(tmp, **kwargs)
    with tmp.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp, path)


def run_one(np, Image, cleanup, row, decision, manifest_sha, decision_sha, cleaner_sha):
    started = time.perf_counter()
    source_path = Path(row["source"]).expanduser().resolve(strict=True)
    if sha_file(source_path) != row["source_sha256"]:
        raise ValueError(f"{row['batch_id']}: source SHA256 differs from manifest")
    with Image.open(source_path) as im:
        source = np.asarray(im.convert("RGBA"), dtype=np.uint8)
        dims = [im.width, im.height]
    if dims != row["dimensions"]:
        raise ValueError(f"{row['batch_id']}: native dimensions differ from manifest")
    ident = row["batch_id"]
    if decision["decision"] != "cleanup":
        return {"id": ident, "status": "retained_no_edit", "source_sha256": row["source_sha256"],
                "decision_sha256": decision_sha, "changed_pixels": 0, "output_created": False,
                "retain_reason": decision["decision"], "processing_seconds": round(time.perf_counter()-started, 6)}

    rgb = source[:, :, :3]
    white = (rgb.min(2) >= 240) & ((rgb.max(2)-rgb.min(2)) <= 20) & (source[:, :, 3] >= 128)
    for region in decision["regions"]:
        x0, y0, x1, y1 = region["roi"]
        for x, y in region["core_seeds"]:
            if not white[y, x]:
                raise ValueError(f"{ident}: seed {(x,y)} does not meet frozen white-core threshold")
    cleaner_decision = {"id": ident, "regions": decision["regions"],
                        "protected_boxes": decision.get("protected_boxes", []),
                        "protected_polygons": decision.get("protected_polygons", [])}
    _matte_output, masks, _ = cleanup(source, cleaner_decision)
    roi = np.zeros(source.shape[:2], dtype=bool)
    for region in decision["regions"]:
        x0, y0, x1, y1 = region["roi"]
        roi[y0:y1, x0:x1] = True
    # The minimum applies to each actual selected gap, not to unrelated white
    # foreground elsewhere in the image. Small regions never create an edit.
    from scipy import ndimage as ndi
    labels, _ = ndi.label(white, np.ones((3, 3)))
    minimum = int(np.ceil(256 * (max(dims) / 512) ** 2))
    removed = np.zeros(source.shape[:2], dtype=bool)
    effective_regions, omitted_regions = [], []
    for region in decision["regions"]:
        x0, y0, x1, y1 = region["roi"]
        selected_labels = [int(labels[y, x]) for x, y in region["core_seeds"]]
        part = np.zeros(source.shape[:2], dtype=bool)
        part[y0:y1, x0:x1] = np.isin(labels[y0:y1, x0:x1], selected_labels)
        part &= masks["core"] & white & ~masks["protected"]
        count = int(part.sum())
        detail = {"name": region["name"], "roi": region["roi"], "core_pixels": count,
                  "core_pixels_at_512": count / (max(dims) / 512) ** 2}
        if count < minimum:
            omitted_regions.append(dict(detail, reason="below_fixed_worthwhile_minimum"))
            continue
        removed |= part
        effective_regions.append(detail)
    after = source.copy()
    after[:, :, 3][removed] = 0
    if not removed.any():
        return {"id": ident, "status": "retained_no_edit", "source_sha256": row["source_sha256"],
                "decision_sha256": decision_sha, "changed_pixels": 0, "output_created": False,
                "retain_reason": "no_reviewed_region_meets_fixed_worthwhile_minimum",
                "omitted_regions": omitted_regions, "processing_seconds": round(time.perf_counter()-started, 6)}
    changed = np.any(source != after, axis=2)
    if not np.array_equal(source[:, :, :3], after[:, :, :3]) or not np.array_equal(changed, removed):
        raise AssertionError(f"{ident}: output changed beyond selected strict white core")
    if np.any(after[:, :, 3] > source[:, :, 3]) or not np.array_equal(source[~removed], after[~removed]):
        raise AssertionError(f"{ident}: alpha/non-core RGBA preservation failed")

    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / ident
    if final.exists():
        raise FileExistsError(f"refusing to overwrite {final}")
    stage = Path(tempfile.mkdtemp(prefix=f".{ident}.stage-", dir=OUT))
    try:
        out = stage / "after.webp"
        Image.fromarray(after, "RGBA").save(out, format="WEBP", lossless=True, exact=True, method=6)
        with Image.open(out) as im:
            decoded = np.asarray(im.convert("RGBA"), dtype=np.uint8)
        if not np.array_equal(decoded, after):
            raise AssertionError(f"{ident}: lossless WebP decode differs from output RGBA")
        mask_specs = {"removed_core_mask.png": removed, "roi_mask.png": roi, "protected_mask.png": masks["protected"]}
        for name, mask in mask_specs.items():
            save_image(Image, Image.fromarray(mask.astype("uint8")*255, "L"), stage / name, format="PNG")
        elapsed = round(time.perf_counter()-started, 6)
        artifact_hashes = {p.name: sha_file(p) for p in stage.iterdir() if p.is_file()}
        result = {"id": ident, "source_path": str(source_path), "source_sha256": row["source_sha256"],
                  "manifest_sha256": manifest_sha, "decision_sha256": decision_sha, "cleaner_sha256": cleaner_sha,
                  "dimensions": dims, "reviewer": decision["reviewer"], "operation": "strict_white_core_alpha_zero_only",
                  "threshold": {"rgb_min": 240, "max_channel_range": 20, "min_alpha": 128},
                  "regions": effective_regions, "omitted_regions": omitted_regions,
                  "minimum_core_pixels_per_region_at_512": 256,
                  "changed_pixels": int(removed.sum()), "output_sha256": artifact_hashes["after.webp"],
                  "output_bytes": out.stat().st_size, "decoded_rgba_sha256": sha(decoded.tobytes()),
                  "artifact_sha256": artifact_hashes, "processing_seconds": elapsed, "q80_created": False}
        (stage / "result.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        os.replace(stage, final)
        result["status"] = "changed"
        result["output_created"] = True
        return result
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify_existing(ident, row, output_result, decision_sha, manifest_sha, cleaner_sha):
    folder = OUT / ident
    if not folder.exists():
        folder = BATCH / "accepted_outputs" / ident
    result_path = folder / "result.json"
    if not result_path.is_file():
        raise ValueError(f"{ident}: changed checkpoint missing result.json")
    result = read(result_path)
    for key, value in (("source_sha256", row["source_sha256"]), ("decision_sha256", decision_sha),
                       ("manifest_sha256", manifest_sha), ("cleaner_sha256", cleaner_sha)):
        if result.get(key) != value:
            raise ValueError(f"{ident}: saved {key} mismatch")
    if result.get("id") != ident:
        raise ValueError(f"{ident}: saved result ID mismatch")
    for name, digest in result.get("artifact_sha256", {}).items():
        if not (folder/name).is_file() or sha_file(folder/name) != digest:
            raise ValueError(f"{ident}: saved artifact hash mismatch: {name}")
    if output_result and result.get("output_sha256") != output_result:
        raise ValueError(f"{ident}: run checkpoint output hash mismatch")
    return result


def main():
    global MANIFEST, APPROVALS, STATE, OUT, BATCH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    BATCH = args.batch.resolve(strict=True)
    from common import verify_batch_scope
    verify_batch_scope(BATCH)
    from non_people_publication import require_open_batch
    require_open_batch(BATCH, allow_existing=False)
    if not BATCH.is_relative_to(HERE / "batches"):
        raise ValueError("batch must be inside production/batches")
    MANIFEST = BATCH / "manifest.json"
    APPROVALS = BATCH / "approved_decisions.json"
    STATE = BATCH / "selected_run_state.json"
    OUT = BATCH / "selected_outputs"
    overall_start = time.perf_counter()
    if not MANIFEST.is_file() or not APPROVALS.is_file():
        raise FileNotFoundError("runner needs manifest.json and root-approved approved_decisions.json")
    manifest_bytes, approval_bytes = MANIFEST.read_bytes(), APPROVALS.read_bytes()
    manifest_sha, decision_sha = sha(manifest_bytes), sha(approval_bytes)
    manifest, approvals = json.loads(manifest_bytes), json.loads(approval_bytes)
    candidates, decisions = approved_candidates(manifest, approvals, manifest_sha)
    protocol = read(PROTOCOL)
    cleaner_sha = sha_file(CLEANER)
    if protocol.get("minimum_core_pixels_per_region_at_512") != 256 or protocol.get("execution_enabled") is not False or protocol.get("activation_overlay_may_enable_execution") is not True:
        raise ValueError("default-disabled protocol/activation-overlay contract or minimum differs")
    if cleaner_sha != protocol.get("engine", {}).get("sha256"):
        raise ValueError("frozen cleaner SHA does not match protocol pin")
    for row in candidates:
        if sha_file(Path(row["source"]).expanduser().resolve(strict=True)) != row["source_sha256"]:
            raise ValueError(f"{row['batch_id']}: manifest source hash changed")

    runner_sha = sha_file(__file__)
    if STATE.exists():
        state = read(STATE)
        pins = {"manifest_sha256": manifest_sha, "approved_decisions_sha256": decision_sha,
                "cleaner_sha256": cleaner_sha, "runner_sha256": runner_sha}
        if any(state.get(k) != v for k, v in pins.items()):
            raise ValueError("resume refused: manifest, approval, cleaner or runner changed")
    else:
        if OUT.exists() and any(OUT.iterdir()):
            raise FileExistsError("selected_outputs exists without a run checkpoint")
        state = {"batch_id": manifest["batch_id"], "status": "running", "manifest_sha256": manifest_sha,
                 "approved_decisions_sha256": decision_sha, "cleaner_sha256": cleaner_sha,
                 "runner_sha256": runner_sha, "candidate_count": len(candidates),
                 "reference_and_noncandidate_rows_not_processed": sum(len(g.get("versions",[])) for g in manifest["groups"]) - len(candidates),
                 "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "images": []}
        atomic_json(STATE, state)

    by_state = {r["id"]: r for r in state.get("images", [])}
    expected = {r["batch_id"] for r in candidates}
    if not set(by_state) <= expected:
        raise ValueError("checkpoint has IDs outside this manifest")
    row_by_id = {r["batch_id"]: r for r in candidates}
    for ident, saved in by_state.items():
        src = row_by_id[ident]
        if saved["status"] == "changed":
            verify_existing(ident, src, saved.get("output_sha256"), decision_sha, manifest_sha, cleaner_sha)
        elif sha_file(src["source"]) != src["source_sha256"] or (OUT/ident).exists():
            raise ValueError(f"{ident}: retained no-edit source/checkpoint mismatch")

    if state.get("status") == "complete":
        print(json.dumps({"status": "already_complete_verified", "images": len(by_state)}))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    preflight_seconds = round(start-overall_start, 6)
    np, Image, cleanup = image_stack(protocol, cleaner_sha)
    try:
        for row in candidates:
            ident = row["batch_id"]
            if ident in by_state:
                continue
            if (OUT/ident).exists():
                result = verify_existing(ident, row, None, decision_sha, manifest_sha, cleaner_sha)
                rec = {"id": ident, "status": "changed", "source_sha256": row["source_sha256"],
                       "decision_sha256": decision_sha, "output_sha256": result["output_sha256"],
                       "changed_pixels": result["changed_pixels"], "output_created": True,
                       "processing_seconds": result["processing_seconds"], "result_path": str(OUT/ident/"result.json")}
            else:
                result = run_one(np, Image, cleanup, row, decisions[ident], manifest_sha, decision_sha, cleaner_sha)
                rec = result if result["status"] == "retained_no_edit" else {
                    "id": ident, "status": "changed", "source_sha256": row["source_sha256"],
                    "decision_sha256": decision_sha, "output_sha256": result["output_sha256"],
                    "changed_pixels": result["changed_pixels"], "output_created": True,
                    "processing_seconds": result["processing_seconds"], "result_path": str(OUT/ident/"result.json")}
            state["images"].append(rec); by_state[ident] = rec
            state["run_elapsed_seconds"] = round(time.perf_counter()-start, 6)
            state["last_image_seconds"] = rec["processing_seconds"]
            state["overall_stage_timing"] = {"preflight_seconds": preflight_seconds,
                                               "processing_seconds": state["run_elapsed_seconds"],
                                               "total_seconds": round(time.perf_counter()-overall_start, 6)}
            atomic_json(STATE, state)
    except Exception as e:
        state["status"] = "paused_error_resumable"
        state["last_error"] = f"{type(e).__name__}: {e}"
        state["run_elapsed_seconds"] = round(time.perf_counter()-start, 6)
        state["overall_stage_timing"] = {"preflight_seconds": preflight_seconds,
                                           "processing_seconds": state["run_elapsed_seconds"],
                                           "total_seconds": round(time.perf_counter()-overall_start, 6)}
        atomic_json(STATE, state)
        raise
    state["status"] = "complete"
    state["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    state["run_elapsed_seconds"] = round(time.perf_counter()-start, 6)
    state["overall_stage_timing"] = {"preflight_seconds": preflight_seconds,
                                       "processing_seconds": state["run_elapsed_seconds"],
                                       "total_seconds": round(time.perf_counter()-overall_start, 6)}
    state["changed_outputs"] = sum(r["status"] == "changed" for r in state["images"])
    state["retained_without_output_copy"] = sum(r["status"] == "retained_no_edit" for r in state["images"])
    atomic_json(STATE, state)
    print(json.dumps({k: state[k] for k in ("status", "candidate_count", "changed_outputs", "retained_without_output_copy", "run_elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    from common import image_worker
    from non_people_publication import operator_lock
    with operator_lock(), image_worker():
        main()
