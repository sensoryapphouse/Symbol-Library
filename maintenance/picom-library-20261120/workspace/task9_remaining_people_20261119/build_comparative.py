from pathlib import Path
import json,base64,hashlib,collections,xml.etree.ElementTree as E
from raster_rig import el,group,S
from anchors import D
H=Path(__file__).resolve().parent;rows=json.loads((H/'measured_templates.json').read_text());bases=json.loads((H/'bases.json').read_text());metrics=json.loads((H.parent/'task9_full_figures_20261119/measurements.json').read_text())
def annotations(root):
 c=collections.Counter()
 def walk(e):
  t=e.tag.rsplit('}',1)[-1]
  if e.get('data-full-style-figure') or t in ['defs','metadata','title','desc']:return
  if t in ['path','ellipse','circle','rect','polygon','polyline','line']:c[(t,json.dumps(e.attrib,sort_keys=True))]+=1
  for ch in e:walk(ch)
 walk(root);return c

# Prevent accidental regeneration of accepted Library outputs.
if (H/'published.json').exists():
 _done={x['output'] for x in json.loads((H/'published.json').read_text())}
 if (H/'comparative_outputs.json').exists() and any(x['output'] in _done for x in json.loads((H/'comparative_outputs.json').read_text())):raise SystemExit('Published outputs exist; do not regenerate them.')

out=[]
standing={'cleaner','cleanest','dirtier','dirtiest','drier','driest','wetter','wettest','shorter (1)','shortest','taller','tallest'}
for b in bases:
 for r in rows:
  if r['category']!='Comparatives' or r['gender']!=b['gender'] or r['concept'] not in standing:continue
  root=E.parse(r['source']).getroot();before=annotations(root);defs=el('defs');defs.append(el('image',{'id':'own-character','width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(Path(b['path']).read_bytes()).decode()}));root.insert(0,defs)
  key='kawaii_'+r['concept'].replace(' (1)','').replace(' ','_')+'_'+r['gender'].lower();old=metrics[key];people=[e for e in root.iter() if e.get('data-comparative-person')];fits=[];bb=b['bbox'];cfg=D[(b['style'],b['gender'])]
  for i,g in enumerate(people):
   target=old[i]['body'];s=target['h']/(bb[3]-bb[1]);tx=target['x']+target['w']/2-s*cfg['cx'];ty=target['y']+target['h']-s*bb[3]
   full=next(e for e in g if e.get('data-full-style-figure'));index=list(g).index(full);g.remove(full);new=group([el('use',{'href':'#own-character'})],f'matrix({s} 0 0 {s} {tx} {ty})');new.set('data-full-style-figure','1');g.insert(index,new)
   for w in g:
    kind=w.get('data-preserved-prop','')
    if kind=='dirt on clothing':
     e=next(iter(w));x=float(e.get('cx'));y=float(e.get('cy'));top=old[i]['top'];leg=y>top['y']+top['h'];nx=max(.2,min(.8,(x-top['x'])/top['w']));ny=max(.15,min(.85,(y-top['y'])/top['h']))
     px=cfg['cx']+(nx-.5)*cfg['chest_width']*.6;py=cfg['chest'][1]+(ny-.5)*55
     if leg:px=cfg['cx']-20;py=cfg['hip']+40
     w.set('transform',f'translate({tx+s*px} {ty+s*py}) scale(.7) translate({-x} {-y})')
    elif kind=='odour beside head':w.set('transform',f'translate({max(0,tx+s*bb[2]+12-322)} 0)')
   fits.append([s,tx,ty])
  assert annotations(root)==before
  root.set('data-style',b['style']);root.set('data-review-status','pending');root.set('data-substitution','own-complete-style-figure');dest=H/'staging'/b['style']/r['category']/(r['name']+'.svg');dest.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
  out.append(dict(r,style=b['style'],base=b['path'],output=str(dest),fits=fits,annotation_primitives=sum(before.values()),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status='pending'))
(H/'comparative_outputs.json').write_text(json.dumps(out,indent=2));print('Built',len(out),'standing comparatives, annotations preserved.')
