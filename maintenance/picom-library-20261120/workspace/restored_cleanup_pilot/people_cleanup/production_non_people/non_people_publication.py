"""Bind Non-People publication to frozen batch or governing prior review lineage."""
import contextlib
import fcntl
import json
import os
import re
import stat
import unicodedata
from pathlib import Path

from common import HERE, LIBRARY, digest, read, require
from publication_transaction import Publication, checked_bytes, document, exists, fingerprint, sync_directory

ARTIFACTS = {'after.webp', 'removed_core_mask.png', 'roi_mask.png', 'protected_mask.png'}
PRIOR_COUNT = 266


@contextlib.contextmanager
def operator_lock():
    with (HERE / 'publication.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def path_key(path):
    return unicodedata.normalize('NFD', str(path)).casefold()


def scratch_roots(batch):
    return (batch / 'previews', batch / 'selected_outputs', batch / 'accepted_outputs',
            batch / 'independent_output_review' / 'evidence')


def producer_image(batch, path):
    parts = path.relative_to(batch).parts
    if len(parts) == 3 and parts[:2] == ('previews', 'sources'):
        return bool(re.fullmatch(r'(?:np\d{5}|r_[0-9a-f]{20})_(?:source_purple|strict_cc_overlay)(?:\.tmp-\d+)?\.png', parts[2]))
    if len(parts) == 3 and parts[:2] == ('previews', 'contact_sheets'):
        return bool(re.fullmatch(r'npg\d{5}_native512_\d{2}(?:\.tmp-\d+)?\.png', parts[2]))
    if len(parts) == 3 and parts[0] in ('selected_outputs', 'accepted_outputs'):
        if not re.fullmatch(r'(?:np\d{5}|\.np\d{5}\.stage-[a-z0-9_]{8})', parts[1]):
            return False
        canonical = re.sub(r'(?<=\.png)\.tmp-\d+$', '', parts[2])
        return canonical in ARTIFACTS
    return len(parts) == 3 and parts[:2] == ('independent_output_review', 'evidence') and bool(
        re.fullmatch(r'np\d{5}_(?:full|normal|region_\d{2,})\.png', parts[2]))


def media_files(batch):
    """Identify scratch only in producer-owned paths. Keep all review/result metadata."""
    result = set()
    for root in scratch_roots(batch):
        if not exists(root):
            continue
        require(stat.S_ISDIR(root.lstat().st_mode) and root.resolve() == root, f'Unsafe scratch root: {root}')
        def fail(error):
            raise error
        for folder, dirs, names in os.walk(root, onerror=fail):
            for name in dirs:
                path = Path(folder) / name
                require(stat.S_ISDIR(path.lstat().st_mode), f'Unsafe scratch directory: {path}')
            for name in names:
                path = Path(folder) / name
                if producer_image(batch,path):
                    require(stat.S_ISREG(path.lstat().st_mode), f'Unsafe scratch file: {path}')
                    result.add(str(path))
    return result


def destination(relative):
    rel = Path(relative)
    require(not rel.is_absolute() and str(rel) == relative and '..' not in rel.parts
            and len(rel.parts) >= 2 and rel.parts[0] not in ('People', '_manifest')
            and rel.suffix == '.webp', f'Invalid Non-People Library path: {relative}')
    return LIBRARY / rel


def publication(folder, kind, rows, pins, expected_retire=None, scratch=None):
    """Rebuild the exact transaction. First invocation captures sizes and scratch identities."""
    intent_path = folder / 'intent.json'
    saved = document(intent_path) if exists(intent_path) else None
    saved_rows = saved['deliveries'] if saved is not None else [None] * len(rows)
    require(len(saved_rows) == len(rows), 'Publication intent delivery set differs')
    deliveries = []
    workspace_paths, library_paths = set(), set()
    for row, recorded in zip(rows, saved_rows):
        library = destination(row['relative_path'])
        workspace = Path(row['delivery_path'])
        require(str(library) == row['source'] and workspace.is_absolute()
                and workspace.is_relative_to(HERE.parent) and workspace.name == 'after.webp'
                and workspace.parent.parent.name == 'accepted_outputs', 'Delivery outside exact accepted workspace or Library')
        require(path_key(library) not in library_paths and path_key(workspace) not in workspace_paths,
                'Duplicate publication file identity')
        require(row['source_sha256'] != row['delivery_sha256'], 'Accepted output must differ from the source')
        workspace_paths.add(path_key(workspace))
        library_paths.add(path_key(library))
        output_bytes = row.get('output_bytes')
        if output_bytes is None:
            output_bytes = (recorded['output']['bytes'] if recorded is not None
                            else fingerprint(workspace, row['delivery_sha256'])['bytes'])
        require(type(output_bytes) is int and output_bytes > 0
                and type(row['source_bytes']) is int and row['source_bytes'] > 0, 'Invalid publication size')
        deliveries.append({'source_id': row['source_id'], 'relative_path': row['relative_path'],
                           'library': str(library), 'workspace': str(workspace),
                           'before': {'sha256': row['source_sha256'], 'bytes': row['source_bytes']},
                           'output': {'sha256': row['delivery_sha256'], 'bytes': output_bytes}})
    expected_retire = expected_retire or {}
    scratch = scratch or set()
    if saved is None:
        retire = {name: fingerprint(Path(name), expected_retire.get(name), allow_empty=name not in expected_retire) for name in sorted(scratch)
                  if path_key(name) not in workspace_paths}
    else:
        retire = saved['retire']
        require(all(path_key(name) in workspace_paths or name in retire for name in scratch),
                'New scratch image appeared after the intent was pinned')
    require(set(expected_retire) <= set(retire), 'Required temporary artifact is missing from retirement plan')
    for name, file in retire.items():
        path = Path(name)
        require(kind == 'batch' and path.is_absolute() and str(path) == name and '..' not in path.parts
                and any(path.is_relative_to(root) for root in scratch_roots(folder.parent))
                and producer_image(folder.parent,path) and path_key(name) not in workspace_paths,
                f'Invalid retirement path: {name}')
        require(type(file['bytes']) is int and file['bytes'] >= (1 if name in expected_retire else 0) and
                file['sha256'] == expected_retire.get(name, file['sha256']), f'Invalid retirement binding: {name}')
    intent = {'schema': 'non-people-publication-intent-v1', 'kind': kind,
              'metadata_sha256': pins, 'deliveries': deliveries, 'retire': retire}
    require(saved is None or saved == intent, 'Publication intent differs from reviewed lineage')
    return Publication(folder, intent)


def reviewed_comparisons(batch, versions, checks, reviews, results, manifest):
    from contracts import unique
    evidence = unique(manifest['images'], 'id')
    require(set(evidence)==set(reviews)==set(results), 'Comparison evidence changed set differs')
    files = {}
    evidence_root = batch/'independent_output_review'/'evidence'
    for ident, item in evidence.items():
        version, check, result = versions[ident], checks[ident], results[ident]
        require(item['source_sha256']==version['source_sha256']
                and item['dimensions']==version['dimensions']
                and item['output_sha256']==check['output_sha256']
                and item['result_sha256']==check['result_sha256']
                and item['result_regions']==result['regions'], 'Comparison evidence identity differs')
        full = str(evidence_root/f'{ident}_full.png')
        normal = full if max(version['dimensions'])<=512 else str(evidence_root/f'{ident}_normal.png')
        require(item['paths']=={'full':full,'normal':normal}
                and set(item['evidence_sha256'])=={'full','normal'}, 'Whole comparison paths differ')
        whole = {item['paths'][key]:sha for key,sha in item['evidence_sha256'].items()}
        require(len(set(item['evidence_sha256'].values()))==1 or full!=normal, 'Duplicate whole path has inconsistent hashes')
        regions = item['regions']
        require(len(regions)==len(result['regions']), 'Changed-region comparison count differs')
        paths = dict(whole)
        for n, (region, changed) in enumerate(zip(regions, result['regions']), 1):
            path = str(evidence_root/f'{ident}_region_{n:02}.png')
            require(region['path']==path and region['name']==changed['name']
                    and region['roi']==changed['roi'], 'Changed-region comparison identity differs')
            paths[path] = region['sha256']
        viewed = reviews[ident].get('evidence_paths')
        require(isinstance(viewed,list) and all(isinstance(path,str) for path in viewed)
                and len(viewed)==len(paths) and set(viewed)==set(paths),
                f'{ident}: independent review lacks exact viewed whole and changed-region evidence paths')
        files.update(paths)
    return files


def batch_publication(batch, load_only=False):
    if load_only:
        require(exists(batch / 'publication' / 'intent.json'), 'Batch publication is pending')
    def metadata(path):
        raw, sha, _ = checked_bytes(path)
        pins[str(path)] = sha
        return json.loads(raw)
    pins = {}
    manifest = metadata(batch / 'manifest.json')
    delivery = metadata(batch / 'accepted_delivery.json')
    audit = metadata(batch / 'mechanical_audit.json')
    decisions = metadata(batch / 'approved_decisions.json')
    run = metadata(batch / 'selected_run_state.json')
    review = metadata(batch / 'independent_output_review.json')
    for field, name in (('manifest_sha256', 'manifest.json'), ('mechanical_audit_sha256', 'mechanical_audit.json'),
                        ('output_review_sha256', 'independent_output_review.json'), ('decisions_sha256', 'approved_decisions.json')):
        require(delivery[field] == pins[str(batch / name)], f'Seal {field} differs')
    require(not audit['errors'] and run['status'] == 'complete', 'Run or audit incomplete')
    for group in manifest['groups']:
        path = batch / 'source_reviews' / (group['group_id'] + '.json')
        if exists(path):
            metadata(path)
            require(decisions['source_checkpoint_sha256'][path.name] == pins[str(path)],
                    f'Source checkpoint differs: {path}')
    from contracts import unique
    versions = unique([r for group in manifest['groups'] for r in group['versions']], 'batch_id')
    items = unique(delivery['images'], 'id')
    checks = unique(audit['images'], 'id')
    runs = unique(run['images'], 'id')
    require(set(versions) == set(items) == set(checks) == set(runs), 'Sealed batch sets differ')
    changed = {ident for ident, row in runs.items() if row['status'] == 'changed'}
    rows = []
    retire = {}
    results = {}

    def dispose(path, sha):
        name = str(path)
        require(name not in retire or retire[name] == sha, f'Conflicting evidence hash: {path}')
        retire[name] = sha

    for ident, row in versions.items():
        item = items[ident]
        require(Path(ident).name == ident and ident not in ('.', '..') and item['source_path'] == row['source']
                and item['source_sha256'] == row['source_sha256'], 'Sealed source identity differs')
        accepted = item['delivery'] == 'cleaned'
        if not accepted:
            require(item['delivery'] == 'original' and item['path'] == row['source']
                    and item['sha256'] == row['source_sha256'], 'Retained source identity differs')
        if accepted:
            require(ident in changed and row['review_required'] is True, 'Only changed reviewed subjects may publish')
        if ident in changed:
            directory = batch / ('accepted_outputs' if accepted else 'selected_outputs') / ident
            result_path = directory / 'result.json'
            result = results[ident] = metadata(result_path)
            check = checks[ident]
            require(check['passed'] is True and check['result_sha256'] == pins[str(result_path)]
                    and set(check['artifact_sha256']) == ARTIFACTS, 'Changed artifact audit differs')
            for name, sha in check['artifact_sha256'].items():
                if name != 'after.webp' or not accepted:
                    dispose(directory / name, sha)
            if accepted:
                source = row['source']
                workspace = directory / 'after.webp'
                require(item['path'] == str(workspace) and item['sha256'] == result['output_sha256']
                        == check['artifact_sha256']['after.webp'], 'Accepted output audit differs')
                rows.append({'relative_path': str(Path(source).relative_to(LIBRARY)),
                             'source_id': row['production_source_id'], 'source': source,
                             'source_sha256': row['source_sha256'], 'source_bytes': row['source_bytes'],
                             'delivery_path': item['path'], 'delivery_sha256': item['sha256'],
                             'output_bytes': result['output_bytes']})
        preview = metadata(batch / 'previews' / 'checkpoints' / (ident + '.json'))
        require(preview['source_sha256'] == row['source_sha256'], 'Preview source binding differs')
        for name, sha_field in (('source_png', 'source_png_sha256'), ('strict_cc_overlay', 'overlay_png_sha256')):
            dispose(batch / preview[name], preview[sha_field])
    for contact in manifest['preview_preparation']['contact_sheets_512']:
        dispose(batch / contact['path'], contact['sha256'])
    if changed:
        evidence_path = batch/'independent_output_review'/'review_manifest.json'
        evidence = metadata(evidence_path)
        require(delivery['comparison_manifest_sha256']==pins[str(evidence_path)], 'Sealed comparison evidence changed')
        reviewed = unique(review['images'],'id')
        for name, sha in reviewed_comparisons(batch, versions, checks, reviewed, results, evidence).items():
            dispose(Path(name),sha)
    return publication(batch / 'publication', 'batch', sorted(rows, key=lambda r: r['relative_path']),
                       pins, retire, media_files(batch))


def require_committed(batch):
    manifest = read(batch / 'manifest.json')
    seal_path = batch / 'accepted_delivery.json'
    seal = read(seal_path)
    seal_sha = digest(seal_path)
    progress = read(HERE / 'progress.json')
    require(any(row['batch_id'] == batch.name and row['manifest_sha256'] == seal_sha
                for row in progress['sealed_batches']), 'Sealed batch has no matching progress commit')
    identities = {v['batch_id']: v['production_source_id'] for group in manifest['groups']
                  for v in group['versions'] if v['review_required']}
    expected = {identities[item['id']]: item for item in seal['images'] if item['id'] in identities}
    require(len(expected) == len(identities), 'Sealed subject set differs from manifest')
    latest = {}
    with (HERE / 'ledger.jsonl').open() as ledger:
        for line in ledger:
            require(line.endswith('\n'), 'Incomplete ledger tail')
            event = json.loads(line)
            key = event.get('production_source_id')
            if key in expected and event.get('status_to'):
                latest[key] = event
    require(set(latest) == set(expected), 'Sealed subjects are missing ledger events')
    for key, item in expected.items():
        event = latest[key]
        require(event['event']=='sealed_batch_delivery' and event['proof_sha256']==seal_sha
                and event['batch_id']==batch.name and event['delivery']==item
                and event['source_reviewed'] is True
                and event['status_to']==('accepted' if item['delivery']=='cleaned' else 'original_retained')
                and (item['delivery']!='cleaned' or event['output_reviewed'] is True),
                'Ledger does not commit exact independently reviewed seal')
    sync_directory(HERE)


def prior_publication(rows, pins, load_only=False):
    if load_only:
        require(exists(HERE / 'prior_publication' / 'intent.json'), 'Governing prior publication is pending')
    from source_versions import EXTRA
    selected = []
    for row in rows:
        if row['delivery_kind'] == 'original':
            continue
        require(row['relative_path'] not in EXTRA, 'Superseded mum output cannot publish')
        path = Path(row['delivery_path'])
        require(path.is_relative_to(HERE.parent / 'production' / 'batches')
                or any(path.is_relative_to(HERE.parent / b) for b in ('batch002', 'batch003')),
                f'Prior delivery is outside governing legacy workspaces: {path}')
        selected.append(row)
    require(len(selected) == PRIOR_COUNT, 'Governing prior accepted output count differs')
    return publication(HERE / 'prior_publication', 'prior', sorted(selected, key=lambda r: r['relative_path']), pins)


def overlay_rows(rows, tx, pins):
    """Preserve historical lineage and bind final rows to exact current Library deliveries."""
    from verification import merge_pins
    receipts = tx.completed_pins()
    merge_pins(pins, tx.intent['metadata_sha256'])
    merge_pins(pins, receipts)
    by_relative = {row['relative_path']: row for row in tx.intent['deliveries']}
    changed = set()
    for row in rows:
        if row['delivery_kind'] == 'original':
            continue
        rel = row['relative_path']
        item = by_relative.get(rel)
        require(item is not None and item['source_id'] == row['source_id']
                and item['library'] == row['source'] and item['workspace'] == row['delivery_path']
                and item['before']['sha256'] == row['source_sha256']
                and item['output']['sha256'] == row['delivery_sha256'], 'Publication and historical delivery lineage differ')
        require(not exists(Path(item['workspace'])), 'Consumed accepted work file reappeared')
        row.update(delivery_path=item['library'], expected_source_bytes=item['before']['bytes'],
                   expected_delivery_bytes=item['output']['bytes'],
                   publication_intent_path=str(tx.intent_path),
                   publication_intent_sha256=receipts[str(tx.intent_path)],
                   publication_complete_path=str(tx.complete_path),
                   publication_complete_sha256=receipts[str(tx.complete_path)])
        changed.add(rel)
    require(set(by_relative) == changed, 'Publication receipt adds or omits a governing accepted result')
    require(not any(exists(Path(name)) for name in tx.intent['retire']), 'Retired image reappeared')


def require_admitted_receipt(folder, kind, count=None):
    """Check closeout metadata and scratch absence without reopening Library images."""
    message = f'Complete publication and retirement for {folder.parent.name if kind=="batch" else "governing prior outputs"} first'
    intent_path = folder / 'intent.json'
    require(exists(intent_path), message)
    intent = document(intent_path)
    require(intent['kind']==kind and (count is None or len(intent['deliveries'])==count), message)
    Publication(folder, intent).completed_pins()
    require(not any(exists(Path(row['workspace'])) for row in intent['deliveries']), 'Consumed workspace image reappeared')
    require(not any(exists(Path(name)) for name in intent['retire']), 'Retired image reappeared')
    if kind == 'batch':
        seal = folder.parent / 'accepted_delivery.json'
        require(digest(seal)==intent['metadata_sha256'].get(str(seal)), 'Published seal metadata changed')
        require(not media_files(folder.parent), 'New producer scratch appeared after publication')


def require_open_batch(batch, allow_existing=True, closing=False):
    """Admission check held under the operator lock by producers and closeout."""
    require_admitted_receipt(HERE / 'prior_publication', 'prior', PRIOR_COUNT)
    already_sealed = exists(batch / 'accepted_delivery.json')
    if closing and already_sealed:
        return
    for folder in (HERE / 'batches').glob('batchN*'):
        if exists(folder / 'accepted_delivery.json'):
            require_admitted_receipt(folder / 'publication', 'batch')
    if not allow_existing:
        require(not already_sealed, f'{batch.name} is sealed and cannot generate more image evidence')
