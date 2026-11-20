from pathlib import Path
import json, re, hashlib, collections, html
from PIL import Image, ImageDraw, ImageFont
from audit import HERE, render

rows=json.loads((HERE/'results.json').read_text())
inventory=json.loads((HERE/'inventory.json').read_text())
refs=[r for r in inventory['files'] if r['kind']=='reference']
byid={r['id']:r for r in rows}
refnames={r['name']:r for r in refs}
base={'clean':'cleaner','dirty':'dirtier','dry':'drier','fast':'faster','noisy':'noisier','old':'older','short':'shorter (1)','slow':'slower','strong':'stronger','tall':'taller','weak':'weaker','wet':'wetter','young':'younger'}
for r in rows:
    name=re.sub(r' \(\d+\)$','',r['name'])
    r['concept']=name
    # Height comparisons use Fluent's people-height shorter (1), not its object-length shorter.
    refname='shorter (1)' if name=='shorter' else base.get(name,name)
    r['reference']=refnames.get(refname)
    r['reference_note']='Related comparative reference; this base-word variant is not an exact vocabulary match.' if name in base else 'Concept reference; composition and figure count may differ.'
    r['uri']=Path(r['path']).as_uri()
    if r['reference']:r['reference']['uri']=Path(r['reference']['path']).as_uri()
    r['small_display_reviewed']=r['small_arrow']
    r['proposed_action_approved']=False
for r in refs:r['uri']=Path(r['path']).as_uri()

styles=sorted(set(r['style'] for r in rows))
stylecounts=[]
for s in styles:
    ss=[r for r in rows if r['style']==s];c=collections.Counter(r['visual_status'] for r in ss)
    stylecounts.append(dict(style=s,total=len(ss),missing=c['missing'],upward=c['upward'],small=sum(r['small_arrow'] for r in ss),angled=c['angled_down'],single=c['not_required_single'],proposed=sum(r['proposed_action']!='retain' for r in ss)))
shared={}
for name in ['older','younger','youngest','shorter (1)','taller']:
    rr=[r for r in rows if r['style'] not in ('Sommi','Sommi clothed') and r['name']==name]
    shared[name]=dict(total=len(rr),statuses=dict(collections.Counter(r['visual_status'] for r in rr)))
assert all(v['total']==17 for v in shared.values())
assert len(rows)==730 and len(styles)==19 and len(refs)==85
assert sum(r['proposed_action']!='retain' for r in rows)==245

# One compact illustration of ORIGINALS only, retained as evidence for the chat.
examples=[('A0023','Missing selector','Same older pose: 3D'),('A0141','Missing selector','Same older pose: Doll'),('A0637','Missing selector','Same older pose: Wizard'),('A0671','Points upward','Wood / taller'),('A0501','Tiny selector: 17 px','Sommi / taller (1)'),('A0502','Keep this badge','Sommi / taller — single figure')]
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
smallfont=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',15)
sheet=Image.new('RGB',(1080,866),'#ffffff');d=ImageDraw.Draw(sheet)
d.text((18,12),'Comparative arrow audit — unchanged originals',font=font,fill='#172638')
for i,(id,title,label) in enumerate(examples):
    x=(i%3)*360;y=50+(i//3)*403;r=byid[id]
    d.text((x+14,y),title,font=font,fill='#172638')
    tile=Image.new('RGB',(332,332),'#e5edf5');im=render(Path(r['path'])).resize((332,332),Image.Resampling.LANCZOS);tile.paste(im,(0,0),im);sheet.paste(tile,(x+14,y+29))
    d.text((x+14,y+367),label,font=smallfont,fill='#172638')
sheet.save(HERE/'examples.jpg',quality=92)

table=''.join(f"<tr><td>{html.escape(s['style'])}</td>"+''.join(f'<td>{s[k]}</td>' for k in ['total','missing','upward','small','angled','single','proposed'])+'</tr>' for s in stylecounts)
rules='''<ol>
<li><strong>Select the intended person.</strong> In a multi-figure comparison, use a downward arrow pointing at the person represented by the word. Work out the target from the actual scene and the Fluent concept reference; do not infer it from left/right position or the filename suffix alone.</li>
<li><strong>Keep grammatical badges distinct.</strong> A separate up-right comparative badge and a superlative star have different jobs. Preserve them. Do not add a person-selection arrow to a single-figure image merely to make it match the others.</li>
<li><strong>Make the selector readable.</strong> Proposed existing-arrow minimum: 40 px high and 24 px wide, including outline, on a 512 px canvas (scale proportionally for 1024 px and SVG). New or enlarged arrows: aim for 64–80 px high and 32–48 px wide; a shaft about 8–12 px wide and a 3–4 px dark outline. These are practical proposals, not an established accessibility standard. Check the whole symbol at 128 px and 96 px before acceptance.</li>
<li><strong>Place it without hiding the drawing.</strong> Prefer a straight downward green arrow with a dark outline, with its tip roughly 8–16 px above the head, hat or antenna. Keep it inside the canvas. If there is too little room, use a clear downward-angled position rather than shrink below the minimum or cover a face or object.</li>
<li><strong>Keep adequate existing arrows.</strong> Retain clear downward-angled arrows and usable red arrows; colour alone is not a defect. Change the 15 upward arrows above the taller person if we adopt the consistent downward-selector rule. Leave unrelated height/motion indicators intact.</li>
<li><strong>Use shared poses to organise repairs, then verify each result.</strong> Decide the referent once for genuinely matching compositions; adapt placement for hair, hats, antennae and figure spacing. Inspect every changed output against its original on pastel and dark backgrounds. Preserve People originals and avoid extra image copies.</li>
</ol>'''

page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Comparative arrow audit — 19 November 2026</title>
<style>
*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#213044;background:#f4f6f8}main{max-width:1250px;margin:auto;padding:24px}h1,h2,h3{line-height:1.2}h1{font-size:30px}h2{margin-top:32px}a{color:#0861ab}section{background:white;border:1px solid #dbe1e7;border-radius:10px;padding:20px;margin:20px 0}.notice{border-left:5px solid #d09120;padding:12px;background:#fff8e9}.stats{display:flex;gap:12px;flex-wrap:wrap}.stats div{background:#e9f0f6;border-radius:8px;padding:12px;min-width:150px}.stats b{display:block;font-size:28px}.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0}button,select,input{font:inherit;padding:7px;border:1px solid #9eacba;border-radius:5px;background:white;color:#213044}button{cursor:pointer}button:disabled{opacity:.4;cursor:default}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #dde3e9;text-align:right;padding:7px}td:first-child,th:first-child{text-align:left}.overflow{overflow:auto}.viewer{display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap}.stage{background:var(--image-bg,#e5edf5);border-radius:6px}.full{width:min(100%,512px);height:auto;display:block}.small{width:128px;height:128px;display:block}.tiny{width:96px;height:96px;display:block}.ref{width:256px;height:256px;display:block}.side{max-width:540px}.path{overflow-wrap:anywhere;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}.card{border:1px solid #d9e1e8;padding:10px;border-radius:7px}.card img{width:100%;aspect-ratio:1;object-fit:contain;display:block}.card b{display:block}.flag{color:#a84400;font-weight:650}.muted{color:#596878}.thumbs{display:flex;align-items:flex-start;gap:14px}.hero{width:100%;max-width:1080px}li{margin:10px 0}summary{cursor:pointer;font-weight:650}.tag{display:inline-block;background:#e9eef3;border-radius:4px;padding:2px 6px;font-size:13px}#status{font-weight:bold}nav{display:flex;gap:20px;flex-wrap:wrap}pre{white-space:pre-wrap}body.darkImages{--image-bg:#283240}body.whiteImages{--image-bg:#fff}
</style><main>
<h1>Comparative arrow audit</h1><p>19 November 2026 · Task 8 · All current <code>01 Comparatives</code> targets</p>
<p class="notice"><strong>Review and proposed rules only. No source image has been changed.</strong> The 245 proposed repairs depend on approval of the rules below. This is an arrow audit, not a full semantic or background-cleanup certification.</p>
<nav><a href="#findings">Findings</a><a href="#rules">Proposed rules</a><a href="#review">One-symbol review</a><a href="#compare">Across styles</a><a href="#coverage">Coverage</a></nav>
<section id="findings"><div class="stats"><div><b>730</b>targets / 19 styles</div><div><b>205</b>missing selectors</div><div><b>15</b>upward selectors</div><div><b>25</b>below proposed size floor</div><div><b>245</b>proposed repairs</div></div>
<p><strong>The shared-pose pattern is real, but it is not identical across styles.</strong> <code>older</code> and <code>younger</code> lack selection arrows in all 17 common-layout styles. <code>youngest</code> lacks them in 14 of those 17; Clay plasticine, Friendly aliens and Monkey already have them. <code>shorter (1)</code> lacks them in 11 of 17. <code>taller</code> has an upward arrow in 15 of 17; Clay plasticine and Teddy bear have no selection arrow.</p>
<p>The 25 small downward arrows are 16–37 px high at a 512 px canvas. At 128 px display size that is only 4–9.25 px high. All 25 were checked at native size and at 128 px on pastel and dark backgrounds.</p>
<p><strong>485 targets have no proposed arrow change:</strong> 368 have downward selectors meeting the proposed size floor, 22 have downward-angled selectors, and 95 Sommi/Sommi clothed images show a single figure. A single figure may carry a comparative badge or superlative star; those are not misdirected person-selection arrows.</p>
<img class="hero" src="examples.jpg" alt="Six unchanged examples showing missing selectors, upward selector, tiny selector and a single-figure badge to retain">
<p class="muted">Examples are unchanged originals, resized only for this illustration. Use the viewer below for the source and its Fluent concept reference.</p></section>
<section id="rules"><h2>Proposed arrow rules — awaiting approval</h2>__RULES__
<p><strong>Repair scope:</strong> add 205 selectors, redirect 15 upward selectors, enlarge 25 small selectors. Do not redraw all arrows for cosmetic consistency. The minimum is a screening floor; a marginal arrow must still be clear at display size. Outline-only measurements are not inferred from coloured pixels.</p>
<p><strong>Pose reuse:</strong> a common target and approximate position can be shared, but not a blind coordinate stamp. The two Sommi families have substantially different compositions. Some numbered variants select a middle figure; do not enforce a blanket “two people for every comparative, three for every superlative” rule.</p>
<p><strong>Sequence:</strong> this audit does not start Task 9 (figure substitutions), plurals or tenses. Some comparative compositions may later be rebuilt under Task 9; avoid duplicating repairs to those files without agreeing the implementation sequence. Mulberry source SVGs in People remain read-only.</p></section>
<section id="review"><h2>One-symbol review</h2><p>Includes every target, including images with no proposed change. Images are loaded directly from their current source paths.</p>
<div class="controls"><label>Style <select id="style"><option value="">All 19 styles</option></select></label><label>Show <select id="filter"><option value="proposed">Proposed repairs (245)</option><option value="all">All targets (730)</option><option value="missing">Missing selector (205)</option><option value="upward">Upward selector (15)</option><option value="small">Small selector (25)</option><option value="angled_down">Downward angled (22)</option><option value="not_required_single">Single figure (95)</option><option value="retain">No proposed change (485)</option></select></label><label>Search <input id="query" placeholder="Concept, filename or ID"></label></div>
<div class="controls"><button id="previous">Previous</button><button id="next">Next</button><span id="position"></span><label>Background <select class="background"><option value="pastel">Pastel</option><option value="dark">Dark</option><option value="white">White</option></select></label></div>
<h3 id="title"></h3><p id="status"></p><p id="reason"></p><div id="viewer" class="viewer"></div><p id="source" class="path"></p><p id="measurement" class="muted"></p><p id="evidence" class="muted"></p></section>
<section id="compare"><h2>Compare the same concept across every style</h2><p>Includes every numbered variant of the chosen concept. A matching word does not guarantee a matching pose or referent; compare the drawings before sharing a placement.</p><div class="controls"><label>Concept <select id="concept"></select></label><label>Background <select class="background"><option value="pastel">Pastel</option><option value="dark">Dark</option><option value="white">White</option></select></label><span id="compareCount"></span></div><div id="grid" class="grid"></div></section>
<section id="coverage"><h2>Coverage and limits</h2><p>678 Library WebPs across all 18 styles with a <code>01 Comparatives</code> folder, plus 52 retained native Mulberry SVGs in People. All 730 target cells were visually inspected; all 85 Fluent references were inspected separately. 52 target files received native-size follow-ups for small arrows, connected arrows or disagreements with the component detector. No source was excluded because Python found no arrow.</p>
<p>Contact-sheet screening establishes presence and direction; it is not equivalent to native-size inspection of all 730 files. Python components supplied size measurements and flagged disagreements, not semantic decisions. One native follow-up corrected a missed omission: 3D animated cartoon <code>weakest</code>. A coloured motion streak in Monster <code>fastest</code> was rejected as a false arrow candidate.</p>
<p>Sommi companion objects has no <code>01 Comparatives</code> folder, so there are no targets there for this audit. No other Library style was silently omitted. Current Wood comparative images depict wooden figures; the previously reported robot contamination was not seen in these 26 current files.</p>
<div class="overflow"><table><thead><tr><th>Style</th><th>Checked</th><th>Missing</th><th>Up</th><th>Small</th><th>Angled</th><th>Single</th><th>Proposed repairs</th></tr></thead><tbody>__TABLE__</tbody><tfoot><tr><th>Total</th><th>730</th><th>205</th><th>15</th><th>25</th><th>22</th><th>95</th><th>245</th></tr></tfoot></table></div>
<p class="muted">“Small” is a subset of downward selectors; the columns are not all additive. “Up” means the arrow above the taller person, not a comparative badge. Angled and single-figure cases are retained under this proposal.</p>
<p>Normalised measurements use a 512 px canvas. 43 WebPs are 1024 × 1024; other WebPs are 512 × 512. Mulberry SVGs were rendered at 512 × 512 for measurement. Where an arrow touches the figure, its coloured core is reported separately and is not treated as the full outlined arrow.</p>
<p>Before/after SHA-256 verification: <strong>all 815 audited source files unchanged</strong> (730 targets + 85 references). Source hashes, exact paths, decisions and review coverage are saved in <a href="results.json">results.json</a> and <a href="verification.json">verification.json</a>. No approval is recorded and no correction has been applied.</p>
<details><summary>All 85 Fluent references</summary><div id="references" class="grid"></div></details></section></main>
<script id="audit-data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('audit-data').textContent), rows=data.rows;
const $=id=>document.getElementById(id);let selected=[],index=0;
const labels={missing:'Missing selection arrow',upward:'Upward arrow above taller person',down_present:'Downward selection arrow',angled_down:'Downward-angled selector — retain if clear',not_required_single:'Single figure — selector not required'};
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function pic(r,cls){const i=el('img',undefined,cls+' stage');i.src=r.uri;i.alt=r.style+' / '+r.name;i.loading='lazy';return i}
function link(r){const a=el('a',r.path);a.href=r.uri;a.target='_blank';return a}
for(const s of data.styles){const o=el('option',s);o.value=s;$('style').append(o)}
for(const c of [...new Set(rows.map(r=>r.concept))].sort()){const o=el('option',c);o.value=c;$('concept').append(o)}
$('concept').value='older';
function applyFilter(){const f=$('filter').value,s=$('style').value,q=$('query').value.toLowerCase();selected=rows.filter(r=>(!s||r.style===s)&&(!q||(r.name+' '+r.id).toLowerCase().includes(q))&&(f==='all'||f==='proposed'&&r.proposed_action!=='retain'||f==='retain'&&r.proposed_action==='retain'||f==='small'&&r.small_arrow||f===r.visual_status));index=0;show()}
function show(){const r=selected[index];$('position').textContent=selected.length?(index+1)+' of '+selected.length:'No matching files';$('previous').disabled=!r||index===0;$('next').disabled=!r||index===selected.length-1;for(const k of ['viewer','source','measurement','evidence','title','status','reason'])$(k).replaceChildren();if(!r)return;
 $('title').textContent=r.id+' · '+r.style+' · '+r.name;$('status').textContent=labels[r.visual_status]+' · Proposed action: '+r.proposed_action;$('status').className=r.proposed_action==='retain'?'':'flag';$('reason').textContent=r.reason;
 $('viewer').append(pic(r,'full'));const side=el('div',undefined,'side'),small=el('div',undefined,'thumbs');for(const [size,cls] of [[128,'small'],[96,'tiny']]){const item=el('div');item.append(el('p',size+' px display'),pic(r,cls));small.append(item)}side.append(small);
 if(r.reference){side.append(el('h3','Fluent: '+r.reference.name),pic(r.reference,'ref'),el('p',r.reference_note,'muted'));const p=el('p',undefined,'path');p.append(link(r.reference));side.append(p)}$('viewer').append(side);$('source').append(link(r));
 const m=r.arrow_measurement;$('measurement').textContent=(m?'Arrow: '+m.width_at_512+' × '+m.height_at_512+' px at 512 canvas. '+m.method+'. ':'')+'File: '+(r.bytes/1024).toFixed(1)+' KiB; '+(r.path.endsWith('.svg')?'native SVG; measured at 512 × 512':r.size.join(' × '))+(r.measurement_note?' · '+r.measurement_note:'');
 $('evidence').textContent='Reviewed: contact sheet'+(r.native_followup_reviewed?', native-size follow-up':'')+(r.small_display_reviewed?', 128 px pastel and dark':'')+'. '+(r.native_note||'');
 try{history.replaceState(null,'','#'+r.id)}catch(e){/* Some local-file viewers restrict history updates. */}
}
function compare(){const ss=rows.filter(r=>r.concept===$('concept').value);$('compareCount').textContent=ss.length+' variants across '+new Set(ss.map(r=>r.style)).size+' styles';$('grid').replaceChildren();for(const r of ss){const c=el('article',undefined,'card');c.append(el('b',r.style),el('span',r.name+' · '+r.id,'muted'),pic(r,''),el('p',r.proposed_action,r.proposed_action==='retain'?'':'flag'));const b=el('button','Inspect source and reference');b.onclick=()=>{$('filter').value='all';$('style').value='';$('query').value=r.id;applyFilter();$('review').scrollIntoView({behavior:'smooth'})};c.append(b);$('grid').append(c)}}
$('previous').onclick=()=>{if(index>0){index--;show()}};$('next').onclick=()=>{if(index<selected.length-1){index++;show()}};
for(const id of ['style','filter'])$(id).onchange=applyFilter;$('query').oninput=applyFilter;$('concept').onchange=compare;
for(const b of document.querySelectorAll('.background'))b.onchange=()=>{document.body.classList.toggle('darkImages',b.value==='dark');document.body.classList.toggle('whiteImages',b.value==='white');document.querySelectorAll('.background').forEach(x=>x.value=b.value)};
for(const r of data.refs){const c=el('article',undefined,'card');const a=el('a',r.name);a.href=r.uri;a.target='_blank';c.append(a,pic(r,''));$('references').append(c)}
const initial=location.hash.slice(1);if(rows.some(r=>r.id===initial)){$('filter').value='all';$('query').value=initial}applyFilter();compare();
</script></html>'''
payload=dict(rows=rows,styles=styles,refs=refs)
page=page.replace('__RULES__',rules).replace('__TABLE__',table).replace('__DATA__',json.dumps(payload,ensure_ascii=False).replace('</','<\\/'))
(HERE/'index.html').write_text(page)
(HERE/'results.json').write_text(json.dumps(rows,indent=2))
(HERE/'summary.json').write_text(json.dumps(dict(status='audit complete; proposed rules awaiting user approval; no source image edits',targets=730,target_styles=19,references=85,missing=205,upward=15,small=25,proposed_repairs=245,retained=485,styles=stylecounts,shared_concepts=shared,source_images_modified=0),indent=2))
verification=[]
for r in inventory['files']:
    actual=hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()
    assert actual==r['sha256'],r['path']
    verification.append(dict(id=r['id'],path=r['path'],sha256=actual,unchanged=True))
(HERE/'verification.json').write_text(json.dumps(dict(verified_files=len(verification),changed_files=0,records=verification),indent=2))
print('Report built; hashes unchanged:',len(verification));print('Shared-concept counts:',json.dumps(shared))
