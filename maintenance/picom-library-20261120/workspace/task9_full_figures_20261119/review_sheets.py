from pathlib import Path
import json,subprocess,io
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;T=Path('/private/tmp/task9_full_figures_20261119');rows=json.loads((H/'outputs.json').read_text());font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
checks=[]
def render(p):return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',p]))).convert('RGBA')
for start in range(0,len(rows),6):
 sheet=Image.new('RGB',(1120,930),'white');d=ImageDraw.Draw(sheet)
 for j,r in enumerate(rows[start:start+6]):
  x=j%2*560;y=j//2*310;d.text((x+8,y+3),r['id']+'     BEFORE  |  AFTER',font=font,fill='black')
  bb=[]
  for k,key in enumerate(['source','output']):
   im=render(r[key]);b=im.getchannel('A').getbbox();bb.append(b);im=im.resize((280,280),Image.Resampling.LANCZOS);sheet.paste('#e5edf5',(x+k*280,y+25,x+(k+1)*280,y+305));sheet.paste(im,(x+k*280,y+25),im)
  checks.append({'id':r['id'],'source_alpha_bbox':bb[0],'output_alpha_bbox':bb[1],'sheet':start//6+1})
 sheet.save(T/f'review_{start//6+1:02}.jpg',quality=94)
(H/'render_checks.json').write_text(json.dumps(checks,indent=2));print('Rendered 16 before/after sheets covering every output.')
