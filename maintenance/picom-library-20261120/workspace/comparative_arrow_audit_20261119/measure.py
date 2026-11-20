import json
from pathlib import Path
import numpy as np
from scipy import ndimage
from audit import render,HERE
inv=json.loads((HERE/'inventory.json').read_text());obs=json.loads((HERE/'observations.json').read_text());output=[];disagree=[]
for r in inv['files']:
 if r['kind']=='reference':continue
 o=obs['styles'][r['style']];n=int(r['id'][1:]);status='not_required_single' if n in o.get('not_required_single',[]) else 'missing' if n in o['missing'] else 'upward' if n in o['upward'] else 'angled_down' if n in o['angled'] else 'down_present'
 im=render(Path(r['path']));a=np.array(im);rgb=a[:,:,:3].astype(float);R,G,B=[rgb[:,:,i] for i in range(3)]
 colour=((G>1.25*R)&(G>1.18*B)&(G>60))|((R>1.5*G)&(R>1.5*B)&(R>90))
 labels,_=ndimage.label(a[:,:,3]>32);cc=[]
 for j,sl in enumerate(ndimage.find_objects(labels),1):
  y,x=sl;w=x.stop-x.start;h=y.stop-y.start;mask=labels[sl]==j;area=int(mask.sum());col=int((colour[sl]&mask).sum())
  if 2<=w<=im.width*.28 and 3<=h<=im.height*.30 and y.start<im.height*.6 and col>=3 and col/max(area,1)>.12:
   cc.append({'bbox':[x.start,y.start,x.stop,y.stop],'width_at_512':w*512/im.width,'height_at_512':h*512/im.height,'coloured_pixels':col,'area':area})
 r=dict(r,visual_status=status,arrow_candidates=cc)
 output.append(r)
 if status in ('upward','angled_down','down_present') and len(cc)!=1 or status=='missing' and cc:disagree.append({'id':r['id'],'style':r['style'],'name':r['name'],'status':status,'candidates':cc})
(HERE/'measured.json').write_text(json.dumps(output,indent=2));(HERE/'measurement_followups.json').write_text(json.dumps(disagree,indent=2))
print('Coverage',len(output),'styles',len(obs['styles']));print('Followups',json.dumps(disagree))
from collections import Counter
print('Statuses',Counter(r['visual_status'] for r in output))
print('One-component-arrow height stats',np.percentile([r['arrow_candidates'][0]['height_at_512'] for r in output if r['visual_status']=='down_present' and len(r['arrow_candidates'])==1],[0,10,50,90,100]))
