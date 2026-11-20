from pathlib import Path
import json,hashlib,os
H=Path(__file__).resolve().parent;rows=json.loads((H/'publish_manifest.json').read_text());expected=json.loads((H/'existing_hashes.json').read_text());source=json.loads((H/'source_hashes.json').read_text())
for p,sha in {**expected,**source}.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,p
for r in rows:
 assert not Path(r['destination']).exists(),r['destination']
 assert hashlib.sha256(Path(r['staged_path']).read_bytes()).hexdigest()==r['sha256'],r['id']
receipt=[]
for r in rows:
 dst=Path(r['destination']);dst.parent.mkdir(parents=True,exist_ok=True);os.rename(r['staged_path'],dst)
 assert hashlib.sha256(dst.read_bytes()).hexdigest()==r['sha256']
 receipt.append({'id':r['id'],'path':str(dst),'sha256':r['sha256'],'bytes':dst.stat().st_size,'source':r['source'],'method':'move accepted new SVG; no overwrite, no backup copy'})
 (H/'published.json').write_text(json.dumps({'complete':False,'files':receipt},indent=2))
for p,sha in {**expected,**source}.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,p
for p in sorted((H/'outputs').glob('*')):p.rmdir()
(H/'outputs').rmdir()
(H/'published.json').write_text(json.dumps({'complete':True,'count':len(receipt),'total_bytes':sum(r['bytes'] for r in receipt),'original_and_existing_file_hashes_verified':len({**expected,**source}),'files':receipt},indent=2))
master=Path('/Users/paulblenkhorn/Desktop/picom_review/LIBRARY_TASKS.md');heading='## Task 9 — 96 full-figure comparatives complete; all People styles retained in scope — 2026-11-19'
entry='''

## Task 9 — 96 full-figure comparatives complete; all People styles retained in scope — 2026-11-19

Paul approved full figures for 3D animated cartoon and Kawaii, preserving arrows, details and meaningful poses, with every changed image checked. Completed 96 SVGs: 24 concepts × two genders × two styles. Every output was compared visually to its saved source; posed parts preserve running/walking, strong/weak stance, age and size differences. Grey hair and walking sticks are retained for older figures. Dirt, odour and crossed-out drops were adjusted to the full bodies. All semantic annotation primitives remain; arrows/star geometry and scene opacity/transforms remain unchanged. Weak postures were refined and rechecked; all age cases were rechecked after aligning sticks with hands and ground.

Finished new files: Library/3D animated cartoon/Comparatives/People and Library/Kawaii/Comparatives/People. The People subfolder avoids mixing these with existing root-level object alternatives. No existing Library or People file was replaced. Accepted outputs were moved from staging, with no backup copies.

Review and evidence: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_full_figures_20261119/index.html — published.json, visual_review_log.json, source_hashes.json, existing_hashes.json and people_style_status.json. Status for ALL 19 People styles is visible in this review. This completion supersedes the preview-only gate for these 96 files; it does not mark Task 9 complete.

Paul clarified that the full-figure question concerns the other People styles too, including Monkey, Friendly aliens, Robot and Doll. They were not excluded. Read-only assessment of proposed bases plus cleaner/faster/older in ALL 12 outstanding styles confirms useful full-character artwork and poses already exist in their numbered folders. Recommend reusing their own complete characters and posed artwork for missing root-level substitutions, retaining arrows/objects and characteristic tails/antennae/horns/robot joints/clothing/textures. No whole-style tracing or blanket replacement of good numbered drawings. Standing cutouts do not replace action poses.

**Outstanding style-root substitutions remain explicitly tracked for all 12:** Basic; Classic flat TV cartoon; Clay plasticine; Doll; Friendly aliens; Monkey; Monster; Robot; Soccer player; Teddy bear; Wizard; Wood. No new Pronouns, Contractions or Comparatives have been generated for those 12 in this pass. Base/variant choices and reuse of numbered artwork remain to be resolved. Do not confuse missing unnumbered folders with absence of numbered symbols, or mark those styles done.

**Existing work still to reuse/publish:** 480 approved People substitutions (340 Pronouns, 140 Contractions) in the five saved SVG styles; five they-them corrections remain. Flat outlined, Mulberry and Simple anime retain their 144 comparative adaptations under the earlier decision. Complete figures could also be considered for them, but no further edits were authorised or made here. The 65 generic drawings and 375 non-person components remain unchanged. Other publication mapping remains outstanding. Sommi and Sommi clothed remain completed and excluded from new work. Non-People are excluded. Task 10 (plurals/tenses) remains later; do not skip remaining Task 9 work.
'''
s=master.read_text()
if heading not in s:master.write_text(s+entry)
print(json.dumps({'published':len(receipt),'bytes':sum(r['bytes'] for r in receipt),'existing_files_unchanged':len({**expected,**source}),'master_plan_updated':True}))
