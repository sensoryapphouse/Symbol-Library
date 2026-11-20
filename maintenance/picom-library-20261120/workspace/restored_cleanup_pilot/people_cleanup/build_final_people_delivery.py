#!/usr/bin/env python3
"""Build a linked delivery catalog only from a completed, pinned People byte audit."""
from __future__ import annotations

import collections
import datetime
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBRARY = Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
VERIFICATION = ROOT / 'final_people_verification'
OUTPUT = ROOT / 'final_people_delivery'
SCOPE = 57073
ACCEPTED = {'accepted': 'cleaned', 'accepted_prior_cleaned': 'cleaned', 'accepted_prior_repair': 'repair'}
ORIGINAL = {'original_retained', 'completed_original', 'below_eligibility_unprocessed'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned_bytes(path, expected):
    raw = Path(path).read_bytes()
    if sha(raw) != expected:
        raise ValueError(f'Changed proof or metadata: {path}')
    return raw


def validate_records(records, proof, library=LIBRARY):
    """Check the exact invocation and original/delivery identity in every byte receipt."""
    paths, ids, catalog = set(), set(), []
    for record in records:
        relative = record['relative_path']
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or relative in paths or record['source_id'] in ids:
            raise ValueError('Invalid or duplicate source identity')
        paths.add(relative)
        ids.add(record['source_id'])
        if record['invocation'] != proof['invocation'] or record.get('passed') is not True:
            raise ValueError('Unverified record or different audit invocation')
        source, delivery = record['source'], record['delivery']
        for receipt in (source, delivery):
            expected = receipt['expected_sha256']
            if (receipt.get('matches') is not True or receipt.get('stable_during_read') is not True
                    or receipt['actual_sha256'] != expected or len(expected) != 64
                    or any(c not in '0123456789abcdef' for c in expected)
                    or not isinstance(receipt['bytes'], int) or receipt['bytes'] <= 0):
                raise ValueError('Failed or incomplete byte receipt')
        if Path(source['path']).resolve() != (library / rel).resolve():
            raise ValueError('Original source lies outside its exact Library path')
        status = record['status']
        same_path = Path(source['path']).resolve() == Path(delivery['path']).resolve()
        if status in ORIGINAL:
            if not same_path or source['actual_sha256'] != delivery['actual_sha256'] or source['bytes'] != delivery['bytes']:
                raise ValueError('Retained original differs from source bytes')
            kind = 'original'
        elif status in ACCEPTED:
            if same_path:
                raise ValueError('Accepted output overwrites its original')
            kind = ACCEPTED[status]
        else:
            raise ValueError(f'Unfinished or unknown status: {status}')
        catalog.append({
            'relative_path': relative, 'source_id': record['source_id'], 'status': status,
            'delivery_kind': kind, 'source_path': source['path'], 'source_sha256': source['actual_sha256'],
            'source_bytes': source['bytes'], 'delivery_path': delivery['path'],
            'delivery_sha256': delivery['actual_sha256'], 'delivery_bytes': delivery['bytes'],
        })
    if len(catalog) != proof['scope_total']:
        raise ValueError('Incomplete People scope in byte receipts')
    if dict(collections.Counter(r['status'] for r in catalog)) != proof['status_counts']:
        raise ValueError('Status counts differ from completed audit')
    return sorted(catalog, key=lambda r: r['relative_path'])


def load_verified_catalog():
    pointer_raw = (VERIFICATION / 'latest_status.json').read_bytes()
    pointer = json.loads(pointer_raw)
    if pointer.get('status') != 'complete' or pointer.get('completion_claim') is not True:
        raise ValueError('Full People verification has not completed')
    proof_path = Path(pointer['proof_path'])
    proof_raw = pinned_bytes(proof_path, pointer['proof_sha256'])
    proof = json.loads(proof_raw)
    if (proof.get('status') != 'complete' or proof.get('completion_claim') is not True
            or proof.get('scope_total') != SCOPE or proof.get('originals_byte_checked_this_invocation') != SCOPE
            or proof.get('failed_file_records') != 0 or proof.get('changed_lineage') != []
            or proof.get('library_written') is not False or proof.get('images_decoded_or_changed') is not False
            or proof.get('invocation') != pointer['invocation'] or proof.get('pass_id') != pointer['pass_id']
            or Path(proof['immutable_proof_path']).resolve() != proof_path.resolve()):
        raise ValueError('Incomplete or inconsistent final proof')
    plan_path = proof_path.parent.parent / 'plan.json'
    plan = json.loads(pinned_bytes(plan_path, proof['plan_sha256']))
    if (plan.get('status') != 'ready_for_full_hash_verification' or plan.get('required_reviews_remaining') != 0
            or plan.get('binding_issue_count') != 0 or plan.get('scope_total') != SCOPE
            or plan.get('scope_unique_paths') != SCOPE or plan.get('scope_missing_paths') != 0 or plan.get('scope_extra_paths') != 0
            or plan.get('metadata_sha256') != proof['metadata_sha256']
            or plan.get('signature_sha256') != proof['signature_sha256']):
        raise ValueError('Completed proof does not match its approved plan')
    pinned_bytes(ROOT / 'verify_all_people_completion.py', plan['verifier_sha256'])
    for path, expected in proof['metadata_sha256'].items():
        pinned_bytes(path, expected)
    checkpoint_raw = pinned_bytes(proof['checkpoint_path'], proof['checkpoint_sha256'])
    catalog = validate_records([json.loads(line) for line in checkpoint_raw.splitlines() if line], proof)
    if (VERIFICATION / 'latest_status.json').read_bytes() != pointer_raw:
        raise ValueError('Verification pointer changed while building delivery')
    return catalog, proof, pointer['proof_sha256']


def render_index(rows, summary):
    data = [{**r, 'before': Path(r['source_path']).as_uri(), 'after': Path(r['delivery_path']).as_uri()} for r in rows]
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    counts = html.escape(f"{summary['scope_total']:,} People symbols accounted for; {len(rows):,} accepted updates. Originals remain in Library.")
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>People symbols — accepted updates</title><style>
body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:1150px;color:#20242b;background:#fafafa}
input,select,button{font:inherit;padding:8px;margin:4px}input{width:min(440px,85vw)}h1{font-size:1.5rem}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.pair[hidden]{display:none}.card{min-width:0}img{display:block;width:100%;aspect-ratio:1;object-fit:contain;background-color:#ddd;background-image:conic-gradient(#fff 25%,transparent 0 50%,#fff 0 75%,transparent 0);background-size:20px 20px;border:1px solid #aaa}
.muted{color:#555}#path{overflow-wrap:anywhere}button:disabled{opacity:.4}@media(max-width:650px){.pair{grid-template-columns:1fr}}
</style><h1>People symbols — accepted updates</h1><p>''' + counts + '''</p>
<p><a href="accepted_deliveries.json">Accepted delivery manifest</a> · <a href="all_people_dispositions.jsonl">Every symbol’s disposition</a> · <a href="summary.json">Verification and counts</a></p>
<label>Find a symbol <input id="search" type="search" placeholder="Style, category or symbol name"></label>
<label>Style <select id="style"><option value="">All styles</option></select></label>
<label>Update <select id="kind"><option value="">All updates</option><option value="cleaned">Background cleanup</option><option value="repair">Prior repair</option></select></label>
<p><button id="prev">Previous</button> <span id="position"></span> <button id="next">Next</button></p>
<h2 id="path"></h2><div class="pair" id="pair"><section class="card"><h3>Original</h3><img id="before" alt="Original symbol"><p id="before-size"></p><a id="before-link">Open original WebP</a></section>
<section class="card"><h3>Accepted</h3><img id="after" alt="Accepted symbol"><p id="after-size"></p><a id="after-link">Open accepted WebP</a></section></div>
<p class="muted">The checkerboard shows transparency. Use the arrow keys or buttons to move between symbols.</p>
<script id="records" type="application/json">''' + encoded + '''</script><script>
const rows=JSON.parse(document.getElementById('records').textContent),$=id=>document.getElementById(id);
let selected=rows,index=0;
for(const name of [...new Set(rows.map(r=>r.relative_path.split('/')[0]))].sort()){const o=document.createElement('option');o.value=name;o.textContent=name;$('style').append(o);}
function size(bytes){return bytes.toLocaleString()+' bytes ('+(bytes/1024).toFixed(1)+' KiB)';}
function render(){const r=selected[index];$('position').textContent=selected.length?(index+1)+' of '+selected.length:'No matching symbols';$('prev').disabled=index===0;$('next').disabled=index>=selected.length-1;$('pair').hidden=!r;$('path').textContent=r?r.relative_path:'';if(!r)return;for(const side of ['before','after']){$(side).src=r[side];$(side+'-link').href=r[side];} $('before-size').textContent=size(r.source_bytes);$('after-size').textContent=size(r.delivery_bytes);try{history.replaceState(null,'','#'+encodeURIComponent(r.relative_path));}catch(e){if(e.name!=='SecurityError')throw e;location.hash=encodeURIComponent(r.relative_path);}}
function filter(){const q=$('search').value.toLowerCase(),s=$('style').value,k=$('kind').value;selected=rows.filter(r=>r.relative_path.toLowerCase().includes(q)&&(!s||r.relative_path.split('/')[0]===s)&&(!k||r.delivery_kind===k));index=0;render();}
for(const id of ['search','style','kind'])$(id).addEventListener('input',filter);
$('prev').onclick=()=>{if(index>0){index--;render();}};$('next').onclick=()=>{if(index+1<selected.length){index++;render();}};
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='ArrowLeft')$('prev').click();if(e.key==='ArrowRight')$('next').click();});
let initial='';try{initial=decodeURIComponent(location.hash.slice(1));}catch(e){}const found=rows.findIndex(r=>r.relative_path===initial);if(found>=0)index=found;render();
</script></html>'''


def atomic_bytes(path, raw):
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    with temp.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def main():
    catalog, proof, proof_sha = load_verified_catalog()
    accepted = [r for r in catalog if r['delivery_kind'] != 'original']
    summary = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope_total': SCOPE, 'accepted_updates': len(accepted), 'originals_retained': SCOPE-len(accepted),
               'status_counts': proof['status_counts'], 'delivery_kind_counts': dict(collections.Counter(r['delivery_kind'] for r in catalog)),
               'verification_completed_utc': proof['completed_utc'], 'verification_proof_path': proof['immutable_proof_path'],
               'verification_proof_sha256': proof_sha, 'source_checkpoint_sha256': proof['checkpoint_sha256'],
               'library_written': False, 'images_copied_or_changed': False,
               'builder_sha256': sha(Path(__file__).read_bytes())}
    payloads = {
        'accepted_deliveries.json': (json.dumps(accepted, ensure_ascii=False, indent=2)+'\n').encode(),
        'all_people_dispositions.jsonl': ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in catalog).encode(),
        'index.html': render_index(accepted, summary).encode(),
    }
    summary['artifacts_sha256'] = {name: sha(raw) for name, raw in payloads.items()}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, raw in payloads.items():
        atomic_bytes(OUTPUT/name, raw)
    atomic_bytes(OUTPUT/'summary.json', (json.dumps(summary, ensure_ascii=False, indent=2)+'\n').encode())
    print(json.dumps({'accepted_updates': len(accepted), 'scope_total': SCOPE, 'index': str(OUTPUT/'index.html')}))


if __name__ == '__main__':
    main()
