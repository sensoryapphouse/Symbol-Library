from pathlib import Path
import json,io,subprocess,collections
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;T=Path('/private/tmp/task9_remaining_people_20261119/action');T.mkdir(exist_ok=True)
r=json.loads((H/'action_outputs.json').read_text());groups=collections.defaultdict(list)
for x in r:groups[(x['category'],x['concept'])].append(x)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13);pages=[]
def render(p):return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','256','-h','256',p]))).convert('RGBA')
for page,((cat,concept),xs) in enumerate(groups.items(),1):
 xs.sort(key=lambda x:(x['style'],x['gender']));refs=[next(x for x in xs if x['gender']==g) for g in sorted({x['gender'] for x in xs})];items=[dict(x,style='REFERENCE '+x['gender'],output=x['source']) for x in refs]+xs
 sheet=Image.new('RGB',(1536,840),'#e7edf4');d=ImageDraw.Draw(sheet)
 for i,x in enumerate(items):
  im=render(x['output']);bb=im.getchannel('A').getbbox();assert bb and min(bb)>=0
  c=i%6*256;y=i//6*280;sheet.paste(im,(c,y+22),im);d.text((c+4,y+3),x['style']+' '+x['gender'],font=font,fill='black')
 dest=T/f'{page:02}_{cat}_{concept}.jpg';sheet.save(dest,quality=93);pages.append({'page':page,'concept':concept,'category':cat,'sheet':str(dest),'outputs':[x['output'] for x in xs]})
 print(page,cat,concept,flush=True)
(H/'action_review_pages.json').write_text(json.dumps(pages,indent=2));print('RENDERED',len(r),'outputs',len(pages),'pages')
