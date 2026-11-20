"""Exact set, role and identity contracts shared by metadata and runtime guards."""
import re
from pathlib import Path
from common import HERE,LIBRARY,require,digest,read
from source_versions import VERSION_KEYS,logical_id

def unique(records,field):
    result={}
    for row in records:
        key=row[field];require(key not in result,'Duplicate '+field+': '+str(key));result[key]=row
    return result

def original_identity(delivery,row):
    require(delivery['delivery']=='original' and delivery['path']==row['source'] and delivery['sha256']==row['source_sha256'],'Skipped/retained original is not exact source identity')

def exact_outputs(rows,runs,decisions,reviews):
    indexed=unique(rows,'batch_id');runs=unique(runs,'id');decisions=unique(decisions,'id');reviews=unique(reviews,'id')
    require(set(runs)==set(decisions)==set(indexed),'Missing or unexpected run/decision sources')
    changed={i for i,r in runs.items() if r['status']=='changed'}
    require(set(reviews)==changed,'Independent review must cover every changed output exactly once')
    for ident,row in indexed.items():
        require(runs[ident]['source_sha256']==decisions[ident]['source_sha256']==row['source_sha256'],'Output/decision source pin differs')
        if not row['review_required']:require(runs[ident]['status']!='changed','Context reference acquired cleanup')
        if ident in changed:
            q=reviews[ident];require(q['source_sha256']==row['source_sha256'] and q['output_sha256']==runs[ident]['output_sha256'],'Review identity differs')
            require(q.get('actually_viewed') is True and q.get('full_and_allregions_checked') is True,'Changed output visual coverage incomplete')
            require(q.get('reviewer') and q['reviewer']!=decisions[ident].get('reviewer'),'Output reviewer is not independent')
    return indexed

def validate_versions(groups,original):
    global_subjects=set();global_ids=set()
    for group in groups:
        versions=group['versions'];ids=unique(versions,'batch_id');paths=unique(versions,'source');subjects={r['source'] for r in versions if r['role']=='subject'}
        refs=[r for r in versions if r['role']=='reference'];require(len(refs)<=2,'More than2 reference versions per concept')
        require(len({r['style'] for r in refs})==len(refs),'Ambiguous duplicate-style references')
        for ident,row in ids.items():
            require(ident not in global_ids,'Duplicate manifest ID');global_ids.add(ident)
            rel=str(Path(row['source']).relative_to(LIBRARY));require(rel in original,'Source outside original scope');source=original[rel]
            require(row['source']==str(LIBRARY/rel) and row['source_sha256']==source['source_sha256'] and row['dimensions']==source['dimensions']==[512,512],'Source path/SHA/dimensions differ')
            require(row['style']==rel.split('/')[0],'Source style/path differs')
            require(row['production_source_id']==logical_id(rel,source),'Wrong production-source namespace or hash')
            for field in VERSION_KEYS:
                require(row.get(field)==source.get(field),'Current queue source-version identity differs')
            if row['role']=='subject':
                require(re.fullmatch(r'np\d{5}',ident) and ident==source.get('subject_id') and source['partition']=='review_required' and row['review_required'] is True,'Invalid Non-People subject role/ID')
                require(row['source'] not in global_subjects,'Duplicate subject source');global_subjects.add(row['source'])
            else:
                require(row['role']=='reference' and ident=='r_'+row['production_source_id'][:20] and row['review_required'] is False,'Invalid context role/ID')
                require(row['source'] not in subjects,'Reference overlaps subjects')
    return global_subjects

def validate_manifest(manifest,queue,batch_id):
    require(manifest['cohort']==queue['cohort']=='production_non_people' and manifest['batch_id']==batch_id,'Wrong manifest cohort/batch')
    require(manifest['protocol_sha256']==queue['protocol_sha256']==digest(HERE/'protocol.json'),'Protocol pin differs')
    require(manifest['scope_snapshot_sha256']==queue['scope_snapshot_sha256']==digest(HERE/'scope_contract.json'),'Scope pin differs')
    expected=next((b for b in queue['batches'] if b['batch_id']==batch_id),None);require(expected is not None,'Unknown batch ID')
    groups=unique(manifest['groups'],'group_id');require(set(groups)==set(expected['group_ids']),'Missing/unexpected batch concepts')
    qgroups={g['group_id']:g for g in queue['groups']}
    for gid,group in groups.items():
        for field in ('group_key','people_subfolder','normalized_stem','batch_id'):
            require(group[field]==qgroups[gid][field],'Manifest concept/batch binding differs')
        require(re.fullmatch(r'npg\d{5}',gid),'Wrong group namespace')
        current=unique(group['versions'],'batch_id');planned=unique(qgroups[gid]['versions'],'batch_id');require(set(current)==set(planned),'Missing/unexpected manifest versions')
        for ident,row in current.items():
            for field in ('source','source_sha256','source_bytes','dimensions','production_source_id','role','review_required','style','style_id',*VERSION_KEYS):
                require(row.get(field)==planned[ident].get(field),'Manifest row differs from frozen queue: '+field)
