#!/usr/bin/env python3
"""Isolated subprocess bridge to proven governing-lineage helpers.
Never import this module into the runtime process: its legacy helpers use their own common.
No image bytes are decoded or read by this metadata bridge.
"""
import argparse,collections,hashlib,importlib.util,json,sys
from pathlib import Path
PARENT=Path(__file__).resolve().parent.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def batch_exact(meta,root,batch_id):
    batch=root/'batches'/batch_id;m=meta.doc(batch/'manifest.json');runs=meta.doc(batch/'selected_run_state.json');dec=meta.doc(batch/'approved_decisions.json');reviews=meta.doc(batch/'independent_output_review.json')
    def unique(rows,key):
        out={r[key]:r for r in rows};need(len(out)==len(rows),'Legacy duplicate identity');return out
    versions=unique([v for g in m['groups'] for v in g['versions']],'batch_id');run=unique(runs['images'],'id');decisions=unique(dec['decisions'],'id');review=unique(reviews['images'],'id')
    need(set(versions)==set(run)==set(decisions),'Legacy source/run/decision sets differ')
    changed={i for i,r in run.items() if r['status']=='changed'};need(set(review)==changed,'Legacy independent review does not cover every changed output')
    for ident in changed:
        q=review[ident];need(q['reviewer']!=decisions[ident]['reviewer'] and q['actually_viewed'] is True and q['full_and_allregions_checked'] is True,'Legacy independent review coverage/identity differs')
        need(q['source_sha256']==versions[ident]['source_sha256'] and q['output_sha256']==run[ident]['output_sha256'],'Legacy review SHA differs')

def original_prior(wanted):
    sys.path.insert(0,str(PARENT));v=load('_governing_people_verifier',PARENT/'verify_all_people_completion.py')
    meta=v.Metadata();root=v.ORIGINAL;current,info=v.load_cohort(root,set(wanted));inventory=meta.doc(root/'inventory.json',info['inventory_sha256']);byid={r['production_source_id']:r for r in inventory['images']}
    brief={sid:{**r,**{k:byid[sid].get(k) for k in ('production_source_id','production_batch_id','final_delivery','prior_work','governing_repair')}} for sid,r in current.items()}
    for line in meta.blob(root/'ledger.jsonl',info['ledger_sha256']).splitlines():
        event=json.loads(line);sid=event.get('production_source_id')
        if sid not in brief:continue
        if event.get('status_to'):
            brief[sid]['status']=event['status_to'];brief[sid]['last_event']={k:event.get(k) for k in ('event','event_id','proof_sha256','batch_id','source_reviewed','output_reviewed','utc')}
        if event.get('delivery'):brief[sid]['final_delivery']=event['delivery']
    need({r['relative_path'] for r in brief.values()}==set(wanted),'Old-topic exact source set differs')
    overrides=v.governing_overrides(meta);cache={};rows=[];issues=[];validated_batches=set()
    for row in brief.values():
        row['cohort']=str(root);rel=row['relative_path'];need(row['source_sha256']==wanted[rel],'Old-topic source differs from original CSV')
        try:
            governing=None
            if row['status']=='below_eligibility_unprocessed':
                need(row.get('simple_eligible') is False,'Legacy below-threshold ambiguity');delivery={'delivery':'original','path':row['source'],'sha256':row['source_sha256']}
            elif row.get('production_queue_id'):
                delivery=v.queued_delivery(row,meta,cache);batch_id=row['last_event']['batch_id']
                if batch_id not in validated_batches:batch_exact(meta,root,batch_id);validated_batches.add(batch_id)
            elif row['status'] in ('completed_original','accepted_prior_cleaned','accepted_prior_repair'):
                delivery=row['final_delivery'];governing=v.prior_delivery(row,meta)
            else:raise ValueError('Unfinished old-topic source: '+row['status'])
            override=overrides.get(row['source'])
            if override:need(row['status']==override['required_status'],'Governing repair/original override replaced');governing=override
            accepted=v.validate_delivery_binding(row,delivery,governing)
            kind='original' if accepted['delivery']=='original' else 'repair' if row['status']=='accepted_prior_repair' else 'cleaned'
            rows.append({'relative_path':rel,'source_id':row['production_source_id'],'source':row['source'],'source_sha256':row['source_sha256'],'status':row['status'],
                'delivery_kind':kind,'delivery_path':accepted['path'],'delivery_sha256':accepted['sha256'],
                'source_bytes':byid[row['production_source_id']]['source_bytes']})
        except Exception as error:issues.append({'relative_path':rel,'error':str(error),'status':row['status']})
    for filename in ('verify_all_people_completion.py','all_people_progress.py'):meta.blob(PARENT/filename)
    meta.blob(root/'common.py')
    if (root/'code_bundle.json').is_file():meta.blob(root/'code_bundle.json')
    return {'rows':rows,'issues':issues,'metadata_sha256':meta.pins,'explicit_lineage_supersessions':meta.supersessions,'status_counts':dict(collections.Counter(r['status'] for r in rows)),
        'source_population':len(wanted),'read_only_metadata':True,'all_old_topic_rows_claimed_reviewed':False}

def completed_prior(wanted):
    sys.path.insert(0,str(PARENT));v=load('_completed_prior_verifier',PARENT/'verify_all_people_completion.py');meta=v.Metadata()
    candidates=meta.doc(PARENT/'production/non_people_scope_extension/prior_candidates.json');rows=[]
    for rel,sha in wanted.items():
        entries=[r for r in candidates.get(rel,[]) if r['source_sha256']==sha]
        need(len(entries)==1,'Completed-original prior lineage missing/ambiguous');entry=entries[0]
        need(entry['kind'] in ('old_pilot_development','old_pilot_validation') and entry.get('changed_pixels')==0 and entry.get('can_skip_new_damage_review') is True,'Completed original is not a proven unchanged historical identity')
        source=str(v.LIBRARY/rel);row={'relative_path':rel,'source':source,'source_sha256':sha,'cohort':str(v.ORIGINAL),'final_delivery':{'delivery':'original','path':source,'sha256':sha,'source':entry['kind'],'id':entry['id']}}
        v.prior_delivery(row,meta)
        rows.append({'relative_path':rel,'source_id':'prior_original_'+hashlib.sha256((rel+'\0'+sha).encode()).hexdigest(),'source':source,'source_sha256':sha,'status':'completed_original','delivery_kind':'original','delivery_path':source,'delivery_sha256':sha})
    meta.blob(PARENT/'verify_all_people_completion.py')
    return {'rows':rows,'issues':[],'metadata_sha256':meta.pins,'read_only_metadata':True}

def queued_completed(rows):
    sys.path.insert(0,str(PARENT));v=load('_queued_non_people_verifier',PARENT/'verify_all_people_completion.py');meta=v.Metadata();cache={};result=[];issues=[];checked=set()
    for row in rows:
        try:
            root=Path(row['cohort']).resolve();need(root==PARENT/'production_non_people','Queued Non-People row belongs to another cohort')
            item=v.queued_delivery(row,meta,cache);batch_id=row['last_event']['batch_id']
            if batch_id not in checked:batch_exact(meta,root,batch_id);checked.add(batch_id)
            accepted=v.validate_delivery_binding(row,item)
            result.append({'relative_path':row['relative_path'],'source_id':row['production_source_id'],'source':row['source'],'source_sha256':row['source_sha256'],'status':row['status'],
                'delivery_kind':'original' if accepted['delivery']=='original' else 'cleaned','delivery_path':accepted['path'],'delivery_sha256':accepted['sha256']})
        except Exception as error:issues.append({'relative_path':row['relative_path'],'error':str(error)})
    meta.blob(PARENT/'verify_all_people_completion.py')
    return {'rows':result,'issues':issues,'metadata_sha256':meta.pins,'read_only_metadata':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('original_prior','completed_prior','queued_completed'),required=True);args=parser.parse_args()
    handlers={'original_prior':original_prior,'completed_prior':completed_prior,'queued_completed':queued_completed}
    result=handlers[args.mode](json.load(sys.stdin));print(json.dumps(result,separators=(',',':')))
