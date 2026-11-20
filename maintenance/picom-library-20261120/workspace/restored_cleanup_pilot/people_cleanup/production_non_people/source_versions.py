"""Overlay only the three approved current source versions after historical reconciliation."""
import hashlib
from common import HERE, LIBRARY, digest, read, require

BASE = HERE.parent
DECISION = BASE/'source_revisions_20261105_np_integration_decision.json'
PLAN = BASE/'source_revisions_20261105_np_integration_plan.json'
REGISTRY = BASE/'source_revisions_20261105/registry.json'
MEASUREMENTS = BASE/'source_revisions_20261105_current_measurements_approved.json'
APPROVED_INPUTS = {
    DECISION: '56e8b8bc3178e468c41b970c7842bad9ad7fe6825a7dcb23f6ab7de129683bc4',
    PLAN: 'c6be22b7c9da49688998cee849588115161b0a8740b0e5800d1e093233dccbe8',
    REGISTRY: 'bca11d43dd083aa9adde4075be14e57f8b45f4d935cccf57209599c4521a3ac0',
    MEASUREMENTS: '5ad7802e721a0fc4e6638927924ea69474063fef4bedfdf47804252f5e5f0016',
}
TOTAL = 170044
PENDING = 168750
PRIOR = 1294
REVIEW = 66079
GROUP = 'npg18129'
BATCH = 'batchN333'
GROUP_KEY = 'People & Relationships/Family::mum'
MUM = 'People & Relationships/Family/mum.webp'
COMPANION = 'Sommi companion objects/'+MUM
EXTRA = {'3D animated cartoon/'+MUM: 'np66078', 'Flat outlined/'+MUM: 'np66079'}
SUBJECTS = {COMPANION: 'np45228', **EXTRA}
VERSION_KEYS = ('historical_source_sha256', 'source_version_id')


def source_id(relative, sha):
    return hashlib.sha256(('remaining-original-non-people-v1\0'+relative+'\0'+sha).encode()).hexdigest()


def version_fields(relative, logical_id, historical_sha, current_sha):
    key = '\0'.join(('non-people-source-version-v1', logical_id, relative, current_sha))
    return {'historical_source_sha256': historical_sha,
            'source_version_id': hashlib.sha256(key.encode()).hexdigest()}


def logical_id(relative, row):
    return row.get('historical_topic_source_id') or source_id(
        relative, row.get('historical_source_sha256', row['source_sha256']))


def exact_relevant(records, field, keys):
    result = {}
    for row in records:
        key = row[field]
        if key in keys:
            require(key not in result, 'Duplicate authorized source-version record')
            result[key] = row
    require(set(result) == set(keys), 'Missing authorized source-version record')
    return result


def apply_overlay(original, pending, prior, historical_resolutions, frozen_by_path):
    for path, expected in APPROVED_INPUTS.items():
        require(digest(path) == expected, 'Approved source-version metadata changed: '+str(path))
    decision, plan, registry, measurements = map(read, (DECISION, PLAN, REGISTRY, MEASUREMENTS))
    require(decision['status'] == 'root_design_decision_for_staged_code_only'
            and decision['population_execution_authorized_by_this_file'] is False,
            'Source-version design cannot grant execution')
    rows = plan['revised_sources']
    require(len(rows) == len(SUBJECTS), 'Unauthorized extra/missing source version')
    planned = exact_relevant(rows, 'relative_path', SUBJECTS)
    registered = exact_relevant(registry['entries'], 'relative_path', SUBJECTS)
    measured = exact_relevant(measurements['entries'], 'path', {str(LIBRARY/rel) for rel in SUBJECTS})
    require(measurements['status'] == 'approved_current_version_measurements'
            and measurements['registry_sha256'] == APPROVED_INPUTS[REGISTRY],
            'Current source measurements are unapproved or unbound')
    replacements = {}
    for rel, subject_id in SUBJECTS.items():
        historical = pending.get(rel) if rel == COMPANION else prior.get(rel)
        path = str(LIBRARY/rel)
        old = planned[rel]['historical_sha256']
        current = planned[rel]['current_sha256']
        reg, measurement = registered[rel], measured[path]
        require(rel in original and historical is not None and rel not in historical_resolutions
                and not historical.get('lineage_hold'), 'Source version outside eligible historical scope or held')
        require(historical['source_sha256'] == original[rel]['source_sha256'] == reg['old_sha256'] == old
                and reg['path'] == path and reg['new_sha256'] == measurement['source_sha256'] == current
                and current != old, 'Approved source-version identity differs')
        require(reg['new_dimensions'] == measurement['dimensions'] == original[rel]['dimensions'] == [512, 512]
                and type(measurement['source_bytes']) is int
                and reg['new_bytes'] == measurement['source_bytes'] > 0
                and measurement['simple_eligible'] is True
                and measurement['strict_white_core_pixel_count_at_512'] >= 256,
                'Current source byte size, dimensions or strict eligibility differ')
        receipt = measurement['stable_byte_receipt']
        require(receipt['sha256'] == current and receipt['stat_before'] == receipt['fstat_opened']
                == receipt['fstat_closed'] == receipt['stat_after']
                and receipt['stat_after'][2] == measurement['source_bytes'],
                'Approved current measurement lacks stable byte evidence')
        lineage = {}
        if rel == COMPANION:
            require(rel not in prior and historical['partition'] == 'review_required'
                    and historical['proposed_subject_id'] == subject_id
                    and historical['proposed_batch_id'] == BATCH and historical['proposed_group_id'] == GROUP,
                    'Historical companion review assignment changed')
        else:
            topic = frozen_by_path[rel]
            require(rel not in pending and historical['partition'] == 'excluded_frozen_topic_inventory'
                    and topic['source'] == path and topic['source_sha256'] == old,
                    'Supplemental review does not match original topic lineage')
            dispositions = reg['historical_dispositions']
            require(len(dispositions) == 1 and dispositions[0]['category'] == 'already_delivered'
                    and dispositions[0]['cohort'] == 'production' and dispositions[0]['status'] == 'accepted',
                    'Missing historical topic disposition')
            delivery = dispositions[0]['delivery']
            require(delivery['delivery'] == 'cleaned' and delivery['source_path'] == path
                    and delivery['source_sha256'] == old and delivery['id'] == topic['production_queue_id'],
                    'Stale cleaned delivery does not match historical topic')
            lineage = {'historical_topic_source_id': topic['production_source_id'],
                       'historical_topic_queue_id': topic['production_queue_id'],
                       'historical_topic_batch_id': topic['production_batch_id'],
                       'stale_cleaned_delivery': {k: delivery[k] for k in ('path', 'sha256')}}
        identity = lineage.get('historical_topic_source_id') or source_id(rel, old)
        replacements[rel] = {
            'relative_path': rel, 'source_path': path, 'source_sha256': current,
            'source_bytes': measurement['source_bytes'], 'dimensions': measurement['dimensions'],
            'original_provenance': historical['original_provenance'], 'group_key': GROUP_KEY,
            'partition': 'review_required', 'candidate': True,
            'strict_white_total': measurement['strict_white_core_pixel_count_at_512'],
            'current_strict_metrics': {k: measurement[k] for k in (
                'strict_white_core_pixel_count_native', 'strict_white_core_pixel_count_at_512',
                'strict_components', 'largest_strict_component_at_512')},
            'proposed_subject_id': subject_id, 'proposed_batch_id': BATCH, 'proposed_group_id': GROUP,
            **version_fields(rel, identity, old, current), **lineage,
        }
    for rel, replacement in replacements.items():
        pending[rel] = replacement
        prior.pop(rel, None)
        original[rel].update(replacement, subject_id=replacement['proposed_subject_id'])


def queue_group(row, decision):
    if row['proposed_group_id'] != GROUP:
        require(not (set(row['subject_relative_paths']) & set(SUBJECTS)), 'Revised subject assigned outside approved group')
        return row
    require(row == decision['existing_group'] and not row['hold_subject_ids'] and not row['context_references'],
            'Historical mum group, hold or context references changed')
    return {**row, 'subject_ids': [*row['subject_ids'], *EXTRA.values()],
            'subject_relative_paths': [*row['subject_relative_paths'], *EXTRA]}


def reject_stale_delivery(row, source):
    stale = source.get('stale_cleaned_delivery')
    if stale:
        require(row['delivery_path'] != stale['path'] and row['delivery_sha256'] != stale['sha256'],
                'Obsolete historical cleaned delivery cannot complete a current source version')
