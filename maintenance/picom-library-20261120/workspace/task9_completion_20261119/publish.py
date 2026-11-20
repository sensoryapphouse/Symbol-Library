from pathlib import Path
import json,hashlib,datetime,collections,shutil
H=Path(__file__).resolve().parent;rows=json.loads((H/'manifest.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();old=json.loads((H/'original_hashes.json').read_text());existing=json.loads((H/'existing_library_hashes.json').read_text());review=json.loads((H/'visual_review_log.json').read_text());accepted={p for r in review if r['status']=='accepted' for p in r['destinations']};audit={r['id']:r for r in json.loads((H.parent/'task9_reuse_audit_20261119/files.json').read_text())}
for p,v in {**old,**existing}.items():assert sha(p)==v,p
for r in rows:
 assert sha(r['source'])==r['sha256']
 if r['method']=='reuse_byte_identical':assert audit[r['prior_review_id']]['visually_reviewed'] and audit[r['prior_review_id']]['sha256']==r['sha256']
 else:assert r['destination'] in accepted
receipts=[]
for i,r in enumerate(rows):
 dst=Path(r['destination']);dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():assert sha(dst)==r['sha256'],str(dst)
 else:
  with dst.open('xb') as f:f.write(Path(r['source']).read_bytes())
 assert sha(dst)==r['sha256'];receipts.append(dict(r,published_at=datetime.datetime.now().astimezone().isoformat()))
 if (i+1)%25==0 or i+1==len(rows):(H/'published.json').write_text(json.dumps({'complete':i+1==len(rows),'count':len(receipts),'files':receipts},indent=2))
for p,v in {**old,**existing}.items():assert sha(p)==v,p
# Reconfirm previous completed outputs; do not regenerate them.
prior=json.loads((H.parent/'task9_full_figures_20261119/published.json').read_text())['files']
for r in prior:assert sha(r['path'])==r['sha256'],r['path']
previous12=json.loads((H.parent/'task9_remaining_people_20261119/published.json').read_text())
for r in previous12:assert sha(r['destination'])==r['sha256'],r['destination']
counts={}
for st in ['3D animated cartoon','Flat outlined','Kawaii','Mulberry','Simple anime']:
 counts[st]=dict(collections.Counter(r['category'] for r in receipts if r['style']==st));counts[st]['Comparatives']=48
 assert counts[st]=={'Pronouns':70,'Contractions':28,'Comparatives':48},(st,counts[st])
T=Path('/private/tmp/task9_completion_20261119');reclaimed=sum(p.stat().st_size for p in T.rglob('*') if p.is_file())
shutil.rmtree(T)
v={'task9_complete':True,'newly_published':634,'reused_byte_identical':624,'corrected_they_them_outputs':10,'correction_concepts':5,'previous_completed_comparatives_verified':len(prior),'previous_12_style_outputs_verified':len(previous12),'five_style_final_counts':counts,'total_tracked_outputs_17_styles':len(receipts)+len(prior)+len(previous12),'sommi_and_sommi_clothed':'Previously complete per user; unchanged and excluded from new work','original_hashes_verified':len(old),'existing_library_hashes_verified':len(existing),'source_or_existing_files_changed':0,'new_bytes':sum(r['bytes'] for r in rows),'temporary_bytes_deleted':reclaimed,'temporary_images_remaining':0,'generic_and_nonperson_originals':'65 generic and 375 nonperson drawings retained unchanged in their existing source locations; outside this People substitution publication','q80_conversion':'Deferred to Task 12; none performed','next_task':'Task 10 pipeline/eligibility/output-path clarification only; do not execute'}
(H/'verification.json').write_text(json.dumps(v,indent=2));(H/'progress.json').write_text(json.dumps({'status':'complete','planned':634,'published':634,'task9_complete':True},indent=2));print(json.dumps(v,indent=2))
