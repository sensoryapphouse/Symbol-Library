from pathlib import Path
import json,hashlib,io,math
from PIL import Image,ImageDraw,ImageFont
import subprocess
import numpy as np
from scipy import ndimage
HERE=Path(__file__).resolve().parent
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
MUL=LIB.parent/'People/Mulberry/01 Comparatives'
FLU=Path('/Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Fluent Symbols/svgs/01 Comparatives')
TMP=Path('/private/tmp/picom_comparative_arrow_audit_20261119');TMP.mkdir(exist_ok=True)
FONT=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
SMALL=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13)

def render(p):
 if p.suffix=='.svg': return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(p)]))).convert('RGBA')
 return Image.open(p).convert('RGBA')

def inventory():
 rows=[];styles=[]
 groups=[(p.name,p/'01 Comparatives','Library') for p in sorted(LIB.iterdir()) if p.is_dir() and not p.name.startswith('_')]+[('Mulberry',MUL,'People retained native SVG'),('Fluent reference',FLU,'reference')]
 for style,folder,kind in groups:
  assets=sorted(p for p in folder.glob('*') if p.suffix.lower() in ('.webp','.svg'))
  styles.append(dict(style=style,folder=str(folder),kind=kind,count=len(assets)))
  for p in assets:
   im=render(p);a=np.array(im.getchannel('A'));labels,n=ndimage.label(a>32);objects=ndimage.find_objects(labels);candidates=[]
   for i,sl in enumerate(objects,1):
    y,x=sl;w=x.stop-x.start;h=y.stop-y.start;area=int(np.count_nonzero(labels[sl]==i))
    if area>=12 and y.start<im.height*.65 and 5<=w<=im.width*.35 and 8<=h<=im.height*.35:
     candidates.append(dict(bbox=[x.start,y.start,x.stop,y.stop],area=area))
   rows.append(dict(id=f'A{len(rows)+1:04}',style=style,kind=kind,name=p.stem,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=list(im.size),bytes=p.stat().st_size,detached_upper_components=candidates))
 (HERE/'inventory.json').write_text(json.dumps(dict(styles=styles,files=rows),indent=2))
 for style in styles:
  subset=[r for r in rows if r['style']==style['style']]
  for page in range(math.ceil(len(subset)/26)):
   ss=subset[page*26:(page+1)*26];sheet=Image.new('RGB',(1100,60+math.ceil(len(ss)/5)*250),'#e5edf5');d=ImageDraw.Draw(sheet);d.text((12,12),f"{style['style']} — page {page+1} — original images",font=FONT,fill='black')
   for j,r in enumerate(ss):
    x=(j%5)*220;y=60+(j//5)*250
    im=render(Path(r['path']));im.thumbnail((210,210),Image.Resampling.LANCZOS);sheet.paste(im,(x+(220-im.width)//2,y),im)
    d.text((x+5,y+211),r['id']+' '+r['name'],font=SMALL,fill='black');d.line((x,y+245,x+220,y+245),fill='#abb8c8')
   out=TMP/(style['style'].replace(' ','_')+f'_{page+1}.jpg');sheet.save(out,quality=91)
 print(json.dumps(styles));print('Sheets',TMP)
if __name__=='__main__':inventory()
