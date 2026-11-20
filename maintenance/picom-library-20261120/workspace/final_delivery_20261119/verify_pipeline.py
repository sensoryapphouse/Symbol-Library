"""Checks on scratch files only, then visual delivery samples from real Library SVGs."""
import pipeline as P
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import sqlite3,json,io,shutil

def main():
 scratch=P.T/'verification';scratch.mkdir(exist_ok=True)
 oldlib=P.LIB;olddb=P.H
 try:
  # Exercise publication, restart between publication/deletion, and collision refusal.
  P.LIB=scratch;P.H=scratch;db=P.dbopen()
  svg=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><circle cx="256" cy="256" r="140" fill="#38ba82"/><path d="M310 100L390 100L350 180Z" fill="red"/></svg>'
  src=scratch/'source.svg';src.write_bytes(svg);dst=src.with_suffix('.webp')
  db.execute('insert into conversions(source,destination,style,width,height,source_sha,old_bytes) values(?,?,?,?,?,?,?)',(str(src),str(dst),'test',512,512,P.digest(svg),len(svg)));db.commit()
  r=db.execute('select * from conversions').fetchone();P.convert_one(db,r);assert dst.exists() and not src.exists()
  # Restore only this scratch source, representing an interruption before unlink.
  src.write_bytes(svg);db.execute('update conversions set status="published"');db.commit()
  P.convert_one(db,db.execute('select * from conversions').fetchone());assert not src.exists()
  src2=scratch/'conflict.svg';src2.write_bytes(svg);dst2=src2.with_suffix('.webp');dst2.write_bytes(dst.read_bytes())
  db.execute('insert into conversions(source,destination,style,width,height,source_sha,old_bytes) values(?,?,?,?,?,?,?)',(str(src2),str(dst2),'test',512,512,P.digest(svg),len(svg)));db.commit()
  try:P.convert_one(db,db.execute('select * from conversions where source=?',(str(src2),)).fetchone());raise AssertionError('Failed collision guard')
  except FileExistsError:pass
  assert src2.read_bytes()==svg
  encoded=dst.read_bytes();stamped,pix,_,_=P.stamp_webp(encoded);assert P.visual_chunks(encoded)==P.visual_chunks(stamped)
  twice,_,_,_=P.stamp_webp(stamped);assert twice==stamped,'WebP stamp not idempotent'
  out,pix,removed=P.stamp_svg(svg);again,_,_=P.stamp_svg(out);assert out==again,'SVG stamp not idempotent'
  assert P.foreign_rights(b'<svg xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:rights>Copyright Someone Else</dc:rights></metadata></svg>')
  assert P.metadata_exclusion(scratch/'Doll/Flags/a.webp')
  sample=scratch/'metadata-check.webp';sample.write_bytes(stamped)
  exif=P.run(['/usr/local/bin/exiftool','-j','-Copyright','-Rights','-WebStatement',str(sample)]).decode()
  assert P.OWNER in exif and 'CC BY-NC 4.0' in exif and P.LICENSE in exif
  test={'at':P.now(),'publish_and_resume':True,'no_clobber':True,'exact_alpha':True,'metadata_no_recode':True,'decoded_pixels_unchanged':True,'metadata_idempotent':True,'foreign_rights_excluded':True,'exiftool_readback':json.loads(exif)}
 finally:
  P.LIB=oldlib;P.H=olddb
  shutil.rmtree(scratch)
 # Real preview examples: each raster style plus arrows, possession, tense and plural.
 plan=json.loads((P.W/'task11_preparation_20261119/rename_plan.json').read_text())
 samples=[]
 for old,style in plan['confirmed_names'].items():
  if old=='Mulberry':continue
  root=P.LIB/style
  paths=[]
  for cat,pattern in [('Pronouns','my.svg'),('Comparatives','cleaner.svg'),('Plurals and tenses','*.svg')]:
   available=sorted((root/cat).rglob(pattern))
   if available:paths.append(available[len(available)//2] if pattern=='*.svg' else available[0])
  samples.append((style,paths[0] if paths else None))
 for name in ['3D cartoon','Alien','Sommi','Basic 3']:
  paths=sorted((P.LIB/name/'Plurals and tenses').rglob('will *.svg'))
  if paths:samples.append((name+' future',paths[len(paths)//2]))
 font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12);pages=[];records=[]
 for start in range(0,len(samples),8):
  part=samples[start:start+8];sheet=Image.new('RGB',(1024,1024),'#dce7f1');d=ImageDraw.Draw(sheet)
  for i,(label,p) in enumerate(part):
   assert p is not None
   data=p.read_bytes();out,metrics=P.encode(data,512,512)
   x=(i%2)*512;y=(i//2)*256
   d.text((x+4,y+3),label+' / '+p.stem,fill='black',font=font)
   for j,im in enumerate([P.rgba(P.render(data,512,512)),P.rgba(out)]):
    im.thumbnail((220,220));sheet.paste(im,(x+256*j,y+30),im)
    d.text((x+256*j+4,y+18),'SVG' if j==0 else 'WebP Q80',fill='black',font=font)
   records.append({'source':str(p),'source_sha256':P.digest(data),'metrics':metrics})
  path=P.T/f'delivery_review_{len(pages)+1}.jpg';sheet.save(path,quality=95);pages.append(str(path))
 test.update(samples=records,review_pages=pages)
 P.save(P.H/'verification.json',test);print(json.dumps({'tests_passed':True,'visual_pages':pages,'samples':len(samples)}),flush=True)
if __name__=='__main__':main()
