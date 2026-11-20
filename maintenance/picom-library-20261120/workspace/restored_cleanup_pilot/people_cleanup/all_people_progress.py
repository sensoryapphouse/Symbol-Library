#!/usr/bin/env python3
"""Refresh a compact, ORIGINAL-People-only rollup outside frozen cohorts.

Reads pinned CSV provenance, frozen inventories and latest complete ledger bytes.
No source images, previews, cleanup, inventory or workflow code are changed.
"""
import argparse
import collections
import contextlib
import csv
import datetime
import fcntl
import hashlib
import html
import io
import json
import os
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/'production'
REMAINING=HERE/'production_remaining_people'


def sha(raw):return hashlib.sha256(raw).hexdigest()

def atomic(path,value):
    temp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    with temp.open('w',encoding='utf-8') as stream:
        stream.write(value);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def is_original_people(source):
    p=source.split('/')
    if p[0] in ('People','New Clothed'):return True
    if p[0]!='Second batch':return False
    if p[1]!='Vocabulary gaps':return p[2]=='People'
    assert p[2]=='_Pending review'
    q=p[4:] if p[3]=='_Transparent backgrounds' else p[3:]
    return q[1]=='People'


def collection_scope():
    path=ORIGINAL/'scope_extension/snapshot.json';raw=path.read_bytes();snapshot=json.loads(raw)
    paths=set()
    for csv_path,expected in snapshot['manifest_csv_sha256'].items():
        blob=Path(csv_path).read_bytes();assert sha(blob)==expected,'Scope manifest changed: '+csv_path
        for row in csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))):
            if not is_original_people(row['source']):continue
            relative=Path(csv_path).stem+'/'+row['rel']
            assert relative not in paths,'Duplicate People provenance path: '+relative
            paths.add(relative)
    assert len(paths)==57073
    assert snapshot['original_people_actual_paths']==57073
    return paths,{'snapshot':str(path),'snapshot_sha256':sha(raw),'frozen_original_inventory_sha256':snapshot['frozen_inventory_sha256'],'manifest_csv_sha256':snapshot['manifest_csv_sha256']}


def load_cohort(root,wanted):
    # Bootstrap must have returned successfully before publishing its union.
    lock_path=root/'bootstrap.lock'
    with contextlib.ExitStack() as stack:
        if lock_path.exists():
            bootstrap_lock=stack.enter_context(lock_path.open('r'))
            try:fcntl.flock(bootstrap_lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError(f'{root.name} bootstrap is still active; retry after it finishes')
        for name in ('inventory.json','ledger.jsonl','queue.json','batch_index.json','summary.json','import_audit.json'):
            if not (root/name).is_file():raise RuntimeError(f'{root.name} initialization incomplete: {name} missing')
        invraw=(root/'inventory.json').read_bytes();inventory=json.loads(invraw);records={};all_ids=set();all_paths=set()
        for row in inventory['images']:
            sid=row['production_source_id'];rel=row['relative_path']
            assert sid not in all_ids and rel not in all_paths,'Duplicate frozen inventory source'
            all_ids.add(sid);all_paths.add(rel)
            if rel not in wanted:continue
            records[sid]={k:row.get(k) for k in ('relative_path','source','source_sha256','status','simple_eligible','production_queue_id')}
        metadata={'inventory_rows':len(all_paths),'people_rows':len(records),'excluded_non_people_rows':len(all_paths)-len(records),'inventory_sha256':sha(invraw)}
        del invraw,inventory
        queue_raw=(root/'queue.json').read_bytes();queue=json.loads(queue_raw)
        index=json.loads((root/'batch_index.json').read_bytes())
        assert index['queue_sha256']==sha(queue_raw),'Frozen queue/index hash mismatch'
        subjects={}
        for group in queue['groups']:
            for version in group['versions']:
                if version['role']!='subject':continue
                sid=version['production_source_id']
                assert sid in all_ids and sid not in subjects,'Queue subject missing/duplicate in inventory'
                subjects[sid]=(version['batch_id'],version['source_sha256'])
        assert len(subjects)==queue['subject_count']
        for sid,row in records.items():
            assert bool(row['production_queue_id'])==(sid in subjects),'Inventory/queue membership mismatch'
            if sid in subjects:assert subjects[sid]==(row['production_queue_id'],row['source_sha256'])
        metadata.update(queue_sha256=sha(queue_raw),all_collection_queue_subjects=len(subjects))
        del queue_raw,queue,subjects,index
        ledger_path=root/'ledger.jsonl';ledger_lock_path=root/'ledger.lock'
        if ledger_lock_path.exists():
            ledger_lock=stack.enter_context(ledger_lock_path.open('r'))
            fcntl.flock(ledger_lock,fcntl.LOCK_SH)
        before=ledger_path.stat();blob=ledger_path.read_bytes();after=ledger_path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError('Ledger changed during read; retry refresh')
        assert not blob or blob.endswith(b'\n'),'Ledger has an incomplete trailing event; retry refresh'
        last_event=None
        for line in blob.splitlines():
            event=json.loads(line);sid=event.get('production_source_id')
            if sid is None:continue
            assert sid in all_ids,'Ledger event refers to unknown frozen source'
            if sid not in records:continue
            record=records[sid]
            assert event.get('source_sha256')==record['source_sha256'],'Ledger source hash differs from inventory'
            if event.get('status_to'):record['status']=event['status_to']
            if event.get('utc'):last_event=max(last_event or event['utc'],event['utc'])
        metadata.update(ledger_sha256=sha(blob),ledger_bytes=len(blob),last_people_event_utc=last_event,
            progress_state_source='Frozen inventory plus append-only ledger; no uncommitted checkpoint progress inferred')
        return records,metadata


def summarize(records):
    counts=collections.Counter(x['status'] for x in records.values())
    queued=[x for x in records.values() if x['production_queue_id']]
    complete=sum(x['status'] in ('accepted','original_retained') for x in queued)
    assert complete<=len(queued)
    prior={k:counts[k] for k in ('completed_original','accepted_prior_cleaned','accepted_prior_repair')}
    return {'scope_total':len(records),'queued_review_total':len(queued),'queued_review_complete':complete,
        'queued_review_remaining':len(queued)-complete,
        'queued_source_reviewed_awaiting_completion':sum(x['status']=='source_reviewed' for x in queued),
        'queued_cleaned_accepted':sum(x['status']=='accepted' for x in queued),
        'queued_original_retained':sum(x['status']=='original_retained' for x in queued),
        'prior_deliveries':dict(prior),'prior_deliveries_total':sum(prior.values()),
        'below_threshold_originals_final_hash_verification_pending':counts['below_eligibility_unprocessed'],
        'unresolved_prior_work':sum(v for k,v in counts.items() if k in ('needs_import_resolution','needs_historical_output_review')),
        'status_counts':dict(counts)}


def render(data):
    total=data['totals'];escape=html.escape;rows=[]
    for cohort in data['cohorts']:
        s=cohort['counts'];rows.append('<tr><td><a href="'+escape(cohort['review_index'])+'">'+escape(cohort['label'])+'</a></td>'+''.join(f'<td>{s[k]:,}</td>' for k in ('scope_total','queued_review_total','queued_review_complete','queued_review_remaining'))+'</tr>')
    pct=100*total['queued_review_complete']/max(1,total['queued_review_total'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>All original People — cleanup progress</title><style>
body{{font:17px/1.5 system-ui,sans-serif;max-width:1050px;margin:36px auto;padding:0 22px;color:#213047;background:#f7f9fc}}h1{{font-size:30px}}a{{color:#174caa}}.stats{{display:flex;flex-wrap:wrap;gap:14px}}.card{{background:#fff;border:1px solid #cad3df;border-radius:10px;padding:16px;min-width:190px}}.card strong{{font-size:27px;display:block}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:10px;border-bottom:1px solid #dbe2eb;text-align:right}}td:first-child,th:first-child{{text-align:left}}progress{{width:100%;height:20px}}.small{{font-size:14px;color:#526071}}
</style><h1>All original People collection</h1><p class="small">Data snapshot: {escape(data['generated_utc'])}. Refresh with <code>python3 all_people_progress.py</code>.</p>
<div class="stats"><div class="card"><strong>57,073</strong>Original People files across all topics</div><div class="card"><strong>{total['queued_review_complete']:,} / {total['queued_review_total']:,}</strong>Queued reviews completed</div><div class="card"><strong>{total['queued_review_remaining']:,}</strong>Queued reviews still to complete</div></div>
<p>Review-queue completion: {pct:.1f}%. This percentage applies only to eligible queued reviews. Below-threshold originals are not counted as visually reviewed.</p><progress value="{total['queued_review_complete']}" max="{total['queued_review_total']}"></progress>
<p>{total['queued_cleaned_accepted']:,} queued sources have accepted improvements; {total['queued_original_retained']:,} completed reviews retain the original. Another {total['queued_source_reviewed_awaiting_completion']:,} sources have recorded source review and await the remaining production checks or sealing.</p>
<table><thead><tr><th>Cohort review index</th><th>People files</th><th>Queued reviews</th><th>Complete</th><th>Remaining</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="small">A cohort review index appears after its first completed batch; its link is retained here for subsequent refreshes.</p>
<h2>Earlier completed deliveries</h2><p>{total['prior_deliveries']['completed_original']:,} originals retained, {total['prior_deliveries']['accepted_prior_cleaned']:,} earlier cleanups and {total['prior_deliveries']['accepted_prior_repair']:,} accepted repairs. These are separate from the queue above. Recorded historical completion does not imply every retained original received a new visual review.</p>
<h2>Originals outside the review queue</h2><p>{total['below_threshold_originals_final_hash_verification_pending']:,} below-threshold originals await final source-hash verification. They remain unchanged and are not claimed as visually reviewed. Unresolved prior-work cases: {total['unresolved_prior_work']:,}.</p>
<p>This rollup excludes all 1,263 Non-people collection files in the original topic inventory. The two People scopes form an exact, non-overlapping union of 57,073 files.</p>
<p><a href="production/scope_extension/snapshot.json">Collection scope evidence</a> · <a href="production/scope_extension/summary.json">Remaining People census</a> · <a href="production_remaining_people/import_audit.json">Follow-on prior-work reconciliation</a> · <a href="production/source_integrity/wood_repairs/review.html">Seven governing Wood repairs</a> · <a href="all_people_progress.json">Machine-readable rollup</a></p>
<p class="small">Counts use frozen inventory plus the latest complete append-only ledger snapshot. Uncommitted reviewer checkpoints are not inferred.</p></html>'''


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    wanted,scope=collection_scope();cohorts=[];union={};ids=set()
    for root,label in [(ORIGINAL,'Original topic cohort — People only'),(REMAINING,'Remaining original People cohort')]:
        records,metadata=load_cohort(root,wanted)
        paths={x['relative_path'] for x in records.values()}
        assert not set(union).intersection(paths),'People scopes overlap'
        assert not ids.intersection(records),'Source IDs overlap between cohorts'
        ids.update(records);union.update({x['relative_path']:x for x in records.values()})
        cohorts.append({'root':str(root),'label':label,'review_index':root.name+'/index.html',
            'review_index_exists':(root/'index.html').is_file(),'inputs':metadata,'counts':summarize(records)})
    assert len(union)==57073 and set(union)==wanted,'People union is incomplete or has extra paths'
    assert cohorts[0]['inputs']['inventory_sha256']==scope['frozen_original_inventory_sha256']
    assert cohorts[0]['inputs']['people_rows']==9628 and cohorts[0]['inputs']['excluded_non_people_rows']==1263
    assert cohorts[1]['inputs']['people_rows']==47445 and cohorts[1]['inputs']['excluded_non_people_rows']==0
    data={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Original People collection across all Library topics',
        'scope_total':57073,'scope_unique_paths':len(union),'scope_missing_paths':0,'scope_extra_paths':0,'scope_overlap_paths':0,
        'excluded_original_topic_non_people':1263,'scope_evidence':scope,'totals':summarize(union),'cohorts':cohorts,
        'completion_definition':'Only sealed accepted/original-retained queued subjects count as queue completion. Threshold skips are not visual reviews.',
        'source_images_read_or_changed':False,'frozen_workflows_changed':False}
    atomic(HERE/'all_people_progress.json',json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    atomic(HERE/'all_people_progress.html',render(data))
    print(json.dumps({'scope_total':57073,**{k:data['totals'][k] for k in ('queued_review_total','queued_review_complete','queued_review_remaining','prior_deliveries_total','below_threshold_originals_final_hash_verification_pending')}}))

if __name__=='__main__':main()
