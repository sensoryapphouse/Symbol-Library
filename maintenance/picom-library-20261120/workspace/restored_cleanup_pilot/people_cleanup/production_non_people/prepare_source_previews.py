#!/usr/bin/env python3
"""Prepare native source views and strict-white component inventories for one batch.

The Library is read-only. All decoding/rendering happens under the production
single-image-worker lock, with numerical thread pools pinned before imports.
"""
import os
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'

import argparse
import json
import math
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import atomic_json,digest,image_worker,utc


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def append_jsonl(p,row):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f:
        f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())

def atomic_png(Image,image,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.stem+f'.tmp-{os.getpid()}'+path.suffix)
    image.save(tmp,format='PNG',optimize=False)
    with tmp.open('rb') as f: os.fsync(f.fileno())
    os.replace(tmp,path)

def component_inventory(np,ndi,rgba,dims):
    h,w=rgba.shape[:2]
    rgb=rgba[:,:,:3].astype(np.int16)
    strict=(rgb.min(axis=2)>=240)&((rgb.max(axis=2)-rgb.min(axis=2))<=20)&(rgba[:,:,3]>=128)
    labels,count=ndi.label(strict,np.ones((3,3),dtype=np.uint8))
    sizes=np.bincount(labels.ravel(),minlength=count+1)
    boxes=ndi.find_objects(labels,max_label=count)
    scale=max(w,h)/512.0
    comps=[]
    for label in range(1,count+1):
        area=int(sizes[label]);area512=area/(scale*scale)
        if area512<64: continue
        sl=boxes[label-1]
        y0,y1=int(sl[0].start),int(sl[0].stop);x0,x1=int(sl[1].start),int(sl[1].stop)
        local=(labels[y0:y1,x0:x1]==label)
        dist=ndi.distance_transform_edt(local)
        ly,lx=np.unravel_index(int(dist.argmax()),dist.shape)
        maxdist=float(dist[ly,lx]);sx,sy=x0+int(lx),y0+int(ly)
        comps.append({'component_label':int(label),'area_pixels_native':area,'area_at_512':round(area512,4),'bbox_xyxy_native':[x0,y0,x1,y1],'interior_seed_native':[sx,sy],'max_distance_pixels_native':round(maxdist,3),'max_distance_at_512':round(maxdist/scale,3)})
    # Labels are the connected-component algorithm's stable top-left scan order.
    return strict,labels,comps,scale

def render_source(Image,rgba_array):
    fg=Image.fromarray(rgba_array,mode='RGBA')
    bg=Image.new('RGBA',fg.size,(120,101,141,255))
    bg.alpha_composite(fg)
    return bg.convert('RGB')

def make_overlay(np,ndi,Image,ImageDraw,ImageFont,base_rgb,labels,components,scale):
    arr=np.asarray(base_rgb).copy()
    contour_color=np.array([255,40,144],dtype=np.uint8)
    image=Image.fromarray(arr,'RGB');draw=ImageDraw.Draw(image);font=ImageFont.load_default()
    for comp in components:
        lab=comp['component_label'];mask=(labels==lab)
        eroded=ndi.binary_erosion(mask,structure=np.ones((3,3),dtype=bool),border_value=0)
        edge=mask&~eroded
        arr[edge]=contour_color
        x0,y0,x1,y1=comp['bbox_xyxy_native']
        image=Image.fromarray(arr,'RGB');draw=ImageDraw.Draw(image)
        draw.rectangle((x0,y0,x1-1,y1-1),outline=(255,40,144),width=max(1,round(scale)))
        draw.text((x0,max(0,y0-10)),str(lab),font=font,fill=(255,40,144),stroke_width=1,stroke_fill=(35,25,40))
        arr=np.asarray(image).copy()
    return image

def make_contact(Image,ImageDraw,ImageFont,tiles,path):
    # Each source tile is kept at its native 512 x 512 pixels; captions occupy
    # additional space below each tile and do not shrink the image.
    tile_w=512;tile_h=512;cap=24;gap=0
    rows=math.ceil(len(tiles)/2);canvas=Image.new('RGB',(1024,rows*(tile_h+cap)),(120,101,141));d=ImageDraw.Draw(canvas);font=ImageFont.load_default()
    for i,(img,label) in enumerate(tiles):
        x=(i%2)*tile_w;y=(i//2)*(tile_h+cap)
        canvas.paste(img,(x,y));d.rectangle((x,y+tile_h,x+tile_w-1,y+tile_h+cap-1),fill=(30,30,35));d.text((x+4,y+tile_h+4),label,font=font,fill=(255,255,255))
    atomic_png(Image,canvas,path)

def finish_group_contact(Image,ImageDraw,ImageFont,batch,group,tile_map,contacts,blind_groups):
    gid=group['group_id'];tiles=tile_map.pop(gid,[]);paths=[]
    sheetdir=batch/'previews'/'contact_sheets'
    for i in range(0,len(tiles),4):
        chunk=tiles[i:i+4];sheet=sheetdir/f'{gid}_native512_{i//4+1:02d}.png';make_contact(Image,ImageDraw,ImageFont,chunk,sheet)
        entry={'group_id':gid,'path':sheet.relative_to(batch).as_posix(),'sha256':digest(sheet),'tile_count':len(chunk),'tile_dimensions':[512,512]}
        contacts.append(entry);paths.append(entry['path'])
    group['contact_sheets_512']=paths
    blind_groups[gid]['contact_sheets_512']=paths

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--batch',required=True,type=Path)
    ap.add_argument('--minimum-free-gib',type=float,default=10.0)
    args=ap.parse_args()
    batch=args.batch.resolve(strict=True)
    from common import verify_batch_scope
    verify_batch_scope(batch)
    started_utc=utc();t0=time.perf_counter()
    free_gib=shutil.disk_usage(HERE).free/(1024**3)
    if free_gib<args.minimum_free_gib: raise RuntimeError(f'free space {free_gib:.2f} GiB is below {args.minimum_free_gib} GiB floor')
    from non_people_publication import operator_lock, require_open_batch
    with operator_lock(), image_worker():
        require_open_batch(batch, allow_existing=False)
        import numpy as np
        from PIL import Image,ImageDraw,ImageFont
        from scipy import ndimage as ndi
        manifest_path=batch/'manifest.json';blind_path=batch/'blind_manifest.json'
        manifest=read(manifest_path);blind=read(blind_path)
        if manifest.get('rule_version')!='people-white-core-v1' or blind.get('batch_id')!=manifest.get('batch_id'):
            raise ValueError('batch protocol or blind manifest does not match')
        prepdir=batch/'previews';srcdir=prepdir/'sources';sheetdir=prepdir/'contact_sheets';checkdir=prepdir/'checkpoints'
        state_path=prepdir/'preparation.json';old_state=read(state_path) if state_path.is_file() else {}
        if old_state.get('status')=='complete':
            all_valid=True
            for group in manifest.get('groups',[]):
                for version in group.get('versions',[]):
                    ckpath=checkdir/f"{version['batch_id']}.json"
                    if not ckpath.is_file(): all_valid=False;break
                    ck=read(ckpath)
                    if not Path(version['source']).is_file() or digest(version['source'])!=version.get('source_sha256'): all_valid=False;break
                    for field,sha_field in [('source_png','source_png_sha256'),('strict_cc_overlay','overlay_png_sha256')]:
                        p=batch/ck.get(field,'')
                        if ck.get('source_sha256')!=version.get('source_sha256') or not p.is_file() or digest(p)!=ck.get(sha_field): all_valid=False;break
                    if not all_valid: break
                if not all_valid: break
            for contact in manifest.get('preview_preparation',{}).get('contact_sheets_512',[]):
                p=batch/contact['path']
                if not p.is_file() or digest(p)!=contact.get('sha256'): all_valid=False;break
            if all_valid:
                result={'batch':manifest['batch_id'],'status':'complete','action':'verified_existing_previews','images':old_state.get('images_total'),'errors':0,'verified_utc':utc(),'elapsed_seconds':round(time.perf_counter()-t0,3)}
                print(json.dumps(result,indent=2));return
        for p in (srcdir,sheetdir,checkdir):p.mkdir(parents=True,exist_ok=True)
        if old_state.get('status')=='incomplete_with_errors':
            old_ready=prepdir/'group_readiness.jsonl'
            if old_ready.is_file():
                archived=prepdir/'group_readiness_failed_attempt_001.jsonl'
                if archived.exists(): archived=prepdir/f'group_readiness_failed_attempt_{int(time.time())}.jsonl'
                os.replace(old_ready,archived)
        append_jsonl(prepdir/'source_prep_ledger.jsonl',{'event':'preview_attempt_started','utc':started_utc,'previous_status':old_state.get('status'),'previous_error_count':len(old_state.get('errors',[]))})
        prep={'batch_id':manifest['batch_id'],'started_utc':old_state.get('started_utc',started_utc),'last_run_started_utc':started_utc,'status':'running','free_space_gib_before':round(free_gib,2),'images_total':sum(len(g.get('versions',[])) for g in manifest['groups']),'processed':0,'resumed_from_checkpoint':0,'errors':[]}
        atomic_json(state_path,prep)
        blind_groups={g['group_id']:g for g in blind['groups']}
        tile_map={};contacts=[]
        eventpath=prepdir/'source_prep_ledger.jsonl'
        total=prep['images_total']
        ordinal=0;last_group=None;last_group_start=1;group_errors=0
        for group in manifest['groups']:
          if last_group is not None:
            finish_group_contact(Image,ImageDraw,ImageFont,batch,last_group,tile_map,contacts,blind_groups)
            ready={'batch_id':manifest['batch_id'],'group_id':last_group['group_id'],'group_key':last_group['group_key'],'images':len(last_group['versions']),'ordinal_range':[last_group_start,ordinal],'contact_sheets':last_group.get('contact_sheets_512',[]),'status':'ready' if group_errors==0 else 'incomplete','group_error_count':group_errors,'members':[{'id':v['batch_id'],'source_sha256':v['source_sha256'],'preview_paths':v.get('preview_paths')} for v in last_group['versions']],'ready_utc':utc()}
            append_jsonl(prepdir/'group_readiness.jsonl',ready)
            print(json.dumps({'group_ready':ready}),flush=True)
            last_group_start=ordinal+1
            group_errors=0
          last_group=group
          for version in group['versions']:
            ordinal+=1
            ident=version['batch_id'];source=Path(version['source']);checkpoint=checkdir/f'{ident}.json'
            source_png=srcdir/f'{ident}_source_purple.png';overlay_png=srcdir/f'{ident}_strict_cc_overlay.png'
            rel_source=source_png.relative_to(batch).as_posix();rel_overlay=overlay_png.relative_to(batch).as_posix()
            try:
                if not source.is_file(): raise FileNotFoundError(source)
                if digest(source)!=version['source_sha256']: raise ValueError(f'{ident}: source SHA changed since manifest freeze')
                ck=read(checkpoint) if checkpoint.is_file() else {}
                reusable=ck.get('source_sha256')==version['source_sha256'] and ck.get('dimensions')==version['dimensions'] and source_png.is_file() and overlay_png.is_file() and digest(source_png)==ck.get('source_png_sha256') and digest(overlay_png)==ck.get('overlay_png_sha256')
                if reusable:
                    info=ck
                    prep['resumed_from_checkpoint']+=1
                else:
                    with Image.open(source) as im:
                        rgba=np.asarray(im.convert('RGBA'))
                    dims=[rgba.shape[1],rgba.shape[0]]
                    if dims!=version['dimensions']: raise ValueError(f'{ident}: dimensions differ from manifest')
                    strict,labels,components,scale=component_inventory(np,ndi,rgba,dims)
                    base=render_source(Image,rgba)
                    overlay=make_overlay(np,ndi,Image,ImageDraw,ImageFont,base,labels,components,scale)
                    atomic_png(Image,base,source_png);atomic_png(Image,overlay,overlay_png)
                    info={'batch_id':ident,'production_source_id':version['production_source_id'],'source_sha256':version['source_sha256'],'dimensions':dims,'role':version['role'],'components_ge64_at_512':components,'strict_white_pixels_native':int(strict.sum()),'strict_white_pixels_at_512':round(float(strict.sum()/(scale*scale)),4),'source_png':rel_source,'source_png_sha256':digest(source_png),'strict_cc_overlay':rel_overlay,'overlay_png_sha256':digest(overlay_png),'prepared_utc':utc(),'decoded_source_image':True}
                    atomic_json(checkpoint,info)
                    append_jsonl(eventpath,{'event':'source_preview_prepared','utc':info['prepared_utc'],'id':ident,'source_sha256':info['source_sha256'],'source_png_sha256':info['source_png_sha256'],'overlay_png_sha256':info['overlay_png_sha256'],'components_ge64_at_512':len(components)})
                version['components_ge64_at_512']=info['components_ge64_at_512']
                version['strict_white_pixels_native']=info['strict_white_pixels_native']
                version['preview_paths']={'source_purple':info['source_png'],'strict_cc_overlay':info['strict_cc_overlay']}
                bgroup=blind_groups[group['group_id']]
                bv=next(v for v in bgroup['versions'] if v['batch_id']==ident)
                bv['components_ge64_at_512']=info['components_ge64_at_512']
                bv['strict_white_pixels_native']=info['strict_white_pixels_native']
                bv['preview_paths']={'source_purple':info['source_png'],'strict_cc_overlay':info['strict_cc_overlay']}
                if version['dimensions']==[512,512]:
                    with Image.open(source_png) as im: tile_map.setdefault(group['group_id'],[]).append((im.copy(),f"{ident} | {version['style']} | {version['role']}"))
                prep['processed']+=1
            except Exception as e:
                err={'id':ident,'source':str(source),'source_sha256':version.get('source_sha256'),'error':f'{type(e).__name__}: {e}','utc':utc()}
                prep['errors'].append(err);group_errors+=1;append_jsonl(eventpath,{'event':'source_preview_error',**err})
            if ordinal%20==0 or ordinal==total:
                prep['last_progress_utc']=utc();prep['last_progress_ordinal']=ordinal
                atomic_json(state_path,prep)
                print(json.dumps({'batch':manifest['batch_id'],'progress':ordinal,'total':total,'processed':prep['processed'],'errors':len(prep['errors']),'elapsed_seconds':round(time.perf_counter()-t0,1)}),flush=True)
        # The last group's contact sheets become ready immediately too.
        if last_group is not None:
            finish_group_contact(Image,ImageDraw,ImageFont,batch,last_group,tile_map,contacts,blind_groups)
            ready={'batch_id':manifest['batch_id'],'group_id':last_group['group_id'],'group_key':last_group['group_key'],'images':len(last_group['versions']),'ordinal_range':[last_group_start,ordinal],'contact_sheets':last_group.get('contact_sheets_512',[]),'status':'ready' if group_errors==0 else 'incomplete','group_error_count':group_errors,'members':[{'id':v['batch_id'],'source_sha256':v['source_sha256'],'preview_paths':v.get('preview_paths')} for v in last_group['versions']],'ready_utc':utc()}
            append_jsonl(prepdir/'group_readiness.jsonl',ready)
            print(json.dumps({'group_ready':ready}),flush=True)
        manifest['preview_preparation']={'started_utc':prep['started_utc'],'completed_utc':utc(),'source_image_worker':'single locked process; numeric threads=1','contact_sheets_512':contacts,'individual_1024_views':'previews/sources/<id>_source_purple.png and strict_cc_overlay.png; each native size'}
        blind['preview_preparation']=manifest['preview_preparation']
        prep['status']='complete' if not prep['errors'] else 'incomplete_with_errors'
        prep['completed_utc']=utc();prep['elapsed_seconds']=round(time.perf_counter()-t0,3);prep['free_space_gib_after']=round(shutil.disk_usage(HERE).free/(1024**3),2);prep['contact_sheets']=len(contacts)
        atomic_json(manifest_path,manifest);atomic_json(blind_path,blind);atomic_json(state_path,prep)
        index_path=HERE/'batch_index.json';index=read(index_path)
        for row in index.get('batches',[]):
            if row['batch_id']==manifest['batch_id']:
                row['manifest_sha256']=digest(manifest_path);row['blind_manifest_sha256']=digest(blind_path)
        atomic_json(index_path,index)
    print(json.dumps({'batch':manifest['batch_id'],'status':prep['status'],'images':total,'processed_or_resumed':prep['processed'],'errors':len(prep['errors']),'contacts':len(contacts),'elapsed_seconds':prep['elapsed_seconds'],'free_gib_after':prep['free_space_gib_after']},indent=2))

if __name__=='__main__':main()
