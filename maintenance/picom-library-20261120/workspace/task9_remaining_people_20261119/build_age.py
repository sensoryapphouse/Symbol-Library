from pathlib import Path
import json,base64,hashlib,collections,xml.etree.ElementTree as E
from PIL import Image
from raster_rig import el,group,S
from anchors import D
H=Path(__file__).resolve().parent;rows=json.loads((H/'measured_templates.json').read_text());bases=json.loads((H/'bases.json').read_text());metrics=json.loads((H.parent/'task9_full_figures_20261119/measurements.json').read_text());lib=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
GRIP={'Basic':[(170,298),(322,327)],'Classic flat TV cartoon':[(316,288),(308,290)],'Clay plasticine':[(317,295),(314,300)],'Doll':[(322,310),(305,320)],'Friendly aliens':[(312,326),(303,317)],'Monkey':[(288,335),(285,331)],'Monster':[(331,327),(170,326)],'Robot':[(324,319),(310,330)],'Soccer player':[(331,316),(306,306)],'Teddy bear':[(329,300),(309,322)],'Wizard':[(326,287),(310,310)],'Wood':[(345,313),(305,318)]}
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
 if (H/'age_outputs.json').exists() and any(x['output'] in _done for x in json.loads((H/'age_outputs.json').read_text())):raise SystemExit('Published outputs exist; do not regenerate them.')

out=[]
for b in bases:
 for r in rows:
  if r['category']!='Comparatives' or r['gender']!=b['gender'] or r['concept'] not in ['older','oldest','younger','youngest']:continue
  root=E.parse(r['source']).getroot();before=annotations(root);people=[e for e in root.iter() if e.get('data-comparative-person')];key='kawaii_'+r['concept']+'_'+r['gender'].lower();old=metrics[key];defs=el('defs');root.insert(0,defs);fits=[];paths=[]
  for i,g in enumerate(people):
   p=Path(b['path']) if i==0 else lib/b['style']/'People & Relationships/People - Roles and Relationships'/('old '+('man' if b['gender']=='M' else 'woman')+'.webp');im=Image.open(p).convert('RGBA');bb=im.getchannel('A').getbbox();cx=D[(b['style'],b['gender'])]['cx'] if i==0 else (bb[0]+bb[2])/2;target=old[i]['body'];s=target['h']/(bb[3]-bb[1]);tx=target['x']+target['w']/2-s*cx;ty=target['y']+target['h']-s*bb[3];defs.append(el('image',{'id':f'own-character{i}','width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode()}));full=next(e for e in g if e.get('data-full-style-figure'));index=list(g).index(full);g.remove(full);new=group([el('use',{'href':f'#own-character{i}'})],f'matrix({s} 0 0 {s} {tx} {ty})');new.set('data-full-style-figure','1');g.insert(index,new)
   if i==1:
    for w in g:
     if w.get('data-preserved-prop')=='walking stick aligned with hand and ground':
      gx,gy=GRIP[b['style']][0 if b['gender']=='M' else 1];px=tx+s*gx;py=ty+s*gy;sy=(ty+s*(bb[3]-3)-py)/(455-217);w.set('transform',f'matrix({s*.5} 0 0 {sy} {px-308*s*.5} {py-217*sy})')
   fits.append([s,tx,ty]);paths.append(str(p))
  assert annotations(root)==before
  root.set('data-style',b['style']);root.set('data-review-status','pending');root.set('data-substitution','own-full-young-and-older-figures');dest=H/'staging'/b['style']/r['category']/(r['name']+'.svg');dest.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
  out.append(dict(r,style=b['style'],base=b['path'],pose_sources=paths,output=str(dest),fits=fits,annotation_primitives=sum(before.values()),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status='pending'))
(H/'age_outputs.json').write_text(json.dumps(out,indent=2));print('Built',len(out),'age comparisons using intact native older figures.')
