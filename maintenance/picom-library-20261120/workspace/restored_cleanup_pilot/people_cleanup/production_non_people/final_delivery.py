#!/usr/bin/env python3
"""Build linked Non-People delivery metadata only from exact complete final receipts."""
import collections,datetime,hashlib,html,json,os
from pathlib import Path
from common import HERE,require,atomic_json,digest
from verification import complete_catalog
OUTPUT=HERE/'final_delivery'

def atomic_bytes(path,raw):
    temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def render_index(rows, summary):
    data = [{**r, 'before': (None if r['source_byte_evidence']=='historical_publication_receipt'
                           else Path(r['source_path']).as_uri()),
             'after': Path(r['delivery_path']).as_uri()} for r in rows]
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    counts = html.escape(f"{summary['scope_total']:,} Non-People symbols accounted for; {len(rows):,} accepted updates. The viewer shows current delivered images and reviewed input hashes.")
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Non-People symbols — accepted updates</title><style>
body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:1150px;color:#20242b;background:#fafafa}
input,select,button{font:inherit;padding:8px;margin:4px}input{width:min(440px,85vw)}h1{font-size:1.5rem}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair[hidden],.card [hidden]{display:none}.card{min-width:0}img{display:block;width:100%;aspect-ratio:1;object-fit:contain;background-color:#ddd;background-image:conic-gradient(#fff 25%,transparent 0 50%,#fff 0 75%,transparent 0);background-size:20px 20px;border:1px solid #aaa}
.muted{color:#555}#path{overflow-wrap:anywhere}button:disabled{opacity:.4}@media(max-width:650px){.pair{grid-template-columns:1fr}}
</style><h1>Non-People symbols — accepted updates</h1><p>''' + counts + '''</p>
<p><a href="accepted_deliveries.json">Accepted delivery manifest</a> · <a href="all_non_people_dispositions.jsonl">Every symbol’s disposition</a> · <a href="summary.json">Verification and counts</a></p>
<label>Find a symbol <input id="search" type="search" placeholder="Style, category or symbol name"></label>
<label>Style <select id="style"><option value="">All styles</option></select></label>
<label>Update <select id="kind"><option value="">All updates</option><option value="cleaned">Background cleanup</option><option value="repair">Prior repair</option></select></label>
<p><button id="prev">Previous</button> <span id="position"></span> <button id="next">Next</button></p>
<h2 id="path"></h2><div class="pair" id="pair"><section class="card"><h3 id="before-title">Reviewed input</h3><img id="before" alt="Original symbol"><p id="before-size"></p><p id="before-hash"></p><a id="before-link">Open original WebP</a></section>
<section class="card"><h3>Current delivery</h3><img id="after" alt="Accepted symbol"><p id="after-size"></p><p id="after-hash"></p><a id="after-link">Open accepted WebP</a></section></div>
<p class="muted">The checkerboard shows transparency. Use the arrow keys or buttons to move between symbols.</p>
<script id="records" type="application/json">''' + encoded + '''</script><script>
const rows=JSON.parse(document.getElementById('records').textContent),$=id=>document.getElementById(id);
let selected=rows,index=0;
for(const name of [...new Set(rows.map(r=>r.relative_path.split('/')[0]))].sort()){const o=document.createElement('option');o.value=name;o.textContent=name;$('style').append(o);}
function size(bytes){return bytes.toLocaleString()+' bytes ('+(bytes/1024).toFixed(1)+' KiB)';}
function render(){const r=selected[index];$('position').textContent=selected.length?(index+1)+' of '+selected.length:'No matching symbols';$('prev').disabled=index===0;$('next').disabled=index>=selected.length-1;$('pair').hidden=!r;$('path').textContent=r?r.relative_path:'';if(!r)return;$('after').src=r.after;$('after-link').href=r.after;
for(const id of ['before','before-link'])$(id).hidden=!r.before;
if(r.before){$('before').src=r.before;$('before-link').href=r.before;}else{$('before').removeAttribute('src');$('before-link').removeAttribute('href');}
$('before-size').textContent=size(r.source_bytes);$('before-hash').textContent='Reviewed input SHA-256 '+r.source_sha256;$('after-size').textContent=size(r.delivery_bytes);$('after-hash').textContent='Current delivery SHA-256 '+r.delivery_sha256;try{history.replaceState(null,'','#'+encodeURIComponent(r.relative_path));}catch(e){if(e.name!=='SecurityError')throw e;location.hash=encodeURIComponent(r.relative_path);}}
function filter(){const q=$('search').value.toLowerCase(),s=$('style').value,k=$('kind').value;selected=rows.filter(r=>r.relative_path.toLowerCase().includes(q)&&(!s||r.relative_path.split('/')[0]===s)&&(!k||r.delivery_kind===k));index=0;render();}
for(const id of ['search','style','kind'])$(id).addEventListener('input',filter);
$('prev').onclick=()=>{if(index>0){index--;render();}};$('next').onclick=()=>{if(index+1<selected.length){index++;render();}};
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='ArrowLeft')$('prev').click();if(e.key==='ArrowRight')$('next').click();});
let initial='';try{initial=decodeURIComponent(location.hash.slice(1));}catch(e){}const found=rows.findIndex(r=>r.relative_path===initial);if(found>=0)index=found;render();
</script></html>'''

def build(catalog,proof,proof_sha,output=OUTPUT):
    require(proof.get('status')=='complete' and proof.get('completion_claim') is True and len(catalog)==proof['scope_total'],'Incomplete final byte proof')
    accepted=[r for r in catalog if r['delivery_kind']!='original']
    published=proof.get('published_library_rows_checked_this_invocation',0)
    if proof['kind']=='whole_original_non_people_final':
        require(published==len(accepted) and all(r['source_byte_evidence']=='historical_publication_receipt'
                and r['source_path']==r['delivery_path'] for r in accepted),'Incomplete published Library catalog')
    summary={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope_total':proof['scope_total'],'accepted_updates':len(accepted),
        'originals_retained':len(catalog)-len(accepted),'status_counts':proof['status_counts'],'delivery_kind_counts':dict(collections.Counter(r['delivery_kind'] for r in catalog)),
        'verification_completed_utc':proof['completed_utc'],'verification_proof_path':proof['immutable_proof_path'],'verification_proof_sha256':proof_sha,
        'source_checkpoint_sha256':proof['checkpoint_sha256'],'library_written':published>0,'published_library_updates_verified':published,
        'current_delivery_rows_verified':proof.get('current_delivery_rows_checked_this_invocation',len(catalog)),
        'historical_input_receipts_bound':proof.get('historical_input_receipts_bound',0),'images_copied_or_changed':False,'builder_sha256':digest(__file__)}
    payloads={'accepted_deliveries.json':(json.dumps(accepted,ensure_ascii=False,indent=2)+'\n').encode(),
        'all_non_people_dispositions.jsonl':b''.join((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode() for r in catalog),
        'index.html':render_index(accepted,summary).encode()}
    summary['artifacts_sha256']={name:hashlib.sha256(raw).hexdigest() for name,raw in payloads.items()};output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,raw in payloads.items():atomic_bytes(output/name,raw)
    atomic_json(output/'summary.json',summary);return summary

def main():
    catalog,proof,proof_sha=complete_catalog();summary=build(catalog,proof,proof_sha)
    print(json.dumps({'scope_total':summary['scope_total'],'accepted_updates':summary['accepted_updates'],'images_copied_or_changed':False}))
if __name__=='__main__':main()
