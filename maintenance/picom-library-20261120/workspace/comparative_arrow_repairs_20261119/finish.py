from repair import HERE,AUDIT,LIB,TMP,ROWS,QUEUE,sha,FONT,SMALL
from pathlib import Path
from PIL import Image,ImageDraw
from collections import Counter
import json,html,datetime,shutil

published=[json.loads(s) for s in (HERE/'published.jsonl').read_text().splitlines()]
assert len(published)==245 and len({r['id'] for r in published})==245
assert {r['id'] for r in published}=={r['id'] for r in QUEUE}
byid={r['id']:r for r in ROWS};pubids={r['id'] for r in published}
for r in published:
 assert r['reviewed'] and sha(Path(r['destination']))==r['output_sha256'],r['id']
assert all(sha(Path(r['path']))==r['sha256'] for r in ROWS if r['id'] not in pubids or r['style']=='Mulberry')
inventory=json.loads((AUDIT/'inventory.json').read_text())
assert all(sha(Path(r['path']))==r['sha256'] for r in inventory['files'] if r['kind']=='reference')
assert not list((HERE/'staging').rglob('*.webp')) and not list((HERE/'staging').rglob('*.svg'))
styles=Counter(r['style'] for r in published)
summary=dict(status='complete',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),repaired=245,reviewed=245,webps_replaced_in_place=236,native_svgs_published=9,people_source_svgs_verified_unchanged=52,unselected_targets_verified_unchanged=485,fluent_references_verified_unchanged=85,source_bytes=sum(r['source_bytes'] for r in published),output_bytes=sum(r['output_bytes'] for r in published),styles=dict(sorted(styles.items())),max_alpha_change_outside_edit=max(r['max_alpha_change_outside_edit'] for r in published),temporary_images_remaining=0)
(HERE/'completion.json').write_text(json.dumps(summary,indent=2))
# Small before/after examples, not backup image copies.
ids=['A0023','A0063','A0038','A0141','A0501','A0580','A0671','A0701']
out=Image.new('RGB',(1060,4*340+50),'white');draw=ImageDraw.Draw(out);draw.text((12,12),'Comparative arrow repairs — before / after',font=FONT,fill='black')
for i,id in enumerate(ids):
 r=byid[id];x=i%2*530;y=50+i//2*340;im=Image.open(HERE/'examples_work'/(id+'.jpg'));out.paste(im,(x+8,y));draw.text((x+10,y+295),r['style']+' / '+r['name'],font=FONT,fill='black')
out.save(HERE/'before_after.jpg',quality=92)
payload=[]
for r in published:
 original=byid[r['id']];payload.append(dict(id=r['id'],style=r['style'],name=r['name'],action=original['proposed_action'],uri=Path(r['destination']).as_uri(),path=r['destination'],source_path=r['source'],bytes=r['output_bytes'],reference=original['reference']))
table=''.join(f'<tr><td>{html.escape(s)}</td><td>{n}</td></tr>' for s,n in sorted(styles.items()))
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Comparative arrow repairs — complete</title><style>
*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;background:#f4f6f8;color:#203044;margin:0}main{max-width:1200px;margin:auto;padding:25px}section{background:#fff;border:1px solid #dce3e9;border-radius:10px;margin:22px 0;padding:22px}h1{font-size:30px}a{color:#0963ab}img.examples{width:100%;max-width:1060px}.controls,.viewer{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}button,select,input{padding:8px;font:inherit;background:#fff;border:1px solid #9cabb8;border-radius:5px}.stage{background:var(--bg,#e5edf5)}.full{width:min(100%,512px);height:auto}.small{width:96px;height:96px}.ref{width:256px;height:256px}.path{font-size:13px;overflow-wrap:anywhere}td,th{padding:6px 12px;text-align:left;border-bottom:1px solid #e1e5e9}table{border-collapse:collapse}.ok{border-left:5px solid #27894b;padding:12px;background:#edf7ef}.dark{--bg:#283240}.white{--bg:#fff}
</style><main><h1>245 comparative arrow repairs completed</h1><p>19 November 2026 · All 19 styles in the approved queue</p><p class="ok"><strong>Every changed result reviewed and published.</strong> 236 WebPs replaced in place in Library; nine finished Mulberry SVGs saved to Library/Mulberry/01 Comparatives. People originals are unchanged. Temporary review sheets and staged images have been deleted.</p>
<section><h2>What changed</h2><p>Added 205 missing selection arrows, redirected 15 upward arrows above the taller person, and enlarged 25 small selectors. Existing adequate arrows, comparative badges and superlative stars were preserved.</p><p>Matching compositions guided the target choice, with individual adjustments for hair, hats, horns, antennae and available space. For example, Basic’s <em>older</em> selects the right-hand figure; the other 16 common-layout versions select the left-hand figure. New arrows point downward or downward at an angle when there is insufficient room directly above the head.</p><img class="examples" src="before_after.jpg" alt="Eight before and after examples"><p>The examples are small review illustrations. No additional full-size backup copies were retained.</p></section>
<section><h2>Review all 245 finished images</h2><div class="controls"><label>Style <select id="style"><option value="">All styles</option></select></label><input id="search" placeholder="Concept or image ID"><button id="prev">Previous</button><button id="next">Next</button><span id="position"></span><label>Background <select id="background"><option value="pastel">Pastel</option><option value="dark">Dark</option><option value="white">White</option></select></label></div><h3 id="title"></h3><p id="action"></p><div id="viewer" class="viewer"></div><p id="path" class="path"></p></section>
<section><h2>Verification and saved record</h2><p>All 245 published hashes match the reviewed output. All 485 targets outside the repair queue and all 85 Fluent reference SVGs retain their original hashes. All 52 People/Mulberry source SVGs remain unchanged. No publishing destination is in People.</p><p>Before encoding, pixels outside the arrow edit regions were checked for exact equality. New arrows do not overlap existing opaque artwork. WebP results were encoded once from their source for each final revision at Q80; alpha preservation outside the edit was checked independently of the small RGB changes caused by WebP encoding. Native SVG outputs retain their vector paths and use local clipping only where an old arrow was removed.</p><p>Every changed result was visually inspected beside its source at 256 px, plus a 96 px preview on a dark background. Tight arrow joins received closer inspection. Basic’s old-arrow remnant and a Mulberry outline fragment were corrected and rechecked before publication.</p><table><thead><tr><th>Style</th><th>Repaired and reviewed</th></tr></thead><tbody>__TABLE__</tbody></table><p><a href="completion.json">Completion checks</a> · <a href="published.jsonl">Per-file paths, hashes and edit records</a> · <a href="../comparative_arrow_audit_20261119/index.html">Original audit and agreed rules</a></p><p>Task 9 and later tasks have not been started.</p></section></main><script type="application/json" id="data">__DATA__</script><script>
const rows=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);let selected=[],index=0;function el(t,text,c){let e=document.createElement(t);if(text)e.textContent=text;if(c)e.className=c;return e}function pic(uri,c,alt){const e=el('img',null,c+' stage');e.src=uri;e.alt=alt;return e}
for(const s of [...new Set(rows.map(r=>r.style))].sort()){let e=el('option',s);e.value=s;$('style').append(e)}
function filter(){let s=$('style').value,q=$('search').value.toLowerCase();selected=rows.filter(r=>(!s||r.style===s)&&(!q||(r.id+' '+r.name).toLowerCase().includes(q)));index=0;show()}
function show(){let r=selected[index];$('position').textContent=selected.length?`${index+1} of ${selected.length}`:'No matches';$('prev').disabled=index===0;$('next').disabled=index>=selected.length-1;for(const id of ['viewer','path','title','action'])$(id).replaceChildren();if(!r)return;$('title').textContent=r.id+' · '+r.style+' · '+r.name;$('action').textContent='Completed: '+r.action+' · '+(r.bytes/1024).toFixed(1)+' KiB';$('viewer').append(pic(r.uri,'full',r.name));let side=el('div');side.append(el('p','96 px display'),pic(r.uri,'small',r.name));if(r.reference){side.append(el('p','Fluent concept reference: '+r.reference.name),pic(r.reference.uri,'ref',r.reference.name))}$('viewer').append(side);let a=el('a',r.path);a.href=r.uri;a.target='_blank';$('path').append(a);try{history.replaceState(null,'','#'+r.id)}catch(e){}}
$('style').onchange=filter;$('search').oninput=filter;$('prev').onclick=()=>{if(index>0){index--;show()}};$('next').onclick=()=>{if(index<selected.length-1){index++;show()}};$('background').onchange=()=>{document.body.className=$('background').value};let id=location.hash.slice(1);if(rows.some(r=>r.id===id))$('search').value=id;filter();
</script></html>'''
page=page.replace('__TABLE__',table).replace('__DATA__',json.dumps(payload).replace('</','<\\/'))
(HERE/'index.html').write_text(page)
shutil.rmtree(HERE/'examples_work')
if TMP.exists():shutil.rmtree(TMP)
if (HERE/'staging').exists():shutil.rmtree(HERE/'staging')
auditpage=AUDIT/'index.html';s=auditpage.read_text();s=s.replace('Repairs are now being applied in verified batches.','All 245 repairs are complete. <a href="../comparative_arrow_repairs_20261119/index.html">Open the finished review.</a>');auditpage.write_text(s)
print(json.dumps(summary,indent=2))
