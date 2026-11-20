from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as E,io,subprocess
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;W=H.parent;A=W/'task9_reuse_audit_20261119';L=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');audit=json.loads((A/'files.json').read_text());styles=['3D animated cartoon','Flat outlined','Kawaii','Mulberry','Simple anime'];assert not (H/'published.json').exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
originals={r['path']:r['sha256'] for r in audit if r['style'] in styles}
for p,v in originals.items():assert sha(p)==v,('Source changed since review',p)
existing={str(p):sha(p) for st in styles for cat in ['Pronouns','Contractions','Comparatives'] for p in (L/st/cat).rglob('*') if p.is_file()}
rows=[]
for r in audit:
 if r['style'] not in styles:continue
 if r['decision']=='reuse' or (r['decision']=='comparative_decision' and r['style'] in ['Flat outlined','Mulberry','Simple anime']):
  assert r['visually_reviewed'];dst=L/r['style']/r['category']
  if r['category']=='Comparatives' and r['style']=='Flat outlined':dst/='People'
  rows.append(dict(style=r['style'],category=r['category'],name=r['name'],concept=r['concept'],source=r['path'],destination=str(dst/(r['name']+'.svg')),sha256=r['sha256'],bytes=r['bytes'],method='reuse_byte_identical',prior_review_id=r['id'],prior_review_sheet=r['visual_sheet']))
def annotations(root,source=False):
 c=collections.Counter()
 def walk(e):
  t=e.tag.rsplit('}',1)[-1]
  if t in ['defs','metadata','title','desc'] or e.get('data-core-style') or e.get('data-core-figure'):return
  if source and t=='g' and (sum(ch.tag.rsplit('}',1)[-1]=='path' for ch in e)>5 or sum(bool(ch.get('data-part')) for ch in e)>5):return
  if t in ['path','rect','circle','ellipse','line','polyline','polygon','text']:
   attrs={k:v for k,v in e.attrib.items() if k not in ['id','class'] and not k.startswith('data-')};c[(t,json.dumps(attrs,sort_keys=True),(e.text or '').strip())]+=1
  for ch in e:walk(ch)
 walk(root);return c
changes=[]
for st in styles:
 old=next(r for r in audit if r['style']==st and r['decision']=='repair_by_reuse');template=Path(old['source_template']);originals[str(template)]=sha(template);ref=annotations(E.parse(template).getroot(),True)
 for sex,key,suffix in [('M','reuse_candidate',''),('F','reuse_candidate_female',' (F)')]:
  src=Path(old[key]);root=E.parse(src).getroot();assert annotations(root)==ref
  figs=[e for e in root.iter() if e.get('data-core-style') and e.get('data-pilot-person')];assert len(figs)==3 and all(e.get('data-gender')==sex for e in figs)
  r=dict(style=st,category='Pronouns',name='they-them'+suffix,concept='they-them',source=str(src),destination=str(L/st/'Pronouns'/('they-them'+suffix+'.svg')),sha256=sha(src),bytes=src.stat().st_size,method='correct_they_them_by_existing_they',gender=sex,previous_source=old['path'],reference=str(template),arrow_primitives_unchanged=True,styled_figures=3)
  rows.append(r);changes.append(r)
assert len(rows)==634 and len(changes)==10
for r in rows:
 assert not Path(r['destination']).exists(),r['destination']
 root=E.parse(r['source']).getroot()
 for e in root.iter():
  for k,v in e.attrib.items():
   if k.rsplit('}',1)[-1]=='href':assert v.startswith(('data:','#')),(r['source'],v)
assert len({r['destination'].casefold() for r in rows})==len(rows)
(H/'manifest.json').write_text(json.dumps(rows,indent=2));(H/'original_hashes.json').write_text(json.dumps(originals,indent=2));(H/'existing_library_hashes.json').write_text(json.dumps(existing,indent=2));(H/'corrections.json').write_text(json.dumps(changes,indent=2));(H/'progress.json').write_text(json.dumps({'status':'prepared; corrections awaiting visual review','reuse':624,'correction_outputs':10,'planned':634,'published':0},indent=2))
T=Path('/private/tmp/task9_completion_20261119');T.mkdir(exist_ok=True);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16);pages=[]
def render(p):return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','320','-h','320',str(p)]))).convert('RGBA')
for page,sts in enumerate([styles[:3],styles[3:]],1):
 sheet=Image.new('RGB',(960,360*len(sts)),'#e7edf4');d=ImageDraw.Draw(sheet);reviewed=[]
 for j,st in enumerate(sts):
  rs=[r for r in changes if r['style']==st];items=[(rs[0]['previous_source'],'Before: Fluent figures'),(rs[0]['source'],'After: default'),(rs[1]['source'],'After: female')]
  for i,(p,label) in enumerate(items):
   im=render(p);sheet.paste(im,(i*320,j*360+38),im);d.text((i*320+6,j*360+3),st,font=font,fill='black');d.text((i*320+6,j*360+21),label,font=font,fill='black')
  reviewed += [r['destination'] for r in rs]
 dst=T/f'corrections_{page}.jpg';sheet.save(dst,quality=94);pages.append({'page':page,'sheet':str(dst),'destinations':reviewed,'status':'pending'})
(H/'review_pages.json').write_text(json.dumps(pages,indent=2));print(json.dumps({'byte_identical_reuse':len(rows)-len(changes),'corrections':len(changes),'source_hashes_verified':len(originals),'existing_library_files_protected':len(existing),'review_pages':pages},indent=2))
