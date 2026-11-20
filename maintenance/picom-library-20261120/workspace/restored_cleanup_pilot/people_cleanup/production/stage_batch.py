#!/usr/bin/env python3
"""Run the already-authorized mechanical stages after all source reviews exist."""
import argparse
import subprocess
import sys
from pathlib import Path
from common import HERE, digest, read, utc, atomic_json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.resolve(strict=True)
    assert batch.is_relative_to(HERE / 'batches')
    if (batch / 'accepted_delivery.json').exists():
        print({'batch': batch.name, 'status': 'already_sealed_do_not_restage'})
        return
    started = utc()
    def run(script, *extra):
        subprocess.run([sys.executable, str(HERE / script), '--batch', str(batch), *extra], check=True)
    run('compile_decisions.py', '--approve')
    run('run_selected.py')
    audit_path = batch / 'mechanical_audit.json'
    audit = read(audit_path) if audit_path.exists() else None
    pins = {'manifest_sha256': digest(batch/'manifest.json'),
            'decisions_sha256': digest(batch/'approved_decisions.json'),
            'run_state_sha256': digest(batch/'selected_run_state.json')}
    if not audit or audit['errors'] or any(audit.get(k) != v for k,v in pins.items()):
        run('qa.py')
        audit = read(audit_path)
    assert not audit['errors']
    state = read(batch/'selected_run_state.json')
    changed = {r['id']: r for r in state['images'] if r['status']=='changed'}
    evidence_path = batch/'independent_output_review'/'review_manifest.json'
    previous = {r['id']: r for r in read(evidence_path)['images']} if evidence_path.exists() else {}
    pending = []
    for ident, row in changed.items():
        saved = previous.get(ident)
        valid = saved and saved['output_sha256']==row['output_sha256'] and saved['source_sha256']==row['source_sha256']
        if valid:
            checks = [(Path(p), saved['evidence_sha256'][kind]) for kind,p in saved['paths'].items()]
            checks += [(Path(r['path']), r['sha256']) for r in saved['regions']]
            valid = all(path.is_file() and digest(path)==expected for path,expected in checks)
        if not valid:
            pending.append(ident)
    if pending:
        run('qa.py', '--evidence', '--ids', *pending)
    if not changed and not (batch/'independent_output_review.json').exists():
        atomic_json(batch/'independent_output_review.json', {'images': [], 'note': 'No changed outputs; no visual output review claimed.'})
    run('commit_progress.py')
    ready = {'batch_id':batch.name,'started_utc':started,'ready_utc':utc(),
             'changed_outputs':len(changed),'mechanical_errors':0,'status':'ready_for_independent_output_review' if changed else 'ready_to_seal_unchanged',
             'source_authorization':'User-authorized production, qualified complete source checkpoints; no automatic semantic classification.'}
    atomic_json(batch/'output_review_readiness.json',ready)
    print(ready)

if __name__ == '__main__':
    main()
