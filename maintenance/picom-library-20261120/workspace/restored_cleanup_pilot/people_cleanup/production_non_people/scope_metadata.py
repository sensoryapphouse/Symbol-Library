"""Independent original-collection scope reconstruction and approved overlay validation."""
import collections,csv,re
from pathlib import Path
from common import HERE,LIBRARY,read,digest,require,validate_bundle
from contracts import unique
from source_versions import apply_overlay,PENDING,PRIOR,TOTAL
PREP=HERE.parent/'production_non_people_preparation'

def original_collection(source):
    p=source.split('/')
    if p[0]=='New non-people-2':require(p[1]=='_Pending review','Unknown collection ambiguity');return True
    if p[0]=='Second batch':
        if p[1]!='Vocabulary gaps':return len(p)>2 and p[2]=='Non-people'
        require(p[2]=='_Pending review','Unknown vocabulary collection ambiguity')
        q=p[4:] if p[3]=='_Transparent backgrounds' else p[3:]
        return len(q)>1 and q[1]=='Non-people'
    prefix='/Users/paulblenkhorn/Desktop/picom_review/staging/vocab_lot/'
    if source.startswith(prefix):
        q=source[len(prefix):].split('/');return len(q)>1 and q[1]=='Non-people'
    return False

def jsonl(path):
    with Path(path).open() as f:
        for line in f:yield __import__('json').loads(line)
def group_key(relative):
    p=Path(relative);return '/'.join(p.parts[1:-1])+'::'+re.sub(r'[\s_-]+','',p.stem.casefold())

def resolution_overlay(pending,document):
    expected={r['relative_path']:r for r in pending.values() if r['lineage_hold']};records=unique(document['records'],'relative_path')
    require(set(records)==set(expected) and len(records)==7,'Approved7 resolution overlay differs from exact historical set')
    require(document['status']=='approved_for_new_cohort_preparation_only','Prior resolution authority differs')
    for rel,record in records.items():
        source=expected[rel];review=source['partition']=='review_required'
        require(record['source_path']==source['source_path'] and record['source_sha256']==source['source_sha256'],'Prior resolution source binding differs')
        require(record['review_required'] is review and record['trial_output_import_allowed'] is False and record['completed_source_review_claimed'] is False,'Historical trial import/review shortcut forbidden')
        require(record['resolution']==('fresh_original_source_review_required' if review else 'original_retained_below_total_threshold_pending_final_byte_proof'),'Unknown/ambiguous prior resolution')
        require(record['proposed_subject_id']==source.get('proposed_subject_id'),'Resolved subject ID differs')
    return records

def reconstruct():
    validate_bundle();contract=read(HERE/'scope_contract.json');manifest=read(PREP/'preparation_manifest.json')
    original={}
    for filename,expected in contract['original_manifest_csv_sha256'].items():
        require(digest(filename)==expected,'Original CSV changed')
        with open(filename,newline='',encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if not original_collection(row['source']):continue
                rel=Path(filename).stem+'/'+row['rel'];require(rel not in original,'Duplicate original CSV source')
                original[rel]={'source_sha256':row['final_sha256'],'collection_source':row['source']}
    pending=unique(list(jsonl(PREP/'pending_inventory.jsonl')),'relative_path');prior=unique(list(jsonl(PREP/'excluded_prior_inventory.jsonl')),'relative_path')
    require(not set(pending)&set(prior) and set(pending)|set(prior)==set(original),'CSV-provenance exact set differs from pending+prior partitions')
    require(len(original)==170044 and len(pending)==168748 and len(prior)==1296,'Pinned scope cardinality differs')
    census=unique(list(jsonl(HERE.parent/'production/non_people_scope_extension/census_checkpoint.jsonl')),'relative_path')
    expected_pending={rel for rel,r in census.items() if r['prior_disposition']!='completed_original'}
    completed={rel for rel,r in census.items() if r['prior_disposition']=='completed_original'}
    require(set(pending)==expected_pending,'Pending set differs from original census')
    frozen=read(HERE.parent/'production/inventory.json')['images'];frozenpaths={r['relative_path'] for r in frozen}
    expected_frozen=set(original)&frozenpaths
    require({rel for rel,r in prior.items() if r['partition']=='excluded_frozen_topic_inventory'}==expected_frozen,'Old-topic prior exact set differs')
    require({rel for rel,r in prior.items() if r['partition']=='previously_completed_original'}==completed,'Prior completed-original exact set differs')
    counts=collections.Counter()
    for rel,row in {**prior,**pending}.items():require(row['source_sha256']==original[rel]['source_sha256'],'Source SHA differs from original CSV')
    for rel,row in pending.items():
        c=census[rel];require(row['source_sha256']==c['source_sha256'] and row['dimensions']==c['dimensions']==[512,512],'Pending source SHA/domain differs')
        require(row['source_path']==str(LIBRARY/rel) and row['group_key']==group_key(rel),'Source path or concept ambiguity')
        expected=('below_total_original_unchanged' if not c['simple_eligible'] else 'review_required' if row['blob_metrics']['nearby_fragment_groups_ge256_inradius3']>0 else 'screened_original_unchanged')
        require(row['partition']==expected and row['candidate']==bool(c['simple_eligible']),'Whole-source screening differs')
        counts[expected]+=1;original[rel].update(dimensions=row['dimensions'],partition=expected,subject_id=row.get('proposed_subject_id'))
    require(counts=={'review_required':66077,'screened_original_unchanged':19778,'below_total_original_unchanged':82893},'Screening exact counts differ')
    frozen_by_path={r['relative_path']:r for r in frozen}
    for rel,row in prior.items():
        dims=row.get('dimensions') or frozen_by_path[rel]['dimensions']
        original[rel].update(dimensions=dims,partition=row['partition'])
    overlay=resolution_overlay(pending,read(PREP/'approved_prior_resolutions.json'))
    apply_overlay(original,pending,prior,overlay,frozen_by_path)
    require(len(original)==TOTAL and len(pending)==PENDING and len(prior)==PRIOR,
            'Effective source-version scope cardinality differs')
    return original,pending,prior,overlay
