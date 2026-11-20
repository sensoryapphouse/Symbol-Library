#!/usr/bin/env python3
"""Compile qualified source selections into pinned, conservative core seeds.

This translates explicit semantic selections; it does not classify images.
References are retained and cannot acquire automatic cleanup decisions.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import time
from pathlib import Path
from common import HERE, atomic_json, digest, image_worker, read, utc

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True, type=Path)
    parser.add_argument('--approve', action='store_true')
    args = parser.parse_args()
    batch = args.batch.resolve(strict=True)
    from common import verify_batch_scope
    from non_people_publication import operator_lock, require_open_batch
    verify_batch_scope(batch)
    with operator_lock():
        require_open_batch(batch, allow_existing=False)
        with image_worker():
            compile_batch(batch, args.approve)


def compile_batch(batch, approve):
    assert batch.is_relative_to(HERE / 'batches')
    manifest_path = batch / 'manifest.json'
    manifest = read(manifest_path)
    rows = [row for group in manifest['groups'] for row in group['versions']]
    assert len({r['batch_id'] for r in rows}) == len(rows)
    proofs, reviews = {}, {}
    for group in manifest['groups']:
        path = batch / 'source_reviews' / (group['group_id'] + '.json')
        required = {r['batch_id'] for r in group['versions'] if r.get('review_required', True)}
        if not path.exists():
            assert not required, f'Missing source checkpoint {path}'
            continue
        checkpoint = read(path)
        proofs[path.name] = digest(path)
        records = checkpoint['source_records']
        allowed = {r['batch_id'] for r in group['versions']}
        ids = {r['id'] for r in records}
        assert len(ids) == len(records) and required <= ids <= allowed
        for record in records:
            assert record['id'] not in reviews
            record = dict(record)
            record.setdefault('reviewer', checkpoint.get('reviewer'))
            reviews[record['id']] = record
    destination = batch / ('approved_decisions.json' if approve else 'draft_decisions.json')
    if destination.exists():
        existing = read(destination)
        assert existing['manifest_sha256'] == digest(manifest_path)
        assert existing['source_checkpoint_sha256'] == proofs, 'Source decisions changed after compilation'
        assert existing['compiler_sha256'] == digest(__file__), 'Compiler changed after compilation'
        for row in rows:
            assert digest(row['source']) == row['source_sha256']
        print({'status': 'existing_compilation_verified', 'images': len(rows)})
        return
    started, clock = utc(), time.perf_counter()
    decisions, regions = [], []
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    for row in rows:
        ident = row['batch_id']
        assert digest(row['source']) == row['source_sha256'], ident
        record = reviews.get(ident)
        required = row.get('review_required', True)
        if not required:
            decisions.append({'id': ident, 'source_sha256': row['source_sha256'],
                'dimensions': row['dimensions'], 'reviewer': 'mechanical_context_reference',
                'source_reviewed': bool(record and record.get('actually_viewed')),
                'source_reason': 'Context reference; excluded from this batch cleanup.',
                'decision': 'unchanged', 'regions': [], 'review_required': False})
            continue
        assert record and record.get('actually_viewed') is True, ident
        assert record['source_sha256'] == row['source_sha256'] and record['dimensions'] == row['dimensions'], ident
        assert record.get('native_view_evidence'), f'{ident}: native source evidence required'
        reviewer = record.get('reviewer')
        assert isinstance(reviewer, str) and reviewer.strip(), f'{ident}: reviewer identity required'
        classification = record['classification']
        assert classification in ('clear_background_gap','none_worthwhile','uncertain_keep')
        assert isinstance(record.get('findings'), str) and record['findings'].strip()
        decision = {'id': ident, 'source_sha256': row['source_sha256'],
            'dimensions': row['dimensions'], 'reviewer': reviewer,
            'source_reviewed': True, 'review_required': True,
            'source_reason': record['findings'], 'source_classification': classification,
            'decision': 'uncertain' if classification == 'uncertain_keep' else 'unchanged',
            'regions': [], 'tiny_targets': record.get('tiny_targets', [])}
        for key in ('protected_boxes','protected_polygons'):
            if key in record:
                decision[key] = record[key]
        proposals = record.get('regions', [])
        if proposals:
            assert classification == 'clear_background_gap'
            a = np.asarray(Image.open(row['source']).convert('RGBA'))
            assert [a.shape[1], a.shape[0]] == row['dimensions']
            white = (a[:, :, :3].min(2) >= 240) & (np.ptp(a[:, :, :3], axis=2) <= 20) & (a[:, :, 3] >= 128)
            labels, _ = ndi.label(white, np.ones((3, 3)))
            inventory = {c.get('label_id', c.get('component_label')): c for c in row['components_ge64_at_512']}
            scale = max(row['dimensions']) / 512
            names = set()
            for region in proposals:
                name = region['name']
                assert isinstance(name, str) and name.strip() and name not in names
                names.add(name)
                selected = region['component_labels']
                assert selected and len(selected) == len(set(selected))
                components = [inventory[label] for label in selected]
                boxes = [c.get('bbox_xyxy', c.get('bbox_xyxy_native')) for c in components]
                assert all(box and len(box) == 4 for box in boxes)
                default = [min(box[0] for box in boxes), min(box[1] for box in boxes),
                           max(box[2] for box in boxes), max(box[3] for box in boxes)]
                roi = region.get('roi') or default
                assert len(roi) == 4 and all(isinstance(v, int) for v in roi)
                x0, y0, x1, y1 = roi
                assert 0 <= x0 < x1 <= row['dimensions'][0] and 0 <= y0 < y1 <= row['dimensions'][1]
                seeds, count = [], 0
                for label in selected:
                    part = labels[y0:y1, x0:x1] == label
                    assert part.any(), (ident, label, roi)
                    distance = ndi.distance_transform_edt(part)
                    y, x = np.unravel_index(distance.argmax(), part.shape)
                    seeds.append([int(x + x0), int(y + y0)])
                    count += int(part.sum())
                detail = {'name': name, 'roi': roi, 'core_seeds': seeds,
                          'source_component_labels': selected, 'reason': region.get('reason', ''),
                          'selected_pixels_before_engine_protection': count,
                          'selected_pixels_at_512': count / scale**2}
                for key in ('protected_boxes','protected_polygons'):
                    if key in region:
                        detail[key] = region[key]
                regions.append({'id': ident, **detail})
                if count / scale**2 < 256:
                    decision.setdefault('omitted_regions', []).append({**detail, 'reason_for_omission': 'below_fixed_256_pixel_minimum'})
                else:
                    decision['regions'].append(detail)
            if decision['regions']:
                decision['decision'] = 'cleanup'
        decisions.append(decision)
    result = {'batch_id': manifest['batch_id'], 'manifest_sha256': digest(manifest_path),
              'compiler_sha256': digest(__file__), 'source_checkpoint_sha256': proofs,
              'root_approval': {'approved': approve, 'approved_by': 'root' if approve else None,
                'utc': utc(), 'basis': 'User-authorized production; stage qualified reviewer selections. Independent safety and worthwhile review is required before acceptance.'},
              'decisions': decisions}
    atomic_json(destination, result)
    atomic_json(batch / 'selected_regions.json', regions)
    timing = {'started_utc': started, 'completed_utc': utc(), 'elapsed_seconds': time.perf_counter()-clock,
              'images': len(decisions), 'cleanup_images': sum(d['decision'] == 'cleanup' for d in decisions),
              'selected_regions': sum(len(d['regions']) for d in decisions),
              'source_reviews_required': sum(r.get('review_required', True) for r in rows)}
    atomic_json(batch / 'geometry_preparation.json', timing)
    print(timing)

if __name__ == '__main__':
    main()
