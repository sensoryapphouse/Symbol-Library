#!/usr/bin/env python3
"""Exact R127 scope adapter; uses the unchanged read-only ROI measurement engine."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
if sys.flags.optimize:
    raise RuntimeError('Optimized Python is forbidden')

BASE = Path(__file__).resolve().parent
CONTROL = BASE / 'source_revisions_20261105_phase2'
BATCH = BASE / 'production_source_revisions_20261105_phase2/batches/batchR127'
APPROVAL = BASE / 'source_revision_roi_adapter_approval_20261105.json'
HELPER = BASE / 'measure_roi_regions.py'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_scope(path):
    resolved = Path(path).resolve(strict=True)
    if resolved != BATCH.resolve(strict=True) or not resolved.is_dir():
        raise ValueError('Only the explicitly approved current R127 revision batch is allowed')
    approval = json.loads(APPROVAL.read_text())
    if approval.get('approved') is not True or approval['batch'] != str(resolved):
        raise ValueError('Exact revision measurement scope approval missing')
    for name, expected in approval['sha256'].items():
        if sha(name) != expected:
            raise ValueError('Approved measurement dependency changed: ' + name)
    sys.path.insert(0, str(CONTROL))
    import controller
    controller.verify_metadata()
    controller.check_approval(CONTROL / 'root_execution_approval.json', 'stage')
    controller.prior('preview')
    return resolved, approval

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True, type=Path)
    parser.add_argument('--check-scope', action='store_true')
    args = parser.parse_args()
    batch, approval = validate_scope(args.batch)
    if args.check_scope:
        print(json.dumps({'status':'exact_revision_measurement_scope_valid','images_processed':False}))
        return
    spec = importlib.util.spec_from_file_location('unchanged_people_roi_measurement_engine', HELPER)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    # The old CLI permits only its two historical batch roots. The stronger exact
    # revision scope/approval check above replaces that CLI path dispatch only.
    # ALLOWED, measurement math, checkpoint/source guards and shared lock are untouched.
    with engine.image_worker():
        result = engine.measure(batch)
    measurement = batch / 'parent_roi_measurements.json'
    receipt = {'status':'exact_revision_read_only_measurement_completed',
        'utc':engine.utc(),'batch':str(batch),'scope_approval_sha256':sha(APPROVAL),
        'adapter_sha256':sha(__file__),'unchanged_helper_sha256':sha(HELPER),
        'phase2_bundle_sha256':sha(CONTROL/'phase2_bundle.json'),
        'measurement_sha256':sha(measurement),'scope_dispatch_only':True,
        'original_helper_allowlist_modified':False,'images_changed':False,
        'single_shared_image_worker':True,'result':result}
    engine.atomic(batch/'parent_roi_scope_adapter_receipt.json', receipt)
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
