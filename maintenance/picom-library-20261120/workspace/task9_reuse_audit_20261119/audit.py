from pathlib import Path
import json,hashlib,re,io,subprocess,math,collections,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;I=H.parent/'task9_inventory_20261119';TMP=Path('/private/tmp/task9_reuse_audit_20261119');TMP.mkdir(exist_ok=True)
raw=json.loads((I/'existing_outputs_raw.json').read_text());templates=json.loads((I/'template_inventory.json').read_text());lookup={(t['category'],t['concept']):t for t in templates};catmap={'Pronouns':'09 Pronouns','Contractions':'02 Contractions','Comparatives':'01 Comparatives'}
ns={'s':'http://www.w3.org/2000/svg'};rows=[];renders={};font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12)
def norm(n):return re.sub(r'[- ]?\([MF]\)$','',n)
def render(p):
 if p.suffix=='.svg':return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(p)]))).convert('RGBA')
 im=Image.open(p).convert('RGBA');im.thumbnail((512,512));return im
for old in raw:
 if old['style']=='Sommi companion objects' or (old['location']=='Library' and old['category']=='Comparatives'):continue
 r=old.copy();p=Path(r['path']);r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r['concept']=norm(r['name']);r['id']=f'R{len(rows)+1:04d}';t=lookup.get((catmap[r['category']],r['concept']));r['classification']=t['classification'] if t else 'test/unmatched';r['expected_people']=t['figure_count'] if t else None;r['source_template']=t['path'] if t else None;r['flags']=[]
 if p.suffix=='.svg':
  root=ET.parse(p).getroot();r['provenance']={k:v for k,v in root.attrib.items() if k.startswith('data-') and k!='data-copyright'};r['core_figure_count']=sum(bool(e.get('data-core-figure')) for e in root.iter());r['styled_figure_count']=sum(bool(e.get('data-core-style')) for e in root.iter());r['genders']=collections.Counter(e.get('data-gender') for e in root.iter() if e.get('data-gender'));r['ids_duplicate']=sorted(k for k,v in collections.Counter(e.get('id') for e in root.iter() if e.get('id')).items() if v>1)
  if t and t['figure_count'] and r['styled_figure_count']!=t['figure_count']:r['flags'].append('person substitution incomplete or special drawing')
  if r['ids_duplicate']:r['flags'].append('duplicate SVG IDs')
 if r['classification']=='no-person':r['review_scope']='non-People component: retain unchanged';r['visual_sheet']=None
 else:r['review_scope']='visual reuse review'
 rows.append(r)
# Render and inspect each People output, one process at a time. Keep contact sheets only.
for style in sorted({r['style'] for r in rows}):
 for cat in ['Pronouns','Contractions','Comparatives']:
  rr=[r for r in rows if r['style']==style and r['category']==cat and r['review_scope']=='visual reuse review'];rr.sort(key=lambda r:(r['concept'].lower(),r['name']))
  slug=re.sub('[^a-z0-9]+','_',style.lower())+'_'+cat.lower()
  for page in range(math.ceil(len(rr)/20)):
   part=rr[page*20:(page+1)*20];sheetname=f'{slug}_{page+1:02d}.jpg';out=Image.new('RGB',(1200,42+math.ceil(len(part)/5)*278),'white');d=ImageDraw.Draw(out);d.text((8,8),style+' / '+cat+f' / {page+1}',font=font,fill='black')
   for j,r in enumerate(part):
    im=render(Path(r['path']));a=np.asarray(im)[:,:,3];bbox=im.getbbox();r['render_bbox']=bbox;r['edge_ink_pixels']=int((a[0]>24).sum()+(a[-1]>24).sum()+(a[:,0]>24).sum()+(a[:,-1]>24).sum());r['opaque_canvas']=bool((a>250).all());r['render_size']=im.size
    if r['edge_ink_pixels']>3:r['flags'].append('ink reaches canvas edge')
    if bbox is None:r['flags'].append('blank render')
    im.thumbnail((230,230));x=j%5*240;y=42+j//5*278;out.paste('#e5edf5',(x,y,x+230,y+230));out.paste(im,(x+(230-im.width)//2,y+(230-im.height)//2),im);d.text((x+2,y+233),r['id']+' '+r['name'],font=font,fill='black');d.text((x+2,y+251),'people '+str(r['expected_people'])+' / styled '+str(r.get('styled_figure_count','raster'))+(' / EDGE' if r['edge_ink_pixels']>3 else ''),font=font,fill='black');r['visual_sheet']=sheetname
   out.save(TMP/sheetname,quality=94)
(H/'files.json').write_text(json.dumps(rows,indent=2));stats=dict(existing_files=len(rows),visual_review_files=sum(r['review_scope']=='visual reuse review' for r in rows),non_people_unchanged=sum(r['classification']=='no-person' for r in rows),contact_sheets=len(list(TMP.glob('*.jpg'))),sheets=[p.name for p in sorted(TMP.glob('*.jpg'))]);(H/'initial_stats.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2))
