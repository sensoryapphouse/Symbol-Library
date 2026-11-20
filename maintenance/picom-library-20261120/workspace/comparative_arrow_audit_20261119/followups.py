from pathlib import Path
import json,math
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw
from audit import HERE,TMP,FONT,SMALL,render
rows=json.loads((HERE/'measured.json').read_text());obs=json.loads((HERE/'observations.json').read_text());byid={r['id']:r for r in rows};follow=json.loads((HERE/'measurement_followups.json').read_text())
ids={r['id'] for r in follow}
for o in obs['styles'].values():ids.update(f'A{x:04}' for x in o.get('tiny_followup',[]))
for r in rows:
 if r['visual_status'] in ('down_present','upward','angled_down'):
  a=np.array(render(Path(r['path'])));R,G,B=[a[:,:,i].astype(float) for i in range(3)]
  mask=(a[:,:,3]>32)&(((G>1.25*R)&(G>1.18*B)&(G>60))|((R>1.8*G)&(R>1.8*B)&(R>90)))
  labels,_=ndimage.label(mask);candidates=[]
  for j,sl in enumerate(ndimage.find_objects(labels),1):
   y,x=sl;w=x.stop-x.start;h=y.stop-y.start;area=int((labels[sl]==j).sum())
   if 3<=w<=110 and 5<=h<=130 and y.start<300 and area>=10:candidates.append(dict(bbox=[x.start,y.start,x.stop,y.stop],area=area))
  if len(r['arrow_candidates'])==1:r['arrow_measurement']=dict(r['arrow_candidates'][0],method='isolated alpha component')
  else:
   r['colour_core_candidates']=candidates
   if candidates:
    core=min(candidates,key=lambda c:c['bbox'][1]);x0,y0,x1,y1=core['bbox'];r['arrow_measurement']=dict(core,width_at_512=x1-x0,height_at_512=y1-y0,method='colour core; outline excluded; native follow-up')
  m=r.get('arrow_measurement')
  if m and (m['height_at_512']<40 or m['width_at_512']<24):ids.add(r['id'])
ids=sorted(ids)
for page in range(math.ceil(len(ids)/4)):
 ss=ids[page*4:(page+1)*4];sheet=Image.new('RGB',(1060,60+math.ceil(len(ss)/2)*360),'#e5edf5');d=ImageDraw.Draw(sheet);d.text((10,8),f'Native upper-region follow-ups {page+1}',font=FONT,fill='black')
 for j,id in enumerate(ss):
  r=byid[id];im=render(Path(r['path']));x=(j%2)*530;y=60+(j//2)*360
  part=im.crop((0,0,512,310));sheet.paste(part,(x+9,y),part)
  d.text((x+9,y+311),id+' '+r['style']+' / '+r['name'],font=SMALL,fill='black')
  m=r.get('arrow_measurement');d.text((x+9,y+331),str(m['bbox'] if m else 'no isolated candidate')+' '+r['visual_status'],font=SMALL,fill='black')
 sheet.save(TMP/f'followup_{page+1}.jpg',quality=94)
(HERE/'measured.json').write_text(json.dumps(rows,indent=2));(HERE/'native_followup_ids.json').write_text(json.dumps(ids,indent=2))
print('Follow-up pages',math.ceil(len(ids)/4),'files',len(ids));print('Under proposed size floor',[(r['id'],r['style'],r['name'],r['arrow_measurement']['height_at_512'],r['arrow_measurement']['width_at_512']) for r in rows if r.get('arrow_measurement') and (r['arrow_measurement']['height_at_512']<40 or r['arrow_measurement']['width_at_512']<24)])
