from pathlib import Path
import json,io,subprocess,xml.etree.ElementTree as E
from PIL import Image,ImageDraw
from poses import make
from raster_rig import el
H=Path(__file__).resolve().parent;T=Path('/private/tmp/task9_remaining_people_20261119');bases=json.loads((H/'bases.json').read_text());records=[]
for start in range(0,len(bases),2):
 out=Image.new('RGB',(1280,560),'#e7edf4');d=ImageDraw.Draw(out)
 for j,b in enumerate(bases[start:start+2]):
  for i,pose in enumerate(['fast','slow','strong','weak','old']):
   defs,body,m=make(b,pose,'asset');svg=el('svg',{'viewBox':'0 0 512 512','width':512,'height':512});svg.extend([defs,body]);im=Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert'],input=E.tostring(svg)))).convert('RGBA');bbox=im.getchannel('A').getbbox();im.thumbnail((256,256));out.paste(im,(i*256,j*280+20),im);d.text((i*256+5,j*280+3),b['style']+' '+b['gender']+' '+pose,fill='black');records.append(dict(m,style=b['style'],bbox=bbox))
 out.save(T/f'native_assets_{start//2+1:02}.jpg',quality=95)
(H/'native_pose_bounds.json').write_text(json.dumps(records,indent=2));print('Rendered 120 native pose assets.')
