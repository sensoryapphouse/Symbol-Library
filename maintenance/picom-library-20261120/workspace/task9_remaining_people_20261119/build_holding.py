from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as E,numpy as np
from raster_rig import el,group,make as rig,S
from holding import make as held
from anchors import D
H=Path(__file__).resolve().parent;rows=json.loads((H/'measured_templates.json').read_text());bases=json.loads((H/'bases.json').read_text())
def person(e):return e.get('data-core-style') and e.get('data-pilot-person')
def oldarm(e):return e.tag.endswith('line') and e.get('stroke-width')=='13' and e.get('x1') in ['206','306'] and e.get('y1')=='275'
def annotations(root):
 out=collections.Counter()
 def walk(e):
  t=e.tag.rsplit('}',1)[-1]
  if person(e) or e.get('data-full-style-figure') or t in ['defs','metadata','title','desc'] or oldarm(e):return
  if t in ['path','rect','ellipse','circle','line','polygon','polyline','text','image']:out[(t,json.dumps(e.attrib,sort_keys=True),e.text or '')]+=1
  for c in e:walk(c)
 walk(root);return out
def mat(v):a,b,c,d,e,f=v;return np.array([[a,c,e],[b,d,f],[0,0,1.]])
def tr(m):return 'matrix('+ ' '.join(str(float(m[i,j])) for i,j in [(0,0),(1,0),(0,1),(1,1),(0,2),(1,2)])+')'

# Prevent accidental regeneration of accepted Library outputs.
if (H/'published.json').exists():
 _done={x['output'] for x in json.loads((H/'published.json').read_text())}
 if (H/'holding_outputs.json').exists() and any(x['output'] in _done for x in json.loads((H/'holding_outputs.json').read_text())):raise SystemExit('Published outputs exist; do not regenerate them.')

records=[]
for b in bases:
 for r in rows:
  if r['gender']!=b['gender'] or not r['books']:continue
  root=E.parse(r['source']).getroot();before=annotations(root);people=[e for e in root.iter() if person(e)];book=r['books'][0];bm=mat(book['ctm']);q=book['rect'];corners=np.array([[q['x'],q['y'],1],[q['x']+q['w'],q['y']+q['h'],1]]).T;glob=bm@corners;bc=glob[:2].mean(axis=1)
  nearest=min(range(len(people)),key=lambda i:abs((mat(r['people'][i]['ctm'])@np.array([r['people'][i]['bbox']['x']+r['people'][i]['bbox']['w']/2,0,1]))[0]-bc[0]))
  overlays=[];changes=[];newbook=None
  for i,g in enumerate(people):
   pm=mat(r['people'][i]['ctm']);target=r['people'][i]['bbox'];local=np.linalg.inv(pm)@glob;bx,by=local[:2,0];bw,bh=local[:2,1]-local[:2,0];bookcx=bx+bw/2;bookcy=by+bh/2;prefix=f'person{i}'
   for ch in list(g):g.remove(ch)
   g.set('data-core-style',b['style']);g.set('data-full-style-figure','1')
   if i!=nearest:
    bb=b['bbox'];cfg=D[(b['style'],b['gender'])];s=min(target['h']/(bb[3]-bb[1]),target['w']/(2*max(cfg['cx']-bb[0],bb[2]-cfg['cx'])));tx=target['x']+target['w']/2-s*cfg['cx'];ty=target['y']+target['h']-s*bb[3];defs,body,arms,_=rig(b,'stand',prefix)
   elif (b['style'],b['gender']) in [('Doll','M')]:
    cfg=D[(b['style'],b['gender'])];bb=b['bbox'];cx,cy=cfg['chest'];s=target['h']/(bb[3]-bb[1]);tx=target['x']+target['w']/2-s*cx;ty=target['y']+target['h']-s*bb[3];nw=cfg['chest_width']*1.1;nh=nw*q['h']/q['w'];nativebook=(cx-nw/2,cy-nh/2,nw,nh);bs=nw/q['w'];bookmap=np.array([[bs,0,cx-bs*(q['x']+q['w']/2)],[0,bs,cy-bs*(q['y']+q['h']/2)],[0,0,1.]]);defs,body,arms,_=rig(b,'hold',prefix,nativebook)
   else:
    defs,body,arms,meta=held(b,prefix);bb=meta['bbox'];ball=meta['ball'];cx=(ball[0]+ball[2])/2;cy=(ball[1]+ball[3])/2
    s=target['h']/(bb[3]-bb[1]);tx=target['x']+target['w']/2-s*cx;ty=target['y']+target['h']-s*bb[3];bs=(ball[3]-ball[1]+10)/q['h'];bookmap=np.array([[bs,0,cx-bs*(q['x']+q['w']/2)],[0,bs,cy-bs*(q['y']+q['h']/2)],[0,0,1.]])
   fit=np.array([[s,0,tx],[0,s,ty],[0,0,1.]])
   root.insert(0,defs);body.set('transform',tr(fit));g.append(body)
   if i==nearest:newbook=pm@fit@bookmap
   if arms is not None:
    arms.set('data-full-style-figure','1');arms.set('transform',tr(pm@fit));overlays.append(arms)
   changes.append({'person':i,'holding':i==nearest,'fit':[s,tx,ty]})
  for parent in root.iter():
   for child in list(parent):
    if oldarm(child):parent.remove(child)
  if newbook is not None:
   rect=next(e for e in root.iter() if e.tag.endswith('rect') and e.get('fill')=='#f5c518');parents={c:p for p in root.iter() for c in p};bg=parents[rect];parents[bg].remove(bg);bg.set('transform',tr(newbook));root.append(bg)
  root.extend(overlays)
  assert annotations(root)==before,(b['style'],r['name'])
  root.set('data-style',b['style']);root.set('data-review-status','pending');root.set('data-substitution','own-full-figure-with-held-book');dest=H/'staging'/b['style']/r['category']/(r['name']+'.svg');dest.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
  records.append(dict(r,style=b['style'],base=b['path'],output=str(dest),changes=changes,annotation_primitives=sum(before.values()),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status='pending'))
(H/'holding_outputs.json').write_text(json.dumps(records,indent=2));print('Built',len(records),'held-book outputs; annotation geometry retained.')
