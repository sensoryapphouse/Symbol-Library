#!/usr/bin/env python3
"""Low-load, ledger-backed cleanup runner for the explicitly reviewed people batch.

No image processing starts unless the protocol is enabled and all 48 source
decisions have been sealed. The script never scans Library and never writes to
source files. Outputs are lossless WebP only; unchanged inputs are copied byte
for byte. No Q80 variants are produced.
"""

# Set thread limits before importing Pillow, NumPy, SciPy, or the cleaner.
import os

for _name in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
PILOT_ROOT = HERE.parent
PROTOCOL_PATH = HERE / "protocol.json"
RUNNER_PATH = Path(__file__).resolve()


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha_bytes(data):
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
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with temp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    try:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def event(ledger, row, new_status, details=None):
    old = row["status"]
    allowed = load_json(PROTOCOL_PATH)["state_machine"]["allowed_transitions"]
    if new_status not in allowed.get(old, []):
        raise RuntimeError(f"disallowed ledger transition {row['id']}: {old} -> {new_status}")
    row["status"] = new_status
    row["updated_utc"] = utc_now()
    ledger["events"].append({
        "utc": row["updated_utc"],
        "id": row["id"],
        "from": old,
        "to": new_status,
        "details": details or {},
    })


def save_ledger(path, ledger):
    ledger["updated_utc"] = utc_now()
    atomic_json(path, ledger)


def protocol_and_paths():
    protocol = load_json(PROTOCOL_PATH)
    scope = protocol["scope"]
    return protocol, HERE / scope["inventory_file"], HERE / scope["source_decisions_file"], HERE / scope["ledger_file"], HERE / scope["output_directory"]


def normalize_dimensions(row):
    dimensions = row.get("dimensions", row.get("native_dimensions"))
    if not (isinstance(dimensions, list) and len(dimensions) == 2 and all(isinstance(v, int) and v > 0 for v in dimensions)):
        raise ValueError(f"{row.get('id')}: inventory needs integer native dimensions [width, height]")
    return dimensions


def load_inventory(inventory_path, protocol):
    inv = load_json(inventory_path)
    rows = inv.get("images") if isinstance(inv, dict) else None
    expected = protocol["scope"]["expected_images"]
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f"inventory must contain exactly {expected} allowlisted images")
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != expected or any(not isinstance(v, str) or not v for v in ids):
        raise ValueError("inventory IDs must be unique non-empty strings")
    counts = {s: 0 for s in protocol["scope"]["expected_style_ids"]}
    for row in rows:
        sid = row.get("style_id")
        if sid not in counts:
            raise ValueError(f"{row.get('id')}: style_id outside frozen scope: {sid}")
        counts[sid] += 1
        if not row.get("source") or not row.get("source_sha256"):
            raise ValueError(f"{row.get('id')}: inventory needs source path and SHA256")
        normalize_dimensions(row)
    if any(n != protocol["scope"]["images_per_style"] for n in counts.values()):
        raise ValueError(f"expected {protocol['scope']['images_per_style']} images per style; got {counts}")
    return inv, rows


def cmd_init(_args):
    protocol, inventory_path, _decisions, ledger_path, output_root = protocol_and_paths()
    if not inventory_path.is_file():
        raise FileNotFoundError(f"frozen allowlist is not available: {inventory_path}")
    if ledger_path.exists():
        raise FileExistsError(f"ledger already exists; refusing to overwrite: {ledger_path}")
    inv, rows = load_inventory(inventory_path, protocol)
    inventory_sha = sha_file(inventory_path)
    if protocol.get("inventory_sha256") and protocol["inventory_sha256"] != inventory_sha:
        raise ValueError("inventory hash differs from the protocol-pinned inventory")
    runner_sha = sha_file(RUNNER_PATH)
    if protocol.get("runner_sha256") and protocol["runner_sha256"] != runner_sha:
        raise ValueError("runner hash differs from the protocol-pinned runner")
    output_root.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    ledger = {
        "protocol_version": protocol["protocol_version"],
        "rule_version": protocol["rule_version"],
        "batch_id": protocol["batch_id"],
        "created_utc": now,
        "updated_utc": now,
        "inventory_path": str(inventory_path),
        "inventory_sha256": inventory_sha,
        "protocol_sha256": sha_file(PROTOCOL_PATH),
        "runner_sha256": runner_sha,
        "cleaner_sha256": protocol["engine"]["sha256"],
        "status": "source_review_pending",
        "images": [],
        "events": [],
    }
    for src in rows:
        source = Path(src["source"]).expanduser().resolve(strict=True)
        actual_sha = sha_file(source)
        if actual_sha != src["source_sha256"]:
            raise ValueError(f"{src['id']}: inventory source hash mismatch")
        ledger["images"].append({
            "id": src["id"],
            "style_id": src["style_id"],
            "style": src.get("style"),
            "concept": src.get("concept"),
            "source_path": str(source),
            "source_sha256": actual_sha,
            "dimensions": normalize_dimensions(src),
            "status": "pending_source_review",
            "decision": None,
            "outputs": {},
            "review": None,
            "updated_utc": now,
        })
    ledger["events"].append({"utc": now, "id": None, "from": None, "to": "source_review_pending", "details": {"images": len(rows), "inventory_sha256": inventory_sha}})
    save_ledger(ledger_path, ledger)
    print(f"Initialized {len(rows)} rows; no image processing performed.")


def import_image_stack(protocol):
    cleaner_path = (HERE / protocol["engine"]["module"]).resolve()
    actual = sha_file(cleaner_path)
    if protocol["engine"].get("must_match_before_run") and actual != protocol["engine"]["sha256"]:
        raise RuntimeError(f"cleaner hash mismatch: expected {protocol['engine']['sha256']}, found {actual}")
    sys.path.insert(0, str(cleaner_path.parent))
    # Delayed third-party imports: thread env limits were set at module load.
    import numpy as np
    from PIL import Image
    from cleaner import cleanup
    return np, Image, cleanup, actual


def source_rgba(np, Image, source_path):
    with Image.open(source_path) as im:
        native = im.size
        rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    return rgba, [native[0], native[1]]


def atomic_save_image(Image, image, path, **options):
    path = Path(path)
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    image.save(temp, **options)
    with temp.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(temp, path)


def write_result_folder(np, Image, row, decision, processed, masks, details, cleaner_sha, out_dir):
    source_path = Path(row["source_path"])
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists():
        raise FileExistsError(f"output already exists; refusing overwrite: {out_dir}")
    stage = Path(tempfile.mkdtemp(prefix=f".{row['id']}.stage-", dir=out_dir.parent))
    try:
        unchanged = details["changed_pixels"] == 0
        image_path = stage / "after.webp"
        if unchanged:
            if source_path.suffix.lower() != ".webp":
                raise ValueError(f"{row['id']}: byte-copy no-op requires a WebP source")
            shutil.copyfile(source_path, image_path)
            encoding = "source-byte-copy"
        else:
            img = Image.fromarray(processed, "RGBA")
            atomic_save_image(Image, img, image_path, format="WEBP", lossless=True, method=6, exact=True)
            encoding = "lossless-webp"
        decoded, dims = source_rgba(np, Image, image_path)
        if dims != row["dimensions"] or decoded.shape != processed.shape or not np.array_equal(decoded, processed):
            raise AssertionError(f"{row['id']}: output decode is not exact native RGBA")
        source, source_dims = source_rgba(np, Image, source_path)
        if source_dims != row["dimensions"]:
            raise AssertionError(f"{row['id']}: source dimensions differ from inventory")
        if np.any(processed[:, :, 3] > source[:, :, 3]):
            raise AssertionError(f"{row['id']}: output alpha increased")
        if not np.array_equal(source[~masks["allowed"]], processed[~masks["allowed"]]):
            raise AssertionError(f"{row['id']}: pixels changed outside allowed regions")
        if not np.array_equal(source[masks["protected"]], processed[masks["protected"]]):
            raise AssertionError(f"{row['id']}: protected pixels changed")
        if unchanged and not np.array_equal(source, processed):
            raise AssertionError(f"{row['id']}: no-op result differs from source")
        mask_hashes = {}
        for name, mask in masks.items():
            mask_path = stage / f"{name}_mask.png"
            mask_img = Image.fromarray((mask.astype(np.uint8) * 255), "L")
            atomic_save_image(Image, mask_img, mask_path, format="PNG", optimize=False)
            mask_hashes[mask_path.name] = sha_file(mask_path)
        result = {
            "id": row["id"],
            "style_id": row["style_id"],
            "source_path": str(source_path),
            "source_sha256": row["source_sha256"],
            "decision_sha256": row["decision_sha256"],
            "cleaner_sha256": cleaner_sha,
            "dimensions": row["dimensions"],
            "decision": decision,
            "cleanup": details,
            "changed_pixels": details["changed_pixels"],
            "output_file": image_path.name,
            "output_encoding": encoding,
            "output_sha256": sha_file(image_path),
            "output_bytes": image_path.stat().st_size,
            "decoded_rgba_sha256": sha_bytes(decoded.tobytes()),
            "mask_sha256": mask_hashes,
            "unchanged_identity_proof": bool(unchanged and sha_file(source_path) == row["source_sha256"] and sha_file(image_path) == row["source_sha256"] and np.array_equal(source, decoded)),
            "q80_outputs_created": False,
        }
        atomic_json(stage / "result.json", result)
        os.replace(stage, out_dir)
        return result
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _ledger_lookup(ledger):
    return {r["id"]: r for r in ledger["images"]}


def cmd_run(_args):
    protocol, inventory_path, decisions_path, ledger_path, output_root = protocol_and_paths()
    if not protocol.get("execution_enabled"):
        raise RuntimeError("execution is disabled in protocol.json; wait for root review/publication")
    current_runner_sha = sha_file(RUNNER_PATH)
    pins = (protocol.get("runner_sha256"), protocol.get("inventory_sha256"), protocol.get("source_proposals_sha256"), protocol.get("source_decisions_sha256"), protocol.get("reference_check_sha256"))
    if not all(pins):
        raise RuntimeError("protocol must pin runner, inventory, all source decisions, and reference check before execution")
    if current_runner_sha != protocol["runner_sha256"]:
        raise RuntimeError("runner hash differs from the protocol pin")
    if not inventory_path.is_file() or not decisions_path.is_file() or not ledger_path.is_file():
        raise FileNotFoundError("inventory, source decisions, and initialized ledger must all exist before run")
    inv, inventory_rows = load_inventory(inventory_path, protocol)
    inv_sha = sha_file(inventory_path)
    if protocol["inventory_sha256"] != inv_sha:
        raise ValueError("inventory no longer matches protocol-pinned SHA256")
    decision_blob = load_json(decisions_path)
    decision_rows = decision_blob.get("images") if isinstance(decision_blob, dict) else None
    if not isinstance(decision_rows, list) or len(decision_rows) != protocol["scope"]["expected_images"]:
        raise ValueError("source decision file must contain one reviewed decision for all 48 images")
    decisions = {d.get("id"): d for d in decision_rows}
    if len(decisions) != len(decision_rows) or set(decisions) != {r["id"] for r in inventory_rows}:
        raise ValueError("source decision IDs must exactly match the frozen inventory")
    decisions_sha = sha_file(decisions_path)
    if protocol["source_decisions_sha256"] != decisions_sha:
        raise ValueError("source decisions differ from the protocol-pinned SHA256")
    proposal_path = HERE / protocol["source_proposals"]["file"]
    if not proposal_path.is_file():
        raise FileNotFoundError(f"required low-cost source proposal record is missing: {proposal_path}")
    proposal_blob = load_json(proposal_path)
    proposal_rows = proposal_blob.get("images") if isinstance(proposal_blob, dict) else None
    if not isinstance(proposal_rows, list) or len(proposal_rows) != protocol["scope"]["expected_images"]:
        raise ValueError("proposal file must contain exactly one proposal for each of the 48 inventory rows")
    proposals = {p.get("id"): p for p in proposal_rows}
    if len(proposals) != len(proposal_rows) or set(proposals) != {r["id"] for r in inventory_rows}:
        raise ValueError("proposal IDs must exactly match the frozen inventory")
    for source_row in inventory_rows:
        proposal = proposals[source_row["id"]]
        if proposal.get("source_sha256") != source_row["source_sha256"]:
            raise ValueError(f"{source_row['id']}: proposal does not bind the frozen source hash")
        model = str(proposal.get("model", proposal.get("model_family", ""))).lower()
        if "luna" not in model or not proposal.get("proposal"):
            raise ValueError(f"{source_row['id']}: proposal must record a non-empty Luna suggestion")
    proposals_sha = sha_file(proposal_path)
    if protocol["source_proposals_sha256"] != proposals_sha:
        raise ValueError("Luna proposal file differs from protocol-pinned SHA256")
    reference_spec = protocol["reference_check"]
    reference_path = HERE / reference_spec["file"]
    if not reference_path.is_file():
        raise FileNotFoundError(f"required original-pose reference check is missing: {reference_path}")
    reference = load_json(reference_path)
    reference_sha = sha_file(reference_path)
    if protocol["reference_check_sha256"] != reference_sha:
        raise ValueError("reference check hash differs from protocol-pinned SHA256")
    if reference.get("status") != "reviewed" or not reference.get("reviewer"):
        raise ValueError("reference check must be completed and name its reviewer")
    pairs = reference.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < reference_spec["minimum_pairs"]:
        raise ValueError(f"reference check needs at least {reference_spec['minimum_pairs']} reviewed pairs")
    inventory_by_id = {r["id"]: r for r in inventory_rows}
    concepts = {str(r.get("normalized_concept", r.get("concept", ""))).strip().lower() for r in inventory_rows}
    covered_concepts = set()
    for pair in pairs:
        left_id, right_id = pair.get("target_id"), pair.get("peer_id")
        if left_id not in inventory_by_id or right_id not in inventory_by_id or left_id == right_id:
            raise ValueError("reference pair IDs must be distinct members of the frozen inventory")
        left, right = inventory_by_id[left_id], inventory_by_id[right_id]
        concept = str(left.get("normalized_concept", left.get("concept", ""))).strip().lower()
        peer_concept = str(right.get("normalized_concept", right.get("concept", ""))).strip().lower()
        if not concept or concept != peer_concept or left["style_id"] == right["style_id"]:
            raise ValueError(f"reference pair {left_id}/{right_id} must be same-concept, cross-style")
        if pair.get("target_sha256") != left["source_sha256"] or pair.get("peer_sha256") != right["source_sha256"]:
            raise ValueError(f"reference pair {left_id}/{right_id} source hash mismatch")
        if pair.get("originals_visually_compared") is not True:
            raise ValueError(f"reference pair {left_id}/{right_id} has no original-image review")
        if pair.get("finding") not in reference_spec["allowed_findings"]:
            raise ValueError(f"reference pair {left_id}/{right_id} is uncertain or unsupported")
        covered_concepts.add(concept)
    if reference_spec.get("must_cover_every_concept_family_in_allowlist") and covered_concepts != concepts:
        raise ValueError(f"reference check concept coverage mismatch: covered={sorted(covered_concepts)} expected={sorted(concepts)}")
    # Preflight all 48 sources and review records before the first output is
    # written. This checks only file identity, dimensions, ROI bounds and seeds.
    from PIL import Image
    regression_map = {item["id"]: item["coordinates"] for item in protocol["known_regressions"]}
    preflight_ledger = load_json(ledger_path)
    preflight_states = _ledger_lookup(preflight_ledger)
    for source_row in inventory_rows:
        ident = source_row["id"]
        src_path = Path(source_row["source"]).expanduser().resolve(strict=True)
        source_sha = sha_file(src_path)
        if source_sha != source_row["source_sha256"]:
            raise ValueError(f"{ident}: source hash changed since inventory freeze")
        decision = decisions[ident]
        if decision.get("source_reviewed") is not True or not decision.get("reviewer"):
            raise ValueError(f"{ident}: all source review rows must be complete and attributed")
        if decision.get("source_sha256") != source_sha or decision.get("dimensions") != normalize_dimensions(source_row):
            raise ValueError(f"{ident}: source review hash/dimensions do not match the frozen source")
        if decision.get("decision") not in protocol["source_review"]["decision_values"]:
            raise ValueError(f"{ident}: invalid source decision")
        with Image.open(src_path) as check_image:
            if list(check_image.size) != normalize_dimensions(source_row):
                raise ValueError(f"{ident}: decoded native dimensions changed")
            width, height = check_image.size
            if ident in regression_map:
                for x, y in regression_map[ident]:
                    if not (0 <= x < width and 0 <= y < height):
                        raise ValueError(f"{ident}: regression guard coordinate is outside native bounds")
            if decision["decision"] == "cleanup":
                rgba_check = check_image.convert("RGBA")
                if decision.get("legacy_stage_a") is not None or not decision.get("regions"):
                    raise ValueError(f"{ident}: production cleanup needs explicit new-format ROIs only")
                for region in decision["regions"]:
                    roi = region.get("roi")
                    if not isinstance(roi, list) or len(roi) != 4:
                        raise ValueError(f"{ident}: ROI must be [x0,y0,x1,y1]")
                    x0, y0, x1, y1 = roi
                    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                        raise ValueError(f"{ident}: reviewed ROI is outside native bounds")
                    if region.get("transparent_seed") is not None:
                        raise ValueError(f"{ident}: transparent-gap seeds are excluded from this production mode")
                    if region.get("core_labels"):
                        raise ValueError(f"{ident}: source component labels are not accepted; use source-reviewed core seeds")
                    seeds = region.get("core_seeds", [])
                    if not seeds:
                        raise ValueError(f"{ident}: each cleanup ROI needs at least one reviewed white-core seed")
                    for seed in seeds:
                        sx, sy = seed
                        if not (x0 <= sx < x1 and y0 <= sy < y1):
                            raise ValueError(f"{ident}: white-core seed falls outside its reviewed ROI")
                        r, g, b, a = rgba_check.getpixel((sx, sy))
                        if min(r, g, b) < 240 or max(r, g, b) - min(r, g, b) > 20 or a < 128:
                            raise ValueError(f"{ident}: core seed at {(sx, sy)} fails the frozen source white threshold")
                    for box in list(decision.get("protected_boxes", [])) + list(region.get("protected_boxes", [])):
                        bx0, by0, bx1, by1 = box
                        if not (0 <= bx0 < bx1 <= width and 0 <= by0 < by1 <= height):
                            raise ValueError(f"{ident}: protection box is outside native bounds")
                    for polygon in list(decision.get("protected_polygons", [])) + list(region.get("protected_polygons", [])):
                        if len(polygon) < 3 or any(not (0 <= x < width and 0 <= y < height) for x, y in polygon):
                            raise ValueError(f"{ident}: protection polygon is outside native bounds")
        existing_output = HERE / protocol["scope"]["output_directory"] / ident
        state_status = preflight_states.get(ident, {}).get("status")
        if existing_output.exists() and state_status not in ("selected", "edited", "output_reviewed", "accepted"):
            raise FileExistsError(f"{ident}: output path exists for a non-resumable ledger row")
    ledger = preflight_ledger
    if ledger.get("rule_version") != protocol["rule_version"]:
        raise ValueError("ledger rule version mismatch")
    if ledger.get("protocol_sha256") != sha_file(PROTOCOL_PATH):
        raise ValueError("protocol changed after ledger initialization")
    if ledger.get("runner_sha256") != current_runner_sha:
        raise ValueError("runner changed after ledger initialization")
    if ledger["inventory_sha256"] != inv_sha:
        raise ValueError("ledger inventory hash mismatch; never resume against changed inventory")
    old_reference_sha = ledger.get("reference_check_sha256")
    if old_reference_sha and old_reference_sha != reference_sha:
        raise ValueError("reference check changed after ledger binding; do not resume")
    ledger["reference_check_sha256"] = reference_sha
    ledger["reference_check_reviewer"] = reference["reviewer"]
    old_proposals_sha = ledger.get("source_proposals_sha256")
    if old_proposals_sha and old_proposals_sha != proposals_sha:
        raise ValueError("source proposals changed after ledger binding; do not resume")
    ledger["source_proposals_sha256"] = proposals_sha
    old_decisions_sha = ledger.get("source_decisions_sha256")
    if old_decisions_sha and old_decisions_sha != decisions_sha:
        raise ValueError("source decisions changed after ledger binding; do not resume")
    ledger["source_decisions_sha256"] = decisions_sha
    save_ledger(ledger_path, ledger)
    rows = _ledger_lookup(ledger)
    np, Image, cleanup, cleaner_sha = import_image_stack(protocol)
    if len(inventory_rows) != 48:
        raise AssertionError("batch stop rule: process exactly 48 allowlisted rows")
    for source_row in inventory_rows:
        ident = source_row["id"]
        state = rows[ident]
        if state["status"] not in ("pending_source_review", "selected"):
            continue
        if state.get("decision_sha256") and state["decision_sha256"] != decisions_sha:
            raise ValueError(f"{ident}: decision hash changed after source review was ledgered")
        source_path = Path(state["source_path"])
        current_sha = sha_file(source_path)
        if current_sha != state["source_sha256"] or current_sha != source_row["source_sha256"]:
            raise ValueError(f"{ident}: source changed after inventory freeze")
        decision = decisions[ident]
        if decision.get("source_reviewed") is not True:
            raise ValueError(f"{ident}: source review is not complete")
        if not decision.get("reviewer"):
            raise ValueError(f"{ident}: source review must name its reviewer")
        if decision.get("source_sha256") != current_sha:
            raise ValueError(f"{ident}: source review does not bind the current source hash")
        if decision.get("dimensions") != state["dimensions"]:
            raise ValueError(f"{ident}: source review dimensions mismatch")
        choice = decision.get("decision")
        if choice not in protocol["source_review"]["decision_values"]:
            raise ValueError(f"{ident}: invalid source decision {choice!r}")
        state["decision"] = decision
        state["decision_sha256"] = decisions_sha
        if state["status"] == "pending_source_review":
            if choice == "uncertain":
                event(ledger, state, "held", {"stage": "source_review", "reason": decision.get("uncertainty_notes", [])})
                save_ledger(ledger_path, ledger)
                continue
            if choice == "unchanged":
                event(ledger, state, "unchanged", {"stage": "source_review", "reason": decision.get("retain_notes", [])})
            else:
                if not decision.get("regions"):
                    raise ValueError(f"{ident}: cleanup decision must include at least one bounded reviewed ROI")
                event(ledger, state, "selected", {"stage": "source_review", "regions": len(decision["regions"])})
            save_ledger(ledger_path, ledger)
        if state["status"] == "unchanged":
            # No duplicate visual damage review is needed when the exact source is kept.
            proof_path = Path(state["source_path"])
            rgba, dims = source_rgba(np, Image, proof_path)
            if dims != state["dimensions"] or sha_file(proof_path) != state["source_sha256"]:
                raise AssertionError(f"{ident}: exact unchanged source proof failed")
            state["outputs"] = {
                "output_file": str(proof_path),
                "output_sha256": state["source_sha256"],
                "output_bytes": proof_path.stat().st_size,
                "decoded_rgba_sha256": sha_bytes(rgba.tobytes()),
                "encoding": "source-byte-identity",
                "unchanged_identity_proof": True,
                "q80_outputs_created": False,
            }
            event(ledger, state, "output_reviewed", {"review_method": "unchanged_identity_proof"})
            save_ledger(ledger_path, ledger)
            continue
        if state["status"] != "selected":
            continue
        dest = output_root / ident
        if dest.exists():
            result_path = dest / "result.json"
            if not result_path.is_file():
                raise FileExistsError(f"{ident}: untracked output exists; refusing overwrite/re-run")
            result = load_json(result_path)
            if result.get("source_sha256") != current_sha or result.get("cleaner_sha256") != cleaner_sha or result.get("decision_sha256") != decisions_sha:
                raise ValueError(f"{ident}: existing output does not match this frozen run")
        else:
            source, dims = source_rgba(np, Image, source_path)
            if dims != state["dimensions"]:
                raise ValueError(f"{ident}: native source dimensions differ from inventory")
            candidate_output, candidate_masks, _engine_details = cleanup(source, decision)
            # Production uses only the reviewed, source-valid opaque white core.
            # Discard all cleaner matting output: no fringe/gap/post-matting edits.
            rgb = source[:, :, :3]
            white_core = (rgb.min(axis=2) >= 240) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= 20) & (source[:, :, 3] >= 128)
            roi_mask = np.zeros(source.shape[:2], dtype=bool)
            for region in decision["regions"]:
                x0, y0, x1, y1 = region["roi"]
                if not (0 <= x0 < x1 <= source.shape[1] and 0 <= y0 < y1 <= source.shape[0]):
                    raise ValueError(f"{ident}: reviewed ROI is out of native bounds")
                roi_mask[y0:y1, x0:x1] = True
            removed_core = candidate_masks["core"] & white_core & roi_mask & ~candidate_masks["protected"]
            processed = source.copy()
            processed[:, :, 3][removed_core] = 0
            masks = {
                "allowed": roi_mask,
                "edge": np.zeros(source.shape[:2], dtype=bool),
                "core": removed_core,
                "protected": candidate_masks["protected"],
                "changed": removed_core.copy(),
            }
            if not np.array_equal(source[:, :, :3], processed[:, :, :3]):
                raise AssertionError(f"{ident}: blob-only mode must preserve RGB exactly")
            if not np.array_equal(np.any(source != processed, axis=2), removed_core):
                raise AssertionError(f"{ident}: changes must equal selected white-core pixels only")
            for x, y in regression_map.get(ident, []):
                if removed_core[y, x] or not np.array_equal(source[y, x], processed[y, x]):
                    raise AssertionError(f"{ident}: known foreground regression guard changed at {(x, y)}")
            details = {
                "operation": "reviewed_white_core_only",
                "regions": [
                    {"name": region["name"], "roi": region["roi"], "removed_core_pixels": int((removed_core[region["roi"][1]:region["roi"][3], region["roi"][0]:region["roi"][2]]).sum())}
                    for region in decision["regions"]
                ],
                "removed_core_pixels": int(removed_core.sum()),
                "edge_band_pixels_removed": 0,
                "transparent_gap_pixels_removed": 0,
                "fringe_or_border_pixels_removed": 0,
                "changed_pixels": int(removed_core.sum()),
            }
            row_for_result = dict(source_row)
            row_for_result.update(source_path=str(source_path), source_sha256=current_sha, decision_sha256=decisions_sha)
            result = write_result_folder(np, Image, row_for_result, decision, processed, masks, details, cleaner_sha, dest)
        changed = result["changed_pixels"] > 0
        state["outputs"] = {
            "output_file": str(dest / result["output_file"]),
            "output_sha256": result["output_sha256"],
            "output_bytes": result["output_bytes"],
            "decoded_rgba_sha256": result["decoded_rgba_sha256"],
            "mask_sha256": result["mask_sha256"],
            "changed_pixels": result["changed_pixels"],
            "unchanged_identity_proof": result["unchanged_identity_proof"],
            "q80_outputs_created": False,
        }
        event(ledger, state, "edited" if changed else "unchanged", {"output_sha256": result["output_sha256"], "changed_pixels": result["changed_pixels"], "output_encoding": result["output_encoding"]})
        save_ledger(ledger_path, ledger)
        if not changed:
            event(ledger, state, "output_reviewed", {"review_method": "unchanged_identity_proof"})
            save_ledger(ledger_path, ledger)
    remaining = [r for r in ledger["images"] if r["status"] in ("pending_source_review", "selected", "edited")]
    held_count = sum(r["status"] == "held" for r in ledger["images"])
    if remaining:
        ledger["status"] = "processing_incomplete"
    elif held_count:
        ledger["status"] = "batch_processed_with_holds"
    else:
        ledger["status"] = "outputs_ready_for_review"
    save_ledger(ledger_path, ledger)
    print("Run complete; changed outputs require independent visual review. No Q80 files created.")


def cmd_review(args):
    protocol, _inventory, _decisions, ledger_path, _outputs = protocol_and_paths()
    ledger = load_json(ledger_path)
    review_blob = load_json(args.review_file)
    review_rows = review_blob.get("images") if isinstance(review_blob, dict) else None
    if not isinstance(review_rows, list):
        raise ValueError("review file must contain an images list")
    rows = _ledger_lookup(ledger)
    for review in review_rows:
        ident = review.get("id")
        if ident not in rows:
            raise ValueError(f"unknown reviewed ID: {ident}")
        state = rows[ident]
        if state["status"] != "edited":
            raise ValueError(f"{ident}: visual review applies only to changed edited outputs")
        if not review.get("reviewer") or review.get("reviewer") == state["decision"].get("reviewer"):
            raise ValueError(f"{ident}: reviewer must be named and independent of source decision author")
        if review.get("reviewer_mode") != protocol["changed_output_review"]["reviewer_mode_required"]:
            raise ValueError(f"{ident}: output reviewer must use independent_strong_review mode")
        output_sha = state.get("outputs", {}).get("output_sha256")
        if review.get("reviewed_output_sha256") != output_sha:
            raise ValueError(f"{ident}: visual review is not bound to the current exact output hash")
        verdict = review.get("verdict")
        if verdict not in ("pass", "hold"):
            raise ValueError(f"{ident}: verdict must be pass or hold")
        known_regressions = {item["id"] for item in protocol["known_regressions"]}
        if ident in known_regressions and verdict == "pass" and review.get("regression_retested") is not True:
            raise ValueError(f"{ident} needs an explicit fresh regression comparison before pass")
        state["review"] = review
        if verdict == "pass":
            event(ledger, state, "output_reviewed", {"reviewer": review["reviewer"], "reviewed_output_sha256": output_sha, "findings": review.get("findings", [])})
        else:
            event(ledger, state, "held", {"stage": "output_review", "reviewer": review["reviewer"], "findings": review.get("findings", [])})
        save_ledger(ledger_path, ledger)
    print(f"Recorded {len(review_rows)} independent visual review(s).")


def cmd_accept(args):
    protocol, _inventory, _decisions, ledger_path, _outputs = protocol_and_paths()
    ledger = load_json(ledger_path)
    accept_blob = load_json(args.acceptance_file)
    accept_rows = accept_blob.get("images") if isinstance(accept_blob, dict) else None
    if not isinstance(accept_rows, list):
        raise ValueError("acceptance file must contain an images list")
    rows = _ledger_lookup(ledger)
    for record in accept_rows:
        ident = record.get("id")
        if ident not in rows:
            raise ValueError(f"unknown accepted ID: {ident}")
        state = rows[ident]
        if state["status"] != "output_reviewed":
            raise ValueError(f"{ident}: can accept only after output_reviewed")
        if not record.get("accepted_by"):
            raise ValueError(f"{ident}: acceptance needs accepted_by")
        if record.get("acceptance_role") not in ("root_agent", "designated_reviewer"):
            raise ValueError(f"{ident}: acceptance needs root_agent or designated_reviewer authority")
        output_reviewer = (state.get("review") or {}).get("reviewer")
        if output_reviewer and output_reviewer == record["accepted_by"]:
            raise ValueError(f"{ident}: acceptance must be recorded by an agent other than the output reviewer")
        if record.get("reviewed_output_sha256") != state.get("outputs", {}).get("output_sha256"):
            raise ValueError(f"{ident}: acceptance is not bound to current output SHA256")
        known_regressions = {item["id"] for item in protocol["known_regressions"]}
        if ident in known_regressions and state.get("outputs", {}).get("changed_pixels", 0) and record.get("regression_retested") is not True:
            raise ValueError(f"{ident} changed output requires an explicit fresh regression comparison")
        event(ledger, state, "accepted", {"accepted_by": record["accepted_by"], "reviewed_output_sha256": record["reviewed_output_sha256"]})
        save_ledger(ledger_path, ledger)
    print(f"Accepted {len(accept_rows)} reviewed output(s).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create the 48-row durable ledger; does not process images")
    sub.add_parser("run", help="process only source-reviewed rows after the protocol is enabled")
    review = sub.add_parser("review", help="record exact-hash-bound independent visual reviews")
    review.add_argument("review_file")
    accept = sub.add_parser("accept", help="record explicit acceptance after output review")
    accept.add_argument("acceptance_file")
    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "accept":
        cmd_accept(args)


if __name__ == "__main__":
    main()
