#!/usr/bin/env python3
"""Build isolated cohort metadata in memory. This phase permits dry-run only."""
import argparse,collections,json,re
from pathlib import Path
from common import HERE,LIBRARY,read,digest,require,atomic_json,utc,require_activation
from scope_metadata import PREP,jsonl,reconstruct
from source_versions import BATCH,DECISION,PENDING,REVIEW,SUBJECTS,VERSION_KEYS,logical_id,queue_group
from contracts import unique,validate_versions

def build_runtime():
    original,pending,prior,overlay=reconstruct();protocol=read(HERE/'protocol.json');contract=read(HERE/'scope_contract.json')
    styles=contract['style_catalogue']['style_ids']
    for row in read(HERE.parent/'production/inventory.json')['images']:require(styles[row['style']]==row['style_id'],'Style catalogue ID conflicts with frozen pipeline')
    require(all(rel.split('/')[0] in styles for rel in pending),'Unknown source style catalogue entry')
    sourceids={rel:logical_id(rel,r) for rel,r in {**pending,**prior}.items()}
    images=[];inventory={}
    for rel,row in pending.items():
        review=row['partition']=='review_required'
        item={'production_source_id':sourceids[rel],'source':row['source_path'],'relative_path':rel,'source_sha256':row['source_sha256'],'source_bytes':row['source_bytes'],
            'dimensions':row['dimensions'],'style':rel.split('/')[0],'style_id':styles[rel.split('/')[0]],'group_key':row['group_key'],
            'people_subfolder':'/'.join(Path(rel).parts[1:-1]),'normalized_stem':row['group_key'].split('::',1)[1],
            'simple_eligible':row['candidate'],'strict_white_core_pixel_count_at_512':row['strict_white_total'],'partition':row['partition'],
            'status':'eligible_unprocessed' if review else row['partition']+'_pending_final_byte_proof','final_delivery':None,
            'prior_resolution':overlay.get(rel),'historical_trial_imported':False,'source_reviewed':False,'output_reviewed':False,
            'production_queue_id':row.get('proposed_subject_id'),'production_group_id':row.get('proposed_group_id'),'production_batch_id':row.get('proposed_batch_id')}
        if rel in SUBJECTS:
            item.update({k:row[k] for k in (*VERSION_KEYS,'current_strict_metrics')})
            for key in ('historical_topic_source_id','historical_topic_queue_id','historical_topic_batch_id'):
                if key in row:item[key]=row[key]
        images.append(item);inventory[rel]=item
    def version(rel,ident,role):
        row=pending.get(rel,prior.get(rel));require(row is not None,'Queue source outside preparation')
        return {**{k:row[k] for k in VERSION_KEYS if k in row},'batch_id':ident,'production_source_id':sourceids[rel],'source':str(LIBRARY/rel),'source_sha256':row['source_sha256'],'source_bytes':row['source_bytes'],
            'dimensions':row['dimensions'],'style':rel.split('/')[0],'style_id':styles[rel.split('/')[0]],'role':role,'review_required':role=='subject',
            'simple_eligible':row['candidate'],'strict_white_core_pixel_count_at_512':row['strict_white_total'],'components_ge64_at_512':None}
    groups=[];subjects=set();batchgroups=collections.defaultdict(list);batchrefs=collections.Counter()
    decision=read(DECISION)
    for historical_group in jsonl(PREP/'proposed_queue.jsonl'):
        row=queue_group(historical_group,decision)
        require(re.fullmatch(r'npg\d{5}',row['proposed_group_id']) and re.fullmatch(r'batchN\d{3,}',row['proposed_batch_id']),'Wrong proposed group/batch namespace')
        require(len(row['subject_ids'])==len(row['subject_relative_paths']),'Subject/path alignment differs');versions=[]
        for ident,rel in zip(row['subject_ids'],row['subject_relative_paths']):
            require(rel in pending and rel not in subjects and inventory[rel]['production_queue_id']==ident,'Unexpected/duplicate subject ID/path');subjects.add(rel)
            require(inventory[rel]['group_key']==row['group_key'] and inventory[rel]['production_group_id']==row['proposed_group_id'] and inventory[rel]['production_batch_id']==row['proposed_batch_id'],'Subject assignment differs')
            versions.append(version(rel,ident,'subject'))
        refpaths=set()
        for ref in row['context_references']:
            rel=ref['relative_path'];require(rel not in SUBJECTS,'Revised version cannot inherit a historical context reference');require(rel not in refpaths and rel not in row['subject_relative_paths'],'Duplicate/overlapping reference');refpaths.add(rel)
            require(rel in original and original[rel]['source_sha256']==ref['source_sha256'] and original[rel]['dimensions']==ref['dimensions']==[512,512],'Reference source SHA/dimensions differ')
            require(pending.get(rel,prior.get(rel))['group_key']==row['group_key'],'Cross-concept reference')
            require(not pending.get(rel,prior.get(rel)).get('lineage_hold'),'Historical trial reference forbidden')
            versions.append(version(rel,'r_'+sourceids[rel][:20],'reference'))
        key=row['group_key'];group={'group_id':row['proposed_group_id'],'group_key':key,'people_subfolder':key.split('::',1)[0],'normalized_stem':key.split('::',1)[1],
            'batch_id':row['proposed_batch_id'],'versions':versions,'candidate_count':len(row['subject_ids'])}
        groups.append(group);batchgroups[group['batch_id']].append(group['group_id']);batchrefs[group['batch_id']]+=len(refpaths)
    expected={rel for rel,r in pending.items() if r['partition']=='review_required'};require(subjects==expected and len(subjects)==REVIEW,'Review queue exact subject set differs')
    # Per-batch reference IDs can recur across batches; within each batch they must be unique.
    groups_by_id=unique(groups,'group_id')
    for batch_id,gids in batchgroups.items():
        selected=[groups_by_id[gid] for gid in gids];validate_versions(selected,original)
        n=sum(g['candidate_count'] for g in selected);require(n<=150 and batchrefs[batch_id]<=50,'Batch source/reference ceiling exceeded')
        if batch_id==BATCH:require(n==137 and len(gids)==135 and not batchrefs[batch_id],'Revised mum batch differs from approved integration')
    require(BATCH in batchgroups and len(groups)==26194 and len(batchgroups)==486,'Historical group/batch counts changed')
    queue={'schema_version':1,'created_utc':contract['created_utc'],'cohort':'production_non_people','rule_version':'people-white-core-v1',
        'protocol_sha256':digest(HERE/'protocol.json'),'scope_snapshot_sha256':digest(HERE/'scope_contract.json'),'code_bundle_sha256':digest(HERE/'code_bundle.json'),
        'source_census_sha256':digest(HERE.parent/'production/non_people_scope_extension/census_checkpoint.jsonl'),
        'grouping_rule':'Exact original Non-People topic/subfolder plus normalized stem; original CSV provenance only; no mask transfer.',
        'batch_target_subjects':135,'subject_count':REVIEW,'group_count':len(groups),'batch_count':len(batchgroups),'groups':groups,'batches':[{'batch_id':b,'group_ids':gids} for b,gids in batchgroups.items()]}
    return {'inventory':{'cohort':'production_non_people','images':images},'queue':queue,'summary':{'queue_subject_total':REVIEW,'pending_originals':PENDING,'historical_queue_subject_total':66077,'extra_current_prior_reviews':2,'historical_pending_originals':168748,'historical_prior_paths':1296,'screened_originals':19778,'below_total_originals':82893,
        'historical_fresh_review_resolutions':5,'historical_original_resolutions':2,'groups':len(groups),'batches':len(batchgroups),'runtime_activated':False},
        'scope_proof':{'exact_original_paths':len(original),'exact_pending_paths':len(pending),'exact_prior_paths':len(prior),'all_source_sets_reconciled':True}}

def initialize_runtime(result):
    """Guarded commit path, deliberately unreachable until the reviewed final phase exists."""
    require_activation()
    names=('inventory.json','queue.json','batch_index.json','summary.json','import_audit.json','ledger.jsonl','state.json','progress.json')
    require(all(not (HERE/name).exists() for name in names) and not (HERE/'batches').exists(),'Runtime metadata already exists; never rebuild frozen IDs or progress')
    # Prepare all serialization before the first runtime mutation. An incomplete initialization
    # fails closed on rerun and requires an explicit reviewed recovery, never an ID rebuild.
    import hashlib,os
    outputs={'inventory.json':result['inventory'],'queue.json':result['queue'],'summary.json':result['summary'],'import_audit.json':{'cohort':'production_non_people','approved_prior_resolutions_sha256':digest(PREP/'approved_prior_resolutions.json'),'exact_overlay_count':7,'fresh_original_reviews_required':5,'originals_retained_below_threshold':2,'trial_outputs_imported':0,'scope_proof':result['scope_proof']}}
    queue_bytes=(json.dumps(result['queue'],indent=2,ensure_ascii=False)+'\n').encode()
    outputs['batch_index.json']={'cohort':'production_non_people','queue_sha256':hashlib.sha256(queue_bytes).hexdigest(),'batches':[]}
    initial={r['production_source_id']:{'status':r['status'],'source_sha256':r['source_sha256'],'delivery':None} for r in result['inventory']['images']}
    progress={'cohort':'production_non_people','updated_utc':utc(),'status_counts':dict(collections.Counter(r['status'] for r in initial.values())),
        'sealed_batches':[],'new_production_sources_complete':0,'new_production_accepted':0,'whole_scope_complete':False}
    outputs['state.json']={**progress,'images':initial};outputs['progress.json']=progress
    for name,value in outputs.items():json.dumps(value)
    for name,value in outputs.items():atomic_json(HERE/name,value)
    with (HERE/'ledger.jsonl').open('x') as ledger:ledger.flush();os.fsync(ledger.fileno())
    (HERE/'batches').mkdir()
    return {'status':'initialized_not_processed','cohort':'production_non_people','subjects':REVIEW,'images_decoded':0,'whole_scope_complete':False}

def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--dry-run',action='store_true');mode.add_argument('--initialize',action='store_true');args=parser.parse_args()
    if args.initialize:require_activation()
    result=build_runtime()
    if args.initialize:print(json.dumps(initialize_runtime(result)));return
    report={'created_utc':utc(),'status':'metadata_dry_run_passed','no_runtime_metadata_written':True,'images_decoded':0,'production_execution_enabled':False,
        'summary':result['summary'],'scope_proof':result['scope_proof'],'serialized_inventory_bytes':len(json.dumps(result['inventory']).encode()),'serialized_queue_bytes':len(json.dumps(result['queue']).encode()),
        'code_bundle_sha256':digest(HERE/'code_bundle.json')}
    atomic_json(HERE/'dry_run_validation.json',report);print(json.dumps(report))

if __name__=='__main__':main()
