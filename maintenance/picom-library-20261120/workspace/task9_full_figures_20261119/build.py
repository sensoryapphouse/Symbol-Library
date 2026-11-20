from pathlib import Path
if Path(__file__).with_name('published.json').exists():
 raise SystemExit('This run is published. Do not regenerate staging or replace its source evidence.')
from pathlib import Path
import json,copy,hashlib,collections,io,subprocess,xml.etree.ElementTree as E
from PIL import Image
from rig import make,el,S
H=Path(__file__).resolve().parent;rows=json.loads((H/'inputs.json').read_text());M=json.loads((H/'measurements.json').read_text());BM=json.loads((H.parent/'task9_full_figure_preview_20261119/measurements.json').read_text())['bases'];rigs=json.loads((H/'rig_manifest.json').read_text());cache={}
def prop_counts(root):
 c=collections.Counter()
 def walk(e,person=False):
  tag=e.tag.rsplit('}',1)[-1]
  if tag in ['defs','metadata','title','desc'] or e.get('data-full-style-figure'):return
  if person and e.get('data-part'):return
  if tag in ['path','ellipse','circle','rect','polygon','polyline','line']:c[(tag,json.dumps(dict(e.attrib),sort_keys=True))]+=1
  for ch in e:walk(ch,person or bool(e.get('data-comparative-person')))
 walk(root);return c
for rm in rigs:
 key=(rm['style'],rm['gender'],rm['pose'])
 if rm['pose']=='stand':bbox=BM[rm['style']][rm['gender']]['full']
 else:
  im=Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','900','-h','1040',rm['path']]))).convert('RGBA');b=im.getchannel('A').getbbox();bbox={'x':b[0]/2-100,'y':b[1]/2-20,'w':(b[2]-b[0])/2,'h':(b[3]-b[1])/2}
 cache[key]=dict(rm,bbox=bbox)
records=[]
for r in rows:
 st,gender,concept=r['style'],r['gender'],r['concept'];root=E.parse(r['source']).getroot();before=prop_counts(root);people=[e for e in root.iter() if e.get('data-comparative-person')];changes=[]
 for i,g in enumerate(people):
  pose='stand'
  if concept in ['faster','fastest','slower','slowest']:pose='fast' if i==0 else 'slow'
  if concept in ['stronger','strongest','weaker','weakest']:pose='strong' if i==0 else 'weak'
  if concept in ['older','oldest','younger','youngest'] and i==1:pose='old'
  rm=cache[(st,gender,pose)];full=rm['bbox'];body=M[r['id']][i]['body'];scale=body['h']/full['h'];tx=body['x']+body['w']/2-scale*(full['x']+full['w']/2);ty=body['y']+body['h']-scale*(full['y']+full['h']);new,grip=make(r['base'],st,gender,pose)
  new.set('transform',f'matrix({scale:.9f} 0 0 {scale:.9f} {tx:.9f} {ty:.9f})');new.set('data-full-style-figure','1');new.set('data-pose',pose)
  head=next(e for e in g if e.get('data-part')=='head');new.set('id',head.get('id',f'h{i+1}'));new.set('data-fig',head.get('data-fig',''))
  ids={e.get('id'):f'figure{i+1}-'+e.get('id') for e in new.iter() if e.get('id') and e is not new}
  for e in new.iter():
   if e is not new and e.get('id'):e.set('id',ids[e.get('id')])
   for k,v in list(e.attrib.items()):
    for oldid,newid in ids.items():
     v=v.replace('url(#'+oldid+')','url(#'+newid+')')
     if k.endswith('href') and v=='#'+oldid:v='#'+newid
    e.set(k,v)
  props=[e for e in g if not e.get('data-part')]
  for ch in list(g):g.remove(ch)
  g.append(new);moved=[];metrics=BM[st][gender];bs=metrics['shirt'];bt=metrics['trousers'];old=M[r['id']][i]
  def addprop(e,transform,kind):
   w=el('g',{'data-preserved-prop':kind,'transform':transform});w.append(e);g.append(w);moved.append(kind)
  for e in props:
   if e.tag==f'{{{S}}}ellipse' and e.get('fill')=='#7a4a24':
    x=float(e.get('cx'));y=float(e.get('cy'));top=old['top'];leg=y>top['y']+top['h']
    if leg:targetx=tx+scale*(bt['x']+bt['w']*.35);targety=ty+scale*(bt['y']+bt['h']*.28)
    else:
     nx=max(.2,min(.8,(x-top['x'])/top['w']));ny=max(.18,min(.8,(y-top['y'])/top['h']));central=.75 if st=='3D animated cartoon' and gender=='F' else .58
     targetx=tx+scale*(bs['x']+bs['w']*(.5+(nx-.5)*central));targety=ty+scale*(bs['y']+bs['h']*ny)
    addprop(e,f'translate({targetx:.6f} {targety:.6f}) scale(.78) translate({-x} {-y})','dirt on clothing')
   elif e.get('stroke')=='#7a8b53':
    right=tx+scale*(full['x']+full['w']);dx=max(0,right+12-322);addprop(e,f'translate({dx:.6f} 0)','odour beside head')
   elif concept in ['wetter','wettest','drier','driest'] and i==1 and ((e.tag==f'{{{S}}}path' and e.get('fill')=='#7ec8f0') or (e.tag==f'{{{S}}}line' and e.get('x1')=='120' and e.get('y1')=='132')):
    addprop(e,'translate(0 -65)','crossed-out drop clear of head')
   elif pose=='old' and e.get('stroke')=='#9a6a3a':
    gx=tx+scale*grip[0];gy=ty+scale*grip[1];sy=(body['y']+body['h']-2-gy)/(455-217);sx=1;dx=gx-308;dy=gy-sy*217
    addprop(e,f'matrix(1 0 0 {sy:.8f} {dx:.8f} {dy:.8f})','walking stick aligned with hand and ground')
   else:g.append(e)
  changes.append({'person':i+1,'pose':pose,'scale':scale,'translation':[tx,ty],'prop_adjustments':moved})
 root.set('data-substitution','complete-style-figures-with-semantic-poses');root.set('data-review-status','awaiting-output-review');root.set('data-edit-date','2026-11-19')
 after=prop_counts(root);assert before==after,(r['id'],before-after,after-before)
 ids=[e.get('id') for e in root.iter() if e.get('id')];assert len(ids)==len(set(ids)),r['id']
 dest=H/'outputs'/st/r['filename'];dest.parent.mkdir(parents=True,exist_ok=True);E.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True)
 records.append(dict(r,output=str(dest),changes=changes,annotation_primitives=sum(before.values()),missing_annotations=0,extra_annotations=0))
hashes=json.loads((H/'source_hashes.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
(H/'outputs.json').write_text(json.dumps(records,indent=2));(H/'rig_measurements.json').write_text(json.dumps(list(cache.values()),indent=2))
print('Built 96 SVGs. All original semantic primitives retained; 100 source hashes unchanged.')
