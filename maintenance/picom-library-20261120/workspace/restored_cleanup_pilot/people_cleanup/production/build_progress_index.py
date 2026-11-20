#!/usr/bin/env python3
"""Build a small local entry point to verified production batch reviews."""
import html
import os
from urllib.parse import quote
from common import HERE, digest, read, utc


def main():
    progress = read(HERE / 'progress.json')
    initial = read(HERE / 'summary.json')
    rows = []
    for item in progress['sealed_batches']:
        folder = HERE / 'batches' / item['batch_id']
        verification = read(folder / 'viewer_verification.json')
        assert verification['all_bindings_and_files_valid'] and not verification['errors']
        assert verification['delivery_sha256'] == digest(folder / 'accepted_delivery.json')
        assert verification['html_sha256'] == digest(folder / 'review.html')
        url = quote(str((folder / 'review.html').relative_to(HERE)), safe='/')
        rows.append(f'<tr><td><a href="{url}">{html.escape(item["batch_id"])}</a></td>'
                    f'<td>{item["reviewed_sources"]:,}</td><td>{item["accepted"]:,}</td>'
                    f'<td>{item["reviewed_sources"] - item["accepted"]:,}</td></tr>')
    complete = progress['new_production_sources_complete']
    total = initial['queue_subject_total']
    accepted = progress['new_production_accepted']
    counts = progress['status_counts']
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>People &amp; Relationships topic queue — cleanup progress</title>
<style>
body{{font:17px/1.5 system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#1e293b;background:#f8fafc}}
h1{{font-size:30px}}a{{color:#164eaf}}.stats{{display:flex;flex-wrap:wrap;gap:16px}}
.stat{{background:white;border:1px solid #cbd5e1;border-radius:10px;padding:18px;min-width:150px}}
.stat strong{{font-size:30px;display:block}}progress{{width:100%;height:22px;margin:18px 0}}
table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:10px 16px;border-bottom:1px solid #cbd5e1;text-align:right}}th:first-child,td:first-child{{text-align:left}}
.muted{{color:#475569;font-size:14px}}code{{font-size:14px}}
</style><body><h1>People &amp; Relationships topic queue</h1>
<p class="muted">Snapshot: {html.escape(utc())}. Refresh this page after a batch completes.</p>
<p><strong>Scope correction:</strong> This page tracks the existing topic-folder queue, not the whole original People collection. Its 10,891-file inventory contains 9,628 original People files and 1,263 files from Non-people collections. The complete original People collection contains <strong>57,073 files across topics</strong>; the other <strong>47,445 People files</strong> are being screened separately and are not included in the progress figures below.</p>
<p><a href="scope_extension/snapshot.json">Verified full People inventory scope</a> · <a href="scope_extension/progress.json">Full People screening checkpoint</a>. The earlier whole-People completion estimate based on this topic queue was incorrect.</p>
<div class="stats"><div class="stat"><strong>{complete:,} / {total:,}</strong>Queued symbols completed</div>
<div class="stat"><strong>{accepted:,}</strong>Improvements accepted</div>
<div class="stat"><strong>{total-complete:,}</strong>Queued symbols remaining</div></div>
<progress value="{complete}" max="{total}" aria-label="Queued symbols completed"></progress>
<p>Each eligible source is inspected with matching concepts where available. Every changed output receives an independent full-image and region check. Safe modest improvements are included. Originals remain available; uncertain or unsafe changes are withheld.</p>
<h2>Completed batch reviews</h2><p>Open a batch for one-symbol-at-a-time before-and-after WebPs. Each review also provides unchanged sources and context references.</p>
<table><thead><tr><th>Review</th><th>Sources completed</th><th>Improvements kept</th><th>Originals retained</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Other work within this topic inventory</h2>
<p>{counts.get('accepted_prior_cleaned',0):,} earlier cleanup results and {counts.get('accepted_prior_repair',0):,} earlier foreground repairs are retained. {counts.get('needs_historical_output_review',0):,} earlier outputs await completion of their exact-file review.</p>
<p>{counts.get('below_eligibility_unprocessed',0):,} remaining sources fall below the white-blob screening threshold and are being kept unchanged; their final source-integrity check is pending. These are outside the queued total above.</p>
<p><a href="source_integrity/wood_repairs/review.html">Seven corrected Wood comparative symbols — separate before-and-after review</a></p>
<p class="muted">The WebPs retain native dimensions. No Q80 conversion is being performed in this cleanup.</p>
</body></html>'''
    target = HERE / 'index.html'
    temporary = target.with_name(target.name + f'.tmp-{os.getpid()}')
    with temporary.open('w', encoding='utf-8') as out:
        out.write(page)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, target)
    print({'index': str(target), 'completed': complete, 'accepted': accepted,
           'verified_batch_links': len(rows)})


if __name__ == '__main__':
    main()
