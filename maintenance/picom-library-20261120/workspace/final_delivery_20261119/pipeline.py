"""Authorised sequential delivery: Task 11 -> Task 12 -> final Task 5.

Bounded parallel encoding, one publisher; People is never written; no image backups.
SQLite records publication before removal, permitting interruption-safe resumes.
"""
from pathlib import Path
import os,sys,json,sqlite3,datetime,time,hashlib,subprocess,io,fcntl,re,struct,base64
import xml.etree.ElementTree as E
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from PIL import Image
import numpy as np
H=Path(__file__).resolve().parent; W=H.parent
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
T=Path('/private/tmp/picom_final_delivery_20261119');T.mkdir(exist_ok=True)
RIGHTS='© Sensory App House Ltd, CC BY-NC 4.0'
OWNER='Sensory App House Ltd';LICENSE='https://creativecommons.org/licenses/by-nc/4.0/'
RSVG='/opt/homebrew/bin/rsvg-convert';CWEBP='/opt/homebrew/bin/cwebp';MUX='/opt/homebrew/bin/webpmux'
ENCODERS=int(os.environ.get('PICOM_Q80_WORKERS','1'))
assert 1<=ENCODERS<=4,'Worker count must be explicitly bounded'
def now():return datetime.datetime.now().astimezone().isoformat()
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def save(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2));os.replace(tmp,p)
def dbopen():
 db=sqlite3.connect(H/'delivery.sqlite',timeout=30);db.row_factory=sqlite3.Row
 db.executescript('''CREATE TABLE IF NOT EXISTS conversions(
 source TEXT PRIMARY KEY,destination TEXT UNIQUE,style TEXT,width INTEGER,height INTEGER,
 source_sha TEXT,status TEXT DEFAULT 'pending',output_sha TEXT,old_bytes INTEGER,new_bytes INTEGER,
 metrics TEXT,error TEXT,finished_at TEXT);
 CREATE TABLE IF NOT EXISTS metadata(path TEXT PRIMARY KEY,status TEXT DEFAULT 'pending',reason TEXT,
 before_sha TEXT,after_sha TEXT,pixel_sha TEXT,old_xmp BLOB,old_exif BLOB,old_svg_metadata TEXT,finished_at TEXT);
 CREATE TABLE IF NOT EXISTS events(at TEXT,stage TEXT,detail TEXT);
 CREATE INDEX IF NOT EXISTS conversion_status ON conversions(status);
 CREATE INDEX IF NOT EXISTS metadata_status ON metadata(status);''');return db
def progress(db,stage,state,current=None):
 c=dict(db.execute('select status,count(*) from conversions group by status'))
 m=dict(db.execute('select status,count(*) from metadata group by status'))
 save(H/'progress.json',{'at':now(),'pid':os.getpid(),'stage':stage,'state':state,'current':current,'conversions':c,'licensing':m,'worker_limit':ENCODERS if stage==12 else 1,'compression_workers':ENCODERS,'publisher_workers':1})
def run(args,**kw):
 p=subprocess.run(args,capture_output=True,timeout=90,**kw)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[:2000])
 return p.stdout
def render(data,w,h):return run([RSVG,'-w',str(w),'-h',str(h)],input=data)
def rgba(b):
 im=Image.open(io.BytesIO(b)).convert('RGBA');im.load();return im
def encode(data,w,h):
 png=render(data,w,h);before=rgba(png)
 out=run([CWEBP,'-quiet','-q','80','-m','6','-alpha_q','100','-exact','-metadata','none','-o','-','--','-'],input=png)
 after=rgba(out);assert after.size==(w,h)
 a=np.array(before);b=np.array(after);assert np.array_equal(a[:,:,3],b[:,:,3]),'Alpha changed'
 opacity=a[:,:,3].astype(float)/255
 diff=(a[:,:,:3].astype(float)-b[:,:,:3].astype(float))*opacity[:,:,None]
 weight=max(1,float(opacity.sum()))*3
 mae=float(np.abs(diff).sum()/weight);rmse=float(np.sqrt((diff**2).sum()/weight))
 assert mae<=15 and rmse<=30,('Unexpected Q80 distortion',mae,rmse)
 assert a[:,:,3].max()>0,'Blank render'
 return out,{'quality':80,'method':6,'alpha_exact':True,'width':w,'height':h,'weighted_mae':mae,'weighted_rmse':rmse}
def safe_publish(dest,data):
 assert dest.is_relative_to(LIB) or dest.is_relative_to(T)
 temp=dest.with_name('.'+dest.name+'.picom-tmp')
 # A stale temp is disposable; the original/destination is never overwritten here.
 temp.write_bytes(data)
 with temp.open('rb') as f:os.fsync(f.fileno())
 try:os.link(temp,dest)
 finally:temp.unlink(missing_ok=True)
def prepare_encoding(r):
 # Encoding workers only read their assigned source and return checked bytes.
 # All database writes, publication and source deletion stay in the coordinator.
 src=Path(r['source']);dst=Path(r['destination'])
 if dst.exists():return None
 data=src.read_bytes();assert digest(data)==r['source_sha'],'SVG changed since inventory'
 return encode(data,r['width'],r['height'])
def convert_one(db,r,prepared=None):
 src=Path(r['source']);dst=Path(r['destination'])
 if r['status']=='complete':
  assert dst.exists();return
 if dst.exists():
  if r['output_sha'] and sha(dst)==r['output_sha']:
   if src.exists():assert sha(src)==r['source_sha'];src.unlink()
   db.execute('update conversions set status="complete",finished_at=? where source=?',(now(),str(src)));db.commit();return
  raise FileExistsError('Untracked destination exists; retained both unchanged: '+str(dst))
 assert src.exists() and sha(src)==r['source_sha'],'SVG changed since inventory'
 out,metrics=prepared if prepared is not None else encode(src.read_bytes(),r['width'],r['height'])
 outsha=digest(out)
 db.execute('update conversions set status="ready",output_sha=?,new_bytes=?,metrics=? where source=?',(outsha,len(out),json.dumps(metrics),str(src)));db.commit()
 safe_publish(dst,out)
 assert sha(dst)==outsha and sha(src)==r['source_sha']
 db.execute('update conversions set status="published" where source=?',(str(src),));db.commit()
 src.unlink()
 db.execute('update conversions set status="complete",finished_at=?,error=NULL where source=?',(now(),str(src)));db.commit()
def inventory(db):
 if (H/'inventory.json').exists():return
 rename=json.loads((W/'task11_preparation_20261119/execution.json').read_text());assert rename['state']=='complete'
 plan=json.loads((W/'task11_preparation_20261119/rename_plan.json').read_text());names=plan['confirmed_names']
 jobs=sqlite3.connect(W/'task10_production_20261119/queue.sqlite')
 sources=dict(jobs.execute('select destination,source from jobs where status="published"'))
 aux=json.loads((W/'task10_production_20261119/auxiliary_modal_reconciliation.json').read_text())
 roots={'Pronouns','Contractions','Comparatives','Plurals and tenses'}
 counts={};kept=0
 for old,style in names.items():
  st=LIB/style;assert st.is_dir();n=0
  if old=='Mulberry':kept=sum(1 for _ in st.rglob('*.svg'));continue
  for root in sorted(roots):
   for p in sorted((st/root).rglob('*.svg')):
    width=height=512;source=sources.get(str(p))
    if source and Path(source).suffix.lower()=='.webp':
     with Image.open(source) as im:width,height=im.size
    data=p.read_bytes();E.fromstring(data)
    db.execute('insert or ignore into conversions(source,destination,style,width,height,source_sha,old_bytes) values(?,?,?,?,?,?,?)',(str(p),str(p.with_suffix('.webp')),style,width,height,digest(data),len(data)));n+=1
  counts[style]=n
 db.commit();save(H/'inventory.json',{'at':now(),'by_style':counts,'total':sum(counts.values()),'Basic SVG_kept_native':kept,'scope':sorted(roots),'dimensions':'Task 10 raster source dimensions; other compositions at matching standard Library 512 × 512; Basic SVG remains vector','existing_base_webps':'Excluded; never recompressed'})
def chunks(data):
 assert data[:4]==b'RIFF' and data[8:12]==b'WEBP' and len(data)==struct.unpack('<I',data[4:8])[0]+8
 out=[];pos=12
 while pos<len(data):
  tag=data[pos:pos+4];n=struct.unpack('<I',data[pos+4:pos+8])[0];payload=data[pos+8:pos+8+n];assert len(payload)==n
  out.append((tag,payload));pos+=8+n+(n%2)
 assert pos==len(data);return out
def visual_chunks(data):
 # Metadata can add/change VP8X feature bits, but must never touch encoded pixels.
 return [(tag,p) for tag,p in chunks(data) if tag not in (b'EXIF',b'XMP ',b'VP8X')]
def metadata_exclusion(p):
 rel=p.relative_to(LIB);s=str(rel).casefold()
 if any(x in s for x in ('american sign language','british sign language','asl chart','bsl chart')):return 'Third-party sign-language chart exclusion'
 if any('flag' in part.casefold() for part in rel.parts[1:-1]):return 'Flag collection excluded by saved licence scope'
 if rel.stem.casefold() in ('flag','flags'):return 'Flag asset excluded by saved licence scope'
 return None
RDF='http://www.w3.org/1999/02/22-rdf-syntax-ns#';DC='http://purl.org/dc/elements/1.1/';XR='http://ns.adobe.com/xap/1.0/rights/';CC='http://creativecommons.org/ns#';XMP='http://ns.adobe.com/xap/1.0/'
for prefix,ns in [('rdf',RDF),('dc',DC),('xmpRights',XR),('cc',CC),('xmp',XMP)]:E.register_namespace(prefix,ns)
def xmp_packet(old=None):
 root=E.fromstring(old) if old else E.Element('{adobe:ns:meta/}xmpmeta')
 rdf=root.find('.//{'+RDF+'}RDF')
 if rdf is None:rdf=E.SubElement(root,'{'+RDF+'}RDF')
 # Preserve unrelated metadata; replace only licence/ownership fields for our work.
 tags={f'{{{DC}}}rights',f'{{{DC}}}creator',f'{{{CC}}}license',f'{{{XR}}}Marked',f'{{{XR}}}WebStatement'}
 for e in root.iter():
  for key in list(e.attrib):
   if key in tags:del e.attrib[key]
  for child in list(e):
   if child.tag in tags:e.remove(child)
 for e in list(rdf):
  if e.tag=='{'+RDF+'}Description' and len(e)==0 and not (e.text or '').strip() and set(e.attrib)<= {'{'+RDF+'}about'}:rdf.remove(e)
 desc=E.SubElement(rdf,'{'+RDF+'}Description',{'{'+RDF+'}about':''})
 rights=E.SubElement(desc,'{'+DC+'}rights');alt=E.SubElement(rights,'{'+RDF+'}Alt');E.SubElement(alt,'{'+RDF+'}li',{'{http://www.w3.org/XML/1998/namespace}lang':'x-default'}).text=RIGHTS
 creator=E.SubElement(desc,'{'+DC+'}creator');seq=E.SubElement(creator,'{'+RDF+'}Seq');E.SubElement(seq,'{'+RDF+'}li').text=OWNER
 E.SubElement(desc,'{'+CC+'}license',{'{'+RDF+'}resource':LICENSE})
 E.SubElement(desc,'{'+XR+'}Marked').text='True';E.SubElement(desc,'{'+XR+'}WebStatement').text=LICENSE
 return E.tostring(root,encoding='utf-8',xml_declaration=True)
def foreign_rights(data):
 text=data.decode('utf-8',errors='ignore').casefold()
 # Native Mulberry provenance is different from our generated Mulberry-like style.
 if any(x in text for x in ('mulberrysymbols.org','mulberry symbols','steve lee','arasaac.org','tawasol','sclera.be')):return 'Existing third-party attribution retained'
 try:
  root=E.fromstring(data)
  for e in root.iter():
   if e.tag in ('{'+DC+'}rights','{'+DC+'}creator'):
    claim=' '.join(e.itertext()).strip()
    if claim and not any(x in claim.casefold() for x in ('sensory app house','picom')):return 'Existing third-party rights/creator retained: '+claim[:120]
 except E.ParseError:pass
 return None
def stamp_webp(data):
 ch=dict(chunks(data));oldx=ch.get(b'XMP ',b'');olde=ch.get(b'EXIF',b'')
 if oldx:
  reason=foreign_rights(oldx)
  if reason:raise ValueError(reason)
 xmp=xmp_packet(oldx or None)
 exif=Image.Exif()
 if olde:exif.load(olde)
 existing=exif.get(33432,'')
 if existing and 'sensory app house' not in str(existing).lower():raise ValueError('Existing third-party EXIF copyright retained')
 exif[33432]='Copyright Sensory App House Ltd, CC BY-NC 4.0'
 # webpmux updates metadata only. These fixed temp files are reused serially.
 ip=T/'metadata_input.webp';xp=T/'rights.xmp';ep=T/'rights.exif';mid=T/'metadata_mid.webp';op=T/'metadata_output.webp'
 try:
  ip.write_bytes(data);xp.write_bytes(xmp);ep.write_bytes(exif.tobytes())
  run([MUX,'-set','xmp',str(xp),str(ip),'-o',str(mid)])
  run([MUX,'-set','exif',str(ep),str(mid),'-o',str(op)])
  out=op.read_bytes();assert visual_chunks(data)==visual_chunks(out),'Encoded image data changed during metadata write'
  before=rgba(data);after=rgba(out);assert before.size==after.size and before.tobytes()==after.tobytes(),'Decoded pixels changed'
  c=dict(chunks(out));assert RIGHTS.encode() in c[b'XMP '] and LICENSE.encode() in c[b'XMP ']
  check=Image.Exif();check.load(c[b'EXIF']);assert check[33432]==exif[33432]
  return out,digest(before.tobytes()),oldx,olde
 finally:
  for p in (ip,xp,ep,mid,op):p.unlink(missing_ok=True)
def stamp_svg(data):
 text=data.decode();reason=foreign_rights(data)
 if reason:raise ValueError(reason)
 # Remove only the existing SAH copyright records. Keep figure/construction metadata.
 removed=[]
 def remove(m):removed.append(m.group());return ''
 text=re.sub(r'<!--SAH-COPYRIGHT.*?-->',remove,text,flags=re.S)
 text=re.sub(r'<metadata\b[^>]*\bid=[\"\']sah-copyright[\"\'][^>]*>.*?</metadata>',remove,text,flags=re.S)
 text=re.sub(r'\sdata-copyright=[\"\'][^\"\']*[\"\']',remove,text)
 # Old generators also use the rights sentence in comments, never visible content.
 text=text.replace('© 2026 Sensory App House. All rights reserved.',RIGHTS)
 m=re.search(r'<svg\b[^>]*>',text);assert m
 meta=xmp_packet().decode().split('?>',1)[-1]
 out=(text[:m.end()-1]+' data-copyright="'+RIGHTS+'">'+'<!--SAH-COPYRIGHT '+RIGHTS+'--><metadata id="sah-copyright">'+meta+'</metadata>'+text[m.end():]).encode()
 E.fromstring(out)
 before=rgba(render(data,512,512));after=rgba(render(out,512,512));assert before.tobytes()==after.tobytes(),'SVG appearance changed'
 return out,digest(before.tobytes()),json.dumps(removed)
def stamp_one(db,r):
 p=Path(r['path']);data=p.read_bytes();before_sha=digest(data)
 if r['status']=='ready' and before_sha==r['after_sha']:
  db.execute('update metadata set status="complete",finished_at=? where path=?',(now(),str(p)));db.commit();return
 if r['before_sha']:assert before_sha==r['before_sha'],'File changed since metadata checkpoint'
 if p.suffix.lower()=='.webp':out,pixel,oldx,olde=stamp_webp(data);oldsvg=None
 else:out,pixel,oldsvg=stamp_svg(data);oldx=olde=None
 db.execute('update metadata set status="ready",before_sha=?,after_sha=?,pixel_sha=?,old_xmp=?,old_exif=?,old_svg_metadata=? where path=?',(before_sha,digest(out),pixel,oldx,olde,oldsvg,str(p)));db.commit()
 temp=p.with_name('.'+p.name+'.picom-tmp');temp.write_bytes(out)
 assert sha(temp)==digest(out) and sha(p)==before_sha
 os.replace(temp,p)
 db.execute('update metadata set status="complete",finished_at=?,reason=NULL where path=?',(now(),str(p)));db.commit()
def inventory_metadata(db):
 if (H/'licence_inventory.json').exists():return
 count=0;exclusions={}
 for root,dirs,files in os.walk(LIB):
  dirs[:]=[d for d in dirs if not d.startswith(('_','.'))]
  for name in sorted(files):
   p=Path(root)/name
   if p.suffix.lower() not in ('.webp','.svg'):continue
   reason=metadata_exclusion(p)
   db.execute('insert or ignore into metadata(path,status,reason) values(?,?,?)',(str(p),'excluded' if reason else 'pending',reason));count+=1
   if reason:exclusions[reason]=exclusions.get(reason,0)+1
 db.commit();save(H/'licence_inventory.json',{'at':now(),'files':count,'exclusions':exclusions,'scope':'Final Library only; People originals untouched; third-party scope exclusions retained','rights':RIGHTS,'url':LICENSE})
def update_delivery_links(db):
 from urllib.parse import quote
 mapping={}
 for r in db.execute('select source,destination from conversions where status="complete"'):
  a=r['source'];b=r['destination'];mapping[a]=b;mapping['file://'+quote(a,safe='/')]='file://'+quote(b,safe='/')
 if not mapping:return
 plan=json.loads((W/'task11_preparation_20261119/rename_plan.json').read_text())
 # One dictionary lookup per referenced SVG keeps Basic SVG links unchanged.
 pattern=re.compile(r'(?:file://)?/Users/[^\"\'<>\n]*?\.svg')
 for name in plan.get('current_review_html',[]):
  p=Path(name)
  if not p.exists():continue
  old=p.read_text();new=pattern.sub(lambda m:mapping.get(m.group(),m.group()),old)
  if old!=new:
   temp=p.with_suffix('.html.tmp');temp.write_text(new);temp.replace(p)
def stage12(db):
 inventory(db);progress(db,12,'running');start=time.time();n=0
 rows=db.execute('select * from conversions where status in ("pending","ready","published") order by style,source').fetchall()
 # Keep at most ENCODERS jobs/results in memory; never enqueue the whole Library.
 todo=iter(rows)
 with ThreadPoolExecutor(max_workers=ENCODERS,thread_name_prefix='q80') as pool:
  active={}
  def fill():
   while len(active)<ENCODERS:
    r=next(todo,None)
    if r is None:break
    active[pool.submit(prepare_encoding,dict(r))]=r
  fill()
  while active:
   progress(db,12,'running',[r['source'] for r in active.values()])
   finished,_=wait(active,timeout=10,return_when=FIRST_COMPLETED)
   for future in finished:
    r=active.pop(future)
    try:convert_one(db,r,future.result())
    except Exception as e:
     db.execute('update conversions set status=?,error=? where source=?',('error',str(e),r['source']));db.commit()
     print('CONVERSION ERROR',r['source'],str(e),flush=True)
    n+=1
    if n%100==0:print('Q80',n,'files this session;',round(n*60/max(1,time.time()-start),1),'/minute;',ENCODERS,'encoders',flush=True)
   fill()
 counts=dict(db.execute('select status,count(*) from conversions group by status'))
 assert set(counts)<= {'complete'},('Conversion exceptions require review',counts)
 # Reconcile every output before declaring Task 12 complete.
 for r in db.execute('select * from conversions'):
  assert not Path(r['source']).exists() and sha(r['destination'])==r['output_sha'],r['destination']
 sums=db.execute('select sum(old_bytes),sum(new_bytes) from conversions').fetchone()
 update_delivery_links(db)
 save(H/'task12_completion.json',{'at':now(),'complete':True,'counts':counts,'svg_bytes_before':sums[0],'webp_bytes_after':sums[1],'saved_bytes':sums[0]-sums[1],'Basic SVG_preserved':True,'People_untouched':True})
 progress(db,12,'complete');print('TASK 12 COMPLETE',counts,flush=True)
def stage5(db):
 inventory_metadata(db);progress(db,5,'running');n=0
 # A dedicated cursor permits periodic commit without refetching the full queue.
 rows=db.execute('select * from metadata where status in ("pending","ready") order by path').fetchall()
 for r in rows:
  if n%20==0:progress(db,5,'running',r['path'])
  try:stamp_one(db,r)
  except Exception as e:
   reason=str(e);state='excluded' if ('third-party' in reason) else 'error'
   db.execute('update metadata set status=?,reason=? where path=?',(state,reason,r['path']));db.commit()
   print('LICENCE',state,r['path'],reason,flush=True)
  n+=1
  if n%1000==0:print('Licence verified',n,'this session',flush=True)
 counts=dict(db.execute('select status,count(*) from metadata group by status'))
 assert not any(k not in ('complete','excluded') for k in counts),counts
 # Each file has already passed decoded pixel equality, exact rights readback,
 # and no-recode payload checks. Recheck final hashes for interruption/races.
 for r in db.execute('select path,after_sha from metadata where status="complete"'):
  assert sha(r['path'])==r['after_sha'],r['path']
 exclusions=[dict(r) for r in db.execute('select path,reason from metadata where status="excluded"')]
 save(H/'licence_exclusions.json',exclusions)
 current=LIB/'_manifest'/'final-delivery-20261119.jsonl';current.parent.mkdir(exist_ok=True)
 temp=current.with_suffix('.jsonl.tmp')
 with temp.open('w') as f:
  for r in db.execute('select path,status,after_sha,pixel_sha,reason from metadata order by path'):
   f.write(json.dumps(dict(r),ensure_ascii=False)+'\n')
 temp.replace(current)
 save(H/'completion.json',{'at':now(),'complete':True,'tasks':[10,11,12,5],'licensing':counts,'rights':RIGHTS,'url':LICENSE,'exceptions_record':str(H/'licence_exclusions.json'),'People_untouched':True,'temporary_files_remaining':list(map(str,T.iterdir()))})
 progress(db,5,'complete');print('AUTHORISED DELIVERY SEQUENCE COMPLETE',counts,flush=True)
def main():
 pause=H/'pause.json'
 if pause.exists() and json.loads(pause.read_text()).get('paused'):
  print('Paused by user; explicit resume instruction is required.',flush=True)
  return
 lock=(H/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 db=dbopen()
 # This runner begins only after Task 10 and the approved rename are complete.
 while True:
  ep=W/'task11_preparation_20261119/execution.json'
  if ep.exists() and json.loads(ep.read_text()).get('state')=='complete':break
  progress(db,11,'waiting_verified_rename');time.sleep(15)
 assert json.loads((W/'task10_production_20261119/completion.json').read_text())['task10_complete']
 with (W/'task10_production_20261119/worker.lock').open('a') as shared:
  fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   if not (H/'task12_completion.json').exists():stage12(db)
   if not (H/'completion.json').exists():stage5(db)
  except BaseException as e:
   db.execute('insert into events values(?,?,?)',(now(),'stopped_error',str(e)));db.commit();progress(db,'sequence','stopped_error',str(e));raise
if __name__=='__main__':main()
