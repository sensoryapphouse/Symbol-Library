#!/usr/bin/env python3
"""Append durable source/delivery events and rebuild the compact live snapshot."""
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
from common import HERE, atomic_json, digest, read, utc

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path)
    parser.add_argument('--historical-resolution', action='store_true')
    parser.add_argument('--historical-output-review', action='store_true')
    args = parser.parse_args()
    with (HERE / 'ledger.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = read(HERE / 'inventory.json')['images']
        original = {r['production_source_id']: r for r in inventory}
        states = {key: {'status': r['status'], 'source_sha256': r['source_sha256'],
                        'delivery': r.get('final_delivery')} for key, r in original.items()}
        seen = set()
        with (HERE / 'ledger.jsonl').open() as stream:
            for line in stream:
                event = json.loads(line)
                if event.get('event_id'):
                    seen.add(event['event_id'])
                key = event.get('production_source_id')
                if key in states and event.get('status_to'):
                    states[key].update(status=event['status_to'], last_event=event.get('event_id'))
                    for field in ('delivery','source_reviewed','output_reviewed','batch_id','reason'):
                        if field in event:
                            states[key][field] = event[field]
        pending = []
        def add(kind, source_id, status, proof, **fields):
            assert source_id in original
            stable = {'event': kind, 'production_source_id': source_id, 'status_to': status,
                      'proof_sha256': proof, 'source_sha256': original[source_id]['source_sha256'], **fields}
            event_id = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
            if event_id in seen:
                return
            event = {**stable, 'event_id': event_id, 'utc': utc(), 'actor': 'root',
                     'status_from': states[source_id]['status']}
            pending.append(event)
            seen.add(event_id)
            states[source_id].update(status=status, last_event=event_id)
            for field in ('delivery','source_reviewed','output_reviewed','batch_id','reason'):
                if field in fields:
                    states[source_id][field] = fields[field]
        if args.historical_resolution:
            path = HERE / 'historical_resolution.json'
            resolution = read(path)
            assert resolution['inventory_sha256'] == digest(HERE / 'inventory.json')
            for row in resolution['records']:
                source_id = row['production_source_id']
                assert row['source_sha256'] == original[source_id]['source_sha256']
                assert digest(original[source_id]['source']) == row['source_sha256']
                decision = row['resolution']
                if decision == 'needs_new_output_review':
                    add('historical_review_binding_gap', source_id, 'needs_historical_output_review', digest(path),
                        reason='Existing cleanup retained for exact output review; source cleanup will not be repeated.')
                    continue
                delivery = row['proposed_delivery']
                assert digest(delivery['path']) == delivery['sha256']
                add('historical_delivery_verified', source_id,
                    'accepted_prior_cleaned' if decision == 'complete_cleaned_prior_policy' else 'completed_original',
                    digest(path), delivery=delivery, reason=row.get('reason', decision))
        if args.historical_output_review:
            resolution_path = HERE / 'historical_resolution.json'
            resolution = read(resolution_path)
            assert resolution['inventory_sha256'] == digest(HERE / 'inventory.json')
            expected = {r['production_source_id']: r for r in resolution['records']
                        if r['resolution'] == 'needs_new_output_review'}
            review_path = HERE / 'historical_output_review' / 'reviews.json'
            reviews = read(review_path)
            reviewed = {r['production_source_id']: r for r in reviews['images']}
            assert len(reviewed) == len(reviews['images']) and set(reviewed) == set(expected), 'Historical review must cover every pending source exactly once'
            evidence = read(HERE / 'historical_output_review' / 'evidence_manifest.json')
            assert evidence['resolution_sha256'] == digest(resolution_path)
            deliveries = []
            # Validate every record before writing a delivery or appending ledger events.
            for source_id, prior in expected.items():
                q = reviewed[source_id]
                source = original[source_id]
                assert q['id'] == prior['historical_id']
                assert q['source'] == prior['source'] == source['source']
                assert q['source_sha256'] == prior['source_sha256'] == source['source_sha256'] == digest(source['source'])
                assert q['candidate_lossless_path'] == prior['candidate_lossless_path']
                assert q['output_sha256'] == prior['candidate_lossless_current_sha256'] == digest(q['candidate_lossless_path'])
                assert q['actually_viewed'] is True and q['full_and_allregions_checked'] is True
                assert isinstance(q['reviewer'], str) and q['reviewer'].strip()
                assert isinstance(q['reason'], str) and q['reason'].strip()
                proof = q['evidence']
                assert proof == evidence['images'][q['id']] and proof['all_actual_changes_covered'] is True
                assert proof['source_sha256'] == q['source_sha256'] and proof['output_sha256'] == q['output_sha256']
                assert digest(proof['delta_mask_path']) == proof['delta_mask_sha256']
                assert prior['source_individual_review_completed'] is True
                assert q['safety'] in ('clear', 'uncertain', 'unsafe')
                assert q['proposed_delivery'] in ('cleaned', 'original')
                cleaned = q['proposed_delivery'] == 'cleaned'
                assert not cleaned or q['safety'] == 'clear'
                path = q['candidate_lossless_path'] if cleaned else q['source']
                sha = q['output_sha256'] if cleaned else q['source_sha256']
                assert q['proposed_path'] == path and q['proposed_sha256'] == sha
                deliveries.append({'production_source_id': source_id, 'id': q['id'],
                                   'source_path': q['source'], 'source_sha256': q['source_sha256'],
                                   'delivery': q['proposed_delivery'], 'path': path, 'sha256': sha,
                                   'reviewer': q['reviewer'], 'reason': q['reason']})
            delivery_path = HERE / 'historical_output_review' / 'accepted_delivery.json'
            result = {'resolution_sha256': digest(resolution_path), 'review_sha256': digest(review_path),
                      'policy': 'Preserve safe reviewed legacy improvements, including minor changes; retain originals for unsafe or uncertain results.',
                      'images': deliveries}
            if delivery_path.exists():
                assert read(delivery_path) == result, 'Previously committed historical delivery differs'
            else:
                atomic_json(delivery_path, result)
            for item in deliveries:
                add('historical_exact_output_review', item['production_source_id'],
                    'accepted_prior_cleaned' if item['delivery'] == 'cleaned' else 'completed_original',
                    digest(delivery_path), delivery=item, source_reviewed=True, output_reviewed=True,
                    reason=item['reason'])
        if args.batch:
            batch = args.batch.resolve(strict=True)
            assert batch.is_relative_to(HERE / 'batches')
            manifest = read(batch / 'manifest.json')
            required = {r['batch_id']: r for g in manifest['groups'] for r in g['versions'] if r.get('review_required', True)}
            for checkpoint in sorted((batch / 'source_reviews').glob('g*.json')):
                content = read(checkpoint)
                for record in content['source_records']:
                    ident = record['id']
                    if ident not in required:
                        continue
                    row = required[ident]
                    assert record['source_sha256'] == row['source_sha256'] and record['actually_viewed'] is True
                    assert record['dimensions'] == row['dimensions']
                    source_id = row['production_source_id']
                    # A later source refresh must not roll an accepted delivery back.
                    if states[source_id]['status'] in ('accepted', 'original_retained'):
                        continue
                    add('qualified_source_review', source_id, 'source_reviewed', digest(checkpoint),
                        batch_id=manifest['batch_id'], source_reviewed=True, reason=record['findings'],
                        source_reviewer=record.get('reviewer', content.get('reviewer')),
                        source_classification=record['classification'])
            delivery_path = batch / 'accepted_delivery.json'
            if delivery_path.exists():
                delivery = read(delivery_path)
                assert delivery['manifest_sha256'] == digest(batch / 'manifest.json')
                assert delivery['mechanical_audit_sha256'] == digest(batch / 'mechanical_audit.json')
                assert delivery['output_review_sha256'] == digest(batch / 'independent_output_review.json')
                visually_reviewed = {r['id'] for r in read(batch / 'independent_output_review.json')['images']}
                items = {r['id']: r for r in delivery['images']}
                for ident, row in required.items():
                    item = items[ident]
                    assert item['source_sha256'] == row['source_sha256']
                    assert digest(row['source']) == row['source_sha256']
                    assert digest(item['path']) == item['sha256']
                    add('sealed_batch_delivery', row['production_source_id'],
                        'accepted' if item['delivery'] == 'cleaned' else 'original_retained', digest(delivery_path),
                        batch_id=manifest['batch_id'], source_reviewed=True,
                        output_reviewed=ident in visually_reviewed, delivery=item, reason=item['reason'])
        with (HERE / 'ledger.jsonl').open('a') as stream:
            for event in pending:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        counts = collections.Counter(r['status'] for r in states.values())
        sealed = []
        for folder in sorted((HERE / 'batches').glob('batch*')):
            path = folder / 'accepted_delivery.json'
            if path.exists():
                value = read(path)
                current = [r for r in value['images'] if r.get('review_required', True)]
                sealed.append({'batch_id': folder.name, 'manifest_sha256': digest(path),
                               'reviewed_sources': len(current), 'accepted': sum(r['delivery'] == 'cleaned' for r in current),
                               'review_page': str(folder / 'review.html')})
        snapshot = {'updated_utc': utc(), 'inventory_sha256': digest(HERE / 'inventory.json'),
                    'ledger_sha256': digest(HERE / 'ledger.jsonl'), 'status_counts': dict(counts),
                    'sealed_batches': sealed, 'new_production_sources_complete': sum(x['reviewed_sources'] for x in sealed),
                    'new_production_accepted': sum(x['accepted'] for x in sealed),
                    'note': 'Below-threshold sources remain unchanged and require final source-hash verification. Historical binding gaps are separate from new production.',
                    'images': states}
        atomic_json(HERE / 'state.json', snapshot)
        atomic_json(HERE / 'progress.json', {k: v for k, v in snapshot.items() if k != 'images'})
        print({'events_appended': len(pending), 'status_counts': dict(counts), 'sealed_batches': len(sealed)})

if __name__ == '__main__':
    main()
