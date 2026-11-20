from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;L=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');props=json.loads((H.parent/'task9_inventory_20261119/base_proposals.json').read_text());cand={r['id']:r for r in json.loads((H.parent/'task9_inventory_20261119/candidates.json').read_text())};skip={'3D animated cartoon','Kawaii','Flat outlined','Simple anime','Mulberry','Sommi','Sommi clothed'};rows=[]
for r in props:
 st=r['style']
 if st in skip:continue
 items=[{'label':'proposed standing base','path':cand[r['base_ids'][0]]['path']}]
 for name in ['cleaner','faster','older']:
  p=L/st/'01 Comparatives'/(name+'.webp');items.append({'label':'existing '+name,'path':str(p) if p.exists() else None})
 for item in items:
  if item['path']:item['sha256']=hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
 rows.append({'style':st,'items':items})
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',15)
for start in range(0,len(rows),3):
 sheet=Image.new('RGB',(1160,930),'white');d=ImageDraw.Draw(sheet)
 for j,r in enumerate(rows[start:start+3]):
  y=j*310;d.text((8,y+2),r['style'],font=font,fill='black')
  for k,item in enumerate(r['items']):
   x=k*290;d.text((x+8,y+22),item['label'],font=font,fill='black');sheet.paste('#e5edf5',(x,y+45,x+280,y+305))
   if item['path']:
    im=Image.open(item['path']).convert('RGBA');im.thumbnail((260,260));sheet.paste(im,(x+(280-im.width)//2,y+45+(260-im.height)//2),im)
   else:d.text((x+20,y+120),'Not present',font=font,fill='black')
 sheet.save('/private/tmp/task9_full_figures_20261119/other_'+str(start//3+1)+'.jpg',quality=92)
(H/'other_styles_evidence.json').write_text(json.dumps(rows,indent=2));print('Read-only comparison prepared for',len(rows),'styles.')
