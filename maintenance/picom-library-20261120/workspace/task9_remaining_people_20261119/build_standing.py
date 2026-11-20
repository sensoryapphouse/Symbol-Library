from pathlib import Path
import json,base64,hashlib,collections,xml.etree.ElementTree as E
from raster_rig import el,group,S
from anchors import D
H=Path(__file__).resolve().parent
if (H/'published.json').exists():raise SystemExit('Published standing work exists. Do not regenerate or duplicate it.')
rows=json.loads((H/'measured_templates.json').read_text());bases=json.loads((H/'bases.json').read_text())
def person(e):return e.get('data-comparative-person') or (e.get('data-core-style') and e.get('data-pilot-person'))
def annotations(root):
 out=collections.Counter()
 def walk(e):
  t=e.tag.rsplit('}',1)[-1]
  if person(e) or e.get('data-full-style-figure') or t in ['defs','metadata','title','desc']:return
  if t in ['path','rect','ellipse','circle','line','polygon','polyline','text','image']:out[(t,json.dumps(e.attrib,sort_keys=True),e.text or '')]+=1
  for c in e:walk(c)
 walk(root);return out
records=[]
for b in bases:
 for r in rows:
  if r['gender']!=b['gender'] or r['books'] or r['category']=='Comparatives':continue
  root=E.parse(r['source']).getroot();before=annotations(root);people=[e for e in root.iter() if person(e)];assert len(people)==r['figures']
  defs=el('defs');defs.append(el('image',{'id':'own-character','width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(Path(b['path']).read_bytes()).decode()}));root.insert(0,defs)
  bb=b['bbox'];cx=D[(b['style'],b['gender'])]['cx'];fits=[]
  for i,g in enumerate(people):
   target=r['people'][i]['bbox'];s=min(target['h']/(bb[3]-bb[1]),target['w']/(2*max(cx-bb[0],bb[2]-cx)))
   tx=target['x']+target['w']/2-s*cx;ty=target['y']+target['h']-s*bb[3]
   for ch in list(g):g.remove(ch)
   g.set('data-core-style',b['style']);g.set('data-full-style-figure','1');g.append(el('use',{'href':'#own-character','transform':f'matrix({s:.9f} 0 0 {s:.9f} {tx:.9f} {ty:.9f})'}));fits.append([s,tx,ty])
  assert annotations(root)==before
  root.set('data-style',b['style']);root.set('data-substitution','own-complete-figure-embedded-webp');root.set('data-review-status','pending');root.set('data-edit-date','2026-11-19')
  dest=H/'staging'/b['style']/r['category']/(r['name']+'.svg');dest.parent.mkdir(parents=True,exist_ok=True)
  E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
  records.append(dict(r,style=b['style'],base=b['path'],output=str(dest),fits=fits,annotation_primitives=sum(before.values()),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status='pending'))
(H/'standing_outputs.json').write_text(json.dumps(records,indent=2));print('Built',len(records),'standing outputs; all annotation primitives unchanged.')
