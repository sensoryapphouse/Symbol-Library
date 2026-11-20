from pathlib import Path
import json,re,hashlib,collections,html,io,subprocess,math,datetime
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;R=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols');L=R/'Library';P=R/'People'
def read(n):return json.loads((H/(n+'.json')).read_text())
def save(n,x):(H/(n+'.json')).write_text(json.dumps(x,indent=2,ensure_ascii=False))
def norm(s):return re.sub(r'[- ]?\([MF]\)$','',s)
def esc(s):return html.escape(str(s),quote=True)
def link(p,label=None):return '<a href="'+esc(Path(p).as_uri())+'">'+esc(label or p)+'</a>'
def preview(p,label):return '<figure><a href="'+esc(Path(p).as_uri())+'"><img loading="lazy" src="'+esc(Path(p).as_uri())+'" alt="'+esc(label)+'"></a><figcaption>'+esc(label)+'</figcaption></figure>'
styles=[r for r in read('style_inventory') if r['style']!='Sommi companion objects'];cs=read('candidates');byid={r['id']:r for r in cs};ts=read('templates_raw');existing=[r for r in read('existing_outputs_raw') if r['style']!='Sommi companion objects'];samples=[r for r in read('existing_samples') if r['style']!='Sommi companion objects']
# Classification is based on visual inspection of all 252 rendered templates, with XML as a cross-check.
for t in ts:
 n=t['concept'];m=len(t['metadata_figures']);cat=t['category']
 if cat=='09 Pronouns':
  t['figure_count']=m;t['classification']='group' if m>1 else ('single' if m else 'no-person');t['action']='person substitution' if m else 'retain existing object/symbol; outside People substitution work'
 elif cat=='02 Contractions':
  t['figure_count']=1 if n=="who's" else m;t['classification']='bust exception' if n=="who's" else ('group' if m>1 else ('single' if m else 'no-person'));t['action']='review simplified bust separately' if n=="who's" else ('person substitution with auxiliary preserved' if m else 'retain existing auxiliary/symbol unchanged')
 else:
  if n in ['noisier','noisiest','newer','newest']:count=2;kind='face/bust exception'
  elif n in ['colder','coldest','hotter','hottest','fuller','fullest']:count=1;kind='face/bust exception'
  elif n in ['thinner','thinnest']:count=1;kind='simplified-body exception'
  elif m:count=2;kind='full-body comparison'
  else:count=0;kind='no-person'
  t['figure_count']=count;t['classification']=kind;t['action']='retain existing non-People illustration unchanged' if not count else ('preserve comparative pose, age and body contrast; use existing style treatment where suitable' if kind=='full-body comparison' else 'specific design review; do not apply a standing-figure swap')
 t['visually_inspected']=True
save('template_inventory',ts)
# Keep the five previously selected source references; preserve their already-built SVG figures where usable.
choices={
'3D animated cartoon':(['B001','B003'],'M/F','Saved choices; earlier SVG substitutions already exist in People. Reuse existing vector figures after QA; these are their source references.'),
'Basic':(['B007','B084'],'M/F','Standing somebody and girl avoid the pointing arms in he/she.'),
'Classic flat TV cartoon':(['B086','B009'],'M/F','Standing boy and she. Both preserve the yellow shirt and blue trousers.'),
'Clay plasticine':(['B090','B012'],'M/F','Standing boy and she; avoid the hand-on-chest he pose.'),
'Doll':(['B094','B015'],'M/F','Standing boy and she. This set already distinguishes a boy and a girl with pigtails/pinafore.'),
'Flat outlined':(['B017','B020'],'M/F','Saved choices; existing vector figures and substitutions in People should be reused after QA.'),
'Friendly aliens':(['B023','B022'],'M/F','Standing somebody and she. The female variant already has hair and a purple dress; do not assume this style is ungendered.'),
'Kawaii':(['B024','B027'],'M/F','Saved choices; existing vector figures and substitutions in People should be reused after QA.'),
'Monkey':(['B030','B029'],'M/F','Standing somebody and she. The female variant has a bow.'),
'Monster':(['B033','B032'],'M/F','Standing somebody and she. Female has a bow and closed smiling eyes; retain this existing design if approved.'),
'Mulberry':(['B034','B036'],'M/F','Saved native SVG choices. Existing substitutions are in People/Mulberry; only nine corrected numbered comparatives are in Library/Mulberry. Broader publication remains a separate decision.'),
'Robot':(['B040','B039'],'M/F','Standing somebody and she. Existing female design has hair; use the existing distinction rather than inventing one.'),
'Simple anime':(['B041','B043'],'M/F','Saved choices; existing vector figures and substitutions in People should be reused after QA.'),
'Soccer player':(['B047','B046'],'M/F','Standing somebody and she; consistent kit and no pointing gesture.'),
'Sommi':(['B071','B073','B069'],'N/M/F','Reuse saved neutral, blue-cap male and red-cap female bases. Existing cupped versions B072/B074/B070 are available for held objects. Existing root Pronouns outputs take priority over regeneration.'),
'Sommi clothed':(['B079','B080','B078'],'N/M/F','Reuse the actual saved yellow, blue and pink standing bases. The older description of hats does not match these files. Female clutch assets B076/B077 exist; no equivalent male/neutral cupped base found among the saved root assets. Do not use numbered he/she as clean bases: they include annotations or another figure design.'),
'Teddy bear':(['B062','B061'],'M/F','Standing somebody and she. Female already has a bow.'),
'Wizard':(['B065','B064'],'M/F','Standing somebody and she; consistent hat, robe and belt.'),
'Wood':(['B098','B067'],'M/F','Standing boy and she. Avoid the waving somebody and pointing someone/he.'),
}
proposals=[];coverage=[];source_checks={}
for r in ts+cs+existing:
 source_checks[r['path']]=r['sha256']
for r in samples:
 p=Path(r['path']);source_checks.setdefault(str(p),hashlib.sha256(p.read_bytes()).hexdigest())
for s in styles:
 name=s['style'];ids,gender,note=choices[name];root=L/name
 counts={};files_by={}
 for loc,base in [('Library',L),('People',P)]:
  for category in ['01 Comparatives','02 Contractions','09 Pronouns','Comparatives','Contractions','Pronouns']:
   d=base/name/category;files=sorted(p for p in d.glob('*') if p.is_file() and p.suffix.lower() in ['.svg','.webp','.png']);files_by[(loc,category)]=files
   counts[loc+'/'+category]={'exists':d.is_dir(),'files':len(files)}
 for cat,template_cat in [('Pronouns','09 Pronouns'),('Contractions','02 Contractions'),('Comparatives','01 Comparatives')]:
  target={t['concept'] for t in ts if t['category']==template_cat};per=[]
  for loc in ['Library','People']:
   files=files_by[(loc,cat)];names={norm(p.stem) for p in files if not p.stem.startswith('test_')};per.append(dict(location=loc,path=str((L if loc=='Library' else P)/name/cat),exists=counts[loc+'/'+cat]['exists'],files=len(files),matched_concepts=sorted(names&target),missing_concepts=sorted(target-names),extras=sorted(names-target),tests=[p.name for p in files if p.stem.startswith('test_')]))
  coverage.append(dict(style=name,category=cat,target_concepts=len(target),locations=per))
 prs=[x for x in coverage if x['style']==name and x['category']=='Pronouns'][0]
 libcov,peocov=prs['locations']
 if libcov['files']:status=f"Library/Pronouns exists: {libcov['files']} files / {len(libcov['matched_concepts'])} matched concepts. Assess gaps; do not overwrite."
 elif peocov['files']:status=f"People/Pronouns exists: {peocov['files']} SVGs / {len(peocov['matched_concepts'])} matched concepts. Library/Pronouns absent. Assess reuse/publication before creating replacements."
 else:status='No root Pronouns outputs found in Library or People. New style-root Pronouns folder proposed.'
 proposals.append(dict(style=name,base_ids=ids,gender_proposal=gender,note=note,existing_status=status,counts=counts,proposed_destination=str(root/'Pronouns'),destination_exists=(root/'Pronouns').is_dir(),approved=False))
save('base_proposals',proposals);save('existing_coverage',coverage);save('source_checks',source_checks)
# Concrete known issues, observed in existing files. These are findings, not edits.
issues=[]
for s in ['3D animated cartoon','Flat outlined','Kawaii','Simple anime','Mulberry']:
 p=P/s/'Pronouns/they-them.svg';issues.append(dict(style=s,path=str(p),finding='Still contains the original three Fluent people; saved no-person classification omitted this concept.',status='unchanged; propose targeted correction later'))
issues.append(dict(style='Sommi',path=str(L/'Sommi/Pronouns/they-them.webp'),finding='Still contains the original three Fluent people.',status='unchanged; propose targeted correction later'))
issues.append(dict(style='Sommi clothed',path=str(L/'Sommi clothed/Pronouns/my.webp'),finding='Possessed object is low on the abdomen rather than centred on the chest; old black hand/arm shape remains conspicuous.',status='unchanged; needs placement review before calling complete'))
issues.append(dict(style='Sommi clothed',path=str(L/'Sommi clothed/09 Pronouns/I.webp'),finding='Numbered source visibly contains an iStock mark; unsuitable as a base. It is not selected.',status='unchanged; source-quality finding only'))
save('observed_issues',issues)
summary=dict(date='2026-11-19',scope='19 People styles only. Sommi companion objects and non-People symbols excluded.',styles=len(proposals),fluent_files=len(ts),fluent_concepts=sum(len({t['concept'] for t in ts if t['category']==c}) for c in sorted({t['category'] for t in ts})),existing_files_in_scope=len(existing),existing_people_svg_files=sum(r['location']=='People' for r in existing),existing_visual_samples=len({r['path'] for r in samples}),all_template_contact_sheets_inspected=True,all_19_style_candidates_inspected=True,new_substitutions_created=0,original_images_modified=0,destination_rule='Per-style root Pronouns, Contractions and Comparatives, separate from numbered folders; skip all existing files. No duplicate output tree. No implementation authorised yet beyond this inventory.',gender_note='M/F/N labels follow existing asset names and visual variants, not an inference about a real person. The proposal preserves existing distinctions; final variant policy awaits user review.')
save('summary',summary)
# Build a self-contained HTML index that references source images directly; no source asset copies.
parts=['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Task 9 — People inventory and proposed bases</title><style>
:root{font-family:system-ui,sans-serif;color:#173344;background:#f4f7fa}body{max-width:1240px;margin:auto;padding:24px}h1{font-size:30px}h2{margin-top:36px}p,li{line-height:1.55}a{color:#005c91}nav{position:sticky;top:0;background:#fff;padding:12px;z-index:5;border-bottom:2px solid #a8bfcc;display:flex;gap:20px;flex-wrap:wrap}.box,article{background:white;border:1px solid #c8d5de;border-radius:10px;padding:20px;margin:18px 0}.notice{border-left:6px solid #b77600;background:#fff8e8;padding:16px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;text-align:left;border-bottom:1px solid #cedae2;vertical-align:top}th{background:#e4edf4}figure{margin:0;max-width:245px}figure img{width:220px;height:240px;object-fit:contain;background:#e5edf5;border:1px solid #d0dee9}figcaption{font-size:13px;overflow-wrap:anywhere;max-width:235px;margin-top:6px}.figures{display:flex;gap:18px;flex-wrap:wrap}.small{font-size:13px;color:#4b6577}.path{overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:12px}details{margin:12px 0}summary{cursor:pointer;padding:9px;background:#edf3f7}input,select{font:inherit;padding:8px;margin:5px}#templateGrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(225px,1fr));gap:16px}.badge{background:#e2f1e9;padding:4px 8px;border-radius:5px}.issue{border-left:5px solid #bb7b21;padding-left:16px}.hidden{display:none!important}@media(max-width:650px){body{padding:12px}figure img{width:160px;height:180px}td,th{padding:5px}table{font-size:12px}}
</style><h1>Task 9: People inventory and proposed base figures</h1><p>19 November 2026 · Inventory and proposal only · <strong>No substitutions or source-image changes made.</strong></p><nav><a href="#coverage">Existing work</a><a href="#bases">All 19 styles</a><a href="#findings">Findings</a><a href="#templates">Fluent inventory</a><a href="#next">Proposed next step</a></nav>''']
parts.append('<div class="notice"><strong>People styles only.</strong> Sommi companion objects is excluded. Non-People symbols remain unchanged. The intended destination is <code>Library/&lt;style&gt;/Pronouns/</code>, at the style root beside <code>09 Pronouns</code>, and equivalent root folders for the other two categories. Existing destination files are preserved. No new folders have been created in Library or People.</div>')
parts.append('<div class="box"><p><strong>The existing Pronouns folders are evidence of earlier substitution work.</strong> Five styles have 233 saved SVG outputs each in People: 84 Pronouns, 40 Contractions and 109 Comparatives. Their SVG metadata confirms earlier substitution. Sommi and Sommi clothed have smaller root-folder WebP sets in Library. Reuse these before planning any new work.</p><p>Folder presence and filename coverage do not prove completion. The review found specific omissions, including six existing <code>they-them</code> files that still contain Fluent people. This is a targeted outstanding issue, not a reason to rebuild all existing outputs.</p><p class="small">Inspection: all 252 Fluent template renders, candidates for all 19 People styles, 12 saved Sommi base assets, the previous five-style cutout overview, and '+str(summary['existing_visual_samples'])+' existing-output/source samples. Existing outputs have not all received a new visual QA pass.</p></div>')
parts.append('<h2 id="coverage">Existing root-folder work</h2><p>The numbered <code>09 Pronouns</code> drawings are source illustrations, not proof that Fluent substitution has been applied. Counts below distinguish both trees. Mulberry’s full set is in People; Library/Mulberry currently contains only nine corrected numbered Comparative SVGs.</p><table><tr><th>Style</th><th>Library root Pronouns</th><th>People root Pronouns</th><th>Other root-folder outputs</th></tr>')
for p in proposals:
 name=p['style'];rows=[c for c in coverage if c['style']==name];pr=next(c for c in rows if c['category']=='Pronouns');cells=[]
 for loc in pr['locations']:
  cells.append(link(loc['path'],f"{loc['files']} files · {len(loc['matched_concepts'])}/54 concepts") if loc['exists'] else 'Absent')
 other=[]
 for c in rows:
  if c['category']=='Pronouns':continue
  for loc in c['locations']:
   if loc['files']:other.append(f"{loc['location']}: {c['category']} {loc['files']}")
 parts.append('<tr><td><a href="#style-'+re.sub('[^a-z0-9]+','-',name.lower())+'">'+esc(name)+'</a></td><td>'+cells[0]+'</td><td>'+cells[1]+'</td><td>'+'<br>'.join(other)+'</td></tr>')
parts.append('</table><p class="small">Sommi’s 29 files cover 27 concepts: one concept has M/F filenames and one file is test_book_possessive. Sommi clothed’s 22 files cover 22 concepts. Their numbered folders cover the other concept names, but those are not equivalent composed outputs. The 83 Library Comparatives in 3D and Flat outlined are object-based alternatives (plates, dogs, weights), not the saved People substitutions; leave them unchanged.</p><details><summary>Exact coverage and missing concept names by style/category/location</summary>')
for c in coverage:
 parts.append('<details><summary>'+esc(c['style']+' / '+c['category'])+'</summary>')
 for loc in c['locations']:
  parts.append('<p><strong>'+esc(loc['location'])+'</strong>: '+str(loc['files'])+' files; '+str(len(loc['matched_concepts']))+'/'+str(c['target_concepts'])+' concept names matched.</p><p class="small">Missing names: '+esc(', '.join(loc['missing_concepts']) or 'none')+'</p>')
 parts.append('</details>')
parts.append('</details><h2 id="bases">Proposed base figures — all 19 People styles</h2><p>These are existing source figures for review, not newly extracted cutouts. For the five styles with saved substitutions, prefer the already-built vector figures within those outputs after QA; do not replace them automatically with raster copies. M/F below follows existing male/female asset conventions. Sommi also has a neutral base.</p><p>Recommendation: preserve the existing M/F distinctions in these sets. Dolls, robots, aliens, monkeys, monsters and bears visibly have alternate female designs; the older suggestion that they were all ungendered is not supported by the files. No new visual distinctions are proposed.</p>')
for p in proposals:
 name=p['style'];sid=re.sub('[^a-z0-9]+','-',name.lower());parts.append('<article id="style-'+sid+'"><h3>'+esc(name)+' <span class="badge">'+esc(p['gender_proposal'])+'</span></h3><p>'+esc(p['existing_status'])+'</p><div class="figures">');labels=['Neutral','Male','Female'] if len(p['base_ids'])==3 else ['Male / default','Female']
 for bid,label in zip(p['base_ids'],labels):
  r=byid[bid];parts.append(preview(r['path'],label+' · '+bid+' · '+r['rel']))
 parts.append('</div><p>'+esc(p['note'])+'</p><p class="small">Proposed destination (not created or modified):</p><p class="path">'+esc(p['proposed_destination'])+'</p>')
 saved=[r for r in existing if r['style']==name and r['category']=='Pronouns' and r['name'] in ['he','her']]
 if saved:
  parts.append('<details><summary>Existing composed outputs for comparison</summary><div class="figures">')
  for r in saved:parts.append(preview(r['path'],r['location']+'/Pronouns/'+r['name']))
  parts.append('</div></details>')
 parts.append('</article>')
parts.append('<h2 id="findings">Findings to carry into the next step</h2><ul><li><strong>Pronouns:</strong> 54 concepts now classify as 21 single-person, 18 group and 15 no-person. The saved list put they-them in the wrong category. Current templates total 100 person-containing files and 15 no-person files.</li><li><strong>Contractions:</strong> 40 template files (16 concepts) contain full figures. Who’s has a simplified bust requiring a separate design decision. The other 11 auxiliary/object templates have no complete person to replace.</li><li><strong>Comparatives:</strong> 24 templates contain two full-body figures; 12 more contain faces, busts or simplified bodies. Keep those exceptions separate. The other 49 templates are outside People substitution work.</li><li><strong>Old detector:</strong> counting groups with more than five paths misses current full-body comparatives and they-them. Noisier metadata lists four figure IDs although the visible composition has two busts. Use the verified inventory, not the old heuristic alone.</li><li><strong>Comparative meaning:</strong> existing saved SVG comparatives often adapt the head/style while preserving the posed body. A universal standing-body swap could erase age, speed, strength or wet/dry cues. Review those treatments; do not assume the Pronoun standing base works for every comparative.</li><li><strong>Possessions and groups:</strong> preserve all figures, chest placement and foreground arrows/objects. The old fixed scale/shift values are not a universal placement rule.</li><li><strong>Saved SVGs:</strong> all 1,165 preserved substitution SVG files parse, and none references an external image file. That is a structural check, not visual approval.</li></ul>')
for issue in issues:
 parts.append('<div class="issue"><p><strong>'+esc(issue['style'])+'</strong>: '+esc(issue['finding'])+'</p><p>'+link(issue['path'],str(Path(issue['path']).relative_to(R)))+'</p></div>')
parts.append('<details><summary>View the inspected existing-output samples ('+str(summary['existing_visual_samples'])+')</summary><div class="figures">')
seen=set()
for r in samples:
 if r['path'] in seen:continue
 seen.add(r['path']);parts.append(preview(r['path'],r['style']+' / '+r['category']+' / '+r['name']))
parts.append('</div></details><h2 id="templates">Verified Fluent template inventory</h2><p>252 source files / 167 concept names across the three categories. The complete inventory includes non-person templates to show why they will be left unchanged.</p><label>Category <select id="category"><option value="">All</option><option>01 Comparatives</option><option>02 Contractions</option><option>09 Pronouns</option></select></label><label>Search <input id="query" placeholder="concept or classification"></label><p id="shown"></p><div id="templateGrid"></div>')
parts.append('<h2 id="next">Proposed next step — requires review of these bases</h2><ol><li>Confirm the base and variant choices above. Existing SVG figures are candidates for reuse, not a new whole-style SVG conversion.</li><li>Reuse acceptable existing substitutions. Audit their remaining files before calling them finished, and separate specific defects from genuinely missing outputs.</li><li>For missing People substitutions, use the saved Sommi multi-figure method with the verified figure inventory, preserve semantic annotations and check five examples per affected style before rollout, as the saved plan requires.</li><li>Use style-root Pronouns, Contractions and Comparatives. Create only missing folders/files; never replace an existing pathname. Where a correction or publication would collide, present that conflict before writing. Preserve People originals and numbered source folders.</li></ol><p>No new cutouts, substitutions, Q80 passes, Library folders or source copies were made for this inventory. Temporary inspection contact sheets were deleted after this review was verified. The review page links to originals.</p><p>'+link('/Users/paulblenkhorn/Desktop/picom_review/LIBRARY_TASKS.md','Saved master task list')+' · '+link('/Users/paulblenkhorn/Desktop/picom_review/PRONOUN_SUBSTITUTION_METHOD.md','Saved Sommi method')+'</p>')
jsrows=[dict(id=t['id'],category=t['category'],name=t['name'],classification=t['classification'],count=t['figure_count'],action=t['action'],url=Path(t['path']).as_uri()) for t in ts]
parts.append('<script>const rows='+json.dumps(jsrows).replace('<','\\u003c')+''';const grid=document.querySelector('#templateGrid');function draw(){const q=document.querySelector('#query').value.toLowerCase(),cat=document.querySelector('#category').value;const rr=rows.filter(r=>(!cat||r.category===cat)&&(`${r.name} ${r.classification}`.toLowerCase().includes(q)));grid.replaceChildren();for(const r of rr){const d=document.createElement('div');const a=document.createElement('a');a.href=r.url;const im=document.createElement('img');im.src=r.url;im.loading='lazy';im.alt=r.name;im.style.cssText='width:210px;height:210px;object-fit:contain;background:#e5edf5';a.append(im);const p=document.createElement('p');p.textContent=`${r.id} ${r.name} · ${r.count} figures · ${r.classification}`;p.className='small';d.append(a,p);grid.append(d)}document.querySelector('#shown').textContent=`${rr.length} templates shown`};document.querySelector('#query').addEventListener('input',draw);document.querySelector('#category').addEventListener('change',draw);draw();</script></html>''')
(H/'index.html').write_text('\n'.join(parts))
# Two small overview contact sheets for convenient review; no copied source assets.
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12)
for page in range(2):
 pp=proposals[page*10:(page+1)*10];im=Image.new('RGB',(1100,50+math.ceil(len(pp)/2)*320),'white');d=ImageDraw.Draw(im);d.text((12,12),f'Proposed People bases — {page+1}/2 — source figures only',font=font,fill='black')
 for i,p in enumerate(pp):
  x=i%2*550;y=50+i//2*320;d.text((x+10,y),p['style']+' ('+p['gender_proposal']+')',font=font,fill='black');labels=['N','M','F'] if len(p['base_ids'])==3 else ['M','F'];size=158 if len(labels)==3 else 210
  for j,(bid,label) in enumerate(zip(p['base_ids'],labels)):
   f=Path(byid[bid]['path']);src=Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(f)]))) if f.suffix=='.svg' else Image.open(f);src=src.convert('RGBA');src.thumbnail((size,240));xx=x+12+j*(size+12);yy=y+28
   im.paste('#e5edf5',(xx,yy,xx+size,yy+240));im.paste(src,(xx+(size-src.width)//2,yy+(240-src.height)//2),src);d.text((xx,yy+244),label+' '+bid,font=small,fill='black')
 im.save(H/f'proposed_bases_{page+1}.jpg',quality=90)
print(json.dumps(summary,indent=2));print('Review bytes', (H/'index.html').stat().st_size)
