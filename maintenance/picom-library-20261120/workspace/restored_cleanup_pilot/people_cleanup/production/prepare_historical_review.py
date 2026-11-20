#!/usr/bin/env python3
"""Render bounded, hash-bound evidence for existing historical lossless outputs only."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,hashlib,io,json
from pathlib import Path
from common import HERE,atomic_json,digest,image_worker,read,utc
DEST=HERE/'historical_output_review'
REVIEWER='historical_lossless_output_review_agent:worthwhile_final_20261104'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ids',nargs='+');ap.add_argument('--record');ap.add_argument('--safety',choices=['clear','unsafe','uncertain']);ap.add_argument('--reason');ap.add_argument('--prune',nargs='+');args=ap.parse_args();DEST.mkdir(exist_ok=True)
 resolution=read(HERE/'historical_resolution.json');rows={r['historical_id']:r for r in resolution['records'] if r['resolution']=='needs_new_output_review'};manifest_path=DEST/'evidence_manifest.json';manifest=read(manifest_path) if manifest_path.exists() else {'images':{},'resolution_sha256':digest(HERE/'historical_resolution.json')};assert manifest['resolution_sha256']==digest(HERE/'historical_resolution.json')
 if args.record:
  id=args.record;e=manifest['images'][id];r=rows[id];assert args.safety and args.reason;assert digest(r['source'])==e['source_sha256'] and digest(r['candidate_lossless_path'])==e['output_sha256'];assert all(digest(v['path'])==v['sha256'] for v in e['evidence']);record={'id':id,'production_source_id':r['production_source_id'],'source':r['source'],'source_sha256':e['source_sha256'],'candidate_lossless_path':r['candidate_lossless_path'],'output_sha256':e['output_sha256'],'reviewer':REVIEWER,'actually_viewed':True,'full_and_allregions_checked':True,'safety':args.safety,'worthwhile_policy':'Preserve already-reviewed clear/partial/minor legacy improvement; no retroactive256minimum.','reason':args.reason,'reviewed_utc':utc(),'proposed_delivery':'cleaned' if args.safety=='clear' else 'original','proposed_path':r['candidate_lossless_path'] if args.safety=='clear' else r['source'],'proposed_sha256':e['output_sha256'] if args.safety=='clear' else e['source_sha256'],'evidence':e}
  f=DEST/'records'/f'{id}.json';atomic_json(f,record);aggregate=read(DEST/'reviews.json') if (DEST/'reviews.json').exists() else {'reviewer':REVIEWER,'images':[]};byid={q['id']:q for q in aggregate['images']};assert id not in byid,f'{id} already reviewed';byid[id]=record;aggregate['images']=list(byid.values());atomic_json(DEST/'reviews.json',aggregate);print(id,args.safety);return
 if args.prune:
  log=read(DEST/'pruned_evidence.json') if (DEST/'pruned_evidence.json').exists() else {'files':[]}
  for id in args.prune:
   assert (DEST/'records'/f'{id}.json').exists()
   for e in manifest['images'][id]['evidence']:
    f=Path(e['path'])
    if f.exists():assert digest(f)==e['sha256'];f.unlink();log['files'].append(dict(e,id=id,pruned_utc=utc(),regenerable=True))
  atomic_json(DEST/'pruned_evidence.json',log);return
 assert args.ids and len(args.ids)<=12,'Render1–12 explicit IDs'
 with image_worker():
  import numpy as np
  from PIL import Image,ImageDraw
  from scipy import ndimage as ndi
  def checker(w,h):
   a=Image.new('RGB',(w,h),'#f8f8f8');d=ImageDraw.Draw(a)
   for y in range(0,h,12):
    for x in range(0,w,12):
     if (x//12+y//12)%2:d.rectangle((x,y,x+11,y+11),fill='#d2d2d2')
   return a
  def panel(a,b,label,backgrounds=True):
   w,h=a.size;head=48;c=Image.new('RGB',(max(1024,w*2),h*(2 if backgrounds else 1)+head),'white');d=ImageDraw.Draw(c);d.text((3,3),label,fill='black');d.text((3,23),'BEFORE left / AFTER right; checker top / purple bottom',fill='black')
   for j,bg in enumerate([checker(w,h),Image.new('RGB',(w,h),'#78658d')] if backgrounds else [Image.new('RGB',(w,h),'#78658d')]):
    for k,im in enumerate([a,b]):o=bg.copy();o.paste(im,(0,0),im);c.paste(o,(k*w,head+j*h))
   return c
  live=sum(f.stat().st_size for f in DEST.rglob('*.png') if not f.name.endswith('_delta_mask.png'));ready=[]
  for id in args.ids:
   r=rows[id];assert digest(r['source'])==r['source_sha256'];assert digest(r['candidate_lossless_path'])==r['candidate_lossless_current_sha256'];source=Image.open(r['source']).convert('RGBA');after=Image.open(r['candidate_lossless_path']).convert('RGBA');assert source.size==after.size;result=read(Path(r['candidate_lossless_path']).parent/'result.json');a=np.asarray(source);b=np.asarray(after);delta=np.any(a!=b,axis=2);assert delta.any() and int(delta.sum())==r['historical_changed_pixels'];w,h=source.size
   label=f"{id} | {result['style']} | {result['concept']} | {r['source_sha256'][:10]} > {r['candidate_lossless_current_sha256'][:10]}";panels=[('full',panel(source,after,label))]
   if max(source.size)>512:panels.append(('normal',panel(source.resize((512,512),Image.Resampling.LANCZOS),after.resize((512,512),Image.Resampling.LANCZOS),label+' normal512')))
   regions=[];union=np.zeros(delta.shape,bool)
   for n,reg in enumerate(result['decision'].get('regions',[]),1):
    x0,y0,x1,y1=reg['roi'];union[y0:y1,x0:x1]=True;regions.append({'name':reg['name'],'roi':reg['roi'],'basis':'saved_individual_source_decision'})
   outside=delta&~union
   if outside.any():
    yy,xx=np.where(outside);regions.append({'name':'ALL actual changed pixels outside saved ROIs','roi':[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1],'basis':'actual_decoded_RGBA_delta_outside_saved_ROIs','outside_changed_pixels':int(outside.sum())})
   coverage=np.zeros(delta.shape,bool)
   for n,reg in enumerate(regions,1):
    x0,y0,x1,y1=reg['roi'];margin=max(8,round(max(w,h)*.018));box=[max(0,x0-margin),max(0,y0-margin),min(w,x1+margin),min(h,y1+margin)];coverage[box[1]:box[3],box[0]:box[2]]=True;reg['crop_box']=box;reg['kind']=f'region{n:02}';panels.append((reg['kind'],panel(source.crop(box),after.crop(box),label+' | '+reg['name'])))
   assert np.all(coverage[delta]);blobs=[]
   for kind,im in panels:
    stream=io.BytesIO();im.save(stream,format='PNG');blobs.append((kind,stream.getvalue(),im.size))
   size=sum(len(data) for _,data,_ in blobs)
   if live+size>15*1024*1024:print(json.dumps({'budget_stop':id,'remaining_not_rendered':args.ids[args.ids.index(id):],'live_bytes':live}));break
   target=DEST/'evidence'/id;target.mkdir(parents=True,exist_ok=True);evidence=[]
   for kind,data,dims in blobs:
    f=target/f'{kind}.png';f.write_bytes(data);evidence.append({'kind':kind,'path':str(f),'sha256':hashlib.sha256(data).hexdigest(),'dimensions':dims,'bytes':len(data)})
   mask=target/'actual_delta_mask.png';Image.fromarray(delta.astype('uint8')*255).save(mask)
   manifest['images'][id]={'id':id,'style':result['style'],'concept':result['concept'],'source_sha256':r['source_sha256'],'output_sha256':r['candidate_lossless_current_sha256'],'dimensions':[w,h],'actual_changed_pixels':int(delta.sum()),'all_actual_changes_covered':True,'regions':regions,'evidence':evidence,'delta_mask_path':str(mask),'delta_mask_sha256':digest(mask),'generated_utc':utc()};atomic_json(manifest_path,manifest);live+=size;ready.append(id)
  print(json.dumps({'ready':ready,'live_scratch_bytes':live}))
if __name__=='__main__':main()
