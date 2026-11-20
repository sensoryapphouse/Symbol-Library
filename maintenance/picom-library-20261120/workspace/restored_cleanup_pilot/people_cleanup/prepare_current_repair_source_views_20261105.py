#!/usr/bin/env python3
"""Read-only evidence for nine current repaired People sources; no cleanup."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
if sys.flags.optimize:
    raise RuntimeError('Optimized Python is forbidden')
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
RENDERER = BASE / 'production_remaining_people/prepare_source_previews.py'
REGISTRY = BASE / 'source_revisions_20261105/registry.json'
MEASUREMENTS = BASE / 'source_revisions_20261105_current_measurements_approved.json'
PROPOSAL = BASE / 'source_revisions_20261105_phase3/supplemental_source_queue_proposal.json'
DEST = BASE / 'current_repaired_people_source_review_20261105'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if DEST.exists():
        raise RuntimeError('Evidence directory already exists; no silent overwrite/resume')
    if sha(RENDERER) != 'c8b23850ec66728e0778414e8ea5915aa65e451cb5c8cee05b3f03b2081ac37e':
        raise RuntimeError('Frozen rendering/component functions changed')
    proposal = json.loads(PROPOSAL.read_text())
    measurements = json.loads(MEASUREMENTS.read_text())
    registry = json.loads(REGISTRY.read_text())
    if proposal['registry_sha256'] != sha(REGISTRY) or proposal['measurements_sha256'] != sha(MEASUREMENTS):
        raise RuntimeError('Current repair input pins differ')
    rows = proposal['entries']
    by_path = {r['path']:r for r in registry['entries']}
    measured = {r['path']:r for r in measurements['entries']}
    if len(rows) != 9 or len({r['path'] for r in rows}) != 9:
        raise RuntimeError('Expected exact nine current source checks')
    sys.path.insert(0, str(RENDERER.parent))
    spec = importlib.util.spec_from_file_location('frozen_current_repair_source_renderer', RENDERER)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    pins = {str(p):sha(p) for p in (Path(__file__).resolve(),RENDERER,REGISTRY,MEASUREMENTS,PROPOSAL)}
    entries = []
    with engine.image_worker():
        DEST.mkdir()
        for index,row in enumerate(rows,1):
            path = Path(row['path']); raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != row['source_sha256'] or digest != by_path[str(path)]['new_sha256']:
                raise RuntimeError('Current source bytes differ: ' + str(path))
            with Image.open(io.BytesIO(raw)) as im:
                rgba = np.asarray(im.convert('RGBA')); dimensions = list(im.size)
            if dimensions != row['dimensions'] or dimensions != [512,512]:
                raise RuntimeError('Current dimensions differ')
            strict,labels,components,scale = engine.component_inventory(np,ndimage,rgba,dimensions)
            if int(strict.sum()) != measured[str(path)]['strict_white_core_pixel_count_native']:
                raise RuntimeError('Current white measurement differs from approved current source screen')
            source = engine.render_source(Image,rgba)
            overlay = engine.make_overlay(np,ndimage,Image,ImageDraw,ImageFont,source,labels,components,scale)
            whole_path = DEST / f'current_{index:02d}_source.png'
            overlay_path = DEST / f'current_{index:02d}_overlay.png'
            engine.atomic_png(Image,source,whole_path);engine.atomic_png(Image,overlay,overlay_path)
            entries.append({'id':f'current_{index:02d}','path':str(path),'source_sha256':digest,
                'dimensions':dimensions,'source_bytes':len(raw),'decoded_source_image':True,
                'components_ge64_at_512':components,'strict_white_pixels_native':int(strict.sum()),
                'source_png':str(whole_path),'source_png_sha256':sha(whole_path),
                'strict_cc_overlay':str(overlay_path),'overlay_png_sha256':sha(overlay_path)})
        for filename,digest in pins.items():
            if sha(filename) != digest:
                raise RuntimeError('Source evidence metadata changed during preparation')
        doc={'schema':'current-revision-source-only-previews-v1','not_a_baseline_cohort':True,
             'registry_sha256':sha(REGISTRY),'metadata_sha256':pins,'entries':entries,
             'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'shared_worker_lock':str(BASE/'production/image_worker.lock'),'numeric_threads':1,
             'originals_changed':False,'cleanup_performed':False,'visual_review_performed':False}
        engine.atomic_json(DEST/'preview_manifest.json',doc)
    print(json.dumps({'status':'ready_for_actual_current_source_review','sources':len(entries),
                      'preview_manifest':str(DEST/'preview_manifest.json'),'originals_changed':False}))

if __name__ == '__main__':
    main()
