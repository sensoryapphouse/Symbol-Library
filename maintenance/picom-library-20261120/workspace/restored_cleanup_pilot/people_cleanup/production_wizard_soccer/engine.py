"""Pure pinned outer transform and unchanged strict runner, under one worker.

These functions are fixture-testable but never authorize population execution.
Outer intermediates are not user's originals; records always retain both.
"""
import io
from pathlib import Path
from contracts import *


def stack():
    require_worker()
    if (HERE/'bundle.json').exists():
        require(runtime_versions()==read(HERE/'bundle.json')['runtime_versions'],'Pinned numeric/image environment changed')
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    pins = read(PREP / 'method_provenance_pins.json')['metadata_and_code_sha256']
    source = RUNTIME / 'gender-repair-registration-20261105/background/nearwhite_v3_transform.py'
    require(file_sha(source) == pins[str(source)], 'Pure outer transform changed')
    pure = load('_ws_pinned_outer', source)
    cleaner_path = BASE.parent / 'scripts/cleaner.py'
    require(file_sha(cleaner_path) == pins[str(cleaner_path)], 'Existing cleaner changed')
    cleaner = load('_ws_pinned_cleaner', cleaner_path)
    run_path = BASE / 'production/run_selected.py'
    require(file_sha(run_path) == pins[str(run_path)], 'Existing strict runner changed')
    runner = load('_ws_strict_runner', run_path)
    preview = load('_ws_source_preview', BASE / 'production/prepare_source_previews.py')
    # The preview prepends its directory on import. Restore that precedence
    # if another entry moved ahead of it, without growing the search path.
    production_path = str(BASE / 'production')
    if not sys.path or sys.path[0] != production_path:
        if production_path in sys.path:
            sys.path.remove(production_path)
        sys.path.insert(0, production_path)
    return np, Image, ndi, pure, cleaner, runner, preview


def decode(raw):
    np, Image, *_ = stack()
    with Image.open(io.BytesIO(raw)) as image:
        return np.array(image.convert('RGBA'), dtype=np.uint8)


def exact_webp(array):
    np, Image, *_ = stack()
    stream = io.BytesIO()
    Image.fromarray(array, 'RGBA').save(stream, 'WEBP', lossless=True, exact=True, method=6)
    raw = stream.getvalue()
    require(np.array_equal(decode(raw), array), 'Lossless exact RGBA decode differs')
    return raw


def outer(array):
    np, _, _, pure, *_ = stack()
    if np.all(array[:,:,3] == 255):
        require(array.shape[:2]==(512,512),'Unexpected opaque native dimensions require root review; v3 radii are unchanged')
        result, metrics = pure.transform(array, manual_seeds=())
        mode = 'pinned_opaque_v3_no_manual_seeds'
    else:
        result, metrics, mode = array.copy(), {}, 'already_transparent_identity'
    return result, dict(mode=mode, metrics=metrics, original_rgba_sha256=sha(array.tobytes()),
        outer_rgba_sha256=sha(result.tobytes()), changed=not np.array_equal(array,result))


def components(array):
    np, _, ndi, *_, preview = stack()
    h,w = array.shape[:2]
    strict, labels, rows, scale = preview.component_inventory(np, ndi, array, [w,h])
    return labels, dict(dimensions=[w,h], rgba_sha256=sha(array.tobytes()),
        threshold=dict(rgb_min=240, max_channel_range=20, min_alpha=128, connectivity=8),
        components=rows, component_inventory_minimum_at512=64, removal_minimum_at512=256)


def no_inner_proof(array):
    np,_,ndi,*_=stack()
    rgb=array[:,:,:3].astype(np.int16)
    strict=(rgb.min(2)>=240)&(np.ptp(rgb,axis=2)<=20)&(array[:,:,3]>=128)
    minimum=int(np.ceil(256*(max(array.shape[:2])/512)**2))
    count=int(strict.sum())
    return dict(schema='numeric-no-inner-v1',stage_rgba_sha256=sha(array.tobytes()),
        total_strict_white_pixels=count,minimum_per_region=minimum,
        no_eligible_inner=count<minimum,visual_review_claimed=False,
        proof_rule='Any selected protected/ROI-clipped core is a subset of all strict-white pixels')


def normalize_regions(array,decision):
    """Existing compiler's union-bbox default, without changing strict masks.

    Evidence crop adds native context separately; it never becomes removal ROI.
    """
    np,_,ndi,*_=stack();labels,_=components(array);h,w=array.shape[:2]
    normalized=[]
    for region in decision.get('regions',[]):
        selected=region.get('component_labels')
        require(isinstance(selected,list) and selected and len(set(selected))==len(selected),'Actual component IDs required')
        require(all(type(i) is int and i>0 and np.any(labels==i) for i in selected),'Unknown actual component ID')
        ys,xs=np.nonzero(np.isin(labels,selected))
        bounds=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
        roi=region.get('roi') or bounds
        require(len(roi)==4 and all(type(i) is int for i in roi) and 0<=roi[0]<roi[2]<=w and 0<=roi[1]<roi[3]<=h,'ROI outside native image')
        x0,y0,x1,y1=roi;seeds=[]
        for label in selected:
            part=labels[y0:y1,x0:x1]==label;require(part.any(),'Selected component absent from ROI')
            distance=ndi.distance_transform_edt(part);y,x=np.unravel_index(distance.argmax(),part.shape)
            seeds.append([int(x+x0),int(y+y0)])
        if region.get('core_seeds'):
            require(set(selected)=={int(labels[y,x]) for x,y in region['core_seeds']},'Seed/component IDs differ from actual stage')
            seeds=region['core_seeds']
        crop=[max(0,x0-4),max(0,y0-4),min(w,x1+4),min(h,y1+4)]
        normalized.append(dict(region,roi=list(roi),core_seeds=seeds,selected_component_bounds=bounds,evidence_crop_roi=crop))
    return dict(decision,regions=normalized)


def strict(stage_path, stage_sha, decision, output_root, manifest_sha):
    """Invoke frozen runner on explicit intermediate, discarding all matte output.

    The unchanged runner uses cleaner only for core/protection masks, constructs
    after=source.copy(), and zeros selected strict-core alpha. Its invariants
    compare to this intermediate. True-original review occurs in workflow.seal.
    """
    require_worker()
    np, Image, _, _, cleaner, runner, _ = stack()
    raw, _ = stable_bytes(stage_path, stage_sha)
    array = decode(raw)
    decision=normalize_regions(array,decision)
    labels, inventory_doc = components(array)
    h,w = array.shape[:2]
    require(decision.get('stage_sha256') == stage_sha and decision.get('stage_rgba_sha256') == sha(array.tobytes()), 'Source reviewer did not bind current intermediate')
    for region in decision.get('regions', []):
        ids = region.get('component_labels')
        require(isinstance(ids,list) and ids and len(ids)==len(set(ids)), 'Actual stage component IDs required')
        require(set(ids) == {int(labels[y,x]) for x,y in region['core_seeds']}, 'Seed/component IDs differ from actual stage')
        require(0 not in ids, 'Nonwhite seed')
    row = dict(batch_id=decision['id'], source=str(Path(stage_path).resolve()), source_sha256=stage_sha, dimensions=[w,h])
    manifest = dict(batch_id='supplemental-inner', groups=[dict(versions=[row])])
    approvals = dict(batch_id='supplemental-inner', manifest_sha256=manifest_sha,
        root_approval=dict(approved=True,approved_by='root'), decisions=[dict(decision,source_sha256=stage_sha,dimensions=[w,h])])
    runner.approved_candidates(manifest,approvals,manifest_sha)
    require(not Path(output_root).exists() or Path(output_root).is_dir(), 'Bad strict output directory')
    runner.OUT = inside(output_root)
    decision_sha=sha(payload(approvals));cleaner_sha=file_sha(BASE.parent/'scripts/cleaner.py')
    if (runner.OUT/decision['id']).exists():
        result=runner.verify_existing(decision['id'],row,None,decision_sha,manifest_sha,cleaner_sha)
        result.update(status='changed',output_created=True)
    else:
        result = runner.run_one(np,Image,cleaner.cleanup,row,approvals['decisions'][0],manifest_sha,decision_sha,cleaner_sha)
    stable_bytes(stage_path,stage_sha)
    return result


def evidence(original, final, regions):
    """Native source/final, full blue/dark/alpha, plus all requested region crops."""
    np, Image, *_ = stack()
    files = {}
    def png(name, image):
        output = io.BytesIO(); image.save(output,'PNG'); files[name] = output.getvalue()
    for name,array in (('true-original',original),('final',final)):
        png(name+'-native.png',Image.fromarray(array,'RGBA'))
        for color,label in (((135,183,217,255),'blue'),((48,48,48,255),'dark')):
            bg=Image.new('RGBA',(array.shape[1],array.shape[0]),color)
            png(name+'-'+label+'.png',Image.alpha_composite(bg,Image.fromarray(array,'RGBA')).convert('RGB'))
        png(name+'-alpha.png',Image.fromarray(array[:,:,3],'L'))
        for index,region in enumerate(regions):
            x0,y0,x1,y1=region.get('evidence_crop_roi',region['roi'])
            png(name+f'-region-{index:03d}.png',Image.fromarray(array[y0:y1,x0:x1],'RGBA'))
    return files


def source_evidence(array):
    np,Image,ndi,*_,preview=stack()
    from PIL import ImageDraw,ImageFont
    h,w=array.shape[:2]
    _,labels,comps,scale=preview.component_inventory(np,ndi,array,[w,h])
    base=preview.render_source(Image,array)
    overlay=preview.make_overlay(np,ndi,Image,ImageDraw,ImageFont,base,labels,comps,scale)
    files={}
    for name,image in (('stage-native.png',Image.fromarray(array,'RGBA')),('stage-components.png',overlay)):
        output=io.BytesIO();image.save(output,'PNG');files[name]=output.getvalue()
    return files
