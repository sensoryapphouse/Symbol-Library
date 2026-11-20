#!/usr/bin/env python3
"""Measure explicit checkpoint ROIs numerically; never clean, preview or approve."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE/'production'
ALLOWED=(ORIGINAL/'batches',HERE/'production_remaining_people'/'batches')
sys.path.insert(0,str(ORIGINAL))
from common import image_worker


def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_bytes())
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,document):
    temp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(document,stream,indent=2,ensure_ascii=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def validate_batch(path):
    batch=Path(path).resolve(strict=True)
    if batch.parent not in ALLOWED or not batch.is_dir():raise ValueError('Batch must be an immediate child of an approved production batches directory')
    return batch

def validate_roi(roi,dimensions):
    if not isinstance(roi,list) or len(roi)!=4 or any(type(v) is not int for v in roi):raise ValueError('ROI must contain four integer coordinates')
    x0,y0,x1,y1=roi;w,h=dimensions
    if not (0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError(f'ROI outside native image bounds: {roi}, {dimensions}')
    return x0,y0,x1,y1

def normalize(count,dimensions):return count/(max(dimensions)/512)**2

def labels_of(row):
    selected=row.get('component_labels',[row['component']] if 'component' in row else [])
    if not selected or any(type(v) is not int or v<=0 for v in selected) or len(selected)!=len(set(selected)):raise ValueError('Selected component_labels must be distinct positive integers')
    return selected

def key(row):return (row['id'],tuple(sorted(labels_of(row))),tuple(row['roi']))

def comparable(row):
    return {'source_sha256':row['source_sha256'],'dimensions':row['dimensions'],
        'actual_native_pixels':row['actual_native_pixels'],'actual_at512':row['actual_at512'],
        'passes_minimum256':row['passes_minimum256']}

def verify_existing(existing,measured,groups,id_to_group):
    old={}
    for row in existing.get('measurements',[]):
        if row['id'] not in id_to_group:raise ValueError('Existing measurement has ID outside manifest: '+row['id'])
        if id_to_group[row['id']] not in groups:continue
        k=key(row)
        if k in old:raise ValueError('Duplicate existing ROI measurement')
        old[k]=row
    wanted={key(row):row for row in measured}
    if set(old)!=set(wanted):return False,'ROI selection coverage differs'
    for k,row in wanted.items():
        if comparable(old[k])!=comparable(row):return False,'Numeric/source measurement differs: '+row['id']
        for field in ('checkpoint_sha256','manifest_sha256'):
            if field in old[k] and old[k][field]!=row[field]:return False,field+' differs: '+row['id']
    return True,'All explicit ROI counts and available lineage pins match'


def measure(batch,group_ids=None,verify_only=False):
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    manifest_path=batch/'manifest.json';manifest_raw=manifest_path.read_bytes();manifest=json.loads(manifest_raw);manifest_sha=digest(manifest_raw)
    groups={g['group_id']:g for g in manifest['groups']}
    selected=set(group_ids or groups)
    if not selected or not selected<=set(groups):raise ValueError('Unknown/empty group selection')
    versions={};id_to_group={}
    for group in groups.values():
        for row in group['versions']:
            ident=row['batch_id']
            if ident in versions:raise ValueError('Duplicate manifest image ID: '+ident)
            versions[ident]=row;id_to_group[ident]=group['group_id']
    proposals={};proofs={};skipped=0
    for gid in sorted(selected):
        if Path(gid).name!=gid or gid in ('.','..'):raise ValueError('Invalid group checkpoint name')
        path=batch/'source_reviews'/(gid+'.json')
        if not path.is_file():raise ValueError('Missing source checkpoint: '+str(path))
        raw=path.read_bytes();checkpoint=json.loads(raw);proofs[gid+'.json']=digest(raw)
        if checkpoint.get('group_id')!=gid:raise ValueError('Checkpoint group differs from manifest: '+gid)
        records={}
        for record in checkpoint['source_records']:
            ident=record['id']
            if ident in records or id_to_group.get(ident)!=gid:raise ValueError('Duplicate or foreign source checkpoint record: '+ident)
            records[ident]=record
        for row in groups[gid]['versions']:
            ident=row['batch_id'];record=records.get(ident)
            if not record:
                if row.get('review_required',True):raise ValueError('Required source record missing: '+ident)
                continue
            if record['source_sha256']!=row['source_sha256'] or record['dimensions']!=row['dimensions']:raise ValueError('Source checkpoint hash/dimensions differ: '+ident)
            region_list=record.get('regions',[])
            if not isinstance(region_list,list):raise ValueError('Checkpoint regions must be a list: '+ident)
            for region in region_list:
                if not isinstance(region,dict):raise ValueError('Checkpoint region must be an object: '+ident)
                if 'roi' not in region:skipped+=1;continue
                if not row.get('review_required',True):raise ValueError('Context reference cannot propose ROI cleanup: '+ident)
                if record.get('actually_viewed') is not True or record.get('classification')!='clear_background_gap':raise ValueError('ROI requires a viewed clear-background source checkpoint: '+ident)
                if not isinstance(region.get('name'),str) or not region['name'].strip():raise ValueError('ROI needs a nonempty region name: '+ident)
                validate_roi(region['roi'],row['dimensions']);labels_of(region)
                proposals.setdefault(ident,[]).append((region,gid,proofs[gid+'.json']))
    measurements=[]
    for ident,regions in proposals.items():
        row=versions[ident];raw=Path(row['source']).read_bytes()
        if digest(raw)!=row['source_sha256']:raise ValueError('Actual source SHA differs from manifest: '+ident)
        with Image.open(io.BytesIO(raw)) as image:a=np.asarray(image.convert('RGBA'))
        dimensions=[a.shape[1],a.shape[0]]
        if dimensions!=row['dimensions']:raise ValueError('Actual source dimensions differ from manifest: '+ident)
        white=(a[:,:,:3].min(2)>=240)&(np.ptp(a[:,:,:3],axis=2)<=20)&(a[:,:,3]>=128)
        labels,_=ndi.label(white,np.ones((3,3)))
        inventory={c.get('label_id',c.get('component_label')):c for c in row['components_ge64_at_512']}
        names=set()
        for region,gid,checkpoint_sha in regions:
            if region['name'] in names:raise ValueError('Duplicate region name: '+ident)
            names.add(region['name']);selected_labels=labels_of(region)
            if any(label not in inventory for label in selected_labels):raise ValueError('Selected component absent from manifest inventory: '+ident)
            x0,y0,x1,y1=validate_roi(region['roi'],dimensions);crop=labels[y0:y1,x0:x1]
            if any(not (crop==label).any() for label in selected_labels):raise ValueError('Selected component has no strict-core pixels inside ROI: '+ident)
            count=int(np.isin(crop,selected_labels).sum());normalized=normalize(count,dimensions)
            measurements.append({'id':ident,'name':region['name'],'group_id':gid,'source_sha256':row['source_sha256'],
                'checkpoint_path':str(batch/'source_reviews'/(gid+'.json')),'checkpoint_sha256':checkpoint_sha,
                'manifest_sha256':manifest_sha,'component_labels':selected_labels,'roi':region['roi'],'dimensions':dimensions,
                'actual_native_pixels':count,'actual_at512':normalized,'passes_minimum256':normalized>=256})
    measurements.sort(key=key)
    if len({key(x) for x in measurements})!=len(measurements):raise ValueError('Duplicate requested ROI selection')
    # Checkpoint/manifest changes invalidate the numeric snapshot; never race a review amendment.
    if digest(manifest_path.read_bytes())!=manifest_sha:raise ValueError('Manifest changed during measurement')
    for name,expected in proofs.items():
        if digest((batch/'source_reviews'/name).read_bytes())!=expected:raise ValueError('Checkpoint changed during measurement: '+name)
    target=batch/'parent_roi_measurements.json';old_raw=target.read_bytes() if target.exists() else None;old=json.loads(old_raw) if old_raw else None
    matches,reason=verify_existing(old,measurements,selected,id_to_group) if old else (False,'No existing measurement file')
    legacy=old is not None and old.get('schema_version')!=2
    if verify_only:
        if not matches:raise ValueError('Existing measurements failed read-only verification: '+reason)
        return {'status':'verified_existing_unchanged','measurements':measurements,'legacy_file':legacy,'checkpoint_sha256':proofs,'files_written':False}
    approved=(batch/'approved_decisions.json').exists()
    if approved:
        if not matches:raise ValueError('Approved batch: measurement differs; mutation is forbidden: '+reason)
        return {'status':'approved_existing_verified_unchanged','measurements':measurements,'legacy_file':legacy,'checkpoint_sha256':proofs,'files_written':False}
    preserved=[]
    if old:
        for row in old['measurements']:
            if id_to_group[row['id']] not in selected:
                if not row.get('checkpoint_sha256'):raise ValueError('Legacy measurements outside selected groups require a full-batch refresh')
                preserved.append(row)
    merged=sorted(preserved+measurements,key=key)
    merged_proofs={**(old.get('source_checkpoint_sha256',{}) if old else {}),**proofs}
    document={'schema_version':2,'batch_id':manifest['batch_id'],'manifest_sha256':manifest_sha,
        'source_checkpoint_sha256':merged_proofs,'helper_sha256':digest(Path(__file__).read_bytes()),
        'compiler_reference_sha256':digest((batch.parent.parent/'compile_decisions.py').read_bytes()),
        'single_shared_image_worker':True,'no_images_changed':True,
        'normalization':'native_pixels/(max(width,height)/512)^2, matching compiler',
        'strict_mask':{'rgb_min':240,'max_channel_range':20,'min_alpha':128,'connectivity':8},
        'measurements':merged}
    if old and {k:v for k,v in old.items() if k!='utc'}==document:
        return {'status':'reused_existing_unchanged','measurements':measurements,'files_written':False}
    if (batch/'approved_decisions.json').exists():raise ValueError('Approval appeared during measurement; refusing mutation')
    if old_raw:
        archive=batch/'parent_roi_measurements_history'/(digest(old_raw)+'.json');archive.parent.mkdir(exist_ok=True)
        if archive.exists():
            if archive.read_bytes()!=old_raw:raise ValueError('Existing measurement archive hash collision/mismatch')
        else:
            with archive.open('xb') as stream:stream.write(old_raw);stream.flush();os.fsync(stream.fileno())
    document['utc']=utc();atomic(target,document)
    return {'status':'measurements_written','measurements':measurements,'skipped_regions_without_roi':skipped,'files_written':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch',required=True,type=Path);parser.add_argument('--group-ids',nargs='+');parser.add_argument('--verify-only',action='store_true');args=parser.parse_args();batch=validate_batch(args.batch)
    with image_worker():result=measure(batch,args.group_ids,args.verify_only)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
