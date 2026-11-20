from pathlib import Path
import json,base64,hashlib,collections,xml.etree.ElementTree as E
from PIL import Image
from raster_rig import el,group
H=Path(__file__).resolve().parent
rows=json.loads((H/'measured_templates.json').read_text());styles=json.loads((H/'scope.json').read_text())['styles'];poses={(x['style'],x['pose']):x['path'] for x in json.loads((H/'pose_candidates.json').read_text())};metrics=json.loads((H.parent/'task9_full_figures_20261119/measurements.json').read_text())
assert not any(x['category']=='Comparatives' and x['concept'] in ['faster','fastest','slower','slowest','stronger','strongest','weaker','weakest'] for x in json.loads((H/'published.json').read_text()))
def annotations(root):
 c=collections.Counter()
 def walk(e):
  t=e.tag.rsplit('}',1)[-1]
  if e.get('data-full-style-figure') or t in ['defs','metadata','title','desc']:return
  if t in ['path','ellipse','circle','rect','polygon','polyline','line']:c[(t,json.dumps(e.attrib,sort_keys=True))]+=1
  for ch in e:walk(ch)
 walk(root);return c
out=[]
for st in styles:
 for r in rows:
  if r['category']!='Comparatives' or r['gender']!='M' or r['concept'] not in ['faster','fastest','slower','slowest','stronger','strongest','weaker','weakest']:continue
  root=E.parse(r['source']).getroot();before=annotations(root);people=[e for e in root.iter() if e.get('data-comparative-person')];old=metrics['kawaii_'+r['concept']+'_m'];defs=el('defs');root.insert(0,defs);paths=[];fits=[]
  for i,g in enumerate(people):
   pose=(['run','walk'] if r['concept'] in ['faster','fastest','slower','slowest'] else ['strong','weak'])[i];p=Path(poses[st,pose]);im=Image.open(p).convert('RGBA');bb=im.getchannel('A').getbbox();target=old[i]['body'];maxw=235 if pose in ['strong','weak'] else (180 if pose=='run' else 145);s=min(target['h']/(bb[3]-bb[1]),maxw/(bb[2]-bb[0]));tx=target['x']+target['w']/2-s*(bb[0]+bb[2])/2;ty=target['y']+target['h']-s*bb[3]
   defs.append(el('image',{'id':f'own-character{i}','width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode()}));full=next(e for e in g if e.get('data-full-style-figure'));index=list(g).index(full);g.remove(full);new=group([el('use',{'href':f'#own-character{i}'})],f'matrix({s} 0 0 {s} {tx} {ty})');new.set('data-full-style-figure','1');g.insert(index,new);g.set('data-core-style',st);g.set('data-gender','native-source-variant');fits.append([s,tx,ty]);paths.append(str(p))
  assert annotations(root)==before
  root.set('data-style',st);root.set('data-review-status','pending');root.set('data-substitution','own-intact-native-action-poses');dest=H/'staging'/st/r['category']/(r['name']+'.svg');dest.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
  out.append(dict(r,gender='native',style=st,base=paths[0],pose_sources=paths,output=str(dest),fits=fits,annotation_primitives=sum(before.values()),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),status='pending'))
(H/'action_outputs.json').write_text(json.dumps(out,indent=2));print('Built',len(out),'action comparisons using intact native poses, one variant per style.')
