#!/usr/bin/env python3
"""Build the production metadata inventory and deterministic subject queue.

This script reads cached census/review JSON and file metadata only. It does not
decode or render source images. The original Library is read-only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parents[1]
PEOPLE = HERE.parent
WORKSPACE = HERE.parents[3]
LIBRARY = Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
CENSUS = PEOPLE / 'blob_screen' / 'census_checkpoint.jsonl'
OUT = HERE
sys.path.insert(0, str(HERE))
from common import atomic_json, digest, utc


def jread(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_key(path: str, sha: str) -> str:
    rel = Path(path).resolve().relative_to(LIBRARY.resolve()).as_posix()
    return hashlib.sha256((rel + '\0' + sha).encode('utf-8')).hexdigest()


def norm_stem(name: str) -> str:
    stem = Path(name).stem.casefold()
    return re.sub(r'[\s_-]+', '', stem)


def row_key(path: str, sha: str):
    return (str(Path(path).resolve()), sha)


def add_prior(prior, path, sha, entry):
    if not path or not sha:
        return
    prior[row_key(path, sha)].append(entry)


def find_result_map(path: Path):
    doc = jread(path)
    return {x['id']: x for x in doc.get('results', doc.get('images', []))}


def validate_final_delivery(d, source_path, source_sha):
    """Check delivery references against source/accepted bytes without decoding."""
    dest = Path(d.get('path', '')).expanduser()
    if d.get('source_sha256') != source_sha:
        return False, 'source_hash_disagrees_with_delivery_record'
    if d.get('delivery') == 'original':
        if d.get('sha256') != source_sha or str(dest.resolve()) != str(Path(source_path).resolve()):
            return False, 'original_delivery_not_source_byte_identity'
        return True, 'source_byte_identity'
    if d.get('delivery') == 'cleaned':
        if not dest.is_file():
            return False, 'accepted_file_missing'
        if digest(dest) != d.get('sha256'):
            return False, 'accepted_output_hash_mismatch'
        return True, 'accepted_copy_sha256_verified'
    return False, 'unknown_delivery_class'


def group_order(groups):
    """Deterministically spread groups across underrepresented figure styles."""
    pending = list(groups)
    total = Counter()
    assigned = Counter()
    for g in pending:
        for sid in g['style_ids']:
            total[sid] += g['candidate_count_by_style'][sid]
    ordered = []
    while pending:
        def score(g):
            ratios = [assigned[sid] / max(1, total[sid]) for sid in g['style_ids']]
            return (min(ratios), sum(ratios) / max(1, len(ratios)), g['group_key'])
        g = min(pending, key=score)
        pending.remove(g)
        ordered.append(g)
        for sid, count in g['candidate_count_by_style'].items():
            assigned[sid] += count
    return ordered


def main():
    frozen_paths=(OUT/'inventory.json',OUT/'queue.json',OUT/'batch_index.json')
    if any(p.exists() for p in frozen_paths):
        raise RuntimeError('production inventory/queue is already frozen; use prepare_batch.py for later batches. Refusing to rebuild IDs or overwrite source-review progress.')
    generated = utc()
    rows = []
    by_key = {}
    for line_num, line in enumerate(CENSUS.open(encoding='utf-8'), 1):
        if not line.strip():
            continue
        c = json.loads(line)
        src = str(Path(c['source']).resolve())
        rel = Path(src).relative_to(LIBRARY.resolve())
        if len(rel.parts) < 3 or rel.parts[1] != 'People & Relationships':
            continue
        if c.get('status') != 'ok':
            rows.append({'source': src, 'relative_path': rel.as_posix(), 'source_sha256': c.get('source_sha256'), 'status': 'census_exception', 'census_line': line_num, 'exception': c.get('error')})
            continue
        w, h = c['dimensions']
        area_scale = (w * h) / (512 * 512)
        strict_raw = int(c.get('strict_white_core_pixel_count', 0))
        strict_at_512 = strict_raw / area_scale if area_scale else 0.0
        ref = c.get('refs') or [{}]
        style_id = int(c.get('style_id') or ref[0].get('style_id') or 0)
        style = c.get('style') or ref[0].get('style') or rel.parts[0]
        parent = '/'.join(rel.parts[2:-1])
        stem = norm_stem(rel.name)
        sid = source_key(src, c['source_sha256'])
        try:
            st = Path(src).stat()
            current_size = st.st_size
            size_match = current_size == int(c['source_bytes'])
        except OSError:
            current_size, size_match = None, False
        item = {
            'production_source_id': sid,
            'source': src,
            'relative_path': rel.as_posix(),
            'source_sha256': c['source_sha256'],
            'source_bytes': int(c['source_bytes']),
            'current_source_bytes': current_size,
            'source_size_matches_census': size_match,
            'dimensions': [int(w), int(h)],
            'style_id': style_id,
            'style': style,
            'people_subfolder': parent,
            'normalized_stem': stem,
            'group_key': parent + '::' + stem,
            'strict_white_core_pixel_count_native': strict_raw,
            'strict_white_core_pixel_count_at_512': round(strict_at_512, 4),
            'simple_eligible': strict_at_512 >= 256,
            'strict_component_count': int(c.get('strict_white_core_component_count', 0)),
            'strict_components_area_ge_8_at_512_count': int(c.get('strict_white_core_component_area_ge_8_at_512_count', 0)),
            'broad_candidate': bool(c.get('candidate_image_broad')),
            'focused_candidate': bool(c.get('candidate_image_focused')),
            'census_source_sha256': c['source_sha256'],
            'census_source_bytes': int(c['source_bytes']),
            'census_file_elapsed_seconds': c.get('file_elapsed_seconds'),
            'census_context_source': c.get('census_context_source'),
            'status': 'below_eligibility_unprocessed' if strict_at_512 < 256 else 'eligible_unprocessed',
            'final_delivery': None,
            'prior_work': [],
        }
        rows.append(item)
        by_key[row_key(src, c['source_sha256'])] = item

    prior = defaultdict(list)
    initial_path = PEOPLE / 'ledger.json'
    initial = jread(initial_path)
    for x in initial.get('images', []):
        add_prior(prior, x.get('source_path'), x.get('source_sha256'), {
            'source': 'initial_people48', 'id': x.get('id'), 'status': x.get('status'),
            'decision': (x.get('decision') or {}).get('decision'), 'output_sha256': (x.get('outputs') or {}).get('output_sha256'),
            'unchanged_identity_proof': (x.get('outputs') or {}).get('unchanged_identity_proof'),
        })

    for batch_name in ('batch002', 'batch003'):
        dpath = PEOPLE / batch_name / 'accepted_delivery.json'
        ddoc = jread(dpath)
        for d in ddoc.get('images', []):
            add_prior(prior, d.get('source_path'), d.get('source_sha256'), {
                'source': batch_name, 'id': d.get('id'), 'delivery': d.get('delivery'), 'path': d.get('path'), 'sha256': d.get('sha256'), 'source_sha256': d.get('source_sha256'), 'reason': d.get('reason'),
            })

    b2_refs = jread(PEOPLE / 'batch002' / 'sol_source_reviews' / 'aggregate.json')
    for x in b2_refs.get('reference_records', []):
        group = str(x.get('batch_id', ''))
        # Reference source identity is also available in the frozen manifest.
        m = jread(PEOPLE / 'batch002' / 'manifest.json')
        ref_row = next((v for g in m.get('groups', []) for v in g.get('versions', []) if v.get('batch_id') == group), None)
        if ref_row:
            add_prior(prior, ref_row.get('source'), x.get('source_sha256'), {
                'source': 'batch002_reference_only', 'id': group, 'actually_viewed': x.get('actually_viewed'),
                'pose_compatibility': x.get('pose_compatibility'), 'role': 'reference_only_no_cleanup_decision',
            })

    # Import all prior pilot results only as a closed history. Unchanged source
    # identity is complete; changed outputs without a final explicit delivery
    # resolution are parked and never re-run or silently promoted.
    pilot_results = {}
    pilot_verifiers = {}
    for cohort in ('development', 'validation'):
        results_path = PILOT / cohort / 'results.json'
        result_doc = jread(results_path)
        vr_path = PILOT / cohort / 'independent_verification.json'
        vr_doc = jread(vr_path)
        ver_by_id = {x['id']: x for x in vr_doc.get('results', [])}
        for x in result_doc.get('results', []):
            pilot_results[(cohort, x['id'])] = x
            pilot_verifiers[(cohort, x['id'])] = ver_by_id.get(x['id'], {})
            add_prior(prior, x.get('source'), x.get('source_sha256'), {
                'source': 'old_pilot_' + cohort, 'id': x.get('id'), 'changed_pixels': x.get('changed_pixels'),
                'source_sha256': x.get('source_sha256'), 'result_file': str(results_path),
                'verifier_can_skip_new_damage_review': ver_by_id.get(x['id'], {}).get('can_skip_new_damage_review'),
                'raw_trial_import_forbidden': bool(cohort == 'validation' and x.get('id') in {'v13_05', 'v13_10', 'v14_04'}),
            })

    overrides_doc = jread(PILOT / 'foreground_repairs' / 'delivery_overrides.json')
    overrides = {x['id']: x for x in overrides_doc.get('overrides', [])}
    current_map = {row_key(x['source'], x['source_sha256']): x for x in rows if x.get('source_sha256')}

    # Validate explicit prior final deliveries first, preferring batch003 over
    # batch002 when the same unchanged source was sampled more than once.
    priority = {'batch002': 2, 'batch003': 3}
    best = {}
    for key, entries in prior.items():
        for e in entries:
            if e.get('source') not in priority:
                continue
            if key not in best or priority[e['source']] > priority.get(best[key].get('source'), 0):
                best[key] = e

    pilot_review = {}
    # Build by current source key to avoid relying on legacy pilot IDs as IDs.
    for (cohort, old_id), x in pilot_results.items():
        key = row_key(x.get('source', ''), x.get('source_sha256', ''))
        pilot_review.setdefault(key, []).append((cohort, old_id, x, pilot_verifiers[(cohort, old_id)]))

    for key, item in current_map.items():
        if not item['source_size_matches_census']:
            item['status'] = 'needs_import_resolution'
            item['import_hold_reason'] = 'source_missing_or_size_differs_from_census'
            continue
        entries = prior.get(key, [])
        item['prior_work'] = entries
        chosen = best.get(key)
        if chosen:
            ok, how = validate_final_delivery(chosen, item['source'], item['source_sha256'])
            if ok:
                item['final_delivery'] = {k: chosen.get(k) for k in ('delivery', 'path', 'sha256', 'id', 'source') if chosen.get(k) is not None}
                item['delivery_hash_verified'] = True
                item['delivery_hash_verification'] = how
                item['status'] = 'accepted_prior_cleaned' if chosen['delivery'] == 'cleaned' else 'completed_original'
            else:
                item['status'] = 'needs_import_resolution'
                item['import_hold_reason'] = how
        # Exact initial 48 were reviewed unchanged, with byte-identity output proof.
        if item['status'] == 'eligible_unprocessed' or item['status'] == 'below_eligibility_unprocessed':
            initial_rows = [e for e in entries if e.get('source') == 'initial_people48']
            if initial_rows:
                e = initial_rows[-1]
                if e.get('decision') == 'unchanged' and e.get('unchanged_identity_proof') is True and e.get('output_sha256') == item['source_sha256']:
                    item['status'] = 'completed_original'
                    item['final_delivery'] = {'delivery': 'original', 'path': item['source'], 'sha256': item['source_sha256'], 'id': e.get('id'), 'source': 'initial_people48'}
                    item['delivery_hash_verified'] = True
                    item['delivery_hash_verification'] = 'ledger_source_byte_identity_proof'

        # Apply explicit validation delivery overrides. Never carry forward the
        # rejected raw trial image for v13_05, v13_10, or v14_04.
        for cohort, old_id, x, verifier in pilot_review.get(key, []):
            ov = overrides.get(old_id)
            if ov:
                accepted_path = Path(ov['accepted_path'])
                if not accepted_path.is_file() or digest(accepted_path) != ov['accepted_sha256']:
                    item['status'] = 'needs_import_resolution'
                    item['import_hold_reason'] = 'override_output_missing_or_hash_mismatch'
                    item['final_delivery'] = None
                else:
                    original = ov['status'] == 'original_retained'
                    item['final_delivery'] = {
                        'delivery': 'original' if original else 'separate_repair',
                        'path': str(accepted_path), 'sha256': ov['accepted_sha256'], 'id': old_id,
                        'source': 'foreground_repair_override', 'status': ov['status'], 'raw_trial_rejected': ov.get('raw_trial_rejected', False),
                    }
                    item['status'] = 'completed_original' if original else 'accepted_prior_repair'
                    item['delivery_hash_verified'] = True
                    item['delivery_hash_verification'] = 'override_output_sha256_verified'
            elif int(x.get('changed_pixels') or 0) == 0 and verifier.get('can_skip_new_damage_review') is True:
                if x.get('source_sha256') == item['source_sha256']:
                    item['status'] = 'completed_original'
                    item['final_delivery'] = {'delivery': 'original', 'path': item['source'], 'sha256': item['source_sha256'], 'id': old_id, 'source': 'old_pilot_' + cohort, 'unchanged_identity_proof': True}
                    item['delivery_hash_verified'] = True
                    item['delivery_hash_verification'] = 'independent_exact_identity_proof'
            elif int(x.get('changed_pixels') or 0) > 0:
                # Changed historical pilot output has no final delivery manifest.
                # It is not accepted and is not queued for an automatic rerun.
                if item.get('status') not in ('accepted_prior_cleaned', 'completed_original', 'accepted_prior_repair'):
                    item['status'] = 'needs_import_resolution'
                    item['import_hold_reason'] = 'historical_changed_pilot_has_no_final_delivery_record'
                    item['historical_changed_output_not_imported'] = True
                    item['final_delivery'] = None

        # A reference-only source screen is not a cleanup decision. It remains
        # parked unless another exact prior delivery resolved it.
        if any(e.get('source') == 'batch002_reference_only' for e in entries) and item['status'] in ('eligible_unprocessed', 'below_eligibility_unprocessed'):
            item['status'] = 'needs_import_resolution'
            item['import_hold_reason'] = 'previously_viewed_as_reference_only_not_a_cleanup_source_review'

    # Check all cached source hashes are one-to-one and prepare group membership.
    if len({(r.get('relative_path'), r.get('source_sha256')) for r in rows}) != len(rows):
        raise RuntimeError('duplicate source relative_path + SHA in cached census')
    groups_by_key = defaultdict(list)
    for item in rows:
        if item.get('status') == 'eligible_unprocessed':
            groups_by_key[item['group_key']].append(item)
    group_rows = []
    for gkey, subject_rows in groups_by_key.items():
        styles = Counter(x['style_id'] for x in subject_rows)
        group_rows.append({
            'group_key': gkey,
            'people_subfolder': subject_rows[0]['people_subfolder'],
            'normalized_stem': subject_rows[0]['normalized_stem'],
            'subject_source_ids': [x['production_source_id'] for x in sorted(subject_rows, key=lambda r: (r['style_id'], r['relative_path']))],
            'candidate_count': len(subject_rows),
            'candidate_count_by_style': dict(styles),
            'style_ids': sorted(styles),
        })
    ordered = group_order(group_rows)
    # Freeze a globally unique queue ID and group ID once, before any image work.
    for n, g in enumerate(ordered, 1):
        g['group_id'] = f'g{n:05d}'
    id_by_source = {}
    pnum = 1
    for g in ordered:
        for source_id in g['subject_source_ids']:
            id_by_source[source_id] = f'p{pnum:05d}'
            pnum += 1
    subjects_by_id = {x['production_source_id']: x for x in rows if x.get('status') == 'eligible_unprocessed'}

    # Whole-group batches, aiming for 135 eligible subjects and never exceeding 150.
    batches = []
    current = []
    current_n = 0
    for g in ordered:
        n = g['candidate_count']
        if current and current_n >= 120 and current_n + n > 150:
            batches.append(current)
            current, current_n = [], 0
        current.append(g)
        current_n += n
        if current_n >= 135:
            batches.append(current)
            current, current_n = [], 0
    if current:
        batches.append(current)
    batch_assignment = {}
    for bi, batch_groups in enumerate(batches, 1):
        for g in batch_groups:
            batch_assignment[g['group_id']] = f'batch{bi:03d}'
    for g in ordered:
        g['batch_id'] = batch_assignment[g['group_id']]
        g['versions'] = []
        subjects = [subjects_by_id[s] for s in g['subject_source_ids']]
        candidate_style_ids = [x['style_id'] for x in subjects]
        for x in sorted(subjects, key=lambda r: (r['style_id'], r['relative_path'])):
            g['versions'].append({
                'batch_id': id_by_source[x['production_source_id']],
                'production_source_id': x['production_source_id'],
                'source': x['source'], 'source_sha256': x['source_sha256'], 'source_bytes': x['source_bytes'],
                'dimensions': x['dimensions'], 'style_id': x['style_id'], 'style': x['style'],
                'role': 'subject', 'review_required': True,
                'simple_eligible': True,
                'strict_white_core_pixel_count_at_512': x['strict_white_core_pixel_count_at_512'],
                'components_ge64_at_512': None,
            })
        # Fill a global reference budget later; deterministic selection aims for
        # near-style peers and never includes more than two per concept.
        group_items = [x for x in rows if x.get('group_key') == g['group_key'] and x.get('production_source_id') not in g['subject_source_ids']]
        candidates = sorted(group_items, key=lambda r: (
            min(abs(r['style_id'] - sid) for sid in candidate_style_ids) if candidate_style_ids else 0,
            r['style_id'], r['relative_path']))
        refs=[]
        if candidates:
            refs.append(candidates[0])
        if len(candidates) > 1:
            first_style=refs[0]['style_id']
            second=sorted(candidates[1:], key=lambda r: (-abs(r['style_id']-first_style), r['style_id'], r['relative_path']))[0]
            refs.append(second)
        g['_reference_candidates'] = refs

    # Keep at most 50 contextual reference versions in each batch.
    for bnum, batch_groups in enumerate(batches, 1):
        budget = 50
        for g in batch_groups:
            selected = g['_reference_candidates'][:min(2, budget)]
            for x in selected:
                g['versions'].append({
                    'batch_id': 'r_' + x['production_source_id'][:20],
                    'production_source_id': x['production_source_id'],
                    'source': x['source'], 'source_sha256': x['source_sha256'], 'source_bytes': x['source_bytes'],
                    'dimensions': x['dimensions'], 'style_id': x['style_id'], 'style': x['style'],
                    'role': 'reference', 'review_required': False,
                    'simple_eligible': x['simple_eligible'],
                    'prior_status': x['status'],
                    'strict_white_core_pixel_count_at_512': x['strict_white_core_pixel_count_at_512'],
                    'components_ge64_at_512': None,
                })
                budget -= 1
        for g in batch_groups:
            g['candidate_count'] = sum(v['role'] == 'subject' for v in g['versions'])

    # Whole-group queue file and first prepared batch manifests.
    queue = {
        'schema_version': 1, 'created_utc': generated, 'rule_version': 'people-white-core-v1',
        'source_census_sha256': digest(CENSUS), 'eligibility_rule': {'strict_white_rgb_min': 240, 'max_channel_range': 20, 'min_alpha': 128, 'normalized_total_minimum_at_512': 256},
        'grouping_rule': 'Exact People & Relationships relative subfolder plus casefolded filename stem with spaces/hyphens/underscores removed; parentheses and other punctuation retained.',
        'ordering_rule': 'Deterministic greedy whole-group ordering by least-served eligible styles, tie-broken by group key; no random selection.',
        'batch_target_subjects': 135, 'batch_subject_range': [120, 150], 'maximum_references_per_batch': 50, 'maximum_references_per_group': 2,
        'subject_count': pnum - 1, 'group_count': len(ordered), 'batch_count': len(batches),
        'batches': [],
        'groups': [],
    }
    batch_root = OUT / 'batches'
    batch_root.mkdir(parents=True, exist_ok=True)
    for bnum, batch_groups in enumerate(batches, 1):
        name = f'batch{bnum:03d}'
        bdir = batch_root / name
        bdir.mkdir(parents=True, exist_ok=True)
        # Ensure role rows are globally unique in each batch.
        vers = [v for g in batch_groups for v in g['versions']]
        ids = [v['batch_id'] for v in vers]
        if len(ids) != len(set(ids)):
            raise RuntimeError(f'{name}: duplicate batch_id')
        batch_subjects = sum(v['role'] == 'subject' for v in vers)
        batch_refs = sum(v['role'] == 'reference' for v in vers)
        manifest = {
            'schema_version': 1, 'batch_id': name, 'status': 'awaiting_source_review',
            'protocol_version': 1, 'rule_version': 'people-white-core-v1',
            'created_utc': generated, 'source_census_sha256': queue['source_census_sha256'],
            'queue_sha256': None,
            'grouping_rule': queue['grouping_rule'],
            'selection_rule': 'First whole groups in the frozen deterministic queue until target; includes every eligible subject in each selected concept group and up to two same-concept reference versions when available.',
            'target_subjects': 135, 'actual_subjects': batch_subjects, 'actual_references': batch_refs,
            'groups': [],
        }
        blind = {k:v for k,v in manifest.items() if k not in ('groups','status')}
        blind['status'] = 'awaiting_blind_source_review'
        blind['groups'] = []
        for g in batch_groups:
            gg = {k:g[k] for k in ('group_id','group_key','people_subfolder','normalized_stem','batch_id')}
            gg['versions'] = list(g['versions'])
            manifest['groups'].append(gg)
            bg = {k:gg[k] for k in ('group_id','group_key','people_subfolder','normalized_stem','batch_id')}
            bg['versions'] = []
            for v in g['versions']:
                bg['versions'].append({k:v[k] for k in ('batch_id','production_source_id','source','source_sha256','source_bytes','dimensions','style_id','style','role','review_required')})
            blind['groups'].append(bg)
        atomic_json(bdir / 'manifest.json', manifest)
        atomic_json(bdir / 'blind_manifest.json', blind)
        qrow = {'batch_id': name, 'group_ids': [g['group_id'] for g in batch_groups], 'subject_count': batch_subjects, 'reference_count': batch_refs, 'manifest_path': str((bdir/'manifest.json').resolve()), 'blind_manifest_path': str((bdir/'blind_manifest.json').resolve())}
        queue['batches'].append(qrow)
        for g in batch_groups:
            g['manifest_path'] = qrow['manifest_path']
            g['manifest_path'] = qrow['manifest_path']
    # Attach queue membership/source IDs to the inventory only after manifests exist.
    assigned_by_source = {}
    group_by_source = {}
    for g in ordered:
        for v in g['versions']:
            if v['role'] == 'subject':
                assigned_by_source[v['production_source_id']] = v['batch_id']
                group_by_source[v['production_source_id']] = g['group_id']
    for x in rows:
        if x.get('production_source_id') in assigned_by_source:
            x['production_queue_id'] = assigned_by_source[x['production_source_id']]
            x['production_group_id'] = group_by_source[x['production_source_id']]
            x['production_batch_id'] = next(g['batch_id'] for g in ordered if g['group_id']==x['production_group_id'])

    # Emit frozen queue/order without bulky full census records.
    queue['groups'] = [{k:g[k] for k in ('group_id','group_key','people_subfolder','normalized_stem','batch_id','candidate_count','candidate_count_by_style','versions','manifest_path')} for g in ordered]
    atomic_json(OUT / 'queue.json', queue)
    # Add frozen queue lineage to the batch manifests. Keep manifest hashes in a
    # side index so the queue and its child manifests do not form a hash cycle.
    for q in queue['batches']:
        bdir = batch_root / q['batch_id']
        m = jread(bdir/'manifest.json'); bm = jread(bdir/'blind_manifest.json')
        m['queue_sha256'] = digest(OUT/'queue.json'); bm['queue_sha256'] = m['queue_sha256']
        atomic_json(bdir/'manifest.json',m);atomic_json(bdir/'blind_manifest.json',bm)
    atomic_json(OUT/'batch_index.json', {
        'schema_version':1,
        'queue_sha256':digest(OUT/'queue.json'),
        'batches':[{'batch_id':q['batch_id'],'manifest_sha256':digest(batch_root/q['batch_id']/'manifest.json'),'blind_manifest_sha256':digest(batch_root/q['batch_id']/'blind_manifest.json')} for q in queue['batches']],
    })
    # Build status and provenance summaries.
    status_counts=Counter(x['status'] for x in rows)
    eligible_counts=Counter(x['style'] for x in rows if x['simple_eligible'])
    queued_counts=Counter(x['style'] for x in rows if x.get('production_queue_id'))
    summary={
        'schema_version':1,'generated_utc':generated,'source_library':str(LIBRARY),'census_file':str(CENSUS),'census_sha256':digest(CENSUS),
        'census_images_screened':10891,'inventory_rows':len(rows),'census_exceptions':sum(x.get('status')=='census_exception' for x in rows),
        'simple_eligibility_rule':queue['eligibility_rule'],'simple_eligible_total':sum(bool(x.get('simple_eligible')) for x in rows),
        'queue_subject_total':queue['subject_count'],'queue_group_total':len(ordered),'queue_batch_total':len(batches),
        'status_counts':dict(status_counts),'eligible_by_style':dict(eligible_counts),'queued_by_style':dict(queued_counts),
        'style_counts':dict(Counter(x['style'] for x in rows if x.get('style'))),
        'first_batch':queue['batches'][0] if queue['batches'] else None,
        'first_batch_subjects':queue['batches'][0]['subject_count'] if queue['batches'] else 0,
        'first_batch_references':queue['batches'][0]['reference_count'] if queue['batches'] else 0,
        'source_image_decoding_or_rendering_performed':False,
    }
    # Use atomic JSON but keep snapshot and ledger recoverable independently.
    inventory={'schema_version':1,'generated_utc':generated,'source_library':str(LIBRARY),'census_sha256':summary['census_sha256'],'images':rows}
    atomic_json(OUT/'inventory.json', inventory)
    atomic_json(OUT/'summary.json', summary)

    # Append-only event ledger rebuilt from frozen inventory. Store every source
    # state and provenance reference; future changes append new events.
    tmp=OUT/'ledger.jsonl.tmp'
    with tmp.open('w',encoding='utf-8') as f:
        for x in rows:
            ev={'event':'bootstrap_inventory','utc':generated,'production_source_id':x.get('production_source_id'),'source':x.get('source'),'source_sha256':x.get('source_sha256'),'status':x.get('status'),'simple_eligible':x.get('simple_eligible',False),'production_queue_id':x.get('production_queue_id'),'production_batch_id':x.get('production_batch_id'),'provenance':x.get('prior_work',[]),'final_delivery':x.get('final_delivery'),'import_hold_reason':x.get('import_hold_reason')}
            f.write(json.dumps(ev,ensure_ascii=False,separators=(',',':'))+'\n')
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,OUT/'ledger.jsonl')

    audit={
        'schema_version':1,'generated_utc':generated,'census_sha256':summary['census_sha256'],
        'imports':{
            'initial_people48':{'records':48,'resolution':'All 48 source decisions unchanged; source-byte-identity outputs and approval are hash-bound in ledger.json.'},
            'batch002':{'candidate_records':102,'cleaned':22,'originals':80,'reference_records':11,'resolution':'Accepted delivery SHA verified for every cleaned copy. Original entries are source byte identity. References are parked because reference viewing is not an individual cleanup decision.'},
            'batch003':{'records':158,'cleaned':26,'originals':132,'resolution':'Accepted delivery SHA verified for every cleaned copy. Originals are exact source identity.'},
            'development_validation':{'records':680,'resolution':'Prior source/output pilot records imported. Exact unchanged cases are original deliveries. Explicit validation overrides imported only from their accepted paths and hashes. Changed pilot outputs lacking final delivery records are marked needs_import_resolution; they are excluded from the production queue and raw trial outputs are never imported.'},
        },
        'needs_import_resolution':sum(x['status']=='needs_import_resolution' for x in rows),
        'accepted_cleaned_prior':sum(x['status']=='accepted_prior_cleaned' for x in rows),
        'accepted_separate_repairs':sum(x['status']=='accepted_prior_repair' for x in rows),
        'completed_original_prior':sum(x['status']=='completed_original' for x in rows),
        'queued_production_subjects':summary['queue_subject_total'],
        'unresolved_items':[
            {'production_source_id':x.get('production_source_id'),'source':x.get('source'),'source_sha256':x.get('source_sha256'),'status':x.get('status'),'reason':x.get('import_hold_reason')}
            for x in rows if x.get('status')=='needs_import_resolution'
        ],
        'raw_trial_exclusions':['v13_05','v13_10','v14_04'],
    }
    atomic_json(OUT/'import_audit.json',audit)
    print(json.dumps({'inventory_rows':len(rows),'eligibility':summary['simple_eligible_total'],'queued':summary['queue_subject_total'],'groups':len(ordered),'batches':len(batches),'first_batch':queue['batches'][0] if queue['batches'] else None,'status_counts':dict(status_counts),'import_resolution':audit['needs_import_resolution'],'source_images_decoded':False},indent=2))


if __name__=='__main__': main()
