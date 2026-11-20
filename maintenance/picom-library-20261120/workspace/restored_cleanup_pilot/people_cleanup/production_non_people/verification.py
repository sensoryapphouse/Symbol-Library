"""Whole original Non-People governing-disposition preflight and final byte verification."""
import argparse,collections,json,subprocess,sys
from pathlib import Path
from common import HERE,LIBRARY,require,read,digest,atomic_json,utc,validate_bundle
from scope_metadata import PREP, jsonl, reconstruct
from source_versions import PENDING,REVIEW,TOTAL,VERSION_KEYS,logical_id,version_fields,reject_stale_delivery
from contracts import unique
from byte_proofs import begin_pass,validate_rows,run_pass,load_complete
from prerequisites import verify_generation_metadata
from non_people_publication import batch_publication, overlay_rows, prior_publication


def helper(mode,payload=None):
    result=subprocess.run([sys.executable,str(HERE/'legacy_lineage.py'),'--mode',mode],input=None if payload is None else json.dumps(payload),capture_output=True,text=True)
    require(result.returncode==0,'Isolated governing-lineage helper failed: '+result.stderr[-3000:])
    return json.loads(result.stdout)

def merge_pins(target,pins):
    for path,sha in pins.items():
        if path in target:require(target[path]==sha,'Metadata changed during governing-lineage reconstruction: '+path)
        target[path]=sha

def frozen_metadata():
    bundle=validate_bundle();pins={str(HERE/'code_bundle.json'):digest(HERE/'code_bundle.json')}
    pins.update({str(HERE/name):sha for name,sha in bundle['local_sha256'].items()});pins.update(bundle['external_sha256']);return pins

def pending_audit_plan():
    original,pending,prior,overlay=reconstruct();pins=frozen_metadata()
    rows=[]
    for rel,row in pending.items():
        sha=row['source_sha256'];identity=logical_id(rel,row)
        rows.append({'relative_path':rel,'source_id':identity,'source':str(LIBRARY/rel),'source_sha256':sha,
            'status':'pending_original_activation_byte_audit','delivery_kind':'original','delivery_path':str(LIBRARY/rel),'delivery_sha256':sha,
            **version_fields(rel,identity,row.get('historical_source_sha256',sha),sha), 'expected_source_bytes':row['source_bytes']})
    validate_rows(rows,PENDING);return rows,pins

def read_runtime(pending,pins):
    required=('inventory.json','queue.json','batch_index.json','ledger.jsonl','import_audit.json')
    if any(not (HERE/name).is_file() for name in required):return {},['Runtime initialization has not occurred; all66079 full source reviews remain required.']
    for name in required:pins[str(HERE/name)]=digest(HERE/name)
    inventory=unique(read(HERE/'inventory.json')['images'],'relative_path');require(set(inventory)==set(pending),'Runtime pending inventory exact source set differs')
    ids=unique(list(inventory.values()),'production_source_id');queue=read(HERE/'queue.json');index=read(HERE/'batch_index.json')
    require(index['queue_sha256']==pins[str(HERE/'queue.json')],'Runtime queue/index binding differs')
    require(queue['cohort']=='production_non_people' and queue['subject_count']==REVIEW,'Runtime cohort/subject count differs')
    subjects={}
    for group in queue['groups']:
        for version in group['versions']:
            if version['role']=='subject':
                sid=version['production_source_id'];require(sid not in subjects and sid in ids,'Duplicate/unknown queue source');subjects[sid]=version
    expected={rel for rel,r in pending.items() if r['partition']=='review_required'}
    require({ids[sid]['relative_path'] for sid in subjects}==expected,'Runtime review exact source set differs')
    for rel,row in inventory.items():
        require(row['source_sha256']==pending[rel]['source_sha256'] and row['source']==str(LIBRARY/rel),'Runtime original source SHA/path differs')
        require(row['production_source_id']==logical_id(rel,pending[rel]),'Runtime logical source identity differs')
        require(row['source_bytes']==pending[rel]['source_bytes'],'Runtime source byte size differs')
        for key in VERSION_KEYS:
            require(row.get(key)==pending[rel].get(key),'Runtime source-version binding differs')
        if rel in expected:require(row['production_queue_id']==subjects[row['production_source_id']]['batch_id'],'Runtime review ID differs')
        row['cohort']=str(HERE)
    raw=(HERE/'ledger.jsonl').read_bytes();require(not raw or raw.endswith(b'\n'),'Incomplete runtime ledger tail')
    for line in raw.splitlines():
        event=json.loads(line);sid=event.get('production_source_id');require(sid in ids and event.get('source_sha256')==ids[sid]['source_sha256'],'Unknown/mismatched ledger source')
        row=ids[sid]
        if event.get('status_to'):
            row['status']=event['status_to'];row['last_event']={k:event.get(k) for k in ('event','event_id','proof_sha256','batch_id','source_reviewed','output_reviewed','utc')}
        if event.get('delivery'):row['final_delivery']=event['delivery']
    require(digest(HERE/'ledger.jsonl')==pins[str(HERE/'ledger.jsonl')],'Ledger changed during metadata reconstruction')
    return inventory,[]

def prior_lineage(prior=None):
    if prior is None:
        _,_,prior,_=reconstruct()
    pins={};rows=[];issues=[]
    topic={rel:r['source_sha256'] for rel,r in prior.items() if r['partition']=='excluded_frozen_topic_inventory'}
    previous={rel:r['source_sha256'] for rel,r in prior.items() if r['partition']=='previously_completed_original'}
    for mode,wanted in [('original_prior',topic),('completed_prior',previous)]:
        result=helper(mode,wanted);merge_pins(pins,result['metadata_sha256']);rows.extend(result['rows']);issues.extend(result['issues'])
        require({r['relative_path'] for r in result['rows']}|{r['relative_path'] for r in result['issues']}==set(wanted),'Governing prior helper omitted/added an original source')
    queue=PREP/'proposed_queue.jsonl'
    queue_sha=digest(queue)
    prior_accepted={row['relative_path'] for row in rows if row['delivery_kind']!='original'}
    require(not any(ref['relative_path'] in prior_accepted for group in jsonl(queue)
                    for ref in group['context_references']), 'Governing prior acceptance overlaps a frozen context input')
    require(digest(queue)==queue_sha, 'Frozen context assignments changed during prior lineage reconstruction')
    pins[str(queue)]=queue_sha
    return rows,pins,issues

def final_plan():
    original,pending,prior,overlay=reconstruct();pins=frozen_metadata();unfinished=[]
    rows,prior_pins,issues=prior_lineage(prior)
    merge_pins(pins,prior_pins)
    if not issues:
        try:
            overlay_rows(rows,prior_publication(rows,prior_pins,load_only=True),pins)
        except (ValueError,FileNotFoundError) as error:
            unresolved=[row for row in rows if row['delivery_kind']!='original']
            rows=[row for row in rows if row['delivery_kind']=='original']
            issues.extend({'relative_path':row['relative_path'],'error':str(error),'status':row['status']} for row in unresolved)
    runtime,runtime_notes=read_runtime(pending,pins);completed=collections.defaultdict(list)
    for rel,source in pending.items():
        if source['partition']!='review_required':
            rows.append({'relative_path':rel,'source_id':logical_id(rel,source),'source':str(LIBRARY/rel),'source_sha256':source['source_sha256'],
                'status':source['partition'],'delivery_kind':'original','delivery_path':str(LIBRARY/rel),'delivery_sha256':source['source_sha256']})
            if rel in runtime:
                state=runtime[rel];require(not state.get('production_queue_id') and state['status'] not in ('accepted','accepted_prior_cleaned','accepted_prior_repair'),'Skipped original acquired a cleanup outcome')
            continue
        state=runtime.get(rel)
        if state is None or state['status'] not in ('accepted','original_retained'):
            unfinished.append({'relative_path':rel,'status':None if state is None else state['status']});continue
        require(state.get('production_batch_id')==source['proposed_batch_id'] and state.get('production_queue_id')==source['proposed_subject_id'] and state.get('last_event',{}).get('batch_id')==source['proposed_batch_id'],'Finalized review assignment/event batch differs')
        completed[state['production_batch_id']].append(state)
    for batch_id,states in completed.items():
        result=helper('queued_completed',states);merge_pins(pins,result['metadata_sha256']);issues.extend(result['issues'])
        require({r['relative_path'] for r in result['rows']}|{r['relative_path'] for r in result['issues']}=={r['relative_path'] for r in states},'Completed-batch helper omitted/added a subject')
        viewer=HERE/'batches'/batch_id/'viewer_verification.json'
        if result['issues']:
            rows.extend(result['rows'])
            continue
        try:
            tx=batch_publication(viewer.parent,load_only=True)
            view=read(viewer)
            require(view.get('all_bindings_and_files_valid') is True and not view['errors']
                    and view['delivery_sha256']==digest(viewer.parent/'accepted_delivery.json')
                    and view['publication_complete_sha256']==digest(tx.complete_path)
                    and view['html_sha256']==digest(viewer.parent/'review.html'),'Published viewer binding differs')
            overlay_rows(result['rows'],tx,pins)
        except (ValueError,FileNotFoundError) as error:
            issues.extend({'relative_path':row['relative_path'],'error':str(error),'status':row['status']} for row in result['rows'])
            continue
        rows.extend(result['rows'])
        pins[str(viewer)]=digest(viewer)
        pins[str(viewer.parent/'review.html')]=view['html_sha256']
    for name in ('root_runtime_review.json','root_activation_approval.json'):
        if (HERE/name).is_file():pins[str(HERE/name)]=digest(HERE/name)
    if (HERE/'root_activation_approval.json').is_file():
        approval=read(HERE/'root_activation_approval.json');require(approval.get('approved') is True,'Final verification authority was revoked')
        attestation=Path(approval['attestation_path']).resolve();require(attestation.parent==HERE/'activation_attestations' and digest(attestation)==approval['attestation_sha256'],'Final verification activation attestation differs')
        authority=read(attestation);merge_pins(pins,authority['bound_metadata_sha256']);pins[str(attestation)]=approval['attestation_sha256']
        # Final byte receipts also bind actual People/activation authority. A pointer,
        # governing metadata or approval change during the final pass prevents completion.

    accounted=[r['relative_path'] for r in rows]+[r['relative_path'] for r in unfinished]+[r['relative_path'] for r in issues]
    require(len(accounted)==len(set(accounted)) and set(accounted)==set(original),'Independent final scope missing/duplicate/extra original paths')
    for row in rows:
        rel=row['relative_path'];source=original[rel];sha=source['source_sha256']
        require(row['source_sha256']==sha,'Final disposition is not bound to current source SHA')
        if rel in pending:
            require(row['source_id']==logical_id(rel,source),'Final disposition lost its historical logical identity')
            if 'expected_source_bytes' in row:
                require(row['expected_source_bytes']==pending[rel]['source_bytes'],'Publication input size differs from frozen source')
            row['expected_source_bytes']=pending[rel]['source_bytes']
        reject_stale_delivery(row,source)
        row.update(version_fields(rel,row['source_id'],source.get('historical_source_sha256',sha),sha))
    if not unfinished and not issues:validate_rows(rows,TOTAL)
    report={'created_utc':utc(),'status':'ready_for_full_hash_verification' if not unfinished and not issues else 'blocked','completion_claim':False,
        'scope_total':TOTAL,'scope_unique_paths':len(accounted),'scope_missing_paths':0,'scope_extra_paths':0,'required_reviews_remaining':len(unfinished),
        'binding_issue_count':len(issues),'binding_issues':issues,'unfinished_examples':unfinished[:20],'runtime_notes':runtime_notes,
        'governing_completed_prior':dict(collections.Counter(r['status'] for r in rows if r['relative_path'] in prior)),
        'metadata_sha256':pins,'images_decoded_or_changed':False,'source_or_output_bytes_hashed':0,
        'screened_original_count':19778,'below_total_original_count':82893,'required_review_count':REVIEW,'historical_review_count':66077,'extra_current_prior_reviews':2,'approved_prior_overlay_count':7}
    return rows,report

def complete_catalog():
    from common import require_activation
    require_activation()
    rows,preflight=final_plan();require(preflight['status']=='ready_for_full_hash_verification','Final Non-People dispositions remain unfinished or have governing binding issues')
    catalog,proof,sha=load_complete(HERE/'final_verification','whole_original_non_people_final',rows,TOTAL)
    require(proof['metadata_sha256']==preflight['metadata_sha256'],'Current governing metadata differs from final byte-proof plan')
    return catalog,proof,sha

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');parser.add_argument('--resume-pass');parser.add_argument('--chunk-size',type=int,default=5);args=parser.parse_args()
    if args.verify:
        from active_attestation import activation_approval_context,require_active_attested
        activation_approval_context()
        root=HERE/'final_verification'
        with begin_pass(root,args.resume_pass) as admission:
            require_active_attested()
            rows,report=final_plan();atomic_json(HERE/'final_preflight.json',report)
            require(report['status']=='ready_for_full_hash_verification','Required reviews or governing deliveries remain unresolved')
            proof=run_pass(rows,report['metadata_sha256'],root,'whole_original_non_people_final',TOTAL,
                           args.resume_pass,args.chunk_size,metadata_guard=verify_generation_metadata,admission=admission)
        print(json.dumps({k:proof[k] for k in ('status','completion_claim','scope_total','originals_byte_checked_this_invocation','current_delivery_rows_checked_this_invocation','historical_input_receipts_bound','failed_file_records')}))
    else:
        _,report=final_plan();atomic_json(HERE/'final_preflight.json',report)
        print(json.dumps({k:report[k] for k in ('status','completion_claim','scope_total','required_reviews_remaining','binding_issue_count','governing_completed_prior')}))
if __name__=='__main__':main()
