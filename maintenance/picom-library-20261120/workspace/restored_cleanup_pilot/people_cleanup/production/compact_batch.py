#!/usr/bin/env python3
"""Remove reproducible previews only after sealed delivery and viewer verification."""
import argparse
import shutil
from pathlib import Path
from common import HERE, atomic_json, digest, image_worker, read, utc

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.resolve(strict=True)
    assert batch.is_relative_to(HERE / 'batches')
    delivery_path = batch / 'accepted_delivery.json'
    delivered = read(delivery_path)
    verification = read(batch / 'viewer_verification.json')
    assert verification['delivery_sha256'] == digest(delivery_path)
    assert verification['html_sha256'] == digest(batch / 'review.html')
    assert verification['all_bindings_and_files_valid'] and not verification['errors']
    progress = read(HERE / 'progress.json')
    assert any(x['batch_id'] == batch.name and x['manifest_sha256'] == digest(delivery_path) for x in progress['sealed_batches'])
    for row in delivered['images']:
        assert digest(row['path']) == row['sha256']
        assert digest(row['source_path']) == row['source_sha256']
    log_path = batch / 'preview_compaction.json'
    if log_path.exists():
        plan = read(log_path)
        assert plan['delivery_sha256'] == digest(delivery_path)
    else:
        reviewed = read(batch / 'independent_output_review' / 'review_manifest.json')
        by_id = {r['id']: r for r in reviewed['images']}
        first = next((r for r in delivered['images'] if r['delivery'] == 'cleaned'), None)
        keep = {Path(by_id[first['id']]['paths']['normal']).resolve()} if first else set()
        candidates = []
        for directory in (batch / 'previews', batch / 'independent_output_review' / 'evidence'):
            if not directory.exists():
                continue
            for path in sorted(directory.rglob('*.png')):
                assert not path.is_symlink() and path.is_file()
                resolved = path.resolve(strict=True)
                assert resolved.is_relative_to(directory.resolve()) and resolved.is_relative_to(batch)
                if resolved in keep:
                    continue
                candidates.append({'path': str(resolved), 'sha256': digest(resolved), 'bytes': path.stat().st_size})
        plan = {'batch_id': batch.name, 'planned_utc': utc(), 'status': 'planned',
                'delivery_sha256': digest(delivery_path), 'preserved_examples': [str(p) for p in keep],
                'regeneration': 'Source previews: prepare_source_previews.py --batch PATH. Output comparison PNGs: qa.py --batch PATH --evidence --ids ID ... . Retained sources, lossless outputs, masks and metadata recreate these derivatives.',
                'historical_evidence_note': 'Review records retain the paths actually viewed. These reproducible PNG derivatives were intentionally pruned after review, not lost or unreviewed.',
                'free_bytes_before': shutil.disk_usage(HERE).free, 'files': candidates}
        atomic_json(log_path, plan)
    allowed = [(batch / 'previews').resolve(), (batch / 'independent_output_review' / 'evidence').resolve()]
    for row in plan['files']:
        path = Path(row['path'])
        assert any(path.is_relative_to(directory) for directory in allowed)
        if path.exists():
            assert not path.is_symlink() and path.is_file() and path.resolve() == path
            assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
            path.unlink()
    for path in plan['preserved_examples']:
        assert Path(path).is_file()
    plan.update(status='complete', completed_utc=utc(), files_removed=len(plan['files']),
                logical_bytes_removed=sum(r['bytes'] for r in plan['files']), free_bytes_after=shutil.disk_usage(HERE).free)
    atomic_json(log_path, plan)
    print({k: plan[k] for k in ('batch_id','status','files_removed','logical_bytes_removed')})

if __name__ == '__main__':
    with image_worker():
        main()
