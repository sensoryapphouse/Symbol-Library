#!/usr/bin/env python3
"""Compact offline viewer for the current Library image and historical review metadata."""
import argparse,json
from pathlib import Path
from qa import read
from common import verify_batch_scope
from non_people_publication import batch_publication
from publication_transaction import bound

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True,type=Path)
 batch=verify_batch_scope(ap.parse_args().batch)
 tx=batch_publication(batch,load_only=True);tx.completed_pins()
 m=read(batch/'manifest.json');delivery=read(batch/'accepted_delivery.json')
 runs={r['id']:r for r in read(batch/'selected_run_state.json')['images']}
 d={r['id']:r for r in delivery['images']};cards=[]
 published={r['library']:r for r in tx.intent['deliveries']}
 for group in m['groups']:
  for row in group['versions']:
   id=row['batch_id'];entry=d[id];current=Path(row['source']);accepted=entry['delivery']=='cleaned';regions=[]
   if accepted:
    item=published[str(current)];expected=item['output']
    assert expected['sha256']==entry['sha256']
    regions=read(batch/'accepted_outputs'/id/'result.json')['regions']
   else:
    expected={'sha256':row['source_sha256'],'bytes':row['source_bytes']}
   bound(current,expected)
   cards.append({'id':id,'concept':group.get('group_key',group['group_id']),'style':row['style'],'dimensions':row['dimensions'],'after':current.as_uri(),'source_bytes':row['source_bytes'],'after_bytes':expected['bytes'],'accepted':accepted,'status':runs[id]['status'],'role':entry.get('role'),'reference':entry.get('reference',False),'review_required':entry.get('review_required',True),'newly_processed':entry.get('newly_processed',True),'reason':entry['reason'],'source_sha256':row['source_sha256'],'output_sha256':expected['sha256'],'regions':regions})
 assert len(cards)==len(d)
 payload=json.dumps(cards,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
 page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Non-People cleanup review</title><style>
body{font:14px system-ui;margin:0;background:#eee;color:#222}header{position:sticky;top:0;background:white;padding:12px;display:flex;flex-wrap:wrap;gap:10px;z-index:2}button,select,input{font:inherit;padding:5px}main{padding:12px}.meta{background:white;padding:12px;margin-bottom:10px;overflow-wrap:anywhere}.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pane{min-width:0;background:white;padding:8px}.stage{overflow:auto;max-height:70vh;background:#78658d}.stage img{display:block;max-width:none}.checker{background-color:#eee;background-image:conic-gradient(#bbb 25%,#eee 0 50%,#bbb 0 75%,#eee 0);background-size:24px 24px}.crop{overflow:hidden;background:#78658d}.crop img{display:block;max-width:none}#crops{display:flex;gap:12px;overflow:auto;margin:10px 0}.hash{font-size:11px;color:#555}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style>
<header><b>Non-People symbols</b><button id="prev">←</button><button id="next">→</button><span id="count"></span><select id="filter"><option value="accepted">Accepted</option><option value="all">All processed</option><option value="context">Context references</option></select><input id="search" placeholder="Concept, style or ID"><select id="bg"><option value="purple">Purple</option><option value="checker">Checker</option></select><select id="zoom"><option value="1">Native 1×</option><option value="0.5">0.5×</option><option value="2">2×</option></select></header><main id="app"></main><script>
const DATA=__DATA__,$=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let list=[],i=0;
function filter(){let s=$('search').value.toLowerCase();list=DATA.filter(x=>($('filter').value==='context'?x.review_required===false:($('filter').value==='all'?x.newly_processed:x.accepted))&&(!s||[x.id,x.style,x.concept].join(' ').toLowerCase().includes(s)));i=0;render()}
function pane(src,label,x,z){return `<section class="pane"><b>${esc(label)}</b><div class="stage ${$('bg').value==='checker'?'checker':''}"><img src="${esc(src)}" width="${x.dimensions[0]*z}" height="${x.dimensions[1]*z}" alt="${esc(label+' '+x.id)}"></div></section>`}
function render(){let x=list[i];$('count').textContent=`${list.length?i+1:0} / ${list.length}`;if(!x){$('app').textContent='No matching results.';return}let z=+$('zoom').value;$('app').innerHTML=`<section class="meta"><b>${esc(x.id)} · ${esc(x.style)} · ${esc(x.concept)}</b><p>${x.review_required===false?'Context reference':x.accepted?'Accepted':'Original retained'} · native ${x.dimensions.join('×')} · reviewed input ${x.source_bytes} bytes · current Library image ${x.after_bytes} bytes</p><p>${esc(x.reason)}</p><div class="hash">Historical input SHA ${esc(x.source_sha256)}<br>Current Library SHA ${esc(x.output_sha256)}</div><p>${x.regions.map((r,n)=>`<button data-region="${n}">${esc(r.name)}</button>`).join(' ')}</p><div id="crops"></div></section><div class="pair">${pane(x.after,x.accepted?'Current Library · accepted lossless WebP':'Current Library · original retained',x,z)}</div>`;document.querySelectorAll('[data-region]').forEach(b=>b.onclick=()=>{let r=x.regions[+b.dataset.region],[a,c,d,e]=r.roi,w=d-a,h=e-c;$('crops').innerHTML=[[x.after,'Current Library region']].map(([src,title])=>`<div><b>${title}</b><div class="crop ${$('bg').value==='checker'?'checker':''}" style="width:${w*z}px;height:${h*z}px"><img src="${esc(src)}" width="${x.dimensions[0]*z}" height="${x.dimensions[1]*z}" style="transform:translate(${-a*z}px,${-c*z}px)"></div></div>`).join('')})}
$('prev').onclick=()=>{if(list.length)i=(i+list.length-1)%list.length;render()};$('next').onclick=()=>{if(list.length)i=(i+1)%list.length;render()};$('filter').onchange=filter;$('search').oninput=filter;$('bg').onchange=render;$('zoom').onchange=render;filter();
</script></html>'''.replace('__DATA__',payload)
 out=batch/'review.html';out.write_text(page);assert 'selected_outputs' not in page and 'q80' not in page.lower();print(json.dumps({'review_html':str(out),'rows':len(cards),'accepted':sum(c['accepted'] for c in cards)}))
if __name__=='__main__':main()
