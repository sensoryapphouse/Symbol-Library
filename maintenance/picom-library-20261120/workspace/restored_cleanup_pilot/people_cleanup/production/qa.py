#!/usr/bin/env python3
"""Independent pixel audit and on-demand visual evidence. No semantic verdicts."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'): os.environ[k]='1'
import argparse,datetime,fcntl,hashlib,json,math,struct,time
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
from common import atomic_json as atomic
def folder(batch,id):
 paths=[batch/d/id for d in ('selected_outputs','accepted_outputs') if (batch/d/id).is_dir()]
 if len(paths)!=1:raise ValueError(f'{id}: expected exactly one canonical output folder')
 return paths[0]
def lossless(p):
 b=Path(p).read_bytes();assert b[:4]==b'RIFF' and b[8:12]==b'WEBP' and int.from_bytes(b[4:8],'little')+8==len(b)
 tags=[];i=12
 while i<len(b):
  assert i+8<=len(b);tag=b[i:i+4];n=int.from_bytes(b[i+4:i+8],'little');assert i+8+n<=len(b);tags.append(tag);i+=8+n+(n%2)
 assert i==len(b) and b'VP8L'in tags and b'VP8 'not in tags and b'ANIM'not in tags

def audit_one(batch,row,decision,rec,np,Image,ImageDraw,ndi):
 id=row['batch_id'];assert decision['source_sha256']==row['source_sha256'] and decision['dimensions']==row['dimensions'];assert sha(row['source'])==row['source_sha256'];assert rec['source_sha256']==row['source_sha256']
 out={'id':id,'source_sha256':row['source_sha256'],'status':rec['status'],'passed':True,'role':row.get('role','candidate'),'reference':row.get('reference',row.get('review_required') is False),'review_required':row.get('review_required',True)}
 if rec['status']!='changed':
  assert rec.get('changed_pixels')==0 and rec.get('output_created') is False;assert list(Image.open(row['source']).size)==row['dimensions']
  return out
 f=folder(batch,id);r=read(f/'result.json');protocol=read(Path(__file__).parent/'protocol.json');assert r['manifest_sha256']==sha(batch/'manifest.json');assert r['decision_sha256']==sha(batch/'approved_decisions.json');assert r['cleaner_sha256']==protocol['engine']['sha256']==sha(protocol['engine']['path']);assert r['id']==id and r['source_sha256']==row['source_sha256'];assert decision['source_sha256']==row['source_sha256']
 assert sha(f/'after.webp')==r['output_sha256']==rec['output_sha256'];lossless(f/'after.webp')
 a=np.array(Image.open(row['source']).convert('RGBA'));b=np.array(Image.open(f/'after.webp').convert('RGBA'));h,w=a.shape[:2]
 assert [w,h]==row['dimensions']==r['dimensions'] and a.shape==b.shape;assert hashlib.sha256(b.tobytes()).hexdigest()==r['decoded_rgba_sha256']
 mask=np.any(a!=b,axis=2);white=(a[:,:,:3].min(2)>=240)&(np.ptp(a[:,:,:3],axis=2)<=20)&(a[:,:,3]>=128)
 assert np.array_equal(a[:,:,:3],b[:,:,:3]);assert np.array_equal(a[~mask],b[~mask]);assert np.all(b[:,:,3][mask]==0) and np.all(white[mask]);assert mask.any()
 labels,n=ndi.label(white,np.ones((3,3)));sizes=np.bincount(labels.ravel());scale=max(w,h)/512;selected=set();roi=np.zeros((h,w),bool);explicit=np.zeros((h,w),bool)
 specs={x['name']:x for x in decision['regions']};assert len(specs)==len(decision['regions']);boxes=list(decision.get('protected_boxes',[]));polys=list(decision.get('protected_polygons',[]))
 for reg in decision['regions']:
  x0,y0,x1,y1=reg['roi'];assert 0<=x0<x1<=w and 0<=y0<y1<=h;roi[y0:y1,x0:x1]=True
  for x,y in reg['core_seeds']:assert x0<=x<x1 and y0<=y<y1 and labels[y,x]>0;selected.add(int(labels[y,x]))
  boxes+=reg.get('protected_boxes',[]);polys+=reg.get('protected_polygons',[])
 for x0,y0,x1,y1 in boxes:assert 0<=x0<x1<=w and 0<=y0<y1<=h;explicit[y0:y1,x0:x1]=True
 for poly in polys:
  im=Image.new('L',(w,h));ImageDraw.Draw(im).polygon([tuple(v) for v in poly],fill=255);explicit|=np.asarray(im)>0
 protected=explicit.copy()
 for label in range(1,n+1):
  if sizes[label]>=max(1,round(8*scale*scale)) and label not in selected:protected|=ndi.binary_dilation(labels==label,iterations=max(1,round(scale)))
 for name,expected in [('removed_core_mask.png',mask),('roi_mask.png',roi),('protected_mask.png',protected)]:
  saved=np.asarray(Image.open(f/name).convert('L'));assert saved.shape==(h,w) and set(np.unique(saved)).issubset({0,255});assert np.array_equal(saved>0,expected)
  if name in r.get('artifact_sha256',{}):assert sha(f/name)==r['artifact_sha256'][name]
 assert not np.any(mask&protected);expected_mask=np.zeros((h,w),bool);effective={x['name']:x for x in r['regions']};assert len(effective)==len(r['regions']);assert set(effective)<=set(specs)
 for name,spec in specs.items():
  x0,y0,x1,y1=spec['roi'];part=np.zeros((h,w),bool);seeds=[int(labels[y,x]) for x,y in spec['core_seeds']];part[y0:y1,x0:x1]=np.isin(labels[y0:y1,x0:x1],seeds);part&=~protected
  count=int(part.sum())
  if count>=math.ceil(256*scale*scale):
   assert name in effective;reg=effective[name];assert reg['roi']==spec['roi'] and reg['core_pixels']==count;assert abs(reg['core_pixels_at_512']-count/scale**2)<1e-6;expected_mask|=part
  else:assert name not in effective
 assert np.array_equal(mask,expected_mask) and int(mask.sum())==r['changed_pixels']==rec['changed_pixels']
 out.update(result_sha256=sha(f/'result.json'),artifact_sha256={name:sha(f/name) for name in ('after.webp','removed_core_mask.png','roi_mask.png','protected_mask.png')},output_sha256=r['output_sha256'],changed_pixels=int(mask.sum()),effective_regions=len(effective),rgb_exact=True,nonselected_rgba_exact=True,alpha_only_zero=True,protections_independently_recomputed=True,encoded_lossless=True)
 return out

def evidence(batch,rows,runs,ids,Image,ImageDraw):
 dest=batch/'independent_output_review'/'evidence';dest.mkdir(parents=True,exist_ok=True);mp=dest.parent/'review_manifest.json';existing=read(mp) if mp.exists() else {'images':[]};items={r['id']:r for r in existing['images']}
 def checker(w,h):
  im=Image.new('RGB',(w,h),'#f8f8f8');d=ImageDraw.Draw(im)
  for y in range(0,h,12):
   for x in range(0,w,12):
    if (x//12+y//12)%2:d.rectangle((x,y,x+11,y+11),fill='#d2d2d2')
  return im
 def composite(im,bg):
  out=bg.copy();out.paste(im,(0,0),im);return out
 def pair(a,b,path,label,normal=False):
  if normal:
   a=a.copy();b=b.copy();a.thumbnail((512,512),Image.Resampling.LANCZOS);b.thumbnail((512,512),Image.Resampling.LANCZOS);w=h=512
   aa=Image.new('RGBA',(w,h));bb=aa.copy();aa.paste(a,((w-a.width)//2,(h-a.height)//2));bb.paste(b,((w-b.width)//2,(h-b.height)//2));a,b=aa,bb
  else:w,h=a.size
  head=72;im=Image.new('RGB',(max(1024,2*w),2*h+head),'white');draw=ImageDraw.Draw(im);parts=label.split(' | ');draw.text((4,3),' | '.join(parts[:2]),fill='black');draw.text((4,23),' | '.join(parts[2:]),fill='black');draw.text((4,43),'BEFORE (left) / AFTER (right); checker above / purple below; native pixels unless normal',fill='black')
  for j,bg in enumerate([checker(w,h),Image.new('RGB',(w,h),'#78658d')]):
   for k,img in enumerate([a,b]):im.paste(composite(img,bg),(k*w,head+j*h))
  im.save(path,format='PNG')
 for id in ids:
  row=rows[id];assert runs[id]['status']=='changed';f=folder(batch,id);r=read(f/'result.json');assert sha(row['source'])==row['source_sha256'] and sha(f/'after.webp')==r['output_sha256'];a=Image.open(row['source']).convert('RGBA');b=Image.open(f/'after.webp').convert('RGBA')
  label=f"{id} | {row.get('style','')} | {row.get('concept',row.get('_concept',''))} | {row['source_sha256'][:12]} > {r['output_sha256'][:12]}"
  paths={}
  path=dest/f'{id}_full.png';pair(a,b,path,label);paths['full']=str(path.resolve())
  if max(a.size)<=512:paths['normal']=paths['full']
  else:
   path=dest/f'{id}_normal.png';pair(a,b,path,label,True);paths['normal']=str(path.resolve())
  crops=[]
  for n,reg in enumerate(r['regions'],1):
   x0,y0,x1,y1=reg['roi'];margin=max(6,round(max(a.size)*.012));box=(max(0,x0-margin),max(0,y0-margin),min(a.width,x1+margin),min(a.height,y1+margin));path=dest/f'{id}_region_{n:02}.png'
   pair(a.crop(box),b.crop(box),path,label+' | '+reg['name']);crops.append({'name':reg['name'],'roi':reg['roi'],'crop_box':box,'path':str(path.resolve()),'sha256':sha(path)})
  items[id]={'id':id,'style':row.get('style'),'concept':row.get('_concept'),'dimensions':row['dimensions'],'source_sha256':row['source_sha256'],'output_sha256':r['output_sha256'],'result_sha256':sha(f/'result.json'),'result_regions':r['regions'],'paths':paths,'evidence_sha256':{k:sha(v) for k,v in paths.items()},'regions':crops}
  atomic(mp,{'batch':str(batch),'view_rule':'At most four identity-labelled pairs per viewing tool output; actually inspect whole and every region.','images':list(items.values())})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True,type=Path);ap.add_argument('--evidence',action='store_true');ap.add_argument('--ids',nargs='+');args=ap.parse_args();batch=args.batch.resolve();start=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.perf_counter()
 with (Path(__file__).parent/'image_worker.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  import numpy as np
  from PIL import Image,ImageDraw
  from scipy import ndimage as ndi
  m=read(batch/'manifest.json');rows={v['batch_id']:dict(v,_concept=g.get('group_key',g['group_id'])) for g in m['groups'] for v in g['versions']};assert len(rows)==sum(len(g['versions']) for g in m['groups']);assert all(Path(i).name==i and i not in ('.','..') for i in rows);d={x['id']:x for x in read(batch/'approved_decisions.json')['decisions']};run=read(batch/'selected_run_state.json');assert run['status']=='complete';assert set(d)==set(rows);assert len(d)==len(read(batch/'approved_decisions.json')['decisions']);assert run['manifest_sha256']==sha(batch/'manifest.json') and run['approved_decisions_sha256']==sha(batch/'approved_decisions.json');protocol=read(Path(__file__).parent/'protocol.json');assert run['cleaner_sha256']==protocol['engine']['sha256']==sha(protocol['engine']['path']);runs={r['id']:r for r in run['images']};assert len(runs)==len(run['images']) and set(runs)==set(rows)
  if args.evidence:
   assert args.ids,'Explicit --ids required for on-demand evidence';evidence(batch,rows,runs,args.ids,Image,ImageDraw);return
  checks=[]
  for id,row in rows.items():
   try:checks.append(audit_one(batch,row,d[id],runs[id],np,Image,ImageDraw,ndi))
   except Exception as e:checks.append({'id':id,'passed':False,'error':f'{type(e).__name__}: {e}'})
  assert set(runs)==set(rows)
  result={'started_utc':start,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.perf_counter()-t,'manifest_sha256':sha(batch/'manifest.json'),'decisions_sha256':sha(batch/'approved_decisions.json'),'run_state_sha256':sha(batch/'selected_run_state.json'),'cleaner_sha256':run['cleaner_sha256'],'protocol_sha256':sha(Path(__file__).parent/'protocol.json'),'auditor_sha256':sha(__file__),'errors':[c for c in checks if not c['passed']],'semantic_limit':'Mechanical invariants do not determine foreground meaning or worthwhile improvement.','images':checks};atomic(batch/'mechanical_audit.json',result);print(json.dumps({'checked':len(checks),'failed':len(result['errors'])}));return bool(result['errors'])
if __name__=='__main__':raise SystemExit(main())
