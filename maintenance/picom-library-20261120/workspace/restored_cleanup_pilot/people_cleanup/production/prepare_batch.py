#!/usr/bin/env python3
"""Materialize or verify a frozen whole-concept production batch manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import atomic_json, digest, utc


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def materialize(batch_id):
    queue_path = HERE / 'queue.json'
    queue = read(queue_path)
    index_path = HERE / 'batch_index.json'
    index = read(index_path)
    current_queue_hash = digest(queue_path)
    if current_queue_hash != index.get('queue_sha256'):
        raise ValueError('frozen queue hash differs from batch_index.json')
    match = next((b for b in queue.get('batches', []) if b['batch_id'] == batch_id), None)
    if not match:
        raise KeyError(f'unknown batch {batch_id}')
    bdir = HERE / 'batches' / batch_id
    bdir.mkdir(parents=True, exist_ok=True)
    manifest_path = bdir / 'manifest.json'
    blind_path = bdir / 'blind_manifest.json'
    if manifest_path.is_file() and blind_path.is_file():
        expected = next((x for x in index.get('batches', []) if x['batch_id'] == batch_id), None)
        if expected and digest(manifest_path) == expected['manifest_sha256'] and digest(blind_path) == expected['blind_manifest_sha256']:
            return {'batch_id':batch_id,'action':'verified_existing','manifest_sha256':digest(manifest_path),'queue_sha256':current_queue_hash}
        # Do not overwrite any existing source review or preview checkpoint.
        if (bdir/'source_reviews').exists() or (bdir/'previews').exists():
            raise RuntimeError(f'{batch_id} has review/preview data; refusing to regenerate its manifest')
        raise RuntimeError(f'{batch_id} manifest differs from frozen batch index; manual resolution required')
    groups_by_id = {g['group_id']:g for g in queue.get('groups', [])}
    groups=[]
    for gid in match['group_ids']:
        g=groups_by_id[gid]
        groups.append({k:g[k] for k in ('group_id','group_key','people_subfolder','normalized_stem','batch_id','versions')})
    subjects=sum(v['role']=='subject' for g in groups for v in g['versions'])
    refs=sum(v['role']=='reference' for g in groups for v in g['versions'])
    m={
        'schema_version':1,'batch_id':batch_id,'status':'awaiting_source_review','protocol_version':queue['schema_version'],'rule_version':queue['rule_version'],
        'created_utc':utc(),'source_census_sha256':queue['source_census_sha256'],'queue_sha256':current_queue_hash,
        'grouping_rule':queue['grouping_rule'],'selection_rule':'Frozen whole groups; include every pending eligible subject plus up to two same-concept references per group.',
        'target_subjects':queue['batch_target_subjects'],'actual_subjects':subjects,'actual_references':refs,'groups':groups,
    }
    blind={k:v for k,v in m.items() if k!='groups'}
    blind['status']='awaiting_blind_source_review';blind['groups']=[]
    for g in groups:
        bg={k:g[k] for k in ('group_id','group_key','people_subfolder','normalized_stem','batch_id')};bg['versions']=[]
        for v in g['versions']:
            bg['versions'].append({k:v[k] for k in ('batch_id','production_source_id','source','source_sha256','source_bytes','dimensions','style_id','style','role','review_required')})
        blind['groups'].append(bg)
    atomic_json(manifest_path,m);atomic_json(blind_path,blind)
    new_entry={'batch_id':batch_id,'manifest_sha256':digest(manifest_path),'blind_manifest_sha256':digest(blind_path)}
    entries=[x for x in index.get('batches',[]) if x.get('batch_id')!=batch_id]
    entries.append(new_entry)
    index['batches']=entries
    atomic_json(index_path,index)
    return {'batch_id':batch_id,'action':'created','manifest_sha256':digest(manifest_path),'blind_manifest_sha256':digest(blind_path),'queue_sha256':current_queue_hash,'subjects':subjects,'references':refs,'groups':len(groups)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--batch-id',required=True)
    args=ap.parse_args()
    print(json.dumps(materialize(args.batch_id),indent=2))

if __name__=='__main__': main()
