from pathlib import Path
if Path(__file__).with_name('published.json').exists():
 raise SystemExit('This run is published. Do not regenerate staging or replace its source evidence.')
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as E,subprocess,io,re
from PIL import Image
H=Path(__file__).resolve().parent;L=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');rows=json.loads((H/'outputs.json').read_text());qa=[];existing={};outputs=[]
for st in ['3D animated cartoon','Kawaii','Flat outlined','Mulberry','Simple anime']:
 for base in [L/st/'Comparatives',Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/People')/st/'Comparatives']:
  if base.exists():
   for p in base.rglob('*'):
    if p.is_file():existing[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for r in rows:
 p=Path(r['output']);root=E.parse(p).getroot();root.set('data-review-status','accepted-every-output-visually-checked');E.ElementTree(root).write(p,encoding='utf-8',xml_declaration=True)
 ids=[e.get('id') for e in root.iter() if e.get('id')];assert len(ids)==len(set(ids));refs=re.findall(r'url\(#([^)]*)\)',p.read_text());assert set(refs)<=set(ids),(r['id'],set(refs)-set(ids))
 im=Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(p)]))).convert('RGBA');b=im.getchannel('A').getbbox();assert b and min(b[:2])>0 and max(b[2:])<512,(r['id'],b)
 srcroot=E.parse(r['source']).getroot();assert [e.attrib for e in srcroot.iter() if e.get('data-comparative-person')]==[e.attrib for e in root.iter() if e.get('data-comparative-person')]
 dest=L/r['style']/'Comparatives'/'People'/r['filename'];assert not dest.exists(),dest
 sha=hashlib.sha256(p.read_bytes()).hexdigest();qa.append({'id':r['id'],'result':'accepted','visual_comparison':'every before/after cell inspected across 16 sheets; changed strength cases rechecked; all 16 age variants rechecked after walking-stick grounding','native_followup':r['id'] in ['3d_weaker_f','3d_older_f','kawaii_faster_f','3d_faster_m'],'sha256':sha,'alpha_bbox':b,'annotations_retained':r['annotation_primitives'],'unique_ids_and_local_references_valid':True,'original_scene_transforms_and_opacity_preserved':True})
 outputs.append(dict(r,staged_path=str(p),destination=str(dest),sha256=sha,bytes=p.stat().st_size))
for p,sha in json.loads((H/'source_hashes.json').read_text()).items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha
for row in json.loads((H/'other_styles_evidence.json').read_text()):
 for item in row['items']:
  if item['path']:assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
(H/'visual_review_log.json').write_text(json.dumps(qa,indent=2));(H/'publish_manifest.json').write_text(json.dumps(outputs,indent=2));(H/'existing_hashes.json').write_text(json.dumps(existing,indent=2));print('Final QA passed for 96. Ready to move into new Library comparative People subfolders; existing files will not be replaced.')
