from pathlib import Path
import json,hashlib
from PIL import Image
H=Path(__file__).resolve().parent;R=H.parent;L=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');P=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/People');props=json.loads((R/'task9_inventory_20261119/base_proposals.json').read_text());c={r['id']:r for r in json.loads((R/'task9_inventory_20261119/candidates.json').read_text())};skip={'3D animated cartoon','Kawaii','Flat outlined','Mulberry','Simple anime','Sommi','Sommi clothed'};styles=[r for r in props if r['style'] not in skip];inputs={};bases=[]
def source(path):
 p=Path(path);inputs[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size};return p
for st in styles:
 for gender,ref in zip(['M','F'],st['base_ids']):
  p=source(c[ref]['path']);im=Image.open(p).convert('RGBA');bbox=im.getchannel('A').getbbox();bases.append({'style':st['style'],'gender':gender,'id':ref,'path':str(p),'dimensions':list(im.size),'bbox':list(bbox),'sha256':inputs[str(p)]['sha256']})
 hold=source(L/st['style']/'Grammar & Language/Verbs/hold.webp')
 for cat in ['Comparatives','Pronouns','Contractions']:
  dest=L/st['style']/cat
  assert not dest.exists() or not any(dest.iterdir()),dest
  for f in (L/st['style']/({'Comparatives':'01 Comparatives','Pronouns':'09 Pronouns','Contractions':'02 Contractions'}[cat])).glob('*.webp'):source(f)
raw=json.loads((R/'task9_reuse_audit_20261119/files.json').read_text());templates=[]
for r in raw:
 if r['style']!='Kawaii' or not r.get('styled_figure_count') or r['category']=='Comparatives':continue
 p=source(r['path']);templates.append({'category':r['category'],'concept':r['concept'],'name':r['name'],'gender':'F' if r['name'].endswith(' (F)') or r['name'] in ['she','her','hers','herself',"she's","she'll"] else 'M','source':str(p),'fluent_source':r['source_template'],'figures':r['styled_figure_count']})
for g in ['M','F']:
 p=source(P/'Kawaii/Pronouns'/('they.svg' if g=='M' else 'they (F).svg'));templates.append({'category':'Pronouns','concept':'they-them','name':'they-them'+(' (F)' if g=='F' else ''),'gender':g,'source':str(p),'fluent_source':str(Path('/Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Fluent Symbols/svgs/09 Pronouns/they-them.svg')),'figures':3})
for r in json.loads((R/'task9_full_figures_20261119/published.json').read_text())['files']:
 if '/Kawaii/' not in r['path']:continue
 p=source(r['path']);stem=p.stem;templates.append({'category':'Comparatives','concept':stem.replace(' (F)',''),'name':stem,'gender':'F' if ' (F)' in stem else 'M','source':str(p),'fluent_source':str(Path('/Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Fluent Symbols/svgs/01 Comparatives')/(stem.replace(' (F)','')+'.svg')),'figures':2})
assert len(templates)==146,len(templates)
(H/'bases.json').write_text(json.dumps(bases,indent=2));(H/'templates.json').write_text(json.dumps(templates,indent=2));(H/'sources.json').write_text(json.dumps(inputs,indent=2));(H/'scope.json').write_text(json.dumps({'styles':[r['style'] for r in styles],'outputs_per_style':{'Pronouns':70,'Contractions':28,'Comparatives':48},'planned_outputs':1752,'generic_and_non_person_drawings':'Leave existing files unchanged; this pass substitutes full People figures only.','method':'Self-contained SVG compositions embed existing WebP artwork without recompressing it; vector arrows and objects retained. No whole-style tracing.','source_policy':'Keep all People and numbered Library originals unchanged; publish only new unnumbered root category files.','status':'authorised in full; assets and layout preparation'},indent=2));(H/'progress.json').write_text(json.dumps({'planned':1752,'built':0,'visually_accepted':0,'published':0,'styles':{r['style']:'queued' for r in styles}},indent=2));print('Saved full scope: 12 styles, 24 bases, 146 templates per style, 1,752 planned People substitutions.')
