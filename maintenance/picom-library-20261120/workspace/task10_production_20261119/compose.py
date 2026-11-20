"""Single-worker composition using the user's pinned layout engines, with independent output checks."""
from pathlib import Path
import sys,os,re,io,json,base64,hashlib,sqlite3,subprocess,tempfile,fcntl,datetime,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
H=Path(__file__).resolve().parent;PR=Path('/Users/paulblenkhorn/Desktop/picom_review');T=Path('/private/tmp/task10_production_20261119');T.mkdir(exist_ok=True)
sys.path.insert(0,str(PR))
for x in json.loads((H.parent/'task10_preparation_20261119/method_decision.json').read_text())['scripts'].values():assert hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'],x['path']
import make_plurals_flex as MF,smart_shrink_plurals as SS,tense_annotate as TA
RSVG='/opt/homebrew/bin/rsvg-convert'
def render(text,size=512):
 p=subprocess.run([RSVG,'-w',str(size),'-h',str(size)],input=text.encode(),capture_output=True,timeout=30)
 if p.returncode or not p.stdout:raise ValueError('SVG render failed: '+p.stderr.decode()[:150])
 im=Image.open(io.BytesIO(p.stdout)).convert('RGBA');im.load();return im
# Keep the approved layout math exactly; surface rendering errors instead of accepting an empty mask.
def mask(text):
 a=np.array(render(text,256))[:,:,3]>16
 if not a.any():raise ValueError('Blank source render')
 return a
SS.rmask=mask
# Preserve the saved tense rectangle and threshold while avoiding shared /tmp/_bb.png and silent failure.
def zone(path,x,y,w,h):
 im=render(Path(path).read_text());white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);a=np.array(white.convert('RGB'),dtype=float)/255
 return float(a[y:y+h,x:x+w].mean())<0.997
TA._zone_inked=zone
TA.clock_original=TA.clock
NS='{http://www.w3.org/2000/svg}'
def source_svg(path):
 p=Path(path);data=p.read_bytes()
 if p.suffix.lower()=='.svg':return data.decode('utf-8'),hashlib.sha256(data).hexdigest()
 im=Image.open(io.BytesIO(data));w,h=im.size
 if w!=h:raise ValueError('Non-square raster needs explicit canvas mapping')
 s='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><image width="512" height="512" href="data:image/webp;base64,'+base64.b64encode(data).decode()+'"/></svg>'
 return s,hashlib.sha256(data).hexdigest()
def parts(text):
 m=re.search(r'(<svg[^>]*>)(.*)(</svg>\s*)$',text,re.S)
 if not m:raise ValueError('Unparseable SVG')
 return m.groups()
def compose(row,previews=False,force_tense_shift=False,reviewed_background_overlap=False):
 source,sha=source_svg(row['source']);head,body,tail=parts(source);base=render(source)
 if not base.getchannel('A').getbbox():raise ValueError('Empty original')
 badge=None;scale=1.0
 if row['kind']=='plural':
  badge=MF.anchored_badge(head,'task10plural'+str(row['id']));full=head+body+badge+tail;out,scale=SS.process(full)
  if scale is None:raise ValueError('No plural badge located')
  # Strip the single added badge for an independent foreground-occlusion check.
  p=SS.split(out);content=p[0]+p[1]+p[3];badge_svg=head+badge+tail
 else:
  tmp=T/'source.svg';tmp.write_text(source)
  saved_zone=TA._zone_inked
  try:
   if force_tense_shift:TA._zone_inked=lambda *args:True
   out=TA.annotate(str(tmp),row['kind'])
  finally:
   TA._zone_inked=saved_zone;tmp.unlink(missing_ok=True)
  badge=TA.anchored_clock(row['kind'],head)
  if not out.endswith(badge+tail):raise ValueError('Clock missing or misplaced in structure')
  content=out[:-len(badge+tail)]+tail;badge_svg=head+badge+tail;scale=.82 if content!=source else 1.0
 # All native SVG content or original embedded WebP bytes must remain intact inside the transformed body.
 assert body in content
 after=render(out);subject=render(content);mark=render(badge_svg)
 a=np.array(subject)[:,:,3]>16;b=np.array(mark)[:,:,3]>16
 overlap=int((a&b).sum());edge=int(a[0].sum()+a[-1].sum()+a[:,0].sum()+a[:,-1].sum())
 before_a=np.array(base)[:,:,3]>16;before_edge=int(before_a[0].sum()+before_a[-1].sum()+before_a[:,0].sum()+before_a[:,-1].sum())
 background_overlap=0
 if overlap and reviewed_background_overlap:
  # Narrow exception: these twelve manually inspected cases touch only the
  # existing pale canvas border, never a figure or object. Do not generalise
  # this to white eyes, clothing, objects or other automatically selected rows.
  assert row['id'] in {41672,41673,41674,43539,43540,43541,43650,43651,43652,52835,52836,52837}
  rgb=np.array(subject)[:,:,:3][a&b].astype(int)
  assert rgb.min()>=225 and np.ptp(rgb,axis=1).max()<=5 and np.ptp(rgb,axis=0).max()<=6
  background_overlap=overlap
 if overlap and not background_overlap:raise ValueError(f'Annotation overlaps subject: {overlap} pixels; scale={scale}')
 if not a.any() or not b.any():raise ValueError('Missing subject or annotation')
 if scale<1 and edge>before_edge+4:raise ValueError('New canvas-edge clipping')
 root=E.fromstring(out);ids=[e.get('id') for e in root.iter() if e.get('id')]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate SVG IDs')
 for e in root.iter():
  for k,v in e.attrib.items():
   if k.rsplit('}',1)[-1]=='href' and not v.startswith(('data:','#')):raise ValueError('External image dependency')
 dest=H/'staging'/str(row['id'])/Path(row['destination']).name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(out)
 receipt={'source_sha':sha,'output_sha':hashlib.sha256(dest.read_bytes()).hexdigest(),'scale':scale,'overlap_pixels':overlap,'reviewed_blank_background_overlap':background_overlap,'foreground_overlap_pixels':overlap-background_overlap,'forced_existing_tense_shift':force_tense_shift,'new_edge_pixels':max(0,edge-before_edge),'subject_retained':True,'mark_present':True,'staged':str(dest)}
 if previews:
  for name,im in [('before',base),('after',after)]:im.resize((192,192),Image.Resampling.LANCZOS).save(T/f"{row['id']}_{name}.png")
 return receipt
if __name__=='__main__':
 lock=(H/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 db=sqlite3.connect(H/'queue.sqlite');db.row_factory=sqlite3.Row
 mode=sys.argv[1] if len(sys.argv)>1 else 'sample'
 if mode=='sample':
  ids=[]
  for st, in db.execute('SELECT DISTINCT style FROM jobs ORDER BY style').fetchall():
   for kind,n in [('plural',10),('past',4),('cont',3),('future',3)]:
    rs=db.execute('select id from jobs where style=? and kind=? order by id',(st,kind)).fetchall();ids += [rs[min(len(rs)-1,int(i*len(rs)/n))][0] for i in range(min(n,len(rs)))]
  (H/'first_batch_ids.json').write_text(json.dumps(ids));rows=[dict(db.execute('select * from jobs where id=?',(i,)).fetchone()) for i in ids]
 else:raise ValueError(mode)
 done=fail=0;receipts=[]
 for row in rows:
  if row['status']!='pending':continue
  try:
   receipt=compose(row,True);receipts.append(dict(row,**receipt));db.execute('update jobs set status="review",source_sha=?,output_sha=?,scale=?,note=? where id=?',(receipt['source_sha'],receipt['output_sha'],receipt['scale'],json.dumps(receipt),row['id']));done+=1
  except Exception as e:db.execute('update jobs set status="held",note=? where id=?',(str(e),row['id']));fail+=1
  db.commit()
  (H/'first_batch_receipts.json').write_text(json.dumps(receipts,indent=2))
  if (done+fail)%10==0:print('Checked',done+fail,'ready for visual review',done,'held',fail,flush=True)
 print('FINISHED',done,fail,flush=True)
