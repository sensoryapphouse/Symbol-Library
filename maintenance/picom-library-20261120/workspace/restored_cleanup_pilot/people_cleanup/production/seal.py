#!/usr/bin/env python3
"""Seal hash-bound, independently reviewed outputs under the explicit acceptance policy."""
import argparse,datetime,os,re
from pathlib import Path
from qa import sha,read,atomic,folder

POLICY_PATH=Path(__file__).parent/'acceptance_policy.json'
RULE='Only cleaned entries approve replacement; retained originals are hash-verified. One canonical WebP per accepted result; no copies.'

def load_policy():
 policy=read(POLICY_PATH)
 assert policy['version']==2
 assert policy['authorization']=="I agree - worse on uncertain safety should be lost. Let's keep even odest improvements."
 assert policy['required_safety']=='clear' and policy['accepted_worthwhile']==['clear','modest']
 assert policy['held_safety']==['uncertain','unsafe'] and policy['held_worthwhile']==['negligible','uncertain']
 return policy

def verify_source_checkpoints(batch,manifest,decisions):
 # Match compile_decisions.py: every required group needs a checkpoint, and
 # existing context-only group checkpoints are pinned too.
 proofs={}
 for group in manifest['groups']:
  name=group['group_id']+'.json'
  assert Path(name).name==name,'Invalid source checkpoint name'
  assert name not in proofs,'Duplicate source checkpoint group'
  path=batch/'source_reviews'/name
  required=any(row.get('review_required',True) for row in group['versions'])
  assert path.is_file() or not required,f'Missing source checkpoint {path}'
  if path.is_file():proofs[name]=sha(path)
 assert decisions.get('source_checkpoint_sha256')==proofs,'Source decisions changed after compilation or checkpoint coverage is incomplete'

def accepts(q,policy):
 return q['safety']==policy['required_safety'] and q['worthwhile'] in policy['accepted_worthwhile']

def delivery_reason(q):
 if q['worthwhile']!='modest':return q['reason']
 # Keep the immutable review intact, but remove its superseded delivery instruction.
 observation=re.sub(r'(?i)(?:[,;.]?\s*(?:so\s+)?retain original\.?)', '', q['reason']).strip().rstrip(' .;')
 return observation+'. Accepted under acceptance policy v2: clear safety and a real modest improvement.'

def comparable(d):return {k:v for k,v in d.items() if k!='sealed_utc'}

def validate_migration(old,legacy,current,reviews):
 assert comparable(old)==comparable(legacy),'Existing sealed delivery differs from verified legacy delivery'
 allowed={'acceptance_policy_sha256','acceptance_policy_version','sealed_utc','images','cleaned','originals_retained'}
 assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in current.items() if k not in allowed}
 assert len(old['images'])==len(current['images'])
 for before,after in zip(old['images'],current['images']):
  if before==after:continue
  q=reviews[before['id']]
  assert before['delivery']=='original' and after['delivery']=='cleaned' and q['safety']=='clear' and q['worthwhile']=='modest','Migration may only promote clear-safe modest outputs'
  changed={'delivery','path','sha256','reason','reviewer'}
  assert {k:v for k,v in before.items() if k not in changed}=={k:v for k,v in after.items() if k not in changed}

def publish(batch,result,moves,old_bytes=None):
 # All source, artifact, review and migration validation must finish before any mutation.
 if old_bytes is not None:
  import hashlib
  digest=hashlib.sha256(old_bytes).hexdigest();history=batch/'delivery_history';archive=history/(digest+'.json')
  history.mkdir(exist_ok=True)
  if archive.exists():assert archive.read_bytes()==old_bytes
  else:
   # Atomic archive creation: a crash must never leave a partial history record.
   tmp=history/(digest+'.tmp')
   with tmp.open('wb') as out:out.write(old_bytes);out.flush();os.fsync(out.fileno())
   os.replace(tmp,archive)
 for source,dest,out in moves:
  if source!=dest:
   dest.parent.mkdir(exist_ok=True);assert not dest.exists();os.rename(source,dest)
  assert sha(dest/'after.webp')==out
 atomic(batch/'accepted_delivery.json',result)

def seal(batch,adopt=False):
 # Serialise sealers without taking the image worker lock: no image decode occurs.
 import fcntl
 with (batch/'seal.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  policy=load_policy();target=batch/'accepted_delivery.json';old_bytes=target.read_bytes() if target.exists() else None;old=read(target) if target.exists() else None
  mode='legacy' if old is not None and 'acceptance_policy_sha256' not in old else 'current'
  migrate=mode=='legacy' and adopt
  m=read(batch/'manifest.json');dec=read(batch/'approved_decisions.json');state=read(batch/'selected_run_state.json');audit=read(batch/'mechanical_audit.json');assert state['status']=='complete';review=read(batch/'independent_output_review.json')
  verify_source_checkpoints(batch,m,dec)
  for key,name in [('manifest_sha256','manifest.json'),('decisions_sha256','approved_decisions.json'),('run_state_sha256','selected_run_state.json')]:assert audit[key]==sha(batch/name),f'Stale mechanical audit: {key}'
  assert audit['auditor_sha256']==sha(Path(__file__).parent/'qa.py');protocol=read(Path(__file__).parent/'protocol.json');assert audit['protocol_sha256']==sha(Path(__file__).parent/'protocol.json');assert audit['cleaner_sha256']==state['cleaner_sha256']==protocol['engine']['sha256']==sha(protocol['engine']['path']);assert not audit['errors'];rows={v['batch_id']:v for g in m['groups'] for v in g['versions']};runs={r['id']:r for r in state['images']};checks={r['id']:r for r in audit['images']};decisions={r['id']:r for r in dec['decisions']};reviews={r['id']:r for r in review['images']}
  assert len(reviews)==len(review['images']) and set(reviews)=={id for id,r in runs.items() if r['status']=='changed'},'Review must cover every changed output exactly once'
  assert len(rows)==sum(len(g['versions']) for g in m['groups']) and len(runs)==len(state['images']) and len(checks)==len(audit['images']);assert len(decisions)==len(dec['decisions']) and set(decisions)==set(rows);assert set(rows)==set(runs)==set(checks) and all(c['passed'] for c in checks.values())
  deliveries=[];legacy_deliveries=[];moves=[]
  for id,row in rows.items():
   assert Path(id).name==id and id not in ('.','..');assert sha(row['source'])==row['source_sha256'],f'{id}: original source changed'
   d={'id':id,'source_path':row['source'],'source_sha256':row['source_sha256'],'delivery':'original','path':row['source'],'sha256':row['source_sha256'],'reason':runs[id].get('retain_reason','Original retained: no accepted output.'),'role':row.get('role','candidate'),'reference':row.get('reference',row.get('review_required') is False),'review_required':row.get('review_required',True),'newly_processed':row.get('review_required',True) is not False,'mechanical_context_reference':row.get('mechanical_context_reference',row.get('review_required') is False)}
   if row.get('review_required') is False:
    assert runs[id]['status']!='changed';d['reason']='Context reference: previously completed or outside new processing.'
   if runs[id]['status']=='changed':
    f=folder(batch,id);r=read(f/'result.json');q=reviews[id];assert r['manifest_sha256']==sha(batch/'manifest.json') and r['decision_sha256']==sha(batch/'approved_decisions.json') and r['cleaner_sha256']==audit['cleaner_sha256'];assert sha(f/'result.json')==checks[id]['result_sha256'];assert all(sha(f/name)==digest for name,digest in checks[id]['artifact_sha256'].items());out=sha(f/'after.webp');assert q['source_sha256']==r['source_sha256']==row['source_sha256'];assert q['output_sha256']==r['output_sha256']==checks[id]['output_sha256']==runs[id]['output_sha256']==out
    assert isinstance(q.get('reviewer'),str) and q['reviewer'].strip() and q['reviewer']!=decisions[id].get('reviewer'),'Independent reviewer identity required'
    assert q.get('actually_viewed') is True and q.get('full_and_allregions_checked') is True and isinstance(q.get('reason'),str) and q['reason'].strip(),'Every changed output requires actual full/region visual review'
    assert q['safety'] in ('clear','uncertain','unsafe') and q['worthwhile'] in ('clear','modest','negligible','uncertain')
    legacy_d=dict(d)
    if q['safety']=='clear' and q['worthwhile']=='clear':
     legacy_d.update(delivery='cleaned',path=str((batch/'accepted_outputs'/id/'after.webp').resolve()),sha256=out,reason=q['reason'],reviewer=q['reviewer'])
    else:legacy_d['reason']='Original retained: '+q['reason']
    if (accepts(q,policy) if mode=='current' or migrate else q['safety']=='clear' and q['worthwhile']=='clear'):
     dest=batch/'accepted_outputs'/id
     assert f==dest or not dest.exists()
     moves.append((f,dest,out))
     d.update(delivery='cleaned',path=str((dest/'after.webp').resolve()),sha256=out,reason=delivery_reason(q) if mode=='current' or migrate else q['reason'],reviewer=q['reviewer'])
    else:
     assert f.parent.name!='accepted_outputs',f'{id}: prior accepted folder conflicts with current held review'
     d['reason']='Original retained: '+q['reason']
   deliveries.append(d)
   legacy_deliveries.append(legacy_d if runs[id]['status']=='changed' else dict(d))
  accepted=sum(d['delivery']=='cleaned' for d in deliveries)
  result={'batch_id':m.get('batch_id',batch.name),'sealed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':sha(batch/'manifest.json'),'decisions_sha256':sha(batch/'approved_decisions.json'),'mechanical_audit_sha256':sha(batch/'mechanical_audit.json'),'output_review_sha256':sha(batch/'independent_output_review.json'),'cleaned':accepted,'originals_retained':len(deliveries)-accepted,'images':deliveries,'rule':RULE}
  legacy=dict(result,images=legacy_deliveries,cleaned=sum(d['delivery']=='cleaned' for d in legacy_deliveries))
  legacy['originals_retained']=len(legacy_deliveries)-legacy['cleaned']
  if mode=='current' or migrate:result.update(acceptance_policy_version=policy['version'],acceptance_policy_sha256=sha(POLICY_PATH))
  if old is not None:
   if migrate:validate_migration(old,legacy,result,reviews)
   else:
    assert comparable(old)==comparable(result),'Existing sealed delivery differs: refusing to rewrite ledger-bound delivery'
    assert all(source==dest for source,dest,out in moves),'Sealed delivery has uncommitted folder moves'
    print({'status':'already_sealed_verified','accepted':accepted,'originals_retained':len(deliveries)-accepted});return
  # Recheck immediately before publication after validating all output rows.
  verify_source_checkpoints(batch,m,dec)
  publish(batch,result,moves,old_bytes if migrate else None)
  print({'status':'policy_adopted' if migrate else 'sealed','accepted':accepted,'originals_retained':len(deliveries)-accepted})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True,type=Path)
 ap.add_argument('--adopt-current-acceptance-policy',action='store_true',help='Explicitly promote only previously held clear-safe modest outputs; archive the exact previous delivery.')
 args=ap.parse_args();seal(args.batch.resolve(),args.adopt_current_acceptance_policy)
if __name__=='__main__':main()
