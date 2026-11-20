from pathlib import Path
import json,xml.etree.ElementTree as E,collections
H=Path(__file__).resolve().parent;rows=json.loads((H/'files.json').read_text());F=Path('/Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Fluent Symbols/svgs');books={'his','hers','mine','my','your','yours','our','ours','their','theirs'};ns='{http://www.w3.org/2000/svg}'
def shape_counts(root,source):
 out=collections.Counter()
 def walk(e):
  tag=e.tag.rsplit('}',1)[-1]
  if tag in ['defs','metadata','title','desc']:return
  if e.get('data-core-style') or e.get('data-core-figure'):return
  if source and tag=='g' and sum(c.tag==ns+'path' for c in e)>5:return
  if tag in ['path','rect','circle','ellipse','line','polyline','polygon','text']:
   attrs={k:v for k,v in e.attrib.items() if k not in ['id','class'] and not k.startswith('data-')}
   out[(tag,json.dumps(attrs,sort_keys=True),e.text.strip() if e.text and e.text.strip() else '')]+=1
  for c in e:walk(c)
 walk(root);return out
results=[]
for r in rows:
 if r['location']!='People' or r['category'] not in ['Pronouns','Contractions'] or not r.get('styled_figure_count'):continue
 folder=F/('09 Pronouns' if r['category']=='Pronouns' else '02 Contractions');n=r['concept'];variant=' (F)' if r['name'].endswith('(F)') else ' (M)';src=folder/(n+variant+'.svg')
 if not src.exists():src=folder/(n+'.svg')
 a=shape_counts(E.parse(src).getroot(),True);b=shape_counts(E.parse(r['path']).getroot(),False);missing=a-b;extra=b-a
 results.append(dict(id=r['id'],path=r['path'],source=str(src),book=r['category']=='Pronouns' and n in books,source_annotation_primitives=sum(a.values()),output_annotation_primitives=sum(b.values()),missing_primitives=sum(missing.values()),extra_primitives=sum(extra.values()),missing_details=[{'shape':k,'count':v} for k,v in missing.items()]))
(H/'annotation_checks.json').write_text(json.dumps(results,indent=2));print('files',len(results),'book files',sum(r['book'] for r in results),'missing geometry files',sum(bool(r['missing_primitives']) for r in results));print([(r['id'],r['missing_primitives'],r['extra_primitives']) for r in results if r['missing_primitives']][:40])
