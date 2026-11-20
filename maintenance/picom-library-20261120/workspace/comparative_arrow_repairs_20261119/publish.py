from repair import HERE,LIB,TMP,sha
from pathlib import Path
import json,sys,os,csv,io,datetime,shutil

style=sys.argv[1];reviewed=set(sys.argv[2].split(','));batch=HERE/'staging'/style
records=json.loads((batch/'records.json').read_text())
assert reviewed=={r['id'] for r in records},'Every exact output must be explicitly reviewed'
ledger=HERE/'published.jsonl';receipt=LIB/'_manifest'/'comparative-arrow-repairs-20261119.jsonl'
for r in records:
 assert sha(Path(r['source']))==r['source_sha256'],r['source']
 assert sha(Path(r['staged']))==r['output_sha256'],r['staged']
 if r['source']!=r['destination']:assert not Path(r['destination']).exists(),r['destination']
for r in records:
 dest=Path(r['destination']);dest.parent.mkdir(parents=True,exist_ok=True)
 os.replace(r['staged'],dest);assert sha(dest)==r['output_sha256']
 r.update(reviewed=True,reviewer='primary assistant: all before/after cells and 96px dark previews visually inspected',published_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 for p in (ledger,receipt):
  with p.open('a') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
# Refresh the affected canonical manifest entries without making image backups.
manifest=LIB/'_manifest'/(style+'.csv')
if manifest.exists():
 with manifest.open(newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
else:fields=['rel','source','source_sha256','final_sha256','policy','date','status'];rows=[]
byrel={r['rel']:r for r in rows}
for r in records:
 rel=str(Path(r['destination']).relative_to(LIB/style))
 if rel not in byrel:
  v={k:'' for k in fields};v.update(rel=rel,source=str(Path(r['source']).relative_to(LIB.parent)),source_sha256=r['source_sha256']);rows.append(v);byrel[rel]=v
 v=byrel[rel];v.update(final_sha256=r['output_sha256'],policy=(v.get('policy','')+'; comparative arrow repair approved 2026-11-19').strip('; '),date='2026-11-19',status='ok:arrow-repair-reviewed')
text=io.StringIO();w=csv.DictWriter(text,fieldnames=fields);w.writeheader();w.writerows(rows)
temp=manifest.with_suffix('.csv.arrow-tmp');temp.write_text(text.getvalue());os.replace(temp,manifest)
(HERE/'reviews').mkdir(exist_ok=True);(HERE/'reviews'/(style+'.json')).write_text(json.dumps(records,indent=2))
(batch/'records.json').unlink();batch.rmdir()
reviewdir=TMP/style
if reviewdir.exists():shutil.rmtree(reviewdir)
print('Published, hash-verified and temporary files removed:',style,len(records))
