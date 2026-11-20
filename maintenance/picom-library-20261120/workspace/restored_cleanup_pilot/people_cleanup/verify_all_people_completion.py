#!/usr/bin/env python3
"""Final ORIGINAL-People byte verifier. Default is METADATA-ONLY preflight.

--verify refuses unfinished reviews, then rereads every original and delivery.
No images are decoded, edited, copied, deleted, or written to Library. Resume
preserves prior evidence but always rereads bytes in the current invocation.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import collections
import contextlib
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/'production'
REMAINING=HERE/'production_remaining_people'
LIBRARY=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
OUT=HERE/'final_people_verification'
LEGACY_BATCH002_CLOSEOUT_SHA256='96e4d955e54e600d1703f2544df29e8ab253e5d29f45248a442b8decebfb235a'
FROZEN_REMAINING_SHA256={
    'inventory.json':'dff27f7a7f6cf175b40e1da301406dc5ebfe6ae348135da27e6f7553d86bbe0b',
    'queue.json':'75cd1f1410fcd1de7b507cccb0447e2e1a59dce3232118e6f2f11024ef640e72',
    'code_bundle.json':'c55a38c837eb6fe238cec1322363e28a737414167e84cc1542a37405c025168d',
}
sys.path.insert(0,str(ORIGINAL))
from common import image_worker
from all_people_progress import collection_scope,load_cohort


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def verify_bytes(path,expected):
    """Always read current bytes, including when size/mtime or old SHA match."""
    path=Path(path);before=path.stat();h=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(512*1024),b''):h.update(block);size+=len(block)
    after=path.stat();stable=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    return {'path':str(path),'expected_sha256':expected,'actual_sha256':h.hexdigest(),'bytes':size,
        'stable_during_read':stable,'matches':stable and h.hexdigest()==expected,'verified_utc':utc()}


def validate_scope(rows,wanted):
    paths=[r['relative_path'] for r in rows];ids=[r['production_source_id'] for r in rows]
    if len(paths)!=len(set(paths)) or len(ids)!=len(set(ids)):raise ValueError('Duplicate source path or ID in People scope')
    if set(paths)!=set(wanted):raise ValueError(f'Incomplete/extra People scope: missing={len(set(wanted)-set(paths))}, extra={len(set(paths)-set(wanted))}')


def unfinished(rows):
    issues=[]
    for row in rows:
        status=row['status'];queued=bool(row.get('production_queue_id'))
        okay=status in ('accepted','original_retained') if queued else status in ('completed_original','accepted_prior_cleaned','accepted_prior_repair')
        if not queued and status=='below_eligibility_unprocessed' and row.get('simple_eligible') is False:okay=True
        if not okay:issues.append({'relative_path':row['relative_path'],'status':status,'queued':queued})
    return issues


def validate_delivery_binding(row,delivery,governing=None):
    if not delivery:raise ValueError('Completed row lacks a governing delivery')
    source=Path(row['source']).resolve();output=Path(delivery['path']).resolve();kind=delivery['delivery'];sha=delivery['sha256']
    if delivery.get('source_sha256',row['source_sha256'])!=row['source_sha256']:raise ValueError('Delivery source SHA differs')
    if row['status'] in ('completed_original','original_retained','below_eligibility_unprocessed'):
        if kind!='original' or output!=source or sha!=row['source_sha256']:raise ValueError('Original delivery is not source-byte identity')
    elif row['status'] in ('accepted','accepted_prior_cleaned'):
        if kind!='cleaned' or output==source:raise ValueError('Accepted cleanup must preserve a separate canonical output')
    elif row['status']=='accepted_prior_repair':
        if not governing:raise ValueError('Prior repair requires its governing accepted override')
        if kind not in ('cleaned','separate_repair') or output==source:raise ValueError('Prior repair was replaced by its defective original')
    else:raise ValueError('Delivery validation attempted on unfinished status')
    if governing:
        if Path(governing.get('source_path',row['source'])).resolve()!=source or governing.get('source_sha256',row['source_sha256'])!=row['source_sha256']:raise ValueError('Governing repair source binding differs')
        if output!=Path(governing['path']).resolve() or sha!=governing['sha256']:raise ValueError('Delivery differs from governing accepted repair')
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('Invalid delivery SHA')
    return {'delivery':kind,'path':str(output),'sha256':sha}


def validate_legacy_closeout(closeout,actual_sha,delivery,delivery_sha,current_review_sha):
    """This exact later closeout was independently authorized by root."""
    if actual_sha!=LEGACY_BATCH002_CLOSEOUT_SHA256:raise ValueError('Legacy closeout is not the exact root-authorized SHA')
    seals=closeout.get('sealed_artifact_sha256',{})
    if closeout.get('status')!='complete' or closeout.get('batch_id')!=delivery['batch_id']:raise ValueError('Legacy review aggregate mismatch lacks an explicit completed closeout')
    if datetime.datetime.fromisoformat(closeout['completed_utc'])<=datetime.datetime.fromisoformat(delivery['sealed_utc']):raise ValueError('Legacy closeout does not supersede seal time')
    if seals.get('accepted_delivery.json')!=delivery_sha or seals.get('independent_output_review/independent_output_review.json')!=current_review_sha:raise ValueError('Closeout does not pin unchanged delivery and current review together')
    if closeout['counts']['accepted_improvements']!=delivery['cleaned'] or closeout['counts']['originals_retained_for_delivery']!=delivery['originals_retained']:raise ValueError('Closeout delivery totals differ')
    return seals


def validate_prior_review_row(review,source_sha,output_sha):
    if review['source_sha256']!=source_sha or review['output_sha256']!=output_sha or review.get('decision')!='accept_lossless_output' or review.get('review_status')!='clear':raise ValueError('Prior batch002 accepted output review is mismatched or unsafe')


class Metadata:
    def __init__(self):self.pins={};self.docs={};self.supersessions={}
    def blob(self,path,expected=None):
        path=Path(path).resolve();raw=path.read_bytes();actual=digest(raw)
        if expected and actual!=expected:raise ValueError('Metadata SHA mismatch: '+str(path))
        if str(path) in self.pins and self.pins[str(path)]!=actual:raise ValueError('Metadata changed during preflight: '+str(path))
        self.pins[str(path)]=actual
        return raw
    def doc(self,path,expected=None):
        path=Path(path).resolve()
        if str(path) not in self.docs:self.docs[str(path)]=json.loads(self.blob(path,expected))
        elif expected and self.pins[str(path)]!=expected:raise ValueError('Cached metadata pin mismatch: '+str(path))
        return self.docs[str(path)]
    def match(self,path,rows,key,value):
        found=[r for r in rows if r.get(key)==value]
        if len(found)!=1:raise ValueError('Missing/duplicate metadata binding: '+str(path)+' '+str(value))
        return found[0]


def validate_remaining_frozen_pins(actual):
    for name,expected in FROZEN_REMAINING_SHA256.items():
        if actual.get(name)!=expected:raise ValueError('Frozen remaining People pin differs: '+name)


def validate_historical_source_binding(row,item,review):
    if item.get('source_sha256')!=row['source_sha256'] or review.get('source_sha256')!=row['source_sha256']:raise ValueError('Historical exact-output review source SHA differs from frozen inventory')
    for document,field in ((item,'source_path'),(review,'source')):
        if document.get(field) and Path(document[field]).resolve()!=Path(row['source']).resolve():raise ValueError('Historical exact-output review source path differs from frozen inventory')


def validate_batch003_review_row(review,source_sha,output_sha):
    if review.get('source_sha256')!=source_sha or review.get('output_sha256')!=output_sha:raise ValueError('Prior batch003 accepted review source/output SHA differs')
    if review.get('foreground_safety')!='clear' or review.get('review_status')!='clear' or review.get('worthwhile')!='yes':raise ValueError('Prior batch003 accepted review is not clear-safe and approved worthwhile')


def load_rows(wanted,meta):
    rows=[];lineage=[]
    for root in (ORIGINAL,REMAINING):
        current,info=load_cohort(root,wanted)
        if root==REMAINING:
            validate_remaining_frozen_pins({'inventory.json':info['inventory_sha256'],'queue.json':info['queue_sha256'],
                'code_bundle.json':digest(meta.blob(root/'code_bundle.json',FROZEN_REMAINING_SHA256['code_bundle.json']))})
        inv=meta.doc(root/'inventory.json',FROZEN_REMAINING_SHA256['inventory.json'] if root==REMAINING else info['inventory_sha256'])
        byid={r['production_source_id']:r for r in inv['images']}
        brief={sid:{**current[sid],**{k:byid[sid].get(k) for k in ('production_source_id','production_batch_id','final_delivery','prior_work','governing_repair')}} for sid in current}
        raw=meta.blob(root/'ledger.jsonl',info['ledger_sha256'])
        for line in raw.splitlines():
            event=json.loads(line);sid=event.get('production_source_id')
            if sid not in brief:continue
            if event.get('status_to'):
                brief[sid]['status']=event['status_to']
                brief[sid]['last_event']={k:event.get(k) for k in ('event','event_id','proof_sha256','batch_id','source_reviewed','output_reviewed','utc')}
            if event.get('delivery'):brief[sid]['final_delivery']=event['delivery']
        for row in brief.values():row['cohort']=str(root);rows.append(row)
        for name in ('queue.json','batch_index.json','protocol.json','acceptance_policy.json','summary.json','import_audit.json'):
            meta.blob(root/name,FROZEN_REMAINING_SHA256.get(name) if root==REMAINING else None)
        if (root/'code_bundle.json').is_file():meta.blob(root/'code_bundle.json')
        lineage.append({'cohort':str(root),**info})
    validate_scope(rows,wanted)
    if len(rows)!=57073:raise ValueError('Expected exactly 57,073 original People')
    return rows,lineage


def same_delivery(a,b):
    return Path(a['path']).resolve()==Path(b['path']).resolve() and a['sha256']==b['sha256'] and a['delivery']==b['delivery']


def queued_delivery(row,meta,cache):
    root=Path(row['cohort']);event=row.get('last_event',{});batch_id=event.get('batch_id')
    if event.get('event')!='sealed_batch_delivery' or not batch_id or Path(batch_id).name!=batch_id:raise ValueError('Queued completion lacks a sealed delivery event')
    batch=root/'batches'/batch_id
    if str(batch) not in cache:
        manifest=meta.doc(batch/'manifest.json');delivery=meta.doc(batch/'accepted_delivery.json')
        decisions=meta.doc(batch/'approved_decisions.json');audit=meta.doc(batch/'mechanical_audit.json');reviews=meta.doc(batch/'independent_output_review.json');runs=meta.doc(batch/'selected_run_state.json')
        for key,name in [('manifest_sha256','manifest.json'),('decisions_sha256','approved_decisions.json'),('mechanical_audit_sha256','mechanical_audit.json'),('output_review_sha256','independent_output_review.json')]:
            if delivery[key]!=meta.pins[str((batch/name).resolve())]:raise ValueError('Sealed delivery lineage differs: '+str(batch))
        if audit['errors'] or runs['status']!='complete':raise ValueError('Incomplete/failed batch audit')
        if decisions['root_approval']['approved'] is not True:raise ValueError('Unapproved decisions cannot prove completion')
        if audit['auditor_sha256']!=digest(meta.blob(root/'qa.py')):raise ValueError('Mechanical auditor code binding differs')
        if delivery.get('acceptance_policy_sha256') and delivery['acceptance_policy_sha256']!=digest(meta.blob(root/'acceptance_policy.json')):raise ValueError('Acceptance policy binding differs')
        for key,name in [('manifest_sha256','manifest.json'),('decisions_sha256','approved_decisions.json'),('run_state_sha256','selected_run_state.json')]:
            if audit[key]!=meta.pins[str((batch/name).resolve())]:raise ValueError('Mechanical audit lineage differs')
        protocol=meta.doc(root/'protocol.json')
        if audit['protocol_sha256']!=meta.pins[str((root/'protocol.json').resolve())] or audit['cleaner_sha256']!=protocol['engine']['sha256']:raise ValueError('Protocol/cleaner binding differs')
        meta.blob(protocol['engine']['path'],protocol['engine']['sha256'])
        proofs={}
        for group in manifest['groups']:
            path=batch/'source_reviews'/(group['group_id']+'.json')
            if path.exists():proofs[path.name]=digest(meta.blob(path))
            elif any(v.get('review_required',True) for v in group['versions']):raise ValueError('Required source checkpoint absent')
        if decisions['source_checkpoint_sha256']!=proofs:raise ValueError('Source checkpoint proof differs from compilation')
        cache[str(batch)]=(manifest,delivery,{r['id']:r for r in reviews['images']},meta.pins[str((batch/'accepted_delivery.json').resolve())])
    manifest,document,reviews,current_sha=cache[str(batch)]
    item=meta.match(batch/'accepted_delivery.json',document['images'],'id',row['production_queue_id'])
    version=meta.match(batch/'manifest.json',[v for g in manifest['groups'] for v in g['versions']],'production_source_id',row['production_source_id'])
    if not version.get('review_required',True) or version['source_sha256']!=row['source_sha256'] or version['batch_id']!=row['production_queue_id']:raise ValueError('Queued delivery is not the required source subject')
    if item['source_sha256']!=row['source_sha256'] or Path(item['source_path']).resolve()!=Path(row['source']).resolve() or not same_delivery(item,row['final_delivery']):raise ValueError('Ledger/sealed delivery binding differs')
    if event['proof_sha256']!=current_sha:
        old=meta.doc(batch/'delivery_history'/(event['proof_sha256']+'.json'),event['proof_sha256'])
        if not same_delivery(meta.match('history',old['images'],'id',item['id']),item):raise ValueError('Archived event delivery differs')
    if item['delivery']=='cleaned':
        if Path(item['path']).resolve()!=(batch/'accepted_outputs'/item['id']/'after.webp').resolve():raise ValueError('Queued output is not its canonical accepted delivery')
        review=reviews[item['id']]
        if not (review['actually_viewed'] and review['full_and_allregions_checked'] and review['safety']=='clear' and review['worthwhile'] in ('clear','modest') and review['source_sha256']==row['source_sha256'] and review['output_sha256']==item['sha256']):raise ValueError('Accepted output lacks bound independent clear-safe useful review')
    return item


def prior_delivery(row,meta):
    delivery=row['final_delivery'];source=delivery.get('source');root=Path(row['cohort']);event=row.get('last_event',{})
    if event.get('event')=='historical_exact_output_review':
        doc=meta.doc(root/'historical_output_review/accepted_delivery.json')
        reviews=meta.doc(root/'historical_output_review/reviews.json',doc['review_sha256'])
        meta.doc(root/'historical_resolution.json',doc['resolution_sha256'])
        item=meta.match('historical delivery',doc['images'],'production_source_id',row['production_source_id'])
        review=meta.match('historical review',reviews['images'],'production_source_id',row['production_source_id'])
        validate_historical_source_binding(row,item,review)
        if not same_delivery(item,delivery) or not review['actually_viewed'] or not review['full_and_allregions_checked']:raise ValueError('Historical exact-review delivery binding differs')
        if item['delivery']=='cleaned' and (review['safety']!='clear' or review['output_sha256']!=item['sha256']):raise ValueError('Historical output safety/hash differs')
    elif event.get('event')=='historical_delivery_verified':
        resolution=meta.doc(root/'historical_resolution.json',event['proof_sha256'])
        item=meta.match('historical resolution',resolution['records'],'production_source_id',row['production_source_id'])
        if item['source_sha256']!=row['source_sha256']:raise ValueError('Historical resolution source differs')
        if delivery['delivery']=='cleaned' and item.get('candidate_lossless_current_sha256')!=delivery['sha256']:raise ValueError('Historical accepted output differs from resolution')
    elif source in ('batch002','batch003'):
        document=meta.doc(HERE/source/'accepted_delivery.json')
        item=meta.match('prior delivery',document['images'],'id',delivery['id'])
        if item['source_sha256']!=row['source_sha256'] or not same_delivery(item,delivery):raise ValueError('Prior accepted delivery binding differs')
        folder=HERE/source
        if source=='batch002':
            meta.doc(folder/'approved_decisions.json',document['source_review_sha256'])
            meta.doc(folder/'mechanical_audit.json',document['mechanical_audit_sha256'])
            reviews=meta.doc(folder/'independent_output_review/independent_output_review.json')
            if item['delivery']=='cleaned':
                review_relative='independent_output_review/independent_output_review.json'
                review_path=str((folder/review_relative).resolve());current_review_sha=meta.pins[review_path]
                if current_review_sha!=document['output_review_sha256'] and review_path not in meta.supersessions:
                    closeout=meta.doc(folder/'completion.json',LEGACY_BATCH002_CLOSEOUT_SHA256)
                    seals=validate_legacy_closeout(closeout,meta.pins[str((folder/'completion.json').resolve())],document,
                        meta.pins[str((folder/'accepted_delivery.json').resolve())],current_review_sha)
                    for relative,expected in seals.items():
                        target=(folder/relative).resolve()
                        if not target.is_relative_to(folder.resolve()) or target.suffix not in ('.json','.html','.py','.txt','.md','.cjs'):raise ValueError('Invalid metadata-only closeout artifact')
                        meta.blob(target,expected)
                    meta.supersessions[review_path]={'legacy_seal_review_sha256':document['output_review_sha256'],
                        'governing_review_sha256':current_review_sha,'governing_closeout':str(folder/'completion.json'),
                        'governing_closeout_sha256':meta.pins[str((folder/'completion.json').resolve())],
                        'root_authorized_closeout_sha256':LEGACY_BATCH002_CLOSEOUT_SHA256,
                        'affected_people_sources':[],
                        'basis':'Later completed closeout explicitly pins the unchanged accepted-delivery manifest and current review aggregate; exact accepted source/output review entries are also checked.'}
                review=meta.match('prior exact output review',reviews['images'],'id',item['id'])
                validate_prior_review_row(review,row['source_sha256'],item['sha256'])
                if review_path in meta.supersessions:meta.supersessions[review_path]['affected_people_sources'].append(row['relative_path'])
        else:
            meta.doc(folder/'execution_manifest.json',document['manifest_sha256'])
            reviews=meta.doc(folder/'independent_output_review.json',document['final_review_sha256'])
            if item['delivery']=='cleaned':
                if reviews.get('status')!='complete':raise ValueError('Prior batch003 final review is incomplete')
                review=meta.match('prior batch003 accepted review',reviews['images'],'id',item['id'])
                validate_batch003_review_row(review,row['source_sha256'],item['sha256'])
    elif source=='initial_people48':
        document=meta.doc(HERE/'ledger.json');item=meta.match('initial ledger',document['images'],'id',delivery['id'])
        if item['source_sha256']!=row['source_sha256'] or item['decision']['decision']!='unchanged' or not item['outputs']['unchanged_identity_proof'] or item['outputs']['output_sha256']!=row['source_sha256']:raise ValueError('Initial unchanged identity proof differs')
    elif source and source.startswith('old_pilot_'):
        cohort=source.removeprefix('old_pilot_');folder=HERE.parent/cohort
        results=meta.doc(folder/'results.json');checks=meta.doc(folder/'independent_verification.json')
        item=meta.match('old result',results['results'],'id',delivery['id']);check=meta.match('old identity',checks['results'],'id',delivery['id'])
        if item['source_sha256']!=row['source_sha256'] or item['changed_pixels']!=0 or check['can_skip_new_damage_review'] is not True:raise ValueError('Old pilot is not a proven unchanged identity')
    elif source=='foreground_repair_override':
        overrides=meta.doc(HERE.parent/'foreground_repairs/delivery_overrides.json')
        override=meta.match('repair override',overrides['overrides'],'id',delivery['id'])
        if Path(delivery['path']).resolve()!=Path(override['accepted_path']).resolve() or delivery['sha256']!=override['accepted_sha256']:raise ValueError('Foreground repair override was replaced')
        return {'source_path':row['source'],'source_sha256':row['source_sha256'],'path':override['accepted_path'],'sha256':override['accepted_sha256']}
    elif source=='governing_wood_comparative_repair':
        folder=ORIGINAL/'source_integrity/wood_repairs';document=meta.doc(folder/'accepted_delivery.json')
        for key,name in [('visual_review_sha256','independent_review.json'),('independent_dirtier_check_sha256','independent_dirtier_check.json'),('rendering_verification_sha256','rendering_verification.json')]:meta.doc(folder/name,document[key])
        item=meta.match('governing Wood repair',document['images'],'source_path',row['source'])
        for path,expected in row.get('governing_repair',{}).get('proof_sha256',{}).items():meta.doc(path,expected)
        return item
    else:raise ValueError('Unknown/unbound completed prior delivery: '+str(source))
    return None


def governing_overrides(meta):
    governing={}
    wood=meta.doc(ORIGINAL/'source_integrity/wood_repairs/accepted_delivery.json')
    for key,name in [('visual_review_sha256','independent_review.json'),('independent_dirtier_check_sha256','independent_dirtier_check.json'),('rendering_verification_sha256','rendering_verification.json')]:
        meta.doc(ORIGINAL/'source_integrity/wood_repairs'/name,wood[key])
    if len(wood['images'])!=7:raise ValueError('Seven governing Wood repairs expected')
    for item in wood['images']:governing[item['source_path']]={**item,'required_status':'accepted_prior_repair'}
    overrides=meta.doc(HERE.parent/'foreground_repairs/delivery_overrides.json')
    validation=meta.doc(HERE.parent/'validation/results.json')
    for override in overrides['overrides']:
        item=meta.match('validation repair source',validation['results'],'id',override['id'])
        original=override['status']=='original_retained'
        governing[item['source']]={'source_path':item['source'],'source_sha256':item['source_sha256'],
            'path':override['accepted_path'],'sha256':override['accepted_sha256'],
            'required_status':'completed_original' if original else 'accepted_prior_repair'}
    return governing


def build_plan():
    wanted,scope=collection_scope();meta=Metadata();rows,lineage=load_rows(wanted,meta)
    if meta.pins[str((ORIGINAL/'inventory.json').resolve())]!=scope['frozen_original_inventory_sha256']:raise ValueError('Original frozen inventory pin differs')
    meta.blob(scope['snapshot'],scope['snapshot_sha256'])
    for path,expected in scope['manifest_csv_sha256'].items():meta.blob(path,expected)
    pending=unfinished(rows);issues=[];cache={};overrides=governing_overrides(meta)
    for row in rows:
        if row['status'] in ('accepted','original_retained','completed_original','accepted_prior_cleaned','accepted_prior_repair') or (row['status']=='below_eligibility_unprocessed' and not row.get('simple_eligible')):
            try:
                if Path(row['source']).resolve()!=LIBRARY/row['relative_path']:raise ValueError('Source path differs from exact Library scope')
                governing=None
                if row['status']=='below_eligibility_unprocessed':delivery={'delivery':'original','path':row['source'],'sha256':row['source_sha256']}
                elif row.get('production_queue_id'):delivery=queued_delivery(row,meta,cache)
                else:delivery=row['final_delivery'];governing=prior_delivery(row,meta)
                override=overrides.get(row['source'])
                if override:
                    if row['status']!=override['required_status']:raise ValueError('Governing prior repair/original override status was replaced')
                    governing=override
                row['verified_delivery']=validate_delivery_binding(row,delivery,governing)
            except Exception as exc:issues.append({'relative_path':row['relative_path'],'error':str(exc)})
    if len(set(overrides).intersection(r['source'] for r in rows))!=len(overrides):raise ValueError('A governing prior override is absent from original People scope')
    counts=dict(collections.Counter(r['status'] for r in rows))
    report={'generated_utc':utc(),'mode':'metadata_only_preflight','completion_claim':False,'status':'ready_for_full_hash_verification' if not pending and not issues else 'blocked',
        'scope_total':57073,'scope_unique_paths':len(rows),'scope_missing_paths':0,'scope_extra_paths':0,
        'required_reviews_remaining':len(pending),'unfinished_status_counts':dict(collections.Counter(r['status'] for r in pending)),
        'unfinished_examples':pending[:25],'binding_issue_count':len(issues),'binding_issues':issues,
        'governing_prior_repairs':sum(x['required_status']=='accepted_prior_repair' for x in overrides.values()),
        'governing_overrides_in_scope':len(set(overrides).intersection(r['source'] for r in rows)),
        'explicit_lineage_supersessions':meta.supersessions,
        'status_counts':counts,'scope_evidence':scope,'cohort_lineage':lineage,'metadata_sha256':meta.pins,
        'frozen_remaining_sha256':FROZEN_REMAINING_SHA256,
        'verifier_sha256':digest(Path(__file__).read_bytes()),'source_or_output_bytes_hashed':0,'images_decoded_or_changed':False,
        'completion_gate':'No required review pending, complete unique original-People scope, valid governing deliveries and current SHA verification of every original and delivered file'}
    return rows,report


def publish_final_proof(folder,proof,out_root=OUT):
    """Durably preserve this exact invocation before updating mutable pointers."""
    invocation=proof['invocation']
    if invocation in ('.','..') or Path(invocation).name!=invocation:raise ValueError('Invalid immutable proof invocation ID')
    receipts=Path(folder)/'proofs';receipts.mkdir(parents=True,exist_ok=True)
    receipt=receipts/(invocation+'.json')
    document={**proof,'immutable_proof_path':str(receipt)}
    raw=(json.dumps(document,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    if receipt.exists():
        if receipt.read_bytes()!=raw:raise ValueError('Refusing to overwrite an immutable invocation proof')
    else:
        with receipt.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    atomic(Path(folder)/'final_proof.json',document)
    atomic(Path(out_root)/'final_proof.json',document)
    atomic(Path(out_root)/'latest_status.json',{'status':document['status'],'completion_claim':document['completion_claim'],
        'pass_id':document['pass_id'],'invocation':invocation,'updated_utc':utc(),
        'proof_path':str(receipt),'proof_sha256':digest(raw)})
    return document


def run_verification(rows,preflight,args):
    if preflight['status']!='ready_for_full_hash_verification':raise ValueError('Completion refused: required reviews or delivery binding issues remain')
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'verification.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _run_verification_locked(rows,preflight,args)


def _run_verification_locked(rows,preflight,args):
    signature=digest(json.dumps({'pins':preflight['metadata_sha256'],'verifier':preflight['verifier_sha256']},sort_keys=True).encode())
    pass_id=args.resume_pass or (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    if pass_id in ('.','..') or Path(pass_id).name!=pass_id:raise ValueError('Invalid verification pass ID')
    folder=OUT/'passes'/pass_id
    if args.resume_pass:
        saved=json.loads((folder/'plan.json').read_bytes())
        if saved['signature_sha256']!=signature:raise ValueError('Resume lineage/code changed; preserve old pass and start a new one')
    else:
        folder.mkdir(parents=True,exist_ok=False);atomic(folder/'plan.json',{'signature_sha256':signature,**preflight})
    invocation=uuid.uuid4().hex;checkpoint=folder/('byte_checks_'+invocation+'.jsonl');failed=0;checked=0;started=utc()
    # A new or resumed invocation invalidates the old success pointer immediately.
    # Immutable earlier proofs remain available, but cannot authorize delivery while
    # this current byte check is running or interrupted.
    atomic(OUT/'latest_status.json',{'status':'running','completion_claim':False,
        'pass_id':pass_id,'invocation':invocation,'started_utc':started,'scope_total':57073})
    ordered=sorted(rows,key=lambda r:r['relative_path'])
    with checkpoint.open('a',encoding='utf-8') as stream:
        for start in range(0,len(rows),args.chunk_size):
            with image_worker():
                for row in ordered[start:start+args.chunk_size]:
                    record={'invocation':invocation,'relative_path':row['relative_path'],'source_id':row['production_source_id'],'status':row['status']}
                    try:
                        source=verify_bytes(row['source'],row['source_sha256']);delivery=row['verified_delivery']
                        output=source if Path(delivery['path']).resolve()==Path(row['source']).resolve() else verify_bytes(delivery['path'],delivery['sha256'])
                        record.update(source=source,delivery=output,passed=source['matches'] and output['matches'])
                    except Exception as exc:record.update(passed=False,error_type=type(exc).__name__,error=str(exc))
                    checked+=1;failed+=not record['passed'];stream.write(json.dumps(record,separators=(',',':'))+'\n')
                stream.flush();os.fsync(stream.fileno())
            atomic(folder/'progress.json',{'status':'running','completion_claim':False,'invocation':invocation,'checked_this_invocation':checked,'scope_total':57073,'failed':failed,'updated_utc':utc()})
            time.sleep(.1)
    changed=[]
    with image_worker():
        for path,expected in preflight['metadata_sha256'].items():
            try:
                result=verify_bytes(path,expected)
                if not result['matches']:changed.append(result)
            except Exception as exc:changed.append({'path':path,'error_type':type(exc).__name__,'error':str(exc)})
    proof={'status':'complete' if not failed and not changed and checked==57073 else 'failed','completion_claim':not failed and not changed and checked==57073,
        'pass_id':pass_id,'invocation':invocation,'started_utc':started,'completed_utc':utc(),'scope_total':57073,
        'originals_byte_checked_this_invocation':checked,'failed_file_records':failed,'changed_lineage':changed,
        'checkpoint_path':str(checkpoint),'checkpoint_sha256':verify_bytes(checkpoint,'')['actual_sha256'],
        'signature_sha256':signature,'plan_sha256':verify_bytes(folder/'plan.json','')['actual_sha256'],
        'metadata_sha256':preflight['metadata_sha256'],'status_counts':preflight['status_counts'],
        'explicit_lineage_supersessions':preflight['explicit_lineage_supersessions'],
        'resume_policy':'Every invocation rereads all source/output bytes; no stat-only or cached-SHA reuse. Earlier mismatches remain in their original per-invocation checkpoints, including interrupted/partial files.',
        'earlier_evidence_files':[p.name for p in sorted(folder.glob('byte_checks_*.jsonl')) if p!=checkpoint],
        'images_decoded_or_changed':False,'library_written':False}
    proof=publish_final_proof(folder,proof)
    return proof


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');p.add_argument('--resume-pass');p.add_argument('--chunk-size',type=int,default=50);args=p.parse_args()
    if args.resume_pass and not args.verify:p.error('--resume-pass requires --verify')
    if not 1<=args.chunk_size<=50:p.error('--chunk-size must be 1..50')
    OUT.mkdir(exist_ok=True)
    with (OUT/'verifier.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rows,preflight=build_plan()
        previous=OUT/'preflight.json'
        if previous.is_file():
            raw=previous.read_bytes();archive=OUT/'preflight_history'/(digest(raw)+'.json');archive.parent.mkdir(exist_ok=True)
            if not archive.exists():
                with archive.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        atomic(previous,preflight)
        atomic(OUT/'latest_status.json',{'status':preflight['status'],'completion_claim':False,'updated_utc':utc(),'preflight_path':str(previous),'source_or_output_bytes_hashed':0})
        if args.verify:
            proof=run_verification(rows,preflight,args)
            result={k:proof[k] for k in ('status','completion_claim','pass_id','scope_total','originals_byte_checked_this_invocation','failed_file_records')}
            result['proof_path']=proof['immutable_proof_path']
        else:result={k:preflight[k] for k in ('status','completion_claim','scope_total','required_reviews_remaining','binding_issue_count','source_or_output_bytes_hashed')}
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
