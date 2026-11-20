from pathlib import Path
import json,hashlib,os,datetime,xml.etree.ElementTree as E
H=Path(__file__).resolve().parent;lib=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');f=H/'published.json';published=json.loads(f.read_text()) if f.exists() else [];done={x['output'] for x in published}
sources=json.loads((H/'sources.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v['sha256'] for p,v in sources.items()),'Original source changed'
log=json.loads((H/'visual_review_log.json').read_text());accepted={p for a in log if a['status']=='accepted' for p in a['outputs']};rows=[]
for k in ['standing','holding','comparative','age','action']:
 p=H/(k+'_outputs.json')
 if p.exists():rows+=json.loads(p.read_text())
for r in rows:
 if r['output'] not in accepted or r['output'] in done:continue
 src=Path(r['output']);assert hashlib.sha256(src.read_bytes()).hexdigest()==r['sha256'];dst=lib/r['style']/r['category']/(r['name']+'.svg');assert not dst.exists(),str(dst)
 dst.parent.mkdir(parents=True,exist_ok=True);os.rename(src,dst);assert hashlib.sha256(dst.read_bytes()).hexdigest()==r['sha256'];published.append(dict(r,destination=str(dst),status='accepted',published_at=datetime.datetime.now().astimezone().isoformat()));f.write_text(json.dumps(published,indent=2))
# Delete only reviewed temporary pages whose entire contents have been published.
done={x['output'] for x in published};removed=0
for p in log:
 if all(x in done for x in p['outputs']):
  q=Path(p['sheet'])
  if q.exists() and str(q).startswith('/private/tmp/task9_remaining_people_20261119/'):
   removed+=q.stat().st_size;q.unlink()
for d in sorted((H/'staging').rglob('*'),key=lambda x:len(x.parts),reverse=True):
 if d.is_dir() and not any(d.iterdir()):d.rmdir()
progress=json.loads((H/'progress.json').read_text());progress.update(built=len(rows),accepted=len(accepted),published=len(published),updated_at=datetime.datetime.now().astimezone().isoformat(),temporary_bytes_deleted_this_batch=removed)
progress['style_counts']={st:sum(x['style']==st for x in published) for st in json.loads((H/'scope.json').read_text())['styles']};(H/'progress.json').write_text(json.dumps(progress,indent=2));print('Published',len(published),'total; deleted',removed,'bytes of reviewed sheets; source images unchanged.')
