#!/usr/bin/env python3
"""Read-only screen of the exact registered current repaired source versions."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
import datetime
import fcntl
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = Path(__file__).resolve().parent
REGISTRY = BASE / 'source_revisions_20261105/registry.json'
OUT = BASE / 'source_revisions_20261105_current_measurements.json'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if OUT.exists():
        raise RuntimeError('Immutable measurement already exists; create an explicit new version.')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    registry_sha = digest(REGISTRY)
    registry = json.loads(REGISTRY.read_text())
    entries = []
    def sig(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    with (BASE / 'production/image_worker.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for record in registry['entries']:
            path = Path(record['path'])
            before = sig(path.stat())
            with path.open('rb') as stream:
                opened = sig(os.fstat(stream.fileno()))
                raw = stream.read()
                closed = sig(os.fstat(stream.fileno()))
            after = sig(path.stat())
            actual_sha = hashlib.sha256(raw).hexdigest()
            if not (before == opened == closed == after and actual_sha == record['new_sha256']):
                raise RuntimeError('Current source changed during read: ' + str(path))
            with Image.open(io.BytesIO(raw)) as image:
                rgba = np.asarray(image.convert('RGBA'))
                dimensions = list(image.size)
            if dimensions != record['new_dimensions'] or len(raw) != record['new_bytes']:
                raise RuntimeError('Registry dimensions/bytes mismatch: ' + str(path))
            rgb, alpha = rgba[:,:,:3], rgba[:,:,3]
            strict = (rgb.min(axis=2) >= 240) & ((rgb.max(axis=2)-rgb.min(axis=2)) <= 20) & (alpha >= 128)
            labels, count = ndimage.label(strict, structure=np.ones((3,3), dtype=np.uint8))
            sizes = np.bincount(labels.ravel())[1:]
            pixels = int(strict.sum()); scale = max(dimensions) / 512
            normalized = pixels / (scale * scale)
            entries.append({'path':str(path),'source_sha256':actual_sha,'dimensions':dimensions,
                'source_bytes':len(raw),'strict_white_core_pixel_count_native':pixels,
                'strict_white_core_pixel_count_at_512':normalized,'simple_eligible':normalized>=256,
                'strict_components':int(count),'largest_strict_component_at_512':float(sizes.max()/(scale*scale)) if len(sizes) else 0,
                'alpha_min':int(alpha.min()),'alpha_max':int(alpha.max()),'transparent_pixels':int((alpha==0).sum()),
                'stable_byte_receipt':{'stat_before':before,'fstat_opened':opened,'fstat_closed':closed,'stat_after':after,'sha256':actual_sha}})
        fcntl.flock(lock, fcntl.LOCK_UN)
    if len(entries)!=52 or len({e['path'] for e in entries})!=52 or digest(REGISTRY)!=registry_sha:
        raise RuntimeError('Exact registered source population changed')
    doc={'schema':'current-repaired-source-measurements-v1','status':'measured_current_versions_parent_approval_pending',
         'started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'registry_sha256':registry_sha,'entries':entries,
         'metadata_sha256':{str(Path(__file__).resolve()):digest(__file__),str(REGISTRY):registry_sha},
         'rule':{'strict_white_rgb_min':240,'max_channel_range':20,'min_alpha':128,'normalized_total_minimum_at_512':256,'connectivity':8},
         'shared_worker_lock':str(BASE/'production/image_worker.lock'),'numeric_threads':1,
         'images_edited':False,'visual_reviews_performed':False,
         'eligible_count':sum(e['simple_eligible'] for e in entries)}
    with OUT.open('x') as stream:
        json.dump(doc,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'path':str(OUT),'total':len(entries),'eligible':doc['eligible_count'],
        'eligible_paths':[{'path':e['path'],'white_pixels':e['strict_white_core_pixel_count_at_512']} for e in entries if e['simple_eligible']]}))

if __name__ == '__main__':
    main()
