"""Verify the completed Task 10 work before releasing the authorised rename."""
import sqlite3,json,hashlib,datetime,fcntl
from pathlib import Path
H=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 lock=(H/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 db=sqlite3.connect(H/'queue.sqlite');db.row_factory=sqlite3.Row
 counts=dict(db.execute('select status,count(*) from jobs group by status'))
 assert counts=={'published':53826,'excluded':87},counts
 cache={};errors=[];checked=0
 for r in db.execute('select * from jobs where status="published"'):
  p=r['source']
  if p not in cache:cache[p]=sha(p)
  if cache[p]!=r['source_sha']:errors.append([r['id'],'source changed',p])
  if sha(r['destination'])!=r['output_sha']:errors.append([r['id'],'output changed',r['destination']])
  checked+=1
  if checked%10000==0:print('Verified',checked,flush=True)
 aux=json.loads((H/'auxiliary_modal_reconciliation.json').read_text());assert aux['complete']
 for r in aux['published']:
  assert sha(r['destination'])==r['sha256']
  if r.get('source'):assert sha(r['source'])==r['source_sha256']
 for st in aux['styles'].values():
  for group in st.values():
   for r in group.values():
    if 'path' in r:assert sha(r['path'])==r['sha256']
 assert not errors,errors[:10]
 assert not any((H/'staging').rglob('*.svg'))
 for p in Path('/private/tmp/task10_production_20261119').glob('*'):
  if p.is_file() and (p.name.endswith(('_before.png','_after.png')) or p.name.startswith('clock_review_') or p.name=='auxiliaries_review.jpg'):p.unlink()
 report={'verified_at':datetime.datetime.now().astimezone().isoformat(),'task10_complete':True,'checks_complete':True,'held_cases_disposed':True,'auxiliary_modal_reconciled':True,'queue_counts':counts,'published_queue_outputs':checked,'distinct_queue_sources_verified':len(cache),'auxiliary_reuse_and_fills':len(aux['published']),'semantic_exclusions':87,'source_or_output_errors':errors,'visual_review':'342 validation samples and all 306 clock repairs; 17 schematic auxiliary masters. Remaining bulk outputs independently render/geometry/hash checked, not all visually checked.','temporary_images_removed':True,'next_task':11}
 p=H/'completion.json';tmp=p.with_suffix('.json.tmp');tmp.write_text(json.dumps(report,indent=2));tmp.replace(p)
 print('TASK 10 COMPLETE',checked,'queue outputs plus',len(aux['published']),'auxiliary/modal deliveries; rename gate released',flush=True)
if __name__=='__main__':main()
