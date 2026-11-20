from pathlib import Path
import json,sqlite3,collections
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;T=Path('/private/tmp/task10_production_20261119');db=sqlite3.connect(H/'queue.sqlite');db.row_factory=sqlite3.Row;ids=json.loads((H/'first_batch_ids.json').read_text());rows=[dict(db.execute('select * from jobs where id=?',(i,)).fetchone()) for i in ids];groups=collections.defaultdict(list)
for r in rows:groups[r['style']].append(r)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13);pages=[]
for si,(style,rs) in enumerate(groups.items(),1):
 if any(r['status']=='pending' for r in rs):continue
 for pi in range(2):
  part=rs[pi*10:(pi+1)*10];sheet=Image.new('RGB',(1152,1120),'#e7edf4');d=ImageDraw.Draw(sheet)
  for i,r in enumerate(part):
   x=i%3*384;y=i//3*280;d.text((x+4,y+3),style,font=font,fill='black');d.text((x+4,y+21),r['kind']+': '+Path(r['destination']).stem[:47],font=font,fill='black');d.text((x+4,y+40),'Source | Result'+('  s='+str(r['scale']) if r['scale'] else ''),font=font,fill='black')
   if r['status']=='review':
    for j,k in enumerate(['before','after']):
     im=Image.open(T/f"{r['id']}_{k}.png").convert('RGBA');sheet.paste(im,(x+j*192,y+61),im)
   else:d.text((x+4,y+90),'HELD: '+str(r['note'])[:47],font=font,fill='#a02020')
  path=T/f'review_{si:02}_{pi+1}.jpg';sheet.save(path,quality=94);pages.append({'page':f'{si:02}_{pi+1}','style':style,'sheet':str(path),'ids':[r['id'] for r in part if r['status']=='review']})
(H/'first_review_pages.json').write_text(json.dumps(pages,indent=2));print('Ready pages',len(pages))
