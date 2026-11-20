"""Shared reviewer/viewer contracts; population CLI is bounded batches only."""
from contracts import *

def unique(rows,key):
    result={r[key]:r for r in rows}
    require(len(result)==len(rows),'Duplicate '+key)
    return result


def native_id(identity):
    import re
    value=identity.replace(':','_')
    require(re.fullmatch('[A-Za-z0-9_-]+',value),'Unsafe identity')
    return value


def review_delivery(record,review):
    """Established reviewer contract plus original/outer/final and evidence pins."""
    true=record['true_original'];final=record['final']
    fallback=dict(delivery_kind='original',path=true['path'],sha256=true['sha256'])
    if not record['changed_vs_true_original']:
        require(review is None,'Unchanged final needs no fabricated output review')
        return fallback
    require(isinstance(review,dict),'Every changed FINAL candidate needs independent review')
    require(review.get('target_id')==record['target_id'] and
        review.get('source_sha256')==true['sha256'] and review.get('outer_sha256')==record['outer']['sha256'] and
        review.get('output_sha256')==final['sha256'] and review.get('final_record_sha256')==sha(payload(record)),
        'Review original/outer/final bindings differ')
    require(isinstance(review.get('reviewer'),str) and review['reviewer'].strip() and
        review['reviewer']!=record['source_reviewer'],'Independent reviewer identity required')
    require(review['reviewer'] not in record.get('producer_actors',[]),'Output reviewer must be independent of stage producers')
    require(all(review.get(k) is True for k in ('actually_viewed','full_and_allregions_checked',
        'true_original_native_viewed','final_native_viewed','blue_dark_and_alpha_native_viewed')) and
        isinstance(review.get('reason'),str) and review['reason'].strip(),'Actual full/native/region/evidence review required')
    require(review.get('review_assets_sha256')==record['review_assets_sha256'],'Actual reviewed evidence differs')
    require(review.get('safety') in ('clear','uncertain','unsafe') and
        review.get('worthwhile') in ('clear','modest','negligible','uncertain'),'Invalid review judgement')
    # Reuse policy-v2 function exactly; do not reinterpret slight improvements.
    sys.path.insert(0,str(BASE/'production'))
    seal=load('_ws_original_seal',BASE/'production/seal.py')
    policy=read(BASE/'production/acceptance_policy.json')
    if record.get('source_hold') is True:
        return fallback
    if seal.accepts(review,policy):
        return dict(delivery_kind='cleaned',path=final['path'],sha256=final['sha256'])
    return fallback


def delivery_viewer(rows,checks):
    """Reuse frozen People viewer; one canonical manifest remains authoritative."""
    builder=load('_ws_original_delivery_builder',BASE/'build_final_people_delivery.py')
    verified=unique(checks,'target_id');accepted=[]
    for row in rows:
        if row['delivery']['delivery_kind']=='cleaned':
            check=verified[row['target_id']]
            accepted.append(dict(relative_path=row['relative_path'].removeprefix('People/'),
                source_path=row['true_original']['path'],delivery_path=row['delivery']['path'],
                source_sha256=row['true_original']['sha256'],delivery_sha256=row['delivery']['sha256'],
                source_bytes=check['source']['bytes'],delivery_bytes=check['delivery']['bytes'],delivery_kind='cleaned'))
    html=builder.render_index(accepted,dict(scope_total=len(rows)))
    old=f'{len(rows):,} People symbols accounted for; {len(accepted):,} accepted updates. Originals remain in Library.'
    counts=(f'{SCOPE:,} expected Wizard and Soccer player targets. Available cleanup is complete for {len(rows):,} saved targets '
            f'with {len(accepted):,} accepted updates. Generation is incomplete, with {SCOPE-len(rows):,} held targets.')
    require(old in html,'Inherited viewer counts text differs')
    html=html.replace(old,counts)
    html=html.replace('accepted_deliveries.json','final_delivery_manifest.jsonl').replace('Accepted delivery manifest','Available delivery manifest')
    html=html.replace('all_people_dispositions.jsonl','held_generation_dispositions.jsonl').replace('Every symbol’s disposition','Held generation dispositions')
    html=html.replace('summary.json','../proofs/latest_status.json')
    import re
    embedded=json.loads(re.search(r'<script id="records" type="application/json">(.*?)</script>',html,re.S).group(1))
    require(embedded==[dict(r,before=Path(r['source_path']).as_uri(),after=Path(r['delivery_path']).as_uri()) for r in accepted],
        'Viewer exact original/delivery bindings differ')
    return html.encode()


if __name__=='__main__':
    from batches import main
    main()
