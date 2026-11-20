from pathlib import Path
import json,io,subprocess,xml.etree.ElementTree as E
from PIL import Image,ImageDraw,ImageFont
from raster_rig import make,el
H=Path(__file__).resolve().parent;T=Path('/private/tmp/task9_remaining_people_20261119');bases=json.loads((H/'bases.json').read_text());font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14);out=[]
for si in range(0,len(bases),2):
 sheet=Image.new('RGB',(1400,660),'#e5edf5');draw=ImageDraw.Draw(sheet)
 for j,b in enumerate(bases[si:si+2]):
  for k,pose in enumerate(['stand','fast','slow','strong','weak','old','hold']):
   from anchors import D
   cfg=D[(b['style'],b['gender'])];bw=cfg['chest_width']*1.1;bh=bw*.77;book=(cfg['chest'][0]-bw/2,cfg['chest'][1]-bh/2,bw,bh);defs,body,arms,cfg=make(b,pose,book=book);svg=el('svg',{'viewBox':'0 0 512 512','width':512,'height':512});svg.extend([defs,body])
   if pose=='hold':svg.append(el('rect',{'x':book[0],'y':book[1],'width':bw,'height':bh,'fill':'#f5c518','stroke':'#1a1a1a','stroke-width':4}));svg.append(arms)
   data=E.tostring(svg);im=Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert'],input=data))).convert('RGBA');bbox=im.getchannel('A').getbbox();out.append({'style':b['style'],'gender':b['gender'],'pose':pose,'bbox':bbox})
   thumb=im.resize((200,200),Image.Resampling.LANCZOS);x=k*200;y=j*330;draw.text((x+5,y+5),b['gender']+' '+pose,font=font,fill='black');sheet.paste(thumb,(x,y+50),thumb)
   if si in [0,6,8,10] and pose in ['fast','hold']:im.save(T/(str(si)+'_'+b['gender']+'_'+pose+'.png'))
 draw.text((10,630),bases[si]['style'],font=font,fill='black');sheet.save(T/f'assets_{si//2+1:02}.jpg',quality=95)
(H/'asset_bounds.json').write_text(json.dumps(out,indent=2));print('Rendered 168 posed assets across 12 styles for review.')
