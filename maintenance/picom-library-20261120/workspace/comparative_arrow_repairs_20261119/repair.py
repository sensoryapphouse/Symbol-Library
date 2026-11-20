from pathlib import Path
import sys,json,hashlib,io,math,subprocess,copy
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw,ImageFont
from lxml import etree as ET

HERE=Path(__file__).resolve().parent
AUDIT=HERE.parent/'comparative_arrow_audit_20261119'
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
TMP=Path('/private/tmp/comparative_arrow_repairs_20261119')
FONT=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
SMALL=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12)
ROWS=json.loads((AUDIT/'results.json').read_text());QUEUE=[r for r in ROWS if r['proposed_action']!='retain']
assert len(QUEUE)==245
SELECTED={'A0023','A0063','A0141','A0038','A0501','A0671','A0701','A0580'}
OVERRIDES=HERE/'overrides.json'
def render(p):
 if p.suffix=='.svg':return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(p)]))).convert('RGBA')
 return Image.open(p).convert('RGBA')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clear_rect(r):
 m=r.get('arrow_measurement')
 if r['proposed_action']=='add selector':return None
 b=m['bbox'];x0,y0,x1,y1=b
 if 'isolated alpha' in m['method']:return [max(0,x0-2),max(0,y0-2),min(512,x1+2),min(512,y1+2)]
 return [max(0,x0-6),max(0,y0-6),min(512,x1+6),min(512,y1+2)]
def anchor(r):
 name=r['name'];m=r.get('arrow_measurement')
 if r['proposed_action']!='add selector':return (m['bbox'][0]+m['bbox'][2])/2
 if name=='older':return 340 if r['style']=='Basic' else 210
 return {'cleaner':345,'cleanest':390,'dirtier':345,'dirtiest':390,'drier':345,'faster':385,'fastest':395,'noisier':355,'noisiest':390,'oldest':130,'shorter (1)':350,'shortest':390,'slower':395,'slowest':415,'stronger':375,'strongest':395,'taller':320,'tallest':390,'weaker':360,'weakest':395,'wetter':350,'wettest':395,'younger':350,'youngest':390}[name]
def poly(cx,tip,h=68,w=40,angle=0):
 # Last point is the arrow tip; all coordinates are in the original 512px canvas.
 pts=np.array([[-6,-h],[6,-h],[6,-25],[w/2,-25],[0,0],[-w/2,-25],[-6,-25]])
 a=math.radians(angle);rot=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
 pts=pts@rot.T+np.array([cx,tip]);return [[round(float(x),2),round(float(y),2)] for x,y in pts]
def arrow_image(points):
 text='<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><polygon points="'+' '.join(f'{x},{y}' for x,y in points)+'" fill="#35b84b" stroke="#25352b" stroke-width="3.5" stroke-linejoin="round"/></svg>'
 return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512'],input=text.encode()))).convert('RGBA')
def make_plan(r,source):
 override=json.loads(OVERRIDES.read_text()).get(r['id'],{}) if OVERRIDES.exists() else {}
 rect=override.get('clear',clear_rect(r));base=np.array(source)
 if rect:
  x0,y0,x1,y1=map(int,rect);base[y0:y1,x0:x1]=0
 cx=override.get('anchor_x',anchor(r));alpha=base[:,:,3]
 lo,hi=max(0,int(cx-22)),min(512,int(cx+23))
 hits=np.where(np.sum(alpha[:,lo:hi]>64,axis=1)>=3)[0]
 top=int(hits[0]) if len(hits) else 150
 if 'tip' in override:
  x,y=override['tip'];angle=override.get('angle',0);points=poly(x,y,override.get('height',68),override.get('width',40),angle)
 else:
  points=poly(cx,top-12, min(68,max(64,top-15)))
  if min(p[1] for p in points)<2:
   # Side placement points down towards the upper left edge of the selected head.
   ys,xs=np.where((alpha>64)&(np.indices(alpha.shape)[0]>=top)&(np.indices(alpha.shape)[0]<top+40)&(np.indices(alpha.shape)[1]>cx-90)&(np.indices(alpha.shape)[1]<cx+90))
   left=int(xs.min()) if len(xs) else int(cx-45);right=int(xs.max()) if len(xs) else int(cx+45)
   options=[]
   for dy in (24,34,44):
    for side,edge in [(-1,left-10),(1,right+10)]:
     for angle in (45,30):
      option=poly(edge,top+dy,68,40,side*angle)
      if min(x for x,y in option)<2 or max(x for x,y in option)>510 or min(y for x,y in option)<2:continue
      aa=np.array(arrow_image(option))[:,:,3]>0
      if not np.any(aa&(alpha>0)):options.append(option)
   if not options:raise ValueError(f'No clear arrow placement for {r["id"]}: top {top}, head edges {left,right}')
   points=options[0]
 arrow=arrow_image(points);a=np.array(arrow)
 overlap=int(np.count_nonzero((a[:,:,3]>0)&(base[:,:,3]>0)))
 bounds=[min(p[0] for p in points)-2,min(p[1] for p in points)-2,max(p[0] for p in points)+2,max(p[1] for p in points)+2]
 if min(bounds[:2])<0 or max(bounds[2:])>512:raise ValueError(f'Arrow outside canvas {r["id"]} {bounds}')
 if overlap:raise ValueError(f'Arrow overlaps original {r["id"]}: {overlap} pixels; top={top}, anchor={cx}, points={points}')
 return dict(clear=rect,anchor_x=cx,head_top=top,points=points,arrow_bounds=bounds,overlap_pixels=overlap),Image.fromarray(base),arrow
def svg_edit(path,out,plan):
 tree=ET.parse(str(path));root=tree.getroot();ns='{http://www.w3.org/2000/svg}'
 if plan['clear']:
  x0,y0,x1,y1=plan['clear'];defs=ET.Element(ns+'defs');clip=ET.SubElement(defs,ns+'clipPath',id='comparative-arrow-preserve-figure',clipPathUnits='userSpaceOnUse')
  ET.SubElement(clip,ns+'path',d=f'M0 0H512V512H0Z M{x0} {y0}V{y1}H{x1}V{y0}Z',attrib={'clip-rule':'evenodd'})
  group=ET.Element(ns+'g',attrib={'clip-path':'url(#comparative-arrow-preserve-figure)'})
  for child in list(root):root.remove(child);group.append(child)
  root.append(defs);root.append(group)
 ET.SubElement(root,ns+'polygon',points=' '.join(f'{x},{y}' for x,y in plan['points']),fill='#35b84b',stroke='#25352b',attrib={'stroke-width':'3.5','stroke-linejoin':'round','id':'comparative-selection-arrow'})
 tree.write(str(out),encoding='utf-8',xml_declaration=False)
def prepare(style,only=None):
 rr=[r for r in QUEUE if r['style']==style];batch=HERE/'staging'/style;batch.mkdir(parents=True,exist_ok=True);records=[]
 prior={r['id']:r for r in json.loads((batch/'records.json').read_text())} if (batch/'records.json').exists() else {}
 for r in rr:
  if only and r['id'] not in only:records.append(prior[r['id']]);continue
  p=Path(r['path']);assert sha(p)==r['sha256'],f'Source changed {p}'
  source=render(p);assert source.size==(512,512)
  plan,base,arrow=make_plan(r,source);candidate=Image.alpha_composite(base,arrow);out=batch/(r['id']+p.suffix)
  if p.suffix=='.svg':svg_edit(p,out,plan)
  else:
   info=Image.open(p).info;meta={k:info[k] for k in ('icc_profile','exif','xmp') if k in info}
   candidate.save(out,'WEBP',quality=80,method=6,exact=True,**meta)
  decoded=render(out);s=np.array(source);c=np.array(decoded);expected=np.array(candidate);mask=np.array(arrow)[:,:,3]>0
  if plan['clear']:
   x0,y0,x1,y1=plan['clear'];mask[y0:y1,x0:x1]=True
  # SVG re-render may have a one-unit alpha rounding difference in an enclosing clip group.
  alpha_diff=int(np.count_nonzero(s[:,:,3][~mask]!=c[:,:,3][~mask]));max_alpha=int(np.abs(s[:,:,3].astype(int)-c[:,:,3].astype(int))[~mask].max())
  assert alpha_diff==0 or p.suffix=='.svg' and max_alpha<=1,(r['id'],alpha_diff,max_alpha)
  assert np.array_equal(s[~mask],expected[~mask]),r['id']
  opaque=(~mask)&(s[:,:,3]>128);rgbdiff=np.abs(c[:,:,:3].astype(int)-s[:,:,:3].astype(int));rgbmae=float(rgbdiff[opaque].mean())
  dest=LIB/'Mulberry'/'01 Comparatives'/p.name if p.suffix=='.svg' else p
  records.append(dict(id=r['id'],style=style,name=r['name'],source=str(p),source_sha256=r['sha256'],destination=str(dest),staged=str(out),output_sha256=sha(out),plan=plan,alpha_changed_outside_edit=alpha_diff,max_alpha_change_outside_edit=max_alpha,rgb_mae_outside_edit=rgbmae,source_bytes=p.stat().st_size,output_bytes=out.stat().st_size,reviewed=False))
  if r['id'] in SELECTED:
   ev=HERE/'examples_work';ev.mkdir(exist_ok=True);sheet=Image.new('RGB',(512,290),'#e5edf5');d=ImageDraw.Draw(sheet)
   for i,im in enumerate((source,decoded)):
    im=im.resize((256,256),Image.Resampling.LANCZOS);sheet.paste(im,(i*256,28),im)
   d.text((8,5),'Before',font=FONT,fill='black');d.text((264,5),'After',font=FONT,fill='black');sheet.save(ev/(r['id']+'.jpg'),quality=92)
 (batch/'records.json').write_text(json.dumps(records,indent=2));sheets(records)
 print(style,'prepared',len(records),'files; max RGB MAE',max(r['rgb_mae_outside_edit'] for r in records))
def sheets(records):
 style=records[0]['style'];dest=TMP/style;dest.mkdir(parents=True,exist_ok=True)
 for page in range(math.ceil(len(records)/9)):
  ss=records[page*9:(page+1)*9];sheet=Image.new('RGB',(1230,60+math.ceil(len(ss)/3)*340),'#f5f7fa');d=ImageDraw.Draw(sheet);d.text((12,10),f'{style} — before 128px / after 256px — page {page+1}',font=FONT,fill='black')
  for i,r in enumerate(ss):
   x=i%3*410;y=60+i//3*340
   for k,(p,size,bg) in enumerate([(r['source'],128,'#e5edf5'),(r['staged'],256,'#e5edf5')]):
    im=render(Path(p)).resize((size,size),Image.Resampling.LANCZOS);tile=Image.new('RGB',(size,size),bg);tile.paste(im,(0,0),im);sheet.paste(tile,(x+(140 if k else 0),y))
   # Also inspect final at small display size on dark background.
   im=render(Path(r['staged'])).resize((96,96),Image.Resampling.LANCZOS);tile=Image.new('RGB',(96,96),'#283240');tile.paste(im,(0,0),im);sheet.paste(tile,(x+16,y+150))
   d.text((x+5,y+263),r['id']+' '+r['name'],font=FONT,fill='black');d.text((x+5,y+286),'Before left; final right + 96px dark',font=SMALL,fill='black');d.text((x+5,y+305),'Old-arrow cut: '+str(r['plan']['clear']),font=SMALL,fill='black')
  sheet.save(dest/f'review_{page+1}.jpg',quality=94)
if __name__=='__main__':prepare(sys.argv[1],sys.argv[2].split(',') if len(sys.argv)>2 else None)
