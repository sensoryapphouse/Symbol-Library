#!/usr/bin/env python3
"""Freeze the reviewed Non-People merge after both current prerequisite receipts exist."""
import argparse
import json
import re
from pathlib import Path

from common import HERE, LIBRARY, atomic_json, digest, read, require, utc, validate_bundle
from prerequisites import (
    COMPACT_DIR, CURRENT_VERSION_DIR, HISTORICAL_PUBLICATION_SHA, PUBLICATION_DIR,
    Q80_DIR, Q80_EXTENSION, Q80_EXTENSION_SHA, Q80_OVERLAY_SHA, Q80_RECEIPT, Q80_RECEIPT_SCHEMA,
    Q80_SUCCESSOR_SCOPE, Q80_SUCCESSOR_PINS, Q80_HISTORICAL_RECEIPT_SHA,
    Q80_HISTORICAL_JOURNAL_SHA, Q80_HISTORICAL_REPORT_SHA,
    WIZARD_PROOF_SCHEMA, WIZARD_REVIEW_FILENAME, WIZARD_REVIEW_SHA, WIZARD_SHA, validate_overlay_paths,
)
from publication_transaction import HELPER, HELPER_SHA, checked_bytes, exists
from source_versions import PENDING, PRIOR, REVIEW, TOTAL
import wizard_q80_prerequisite as ws_q80

LIVE_BUNDLE = '4096e0d7cdc2413e2a4da72db1e5c3329d70ebebcb4eaf073313a457d4ef9101'
COMPACT_CANDIDATE = 'd9283cedd3b605e09309f8bc066fd182674845bd3a13c445dfc8fdaf6642298d'
VERSION_REVIEW = '8a2941ea16e99e4643ee4501484653b61112eac785b897779284cce84f46fffe'
VERSION_MANIFEST = '8741635b6448cb2ff514aec0460207b40f5776c68cfdfc0f01d04a49e7fe2e21'
Q80_SUCCESSOR_CODE = {'q80_current.py': 'e15c9a989fb793ea3ed29eda227032c7fbbace326c182867ac368d693f2a1359', 'q80_successors.py': '7e580a7586d213ef53bcbdb1f02cd6c1f0e305f7c8e9e7693aad98ac3f607e0c'}
Q80_PINS = {
    'compress.py': '41f93560e8412158ea2963f79a9d29fe2273ee22ab0c5e97355a5038e34335fd',
    'readiness.json': 'de6ebf8a29b55762beb229dd6ca5066f5a98763072f9378cfa36023c2afbc2bc',
    'continue_unaffected.py': '3a1a327dd9c1bd044b21bd61ba764a4ee003446bf9e44b461356ce2137c914f8',
    'semantic_revisions.json': '4e7378c57d0b0516b571be7ca0210457d62e7a7d22e4c750a2fd4c521ad48491',
}
AUDIT_SHA = 'fd1d1693b7b26a834f680bd45a64658243a90800046a2fdde1496b5baf7697b4'
ORIGINAL_PLAN_SHA = '0c0101b4cb84205e707becb5a2b1a17bc6b58e1c97803067817fb681c667e4cd'
NEW_LOCAL = {'non_people_publication.py', 'publication_transaction.py', 'publish_prior.py', 'test_publication.py',
             'wizard_q80_prerequisite.py', 'test_wizard_q80_prerequisite.py'}
PHASE = 'staged_library_storage_and_current_people_prerequisites'
HISTORICAL_BRIDGE = 'historical_publication_bridge.py'
HISTORICAL_BRIDGE_SHA = '3c78b19f711683a61b58f27bb86ab820660a69dd8c6acb13c7721073a3d8a34e'
MERGE_MANIFEST = 'non_people_current_integration_candidate/changed_code_manifest.json'


def bound_json(path, expected):
    require(isinstance(expected, str) and re.fullmatch(r'[a-f0-9]{64}', expected),
            f'Exact reviewed SHA-256 is required: {path}')
    return json.loads(checked_bytes(path, expected)[0])


def external_pins(base, library, live, finalizer_review_sha, q80_receipt_sha, successor_review_sha):
    compact_path = base/COMPACT_DIR/'non_people/code_bundle.json'
    compact = bound_json(compact_path, COMPACT_CANDIDATE)
    external = dict(compact['external_sha256'])
    require(all(external.get(path) == sha for path, sha in live['external_sha256'].items()),
            'Compact candidate omits reviewed runtime dependencies')
    external[str(compact_path)] = COMPACT_CANDIDATE

    current = base/CURRENT_VERSION_DIR
    version_review_path = current/'root_staged_review.json'
    version_review = bound_json(version_review_path, VERSION_REVIEW)
    require(version_review['manifest_sha256'] == VERSION_MANIFEST, 'Current-version review names the wrong stage')
    external[str(version_review_path)] = VERSION_REVIEW
    checked_bytes(current/'SHA256SUMS', VERSION_MANIFEST)
    external[str(current/'resolver.py')] = version_review['files_sha256']['resolver.py']
    successor_review_path = current/'q80_successor_root_review.json'
    successor_review = bound_json(successor_review_path, successor_review_sha)
    successor_inputs = {str(base/Q80_DIR/name): sha for name, sha in Q80_SUCCESSOR_PINS.items()}
    successor_inputs[str(current/'q80_current_receipt.json')] = Q80_HISTORICAL_RECEIPT_SHA
    require(successor_review['schema'] == 'picom-six-q80-successor-root-review-v1'
            and successor_review['reviewer'] == 'root'
            and successor_review['approved_for_current_q80_successor_reconciliation'] is True
            and successor_review['base_version_review_sha256'] == VERSION_REVIEW
            and successor_review['base_version_manifest_sha256'] == VERSION_MANIFEST
            and successor_review['base_q80_current_sha256'] == version_review['files_sha256']['q80_current.py']
            and successor_review['files_sha256'] == Q80_SUCCESSOR_CODE
            and successor_review['approved_inputs'] == successor_inputs,
            'Exact independent root review of the six-Q80 successor stage is required')
    external[str(successor_review_path)] = successor_review_sha
    external.update({str(current/name): sha for name, sha in Q80_SUCCESSOR_CODE.items()})
    external.update(successor_inputs)

    publication = base/PUBLICATION_DIR
    require(external[str(publication/'bundle.json')] == HISTORICAL_PUBLICATION_SHA,
            'Unexpected historical publication authority')
    review_path = publication/'root_review.json'
    review = bound_json(review_path, finalizer_review_sha)
    finalizer_sha = review['publication_bundle_sha256']
    require(finalizer_sha != HISTORICAL_PUBLICATION_SHA, 'Historical publisher cannot finalize Q80')
    finalizer = bound_json(publication/'bundle.json', finalizer_sha)
    code = finalizer['code_sha256']
    require(finalizer['schema'] == 'ws-library-publication-bundle-v1'
            and finalizer['legacy_bundle_sha256'] == WIZARD_SHA,
            'Wizard finalizer has the wrong legacy authority')
    require(review['schema'] == 'root-wizard-library-publication-review-v1' and review['reviewed_by'] == 'root'
            and review['publication_bundle_sha256'] == finalizer_sha and set(code) == {'publication.py', 'transaction.py'}
            and review['code_sha256'] == code and review['allowed_actions'] == ['finalize', 'nonpeople_gate']
            and review['approved_for_finalization_and_nonpeople_gate'] is True
            and review['approved_for_bounded_batch_publication'] is False,
            'Exact root review for the finalization-only bundle is required')
    external.update({str(publication/'bundle.json'): finalizer_sha, str(review_path): finalizer_review_sha,
                     **{str(publication/name): sha for name, sha in code.items()}, str(HELPER): HELPER_SHA})

    external[str(publication/HISTORICAL_BRIDGE)] = HISTORICAL_BRIDGE_SHA
    historical_bundle = publication/'implementation_history'/HISTORICAL_PUBLICATION_SHA/'bundle.json'
    external[str(historical_bundle)] = HISTORICAL_PUBLICATION_SHA
    ws_pins, _ = ws_q80.closure(base, finalizer, review)
    external.update(ws_pins)

    compression = base/Q80_DIR
    audit = base/'workspace_cleanup_20261106/semantic_repair_overlap_reconciliation_20261106.json'
    overlay = library/'_manifest/current-delivery.jsonl'
    extension = library/'_manifest'/Q80_EXTENSION
    external.update({str(compression/name): sha for name, sha in Q80_PINS.items()})
    external.update({str(audit): AUDIT_SHA, str(overlay): Q80_OVERLAY_SHA, str(extension): Q80_EXTENSION_SHA})
    receipt_path = current/Q80_RECEIPT
    receipt = bound_json(receipt_path, q80_receipt_sha)
    repair_pins = {str(compression/name): Q80_PINS[name] for name in ('continue_unaffected.py', 'semantic_revisions.json')}
    repair_pins[str(audit)] = AUDIT_SHA
    counts = receipt['q80_counts']
    require(receipt['schema'] == Q80_RECEIPT_SCHEMA and receipt['traversal_finished'] is True
            and receipt['full_q80_compression_complete'] is False
            and receipt['original_plan_sha256'] == ORIGINAL_PLAN_SHA
            and receipt['phase1_receipt_sha256'] == Q80_EXTENSION_SHA
            and receipt['historical_overlay_sha256'] == Q80_OVERLAY_SHA
            and receipt['repair_authority'] == repair_pins
            and receipt['historical_overlay_rows'] == 12081 and receipt['q80_phase1_rows'] == 1599
            and receipt['q80_plan_rows'] == sum(counts.values()) == 27596
            and counts == {'replaced': 27549, 'retained': 41, 'reviewed_repair_q80_successor': 6}
            and set(receipt['q80_successors']) == set(receipt['historical_q80_deferrals']) == Q80_SUCCESSOR_SCOPE
            and receipt['q80_deferrals'] == {}
            and receipt['q80_successor_inputs_sha256'] == successor_inputs
            and receipt['q80_journal_sha256'] == Q80_HISTORICAL_JOURNAL_SHA
            and receipt['traversal_report_sha256'] == Q80_HISTORICAL_REPORT_SHA
            and re.fullmatch(r'[a-f0-9]{64}', receipt['current_byte_map_sha256'])
            and receipt['current_library_byte_checks'] == 38085
            and receipt['repaired_original_people_byte_checks'] == 3,
            'Q80 receipt does not establish the reviewed current subset')
    external[str(receipt_path)] = q80_receipt_sha
    # These mutable paths are checked here and rebound from the receipt by the
    # prerequisite guard. The bundle permanently pins the immutable receipt.
    require(not any(exists(compression/('compression.sqlite' + suffix)) for suffix in ('-journal', '-wal', '-shm')),
            'Q80 journal has a recovery sidecar')
    for name, key in (('compression.sqlite', 'q80_journal_sha256'),
                      ('unaffected_progress.json', 'traversal_report_sha256')):
        require(re.fullmatch(r'[a-f0-9]{64}', receipt[key]), 'Invalid Q80 traversal digest')
        checked_bytes(compression/name, receipt[key])
    for path, sha in external.items():
        require(re.fullmatch(r'[a-f0-9]{64}', sha), f'Invalid dependency SHA-256: {path}')
        checked_bytes(Path(path), sha)
    return external


def installed_local_pins(runtime, live, manifest):
    require(manifest['schema'] == 'picom-non-people-merged-changed-code-v1'
            and manifest['live_bundle_sha256'] == LIVE_BUNDLE,
            'Changed-code manifest is for another runtime')
    changed = manifest['replacements']
    expected_names = set(live['local_sha256']) | NEW_LOCAL
    require(set(changed) <= expected_names | {'activation.json'}
            and NEW_LOCAL | {'activation.json', 'scope_contract.json', 'prerequisites.py', 'freeze_core.py'} <= set(changed),
            'Changed-code manifest omits required files or introduces extra files')
    expected = dict(live['local_sha256'])
    expected.update({name: info['sha256'] for name, info in changed.items()})
    require(set(expected) == expected_names | {'activation.json'}, 'Merged local code scope differs')
    for name, sha in expected.items():
        require(re.fullmatch(r'[a-f0-9]{64}', sha), f'Invalid merged file SHA-256: {name}')
        checked_bytes(runtime/name, sha)
    expected.pop('activation.json')
    return dict(sorted(expected.items()))


def freeze(finalizer_review_sha, q80_receipt_sha, merge_manifest_sha, successor_review_sha):
    overlay = read(HERE/'activation.json')
    require(overlay['enabled'] is False, 'Runtime must be disabled while freezing')
    validate_overlay_paths(HERE, overlay)
    require(all(not (HERE/name).exists() for name in (
        'inventory.json', 'queue.json', 'batch_index.json', 'ledger.jsonl', 'batches', 'activation_audit',
        'activation_attestations', 'activation_approval_candidate.json', 'root_activation_approval.json',
        'final_verification', 'prior_publication')),
        'Refusing to refreeze a runtime with population or approval artifacts')
    target = HERE/'code_bundle.json'
    live = bound_json(target, LIVE_BUNDLE)
    old_review = HERE/'root_runtime_review.json'
    old_review_raw = checked_bytes(old_review)[0]
    require(json.loads(old_review_raw).get('code_bundle_sha256') == LIVE_BUNDLE,
            'Existing root review does not bind the prior disabled runtime')
    scope = read(HERE/'scope_contract.json')
    require((scope['original_paths'], scope['pending_paths'], scope['prior_paths'], scope['review_subjects'])
            == (TOTAL, PENDING, PRIOR, REVIEW), 'Non-People scope differs')
    manifest_path = HERE.parent/MERGE_MANIFEST
    local = installed_local_pins(HERE, live, bound_json(manifest_path, merge_manifest_sha))
    external = external_pins(HERE.parent, LIBRARY, live, finalizer_review_sha, q80_receipt_sha, successor_review_sha)
    external[str(manifest_path)] = merge_manifest_sha
    require(scope['wizard_final_proof_gate']['bundle_sha256'] is None
            and scope['wizard_final_proof_gate']['bundle_binding'] == 'exact_root_review_and_external_sha256'
            and scope['wizard_final_proof_gate']['staged_q80_review_sha256'] == ws_q80.STAGED_REVIEW_SHA
            and scope['wizard_final_proof_gate']['proof_schema'] == WIZARD_PROOF_SCHEMA,
            'Scope contract does not identify the reviewed current finalizer')
    bundle = {
        **live, 'phase': PHASE, 'created_utc': utc(), 'previous_reviewed_bundle_sha256': LIVE_BUNDLE,
        'local_sha256': local,
        'external_sha256': external,
        'activation_control': 'Disabled pending exact code review, current People proofs, sequencing authority and fresh pending-original audit and attestation.',
    }
    from byte_proofs import immutable_write
    archive = HERE/'implementation_history'/LIVE_BUNDLE
    immutable_write(archive/'code_bundle.json', checked_bytes(target, LIVE_BUNDLE)[0])
    immutable_write(archive/'root_runtime_review.json', old_review_raw)
    atomic_json(target, bundle)
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-version-integration', action='store_true')
    parser.add_argument('--wizard-finalizer-review-sha256')
    parser.add_argument('--q80-subset-receipt-sha256')
    parser.add_argument('--merged-manifest-sha256')
    parser.add_argument('--q80-successor-review-sha256')
    args = parser.parse_args()
    digests = (args.wizard_finalizer_review_sha256, args.q80_subset_receipt_sha256, args.merged_manifest_sha256, args.q80_successor_review_sha256)
    if args.freeze_version_integration:
        require(all(digests), 'Exact finalizer-review, Q80 receipt, merged manifest and successor-review digests are required')
        bundle = freeze(*digests)
    else:
        require(not any(value is not None for value in digests), 'Reviewed digests apply only when freezing')
        bundle = validate_bundle()
    print(json.dumps({'status': bundle['phase'], 'code_bundle_sha256': digest(HERE/'code_bundle.json'),
                      'local_files': len(bundle['local_sha256']), 'external_inputs': len(bundle['external_sha256'])}))


if __name__ == '__main__':
    main()
