"""Retry only held clocks using the approved 0.82 transform; stage for visual review."""
import compose as C
import sqlite3,json,fcntl,datetime
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
lock=(C.H/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
db=sqlite3.connect(C.H/'queue.sqlite');db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute('select * from jobs where status="held" and note like "Annotation overlaps%" order by id')]
receipts=[];failures=[]
for r in rows:
 old=r['note'];force=old.endswith('scale=1.0');background=old.endswith('scale=0.82')
 try:
  receipt=C.compose(r,True,force_tense_shift=force,reviewed_background_overlap=background)
  receipt['previous_hold']=old;receipt['repair']='Invoke existing 0.82 shift because real clock mask overlaps' if force else 'Manually reviewed blank canvas overlap only; source and standard layout unchanged'
  db.execute('update jobs set status="review",source_sha=?,output_sha=?,scale=?,note=? where id=?',(receipt['source_sha'],receipt['output_sha'],receipt['scale'],json.dumps(receipt),r['id']))
  receipts.append(dict(r,**receipt))
 except Exception as e:failures.append({'id':r['id'],'reason':str(e)})
 db.commit()
 if (len(receipts)+len(failures))%30==0:print('Resolved',len(receipts),'still held',len(failures),flush=True)
(C.H/'clock_hold_receipts.json').write_text(json.dumps(receipts,indent=2));(C.H/'clock_hold_failures.json').write_text(json.dumps(failures,indent=2))
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12);pages=[]
for start in range(0,len(receipts),18):
 part=receipts[start:start+18];sheet=Image.new('RGB',(1152,768),'#e7edf4');draw=ImageDraw.Draw(sheet)
 for i,r in enumerate(part):
  x=i%6*192;y=i//6*256;draw.text((x+4,y+3),str(r['id'])+' '+r['style'][:24],fill='black',font=font);draw.text((x+4,y+20),r['kind']+': '+r['concept'][:24],fill='black',font=font)
  im=Image.open(C.T/f"{r['id']}_after.png").convert('RGBA');sheet.paste(im,(x,y+46),im)
 path=C.T/f'clock_review_{len(pages)+1:02}.jpg';sheet.save(path,quality=94);pages.append({'path':str(path),'ids':[r['id'] for r in part]})
(C.H/'clock_hold_review_pages.json').write_text(json.dumps(pages,indent=2));print('DONE',len(receipts),'ready for visual review;',len(failures),'still held;',len(pages),'pages',flush=True)
