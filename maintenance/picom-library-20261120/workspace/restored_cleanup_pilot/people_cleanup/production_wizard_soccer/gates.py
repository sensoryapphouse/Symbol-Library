"""Fail-closed original-phase3 and generation gates. No image APIs here."""
import re
import sqlite3
from contracts import *


def original_people():
    require(file_sha(PHASE3 / 'phase3_bundle.json') == PHASE3_SHA, 'Wrong original phase3 bundle')
    approval = read(PHASE3 / 'root_execution_approval.json')
    require(approval.get('approved') is True and approval.get('approved_by') == 'root' and
            approval.get('phase3_bundle_sha256') == PHASE3_SHA, 'Original phase3 approval missing')
    # Reuse the authoritative loader: current pointer, immutable proof, complete
    # invocation checkpoints, dependencies and exact original57073 identities.
    sys.path.insert(0,str(PHASE3))
    builder = load('_ws_phase3_builder', PHASE3 / 'build_delivery.py')
    catalog, proof, proof_sha, pointer = builder.load_catalog()
    delivery = BASE / 'final_people_delivery_source_revisions_20261105'
    summary = read(delivery / 'summary.json')
    require(summary['verification_proof_sha256'] == proof_sha and summary['scope_total'] == 57073 and
            summary['phase3_bundle_sha256'] == PHASE3_SHA, 'Original authoritative catalog/proof mismatch')
    for name,digest in summary['artifacts_sha256'].items():
        require(file_sha(delivery / name) == digest,'Original delivery artifact changed')
    actual = jsonl(delivery / 'all_people_dispositions.jsonl')
    require(actual == catalog,'Original canonical catalog differs from verified catalog')
    view = read(delivery / 'viewer_verification.json')
    require(view['summary_sha256'] == file_sha(delivery / 'summary.json') and
            view['exact_bindings_files_and_artifact_hashes'] is True and not view['errors'], 'Original final viewer proof missing')
    return dict(proof_sha256=proof_sha, summary_sha256=file_sha(delivery / 'summary.json'),
        catalog_sha256=file_sha(delivery / 'all_people_dispositions.jsonl'), phase3_bundle_sha256=PHASE3_SHA,
        authority_sha256={**proof['metadata_sha256'],
            str(BASE/'final_people_verification_source_revisions_20261105/latest_status.json'):sha(pointer),
            str(Path(proof['immutable_proof_path'])):proof_sha,
            str(delivery/'summary.json'):file_sha(delivery/'summary.json'),
            str(delivery/'all_people_dispositions.jsonl'):file_sha(delivery/'all_people_dispositions.jsonl'),
            str(delivery/'viewer_verification.json'):file_sha(delivery/'viewer_verification.json')})


def generation_authority(dbpath, dependencies):
    observation_path = PREP/'generation_completion_observation_20261106.json'
    observation_sha = read(HERE/'bundle.json')['dependency_sha256'][str(observation_path)]
    observation = bound_json(observation_path, dependencies, observation_sha)
    producer_root = RUNTIME/'wizard-soccer-registration-20261105'
    closeout_path = producer_root/'eligible-completion/closure.json'
    reconciliation_path = producer_root/'final-production-reconciliation-20261105.json'
    pins = observation['metadata_sha256']
    closeout = bound_json(closeout_path, dependencies, pins[str(closeout_path)])
    reconciliation = bound_json(reconciliation_path, dependencies, pins[str(reconciliation_path)])
    require(observation['writers_released_per_generation_closeout'] is True and
        closeout['own_parent_lease']['status']=='released' and closeout['lease_session_exit_code']==0 and
        closeout['final_reconciliation_sha256']==pins[str(reconciliation_path)] and
        closeout['background_removal_complete'] is False and
        (observation['expected_total'],observation['saved'],observation['held'],observation['eligible_remaining'])==(SCOPE,AVAILABLE,HELD,0) and
        (closeout['saved'],closeout['held'],closeout['eligible_remaining'])==(AVAILABLE,HELD,0) and
        (reconciliation['saved'],reconciliation['held_count'],reconciliation['eligible_remaining'])==(AVAILABLE,HELD,0) and
        reconciliation['status']=='eligible_generation_complete_with_12_held',
        'Exact eligible-only generation writer closeout required')
    holds = {f"{row['lane']}:{row['id']}":row for row in observation['held_cases']}
    producer_holds = {row['target']:row for row in reconciliation['held']}
    require(len(holds)==len(observation['held_cases'])==len(producer_holds)==len(reconciliation['held'])==HELD,
        'Exact held target records required')
    for hold in holds.values():
        producer = producer_holds[hold['target']]
        require(all(hold[k]==producer[k] for k in ('job','hold_path','hold_sha256')) and
            hold['hold_kind']==producer['kind'] and hold['word']==producer['word'] and hold['target_exists'] is False,
            'Held record differs from producer reconciliation')
    dependencies[str(dbpath)] = pins[str(dbpath)]
    return observation_sha, holds


def bound_json(path, dependencies, digest):
    raw, _ = stable_bytes(path, digest)
    dependencies[str(path)] = digest
    return json.loads(raw)


def held_disposition(row, job, digest, observed, dependencies):
    lane, identity, target, style = row['style_queue'], row['concept_id'], row['target'], row['style']
    kind = {106:'STALE_HOST_UNKNOWN_QUARANTINE',107:'KNOWN_OUTPUT_REJECTION'}[lane]
    require(digest is None and (job,target,kind,row['word'])==
        (observed['job'],observed['target'],observed['hold_kind'],observed['word']),
        'Held DB identity, job, status or output digest differs')
    hold_path = RUNTIME/'batch/holds'/(job+'.json')
    require(str(hold_path)==observed['hold_path'], 'Noncanonical generation hold path')
    hold = bound_json(hold_path, dependencies, observed['hold_sha256'])
    require(hold['job']==job and hold['kind']==kind and hold['claim']['style_queue']==lane and
        hold['remote_retry'] is False and hold['rephrase'] is False and identity in hold['concept_ids'] and
        hold['backend_outcome']==('unknown' if lane==106 else 'completed'),
        'Held generation job disposition changed')
    spec_path = RUNTIME/'batch/specs'/(job+'.json')
    require(hold['spec_sha256']==hold['claim']['spec_sha256'],'Held claim spec binding differs')
    spec = bound_json(spec_path, dependencies, hold['spec_sha256'])
    publish = [s for s in spec['slots'].values() if s['role']=='publish']
    require(sorted(s.get('concept_id',s.get('inventory_id')) for s in publish)==sorted(hold['concept_ids']) and
        len([s for s in publish if s.get('concept_id',s.get('inventory_id'))==identity and
             s['target']==target and s['style_name']==style])==1, 'Held spec concept/style/publish identity differs')
    require_absent(target)
    metadata = {name:row[name] for name in ('target_id','concept_id','style_queue','style','target','relative_target','ordinal','category','word')}
    return dict(metadata,job=job,
        disposition='generation_held',generation_status='held',target_absent=True,hold_kind=kind,
        hold_path=str(hold_path),hold_sha256=observed['hold_sha256'],
        spec_path=str(spec_path),spec_sha256=hold['spec_sha256'])


def generation():
    expected = {r['target_id']:r for r in inventory()}
    manifest_path = RUNTIME / 'wizard-soccer-registration-20261105/manifest.json'
    readiness=read(PREP/'scope_readiness_20261105.json')
    require(readiness['registration_manifest']['path']==str(manifest_path),'Generation registration authority changed')
    dependencies={}
    registration = bound_json(manifest_path, dependencies, readiness['registration_manifest']['sha256'])
    require(set(registration['entry_sha256']) == set(expected),'Generation registration identity drift')
    dbpath = RUNTIME / 'batch/wizard-soccer-inventory-20261105.sqlite'
    wal = Path(str(dbpath)+'-wal')
    observation_sha, holds = generation_authority(dbpath, dependencies)
    require_absent(wal)
    stable_bytes(dbpath, dependencies[str(dbpath)])
    db = sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        db.execute('BEGIN')
        rows = db.execute('select lane,id,entry,status,job,output_sha256 from inventory').fetchall()
        cleanup = db.execute('select status from cleanup').fetchall()
        db.rollback()
    finally:
        db.close()
    stable_bytes(dbpath, dependencies[str(dbpath)])
    require_absent(wal)
    require(len(rows)==SCOPE and {f'{q}:{i}' for q,i,*_ in rows} == set(expected),'Incomplete generation identities')
    require(all(status=='complete' for status, in cleanup),'Unresolved generation cleanup jobs')
    outputs=[]; held=[]
    for q,ident,entry_text,status,job,digest in rows:
        key=f'{q}:{ident}'; target=expected[key]['target']; entry=json.loads(entry_text)
        require(entry['target']==target and entry['id']==ident and
                sha(json.dumps(entry,sort_keys=True,separators=(',',':')).encode())==registration['entry_sha256'][key],
                'Generation entry differs from pinned registered concept')
        require(isinstance(job,str) and re.fullmatch(r'[A-Za-z0-9_-]+',job),'Unsafe generation job identity')
        if key in holds:
            require(status=='held','Pinned held target DB status changed')
            held.append(held_disposition(expected[key],job,digest,holds[key],dependencies))
            continue
        require(status=='saved' and isinstance(digest,str) and re.fullmatch(r'[0-9a-f]{64}',digest),'Available generation target not saved')
        rp=RUNTIME/'batch/records'/(job+'.json'); receipt=read(rp)
        slots=[(slot,t) for slot,t in receipt.get('targets',{}).items() if t.get('path')==target and t.get('sha256')==digest]
        require(len(slots)==1,'Saved output lacks exact receipt slot')
        dependencies[str(rp)]=file_sha(rp)
        if receipt.get('receipt_kind')=='approved_mixed_sample_adoption':
            plan_path=Path(registration['plan_snapshot']['path']); plan=read(plan_path)
            require(file_sha(plan_path)==registration['plan_snapshot']['sha256'],'Adoption plan drift')
            adopted=[x for x in plan.get('adopted_outputs',[]) if x['style_queue']==q and x['concept_id']==ident and x['target']==target and x['sha256']==digest]
            require(len(adopted)==1,'Unbound adopted output')
            dependencies[str(plan_path)]=file_sha(plan_path)
        else:
            sp=RUNTIME/'batch/specs'/(job+'.json'); spec=read(sp)
            require(file_sha(sp)==receipt['spec_sha256'],'Saved receipt spec differs')
            slot=spec['slots'][slots[0][0]]
            require(slot['target']==target and slot.get('concept_id',slot.get('inventory_id'))==ident and
                    slot['style_name']==expected[key]['style'] and slot.get('role')=='publish','Spec concept/style/publish identity differs')
            dependencies[str(sp)]=file_sha(sp)
        outputs.append(dict(target_id=key,source=target,source_sha256=digest,job=job))
    require(len(outputs)==AVAILABLE and len(held)==HELD,'Generation saved/held partition differs')
    return dict(schema='wizard-soccer-generation-availability-v1',scope_total=SCOPE,
        rows=sorted(outputs,key=lambda r:r['target_id']),held=sorted(held,key=lambda r:r['target_id']),
        metadata_sha256=dependencies,absent_generation_wal=str(wal),observation_sha256=observation_sha,
        complete_available_saved_receipts=True,full_generation_complete=False,source_bytes_verified=False)


def enter(approval_path, action, input_paths=()):
    require_worker()
    approval=require_approval(approval_path,action)
    for path in input_paths:
        require(approval.get('approved_inputs',{}).get(str(Path(path).resolve()))==file_sha(path),'Operation input not bound by root approval')
    original=original_people()
    reconciled=generation()
    closeout_ref=approval['generation_closeout']
    closeout = bound_json(Path(closeout_ref['path']),{},closeout_ref['sha256'])
    require(Path(closeout_ref['path']).is_absolute() and Path(closeout_ref['path']).suffix=='.json' and
            closeout.get('schema')=='root-available-generation-closeout-v1' and
            closeout.get('approved_by')=='root' and closeout.get('generation_writers_finished') is True and
            closeout.get('reconciliation_sha256')==sha(payload(reconciled)), 'Root available-generation closeout required')
    return dict(original_people=original,generation=reconciled,generation_closeout=closeout_ref,bundle_sha256=approval['bundle_sha256'])
