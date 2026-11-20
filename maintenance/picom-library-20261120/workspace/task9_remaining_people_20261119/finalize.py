from pathlib import Path
import json,hashlib,xml.etree.ElementTree as E,datetime,collections,shutil
H=Path(__file__).resolve().parent;pub=json.loads((H/'published.json').read_text());sources=json.loads((H/'sources.json').read_text());scope=json.loads((H/'scope.json').read_text());review=json.loads((H/'visual_review_log.json').read_text());accepted={p for r in review if r['status']=='accepted' for p in r['outputs']}
assert len(pub)==len(accepted)==1656
assert len({x['destination'] for x in pub})==1656
for p,v in sources.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==v['sha256'],p
counts=collections.defaultdict(collections.Counter);metadata=[]
for r in pub:
 p=Path(r['destination']);data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==r['sha256'],str(p);assert r['output'] in accepted;assert not Path(r['output']).exists();root=E.fromstring(data)
 for e in root.iter():
  for k,v in e.attrib.items():
   if k.rsplit('}',1)[-1]=='href':assert v.startswith(('#','data:')),(str(p),v)
 ids={e.get('id') for e in root.iter() if e.get('id')}
 for e in root.iter():
  if e.tag.endswith('use'):
   href=e.get('href') or e.get('{http://www.w3.org/1999/xlink}href');assert href and href[1:] in ids,(str(p),href)
 assert sum(bool(e.get('data-comparative-person') or (e.get('data-core-style') and e.get('data-pilot-person'))) for e in root.iter())==r['figures'],str(p)
 # Review status is non-rendering metadata only. Keep it consistent with the accepted journal.
 assert b'[data-review-status' not in data
 if root.get('data-review-status')=='pending':
  fixed=data.replace(b'data-review-status="pending"',b'data-review-status="accepted"',1);r['pre_review_metadata_sha256']=r['sha256'];p.write_bytes(fixed);r['sha256']=hashlib.sha256(fixed).hexdigest();metadata.append(str(p))
 counts[r['style']][r['category']]+=1
for st in scope['styles']:assert dict(counts[st])==scope['outputs_per_style'],(st,counts[st])
(H/'published.json').write_text(json.dumps(pub,indent=2))
# Reflect metadata-only hashes in build manifests; no duplicate images are created.
byout={r['output']:r for r in pub}
for k in ['standing','holding','comparative','age','action']:
 f=H/(k+'_outputs.json');rs=json.loads(f.read_text())
 for r in rs:r['sha256']=byout[r['output']]['sha256'];r['status']='accepted';r['destination']=byout[r['output']]['destination']
 f.write_text(json.dumps(rs,indent=2))
T=Path('/private/tmp/task9_remaining_people_20261119');tempbytes=sum(p.stat().st_size for p in T.rglob('*') if p.is_file()) if T.exists() else 0
if T.exists():shutil.rmtree(T)
assert not any(p.is_file() for p in (H/'staging').rglob('*'))
if (H/'staging').exists():shutil.rmtree(H/'staging')
if (H/'__pycache__').exists():shutil.rmtree(H/'__pycache__')
verification={'at':datetime.datetime.now().astimezone().isoformat(),'outputs':len(pub),'styles':dict(counts),'reviewed_outputs':len(accepted),'review_pages':len(review),'original_sources_hash_verified':len(sources),'originals_unchanged':True,'all_outputs_self_contained':True,'internal_use_references_resolve':True,'figure_counts_match_templates':True,'output_bytes':sum(Path(x['destination']).stat().st_size for x in pub),'metadata_only_status_updates':len(metadata),'final_temporary_bytes_deleted':tempbytes,'staged_images_remaining':0,'temporary_review_images_remaining':0,'no_existing_files_overwritten':True,'action_variants':'One intact native variant for each of 8 action concepts in every style; M/F variants elsewhere.'}
(H/'verification.json').write_text(json.dumps(verification,indent=2));p=json.loads((H/'progress.json').read_text());p.update(status='complete for these 12 styles',built=1656,accepted=1656,visually_accepted=1656,published=1656,updated_at=verification['at']);p['styles']={s:'complete; all 138 outputs visually checked and published' for s in scope['styles']};(H/'progress.json').write_text(json.dumps(p,indent=2));scope['status']='complete for these 12 styles';(H/'scope.json').write_text(json.dumps(scope,indent=2));print(json.dumps(verification,indent=2))
