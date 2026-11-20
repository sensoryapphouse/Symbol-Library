from pathlib import Path
if Path(__file__).with_name('published.json').exists():
 raise SystemExit('This run is published. Do not regenerate staging or replace its source evidence.')
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as E
H=Path(__file__).resolve().parent;P=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/People')
rows=[];hashes={}
for st in ['3D animated cartoon','Kawaii']:
 for f in sorted((P/st/'Comparatives').glob('*.svg')):
  r=E.parse(f).getroot()
  if not any(e.get('data-comparative-person') for e in r.iter()):continue
  gender='F' if ' (F)' in f.stem else 'M';concept=f.stem.replace(' (F)','');base=P/st/'Pronouns'/('he.svg' if gender=='M' else 'she.svg')
  rows.append({'style':st,'concept':concept,'gender':gender,'source':str(f),'base':str(base),'filename':f.name,'id':('3d' if st.startswith('3D') else 'kawaii')+'_'+concept.replace(' (1)','').replace(' ','_')+'_'+gender.lower()})
  for p in [f,base]:hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
assert len(rows)==96
(H/'inputs.json').write_text(json.dumps(rows,indent=2));(H/'source_hashes.json').write_text(json.dumps(hashes,indent=2))
print('Inventoried 96 inputs and 4 bases.')
