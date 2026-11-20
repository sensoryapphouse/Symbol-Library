#!/usr/bin/env python3
"""Seeded, all-version concept sample and native source previews for batch003."""
import os
for _k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","VECLIB_MAXIMUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_k]="1"

import hashlib, json, random, re, time
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT_OUT=HERE/"batch003"
OUT=ROOT_OUT/"final"
SCREEN=HERE/"blob_screen"
LIBRARY=Path("/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library")
SEED=2026110503
MIN_IMAGES=140
MAX_IMAGES=170
TARGET=150
STYLECOUNT=16

def now(): return datetime.now(timezone.utc).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def atomic(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(path.name+f".tmp-{os.getpid()}")
    with tmp.open("w",encoding="utf-8") as f: json.dump(obj,f,indent=2,ensure_ascii=False); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
def normstem(p): return re.sub(r"[\s_-]+","",Path(p).stem.casefold())
def context_key(source):
    p=Path(source).resolve(); rel=p.relative_to(LIBRARY.resolve())
    if len(rel.parts)<3 or rel.parts[1]!="People & Relationships": raise ValueError(f"outside People & Relationships: {p}")
    sub=Path(*rel.parts[1:-1]).as_posix()
    return sub+"::"+normstem(p),rel.parts[0],sub,normstem(p)
def read_jsonl(path): return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def exclusions():
    keys=set(); hashes=set(); evidence={}
    def add(source, digest, reason):
        if not source: return
        try: k,style,sub,stem=context_key(source)
        except Exception: return
        keys.add(k)
        if digest: hashes.add(digest)
        evidence.setdefault(reason,{"concept_groups":set(),"sha256_count":set()})["concept_groups"].add(k)
        if digest: evidence[reason]["sha256_count"].add(digest)
    # The first People48 cohort.
    for r in json.loads((HERE/"inventory.json").read_text()).get("images",[]): add(r.get("source"),r.get("source_sha256"),"initial_people48")
    # Batch002 selected concept groups and every style version in them.
    b2=json.loads((HERE/"batch002"/"manifest.json").read_text())
    for g in b2.get("groups",[]):
        for r in g.get("versions",[]): add(r.get("source"),r.get("source_sha256"),"batch002")
    # Earlier development and validation pilots: exclude exact concept variants by path and hash.
    for cohort in ("development","validation"):
        p=HERE.parent/cohort/"selection.json"
        if not p.is_file(): continue
        for r in json.loads(p.read_text()).get("images",[]): add(r.get("source"),r.get("source_sha256"),cohort)
    # Older first 12-image matched pose pilot, if retained in this workspace.
    for p in (HERE.parent.parent/"matched_pose_webp_pilot"/"selection.json", HERE.parent.parent/"matched_pose_webp_pilot"/"candidates.json"):
        if not p.is_file(): continue
        d=json.loads(p.read_text()); rows=d if isinstance(d,list) else d.get("images",d.get("candidates",[]))
        for r in rows:
            if isinstance(r,dict): add(r.get("source") or r.get("source_path"),r.get("source_sha256"),"matched_pose_webp_pilot")
    return keys,hashes,{k:{"concept_groups":len(v["concept_groups"]),"sha256_count":len(v["sha256_count"])} for k,v in evidence.items()}

def choose(groups,styles):
    single_style=[k for k in sorted(groups) if k not in EXCLUDED_KEYS and len({r["style_id"] for r in groups[k]})<2]
    pop=[k for k in sorted(groups) if k not in EXCLUDED_KEYS and len({r["style_id"] for r in groups[k]})>=2]
    pop_hash=sha("\n".join(pop).encode())
    rng=random.Random(SEED); rng.shuffle(pop)
    chosen=[]; total=0; represented=set(); skipped_capacity=[]
    for rank,key in enumerate(pop,1):
        group=groups[key]; n=len(group)
        if total>=MIN_IMAGES and len(represented)==STYLECOUNT and total>=TARGET: break
        if n>MAX_IMAGES: skipped_capacity.append({"key":key,"size":n,"rank":rank,"reason":"single group exceeds max"}); continue
        if total+n>MAX_IMAGES:
            # Continue in the fixed random permutation to fill a whole group that fits.
            skipped_capacity.append({"key":key,"size":n,"rank":rank,"reason":"would exceed max"}); continue
        chosen.append((key,group,rank)); total+=n; represented.update(x["style_id"] for x in group)
    # Deterministic seeded continuation should naturally cover all styles. Fail closed if it did not.
    if not MIN_IMAGES<=total<=MAX_IMAGES or len(represented)!=STYLECOUNT:
        raise RuntimeError(f"random whole-group selection did not satisfy image/style bounds: {total}, styles={sorted(represented)}")
    return chosen,{"seed":SEED,"seeded_uniform_group_shuffle":True,"eligible_fresh_group_count":len(pop),"fresh_group_population_sha256":pop_hash,
                   "target_total_versions":TARGET,"selected_total_versions":total,"minimum_total_versions":MIN_IMAGES,"maximum_total_versions":MAX_IMAGES,
                   "style_ids_represented":sorted(represented),"groups_skipped_for_capacity":skipped_capacity,
                   "single_style_groups_excluded_by_matching_scope":len(single_style),
                   "selected_groups_in_seeded_order":[{"group_key":k,"shuffle_rank":rank,"available_versions":len(g)} for k,g,rank in chosen],
                   "selection_rule":"Add entire fresh groups in a seeded random permutation, continuing after groups that exceed the remaining capacity, until at least 150 versions and all 16 styles are included; hard limit 170. Candidate status is not part of eligibility or selection."}

def main():
    started=now(); t0=time.perf_counter()
    OUT.mkdir(parents=True,exist_ok=True)
    census=read_jsonl(SCREEN/"census_checkpoint.jsonl")
    if len(census)!=10891 or any(r.get("status")!="ok" for r in census): raise RuntimeError("need complete People census")
    inventory=json.loads((HERE/"inventory.json").read_text()); styles={r["style_id"]:r["style"] for r in inventory["images"]}
    style_ids={v:k for k,v in styles.items()}
    for r in census:
        key,sname,sub,stem=context_key(r["source"])
        if r.get("source_sha256") is None: raise ValueError("census missing source hash")
        r.update(style_id=style_ids[sname],style=sname,subfolder=sub,normalized_stem=stem,group_key=key)
    global EXCLUDED_KEYS
    EXCLUDED_KEYS, EXCLUDED_HASHES, exclusion_counts=exclusions()
    groups={}
    for r in census: groups.setdefault(r["group_key"],[]).append(r)
    for v in groups.values(): v.sort(key=lambda r:(r["style_id"],r["source"].casefold()))
    # Exact source-hash exclusions supplement group exclusions for known records whose naming/path changed.
    for k,v in list(groups.items()):
        fresh=[r for r in v if r["source_sha256"] not in EXCLUDED_HASHES]
        if len(fresh)!=len(v):
            # A concept group is inseparable; any known prior hash excludes the entire group.
            EXCLUDED_KEYS.add(k)
    chosen,stats=choose(groups,styles)
    census_raw=(SCREEN/"census_checkpoint.jsonl").read_bytes()
    census_sha=sha(census_raw)
    # Freeze the selection before decoding/rendering any selected image.
    frozen_groups=[]
    for i,(key,versions,rank) in enumerate(chosen,1):
        frozen_groups.append({"group_id":f"g{i:03d}","group_key":key,"random_shuffle_rank":rank,
            "subfolder_exact":versions[0]["subfolder"],"normalized_stem":versions[0]["normalized_stem"],
            "available_style_versions":len(versions),"versions":[{"batch_id":f"b03_s{r['style_id']:02d}_v{j:03d}","style_id":r["style_id"],"style":r["style"],"source":r["source"],"source_sha256":r["source_sha256"],"source_bytes":r["source_bytes"],"dimensions":r["dimensions"],"focused_candidate":bool(r.get("candidate_image_focused")),"broad_candidate":bool(r.get("candidate_image_broad"))} for j,r in enumerate(versions,1)]})
    selection={"batch_id":"batch003","status":"frozen_source_sample_before_visual_review","seed":SEED,"started_utc":started,"census_sha256":census_sha,"excluded_concept_groups":len(EXCLUDED_KEYS),"excluded_sha256_count":len(EXCLUDED_HASHES),"exclusion_counts":exclusion_counts,"excluded_concept_sources":["batch002 manifest","initial People48 inventory","development selection","validation selection","earlier matched_pose pilot metadata if present"],"random_selection":stats,"groups":frozen_groups}
    frozen_bytes=json.dumps(selection,indent=2,ensure_ascii=False).encode()+b"\n"
    selection["selection_frozen_sha256"]=sha(frozen_bytes)
    atomic(OUT/"selection_frozen.json",selection)

    import numpy as np
    from scipy import ndimage
    from PIL import Image,ImageDraw,ImageFont
    checks={"broad_candidate_count":0,"focused_candidate_count":0,"strict_white_core_pixels_at_512":0,"strict_components_ge64_at_512":0}
    groups_out=[]; image_rows=[]; blind_groups=[]
    for gi,g in enumerate(frozen_groups,1):
        groupdir=OUT/"previews"/"groups"/g["group_id"]; groupdir.mkdir(parents=True,exist_ok=True)
        contact={"purple":[],"checker":[]}; versions_out=[]; blind_versions=[]
        for version in g["versions"]:
            path=Path(version["source"]); raw=path.read_bytes()
            if sha(raw)!=version["source_sha256"]: raise ValueError(f"source hash changed: {path}")
            with Image.open(path) as im:
                rgba=im.convert("RGBA"); dims=list(rgba.size)
            if dims!=version["dimensions"] or dims[0]!=dims[1] or dims[0] not in (512,1024): raise ValueError(f"unexpected native dimensions {path} {dims}")
            arr=np.asarray(rgba,dtype=np.uint8); rgb=arr[:,:,:3]
            core=(rgb.min(2)>=240)&((rgb.max(2)-rgb.min(2))<=20)&(arr[:,:,3]>=128)
            labels,n=ndimage.label(core,structure=np.ones((3,3),dtype=np.uint8))
            dist=ndimage.distance_transform_edt(core)
            scale=dims[0]/512
            all_comps=[]
            areas=np.bincount(labels.ravel(),minlength=n+1)
            objects=ndimage.find_objects(labels,max_label=n)
            # Stable connected-component metadata includes all >=64-at-512 regions.
            for lab,sl in enumerate(objects,1):
                area=int(areas[lab]); norm_area=area/(scale*scale)
                if norm_area<64: continue
                if sl is None: continue
                ys,xs=sl; component=(labels[ys,xs]==lab); local_dist=dist[ys,xs]
                pos=np.argmax(np.where(component,local_dist,-1)); py,px=np.unravel_index(pos,component.shape); sy,sx=int(ys.start+py),int(xs.start+px)
                all_comps.append({"label_id":int(lab),"area_px":int(area),"area_at_512":round(norm_area,3),"bbox_xyxy":[int(xs.start),int(ys.start),int(xs.stop),int(ys.stop)],"interior_seed_xy":[sx,sy],"seed_max_edge_distance_px":round(float(dist[sy,sx]),3),"safe_interior_seed_meets_exact_cleanup_threshold":True})
            strict_pixels=int(core.sum()); strict_norm=strict_pixels/(scale*scale)
            checks["strict_white_core_pixels_at_512"]+=round(strict_norm)
            checks["broad_candidate_count"]+=int(bool(version.get("broad_candidate")))
            checks["focused_candidate_count"]+=int(bool(version.get("focused_candidate")))
            checks["strict_components_ge64_at_512"]+=len(all_comps)
            rgba_preview=rgba.copy()
            purple=Image.new("RGBA",dims,(86,67,118,255)); purple.alpha_composite(rgba_preview); purple_rgb=purple.convert("RGB")
            cell=max(8,24*int(scale)); checker=Image.new("RGB",dims,(244,244,244)); cd=ImageDraw.Draw(checker)
            for y in range(0,dims[1],cell):
                for x in range(0,dims[0],cell):
                    if (x//cell+y//cell)%2: cd.rectangle((x,y,x+cell-1,y+cell-1),fill=(202,202,202))
            checker.paste(rgba,(0,0),rgba)
            ident=version["batch_id"]; prefix=ident
            f_purple=f"{prefix}_purple.png"; f_checker=f"{prefix}_checker.png"; f_overlay=f"{prefix}_strict_cc_overlay.png"
            purple_rgb.save(groupdir/f_purple,format="PNG",optimize=False); checker.save(groupdir/f_checker,format="PNG",optimize=False)
            over=purple_rgb.copy(); dr=ImageDraw.Draw(over); line=max(1,round(scale)); font=ImageFont.load_default()
            for c in all_comps:
                x0,y0,x1,y1=c["bbox_xyxy"]; lab=c["label_id"]
                dr.rectangle((x0,y0,x1-1,y1-1),outline=(255,0,185),width=line)
                dr.text((x0,y0),str(lab),fill=(255,0,185),font=font,stroke_width=1,stroke_fill=(0,0,0))
            over.save(groupdir/f_overlay,format="PNG",optimize=False)
            comp_row={"id":ident,"batch_id":ident,"style_id":version["style_id"],"style":version["style"],"source":str(path),"source_sha256":version["source_sha256"],"source_bytes":version["source_bytes"],"dimensions":dims,"focused_candidate":version["focused_candidate"],"broad_candidate":version["broad_candidate"],"strict_white_core_pixels":strict_pixels,"strict_white_core_pixels_at_512":round(strict_norm,3),"proposed_simple_eligibility_total_strict_white_ge256_at_512":strict_norm>=256,"strict_white_component_count":int(n),"components_ge64_at_512":all_comps,"preview_files":{"purple":"previews/groups/"+g["group_id"]+"/"+f_purple,"checker":"previews/groups/"+g["group_id"]+"/"+f_checker,"strict_cc_overlay":"previews/groups/"+g["group_id"]+"/"+f_overlay}}
            for fl in (f_purple,f_checker,f_overlay): comp_row["preview_files"]["sha256_"+fl]=sha_file(groupdir/fl)
            versions_out.append(comp_row); image_rows.append(comp_row)
            blind_versions.append({k:comp_row[k] for k in ("id","batch_id","style_id","style","source","source_sha256","source_bytes","dimensions","strict_white_core_pixels","strict_white_core_pixels_at_512","strict_white_component_count","components_ge64_at_512","preview_files")})
            if dims==[512,512]:
                contact["purple"].append((ident,purple_rgb)); contact["checker"].append((ident,checker))
            # Native1024s are individual PNGs above and never put on a reduced-size contact sheet.
        contacts=[]
        for bg,items in contact.items():
            for page,start in enumerate(range(0,len(items),4),1):
                subset=items[start:start+4]; sheet=Image.new("RGB",(1040,1080),(255,255,255)); sd=ImageDraw.Draw(sheet); sd.text((8,4),f"{g['group_id']} {bg} native 512px · page {page}",fill=(0,0,0))
                for k,(ident,tile) in enumerate(subset):
                    x=(k%2)*520; y=20+(k//2)*520; sd.text((x+4,y+2),ident,fill=(0,0,0)); sheet.paste(tile,(x+4,y+18))
                fn=f"contact_512_{bg}_{page:02d}.png"; sheet.save(groupdir/fn,format="PNG",optimize=False); contacts.append({"file":"previews/groups/"+g["group_id"]+"/"+fn,"sha256":sha_file(groupdir/fn),"tile_count":len(subset),"tile_dimensions_native":[512,512]})
        for v in versions_out:
            for bg in ("purple","checker"): v["contact_sheets"]=[c for c in contacts if f"_{bg}_" in c["file"]]
        group_record={**g,"versions":versions_out,"preview_contact_sheets":contacts}
        groups_out.append(group_record)
        blind_groups.append({"group_id":g["group_id"],"group_key":g["group_key"],"random_shuffle_rank":g["random_shuffle_rank"],"available_style_versions":len(blind_versions),"versions":blind_versions,"preview_contact_sheets":contacts})
        # Per-group completion checkpoint so the source reviewer gets durable files.
        atomic(groupdir/"checkpoint.json",{"status":"complete","group_id":g["group_id"],"source_hashes":[v["source_sha256"] for v in versions_out],"preview_hashes":{f:sha_file(groupdir/f) for f in [*([Path(v["preview_files"]["purple"]).name for v in versions_out]),*([Path(v["preview_files"]["checker"]).name for v in versions_out]),*([Path(v["preview_files"]["strict_cc_overlay"]).name for v in versions_out])]},"contact_sheets":contacts,"completed_utc":now()})
        if gi%5==0: print(f"completed group {gi}/{len(frozen_groups)} at {now()}",flush=True)
    finished=now(); elapsed=round(time.perf_counter()-t0,3)
    census_by_style={s:{"selected":sum(v["style_id"]==sid for v in image_rows),"focused_candidate":sum(v["style_id"]==sid and v["focused_candidate"] for v in image_rows),"nonfocused":sum(v["style_id"]==sid and not v["focused_candidate"] for v in image_rows)} for sid,s in styles.items()}
    final={"batch_id":"batch003","schema_version":1,"status":"source_visual_review_pending","selection_frozen_sha256":selection["selection_frozen_sha256"],"census_sha256":census_sha,"strict_white_rule":{"rgb_min":240,"max_channel_range":20,"min_alpha":128,"connectivity":8,"component_inventory_min_area_at_512":64,"simple_proposed_eligibility_total_pixels_at_512":256,"permission_to_skip_visual_source_review":False},"started_utc":started,"prep_finished_utc":finished,"prep_elapsed_seconds":elapsed,"random_seed":SEED,"exclusion_counts":exclusion_counts,"excluded_concept_group_count":len(EXCLUDED_KEYS),"excluded_source_sha256_count":len(EXCLUDED_HASHES),"selection_probability_caveat":"Seeded group-level random sample of fresh exact People & Relationships subfolder/stem groups, conditioned on covering all 16 styles and reaching 140–170 total variants. All versions in each selected group are included; not an equal-probability per-image sample. Old focused-candidate status and proposed simple eligibility are metadata only; every selected version receives source review.","random_selection":stats,"selected_total_images":len(image_rows),"selected_group_count":len(groups_out),"styles":styles,"counts_by_style":census_by_style,"aggregate_component_screen_counts":checks,"groups":groups_out}
    atomic(OUT/"manifest.json",final)
    blind={"batch_id":"batch003","schema_version":1,"status":"blind_source_visual_review_pending","selection_frozen_sha256":selection["selection_frozen_sha256"],"census_sha256":census_sha,"started_utc":started,"prep_finished_utc":finished,"random_seed":SEED,"groups":blind_groups,"selected_total_images":len(image_rows),"selected_group_count":len(groups_out),"selection_notes":"This manifest deliberately omits prior focused/broad candidate flags. Component measurements and unannotated PNGs are provided for source-semantic review; they are not editing authority."}
    atomic(OUT/"blind_manifest.json",blind)
    atomic(ROOT_OUT/"FINAL_POINTER.json",{"batch_id":"batch003","status":"final_corrected_prep_available","superseded_attempt":{"path":"manifest.json","selected_total_images":153,"group_count":21,"reason":"Pre-review scope correction: single-style groups excluded and blind-manifest filter-pass boolean removed."},"final_manifest":"final/manifest.json","blind_manifest":"final/blind_manifest.json","selection_frozen":"final/selection_frozen.json","final_selection_sha256":selection["selection_frozen_sha256"],"final_total_images":len(image_rows),"final_group_count":len(groups_out),"finished_utc":finished})
    print(json.dumps({"batch_id":"batch003","selected_images":len(image_rows),"groups":len(groups_out),"styles":len(census_by_style),"focused_candidate_metadata":checks["focused_candidate_count"],"proposed_simple_eligible":sum(v["proposed_simple_eligibility_total_strict_white_ge256_at_512"] for v in image_rows),"components_ge64_at512":checks["strict_components_ge64_at_512"],"elapsed_seconds":elapsed,"manifest":str(OUT/"manifest.json"),"blind_manifest":str(OUT/"blind_manifest.json"),"started_utc":started,"finished_utc":finished},indent=2))

if __name__=="__main__": main()
