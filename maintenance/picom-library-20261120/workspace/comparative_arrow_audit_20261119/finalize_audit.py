from pathlib import Path
import json, collections, math
from PIL import Image, ImageDraw
from audit import HERE,TMP,FONT,SMALL,render
rows=json.loads((HERE/'measured.json').read_text());byid={r['id']:r for r in rows}
obs=json.loads((HERE/'observations.json').read_text())
obs['styles']['3D animated cartoon']['missing']=sorted(set(obs['styles']['3D animated cartoon']['missing']+[44]))
(HERE/'observations.json').write_text(json.dumps(obs,indent=2))
r=byid['A0044'];r['visual_status']='missing';r.pop('arrow_measurement',None);r['native_note']='Full original inspected: no selection arrow. Automated colour-core candidate was hair; rejected.'
reviewed=set(json.loads((HERE/'native_followup_ids.json').read_text()))
for r in rows:
 r['contact_sheet_reviewed']=True
 r['native_followup_reviewed']=r['id'] in reviewed
 m=r.get('arrow_measurement')
 r['small_arrow']=bool(r['visual_status']=='down_present' and m and m['method']=='isolated alpha component' and (m['height_at_512']<40 or m['width_at_512']<24))
 r['proposed_action']='add selector' if r['visual_status']=='missing' else 'change upward selector to downward' if r['visual_status']=='upward' else 'enlarge selector' if r['small_arrow'] else 'retain'
 if m and 'core' in m['method']:r['measurement_note']='Colour core only, excluding outline; not used to decide minimum-size failure. Visually checked.'
 if r['id']=='A0320':r['native_note']='Coloured detached component is a motion streak, not an arrow.'
 r['reason']={'missing':'Multiple figures; no arrow identifies the intended referent. Propose a downward selector, after confirming the target in this exact variant.', 'upward':'Red arrow above the taller figure points upward. It can mean height, but conflicts with a consistent downward referent selector.', 'angled_down':'Diagonal arrow points down toward the chosen figure. Retain if clear; not automatically a direction error.', 'not_required_single':'Single-figure image: no referent selector needed. Preserve any comparative badge or superlative star.', 'down_present':'Downward selector present; no presence/direction defect found.'}[r['visual_status']]
 if r['small_arrow']:r['reason']='Downward selector is below the proposed 40 px high / 24 px wide minimum at a 512 px canvas. Enlarge for small-display visibility.'
(HERE/'results.json').write_text(json.dumps(rows,indent=2))
# Comparison at actual 128px presentation; no source changes.
small=[r for r in rows if r['small_arrow']]
for page in range(math.ceil(len(small)/15)):
 ss=small[page*15:(page+1)*15];sheet=Image.new('RGB',(1000,60+math.ceil(len(ss)/3)*195),'white');d=ImageDraw.Draw(sheet)
 d.text((10,10),'Small arrows at 128 px: pastel / dark — original images',font=FONT,fill='black')
 for i,r in enumerate(ss):
  x=(i%3)*333;y=60+(i//3)*195;im=render(Path(r['path'])).resize((128,128),Image.Resampling.LANCZOS)
  for dx,bg in [(0,'#e5edf5'),(140,'#283240')]:
   tile=Image.new('RGB',(128,128),bg);tile.paste(im,(0,0),im);sheet.paste(tile,(x+dx,y))
  d.text((x,y+132),r['id']+' '+r['style'],font=SMALL,fill='black');d.text((x,y+150),r['name']+f" — {r['arrow_measurement']['height_at_512']:g}px arrow",font=SMALL,fill='black')
 sheet.save(TMP/f'small_display_{page+1}.jpg',quality=94)
print('Counts',collections.Counter(r['visual_status'] for r in rows),'small',len(small),'proposed',sum(r['proposed_action']!='retain' for r in rows))
for s in sorted(set(r['style'] for r in rows)):
 ss=[r for r in rows if r['style']==s];print(s,len(ss),collections.Counter(r['visual_status'] for r in ss),sum(r['small_arrow'] for r in ss))
