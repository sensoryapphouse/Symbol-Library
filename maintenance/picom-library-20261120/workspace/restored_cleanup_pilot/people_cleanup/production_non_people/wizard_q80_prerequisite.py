"""Metadata-only binding of the reviewed v3 finalizer and finished Q80 pass.

This is not a replacement for the finalizer's exhaustive current-image proof.
The existing prerequisite subprocess still performs that proof under its locks.
No compression module is imported or executed by this module.
"""
import hashlib
import json
from pathlib import Path

from common import require
from publication_transaction import checked_bytes, exists

Q80_DIR = 'wizard_soccer_q80_candidate'
PUB_DIR = 'wizard_soccer_library_publication'
STAGED_REVIEW = 'root_staged_review_v6_20261113.json'
STAGED_REVIEW_SHA = 'f153f27997e2c88d5d88575fe10287d8e41776e67faaeeba9e90e5b1e305ef51'
BUILD_CODE_MAP_SHA = '0a6af23e89399d527cc261de377ff95c2b9b0317d62ab569128766e3ea818e15'
ARTIFACTS = ('code_manifest.json', 'root_review.json', 'execution_authorization.json',
             'input_plan.json', 'compression.sqlite', 'successor_receipt.json', 'run.py')
HELPERS = {
    'eligible_styles_q80_candidate/compress.py': '41f93560e8412158ea2963f79a9d29fe2273ee22ab0c5e97355a5038e34335fd',
    'wood_q80_delivery_20261106/publish_q80.py': '028d3b465feb033decac37127d93efeb2375eef7a308790e23693920a24baf2d',
    'original_people_compact_authority_candidate/adapter.py': 'ed3283b06aae336c188bc440dc34b32fa59ddbf6de5fcbfafbcee941aad93a90',
    'current_version_candidate/resolver.py': 'e10b36c70731c26a41bb8b842e91c6384e8edb193ff587f5b3dbec438a2b4ac1',
}
SETTINGS = dict(exact=True, format='WEBP', lossless=False, method=6, quality=80)


def no_sidecars(base):
    ledger = base/Q80_DIR/'compression.sqlite'
    require(not any(exists(Path(str(ledger)+suffix)) for suffix in ('-journal', '-wal', '-shm')),
            'Wizard/Soccer Q80 ledger has a recovery sidecar')


def closure(base, finalizer, finalizer_review):
    """Return actual verified pins and the exact subset used by the v3 proof."""
    q80, publication = base/Q80_DIR, base/PUB_DIR
    pins = {}

    def bind(path, expected=None, document=True):
        raw, sha, _ = checked_bytes(path, expected)
        require(pins.get(str(path), sha) == sha, 'Conflicting Wizard/Soccer Q80 pin')
        pins[str(path)] = sha
        return json.loads(raw) if document else raw

    stage = bind(q80/STAGED_REVIEW, STAGED_REVIEW_SHA)
    require(stage['reviewer'] == 'root'
            and stage['status'] == 'exact_staged_source_review_complete_no_live_adoption',
            'Missing exact staged Wizard/Soccer Q80 source review')
    code = {name: stage['reconstructed_future_source_sha256'][name]
            for name in ('publication.py', 'transaction.py')}
    require(finalizer['code_sha256'] == code
            and finalizer_review['code_sha256'] == code,
            'Finalizer is not the reviewed Q80 v3 source')
    authority_path = publication/'wizard_soccer_q80_authority.json'
    authority = bind(authority_path)
    require(set(authority) == {'schema', 'artifact_sha256'}
            and authority['schema'] == 'root-bound-wizard-soccer-q80-finalizer-inputs-v1'
            and set(authority['artifact_sha256']) == {str(q80/name) for name in ARTIFACTS},
            'Wizard/Soccer Q80 authority artifact scope differs')
    artifact_pins = authority['artifact_sha256']
    bridge = q80/'successors.py'
    bridge_sha = stage['reviewed_file_pins']['successors.py']
    dependencies = {
        'publish_q80.py': HELPERS['wood_q80_delivery_20261106/publish_q80.py'],
        str(base/'current_version_candidate/resolver.py'): HELPERS['current_version_candidate/resolver.py'],
        str(bridge): bridge_sha, str(authority_path): pins[str(authority_path)],
    }
    require(finalizer['dependency_sha256'] == dependencies,
            'Finalizer does not bind the exact Q80 authority and resolver')
    bind(bridge, bridge_sha, False)
    no_sidecars(base)
    docs = {name: bind(q80/name, artifact_pins[str(q80/name)], name.endswith('.json'))
            for name in ARTIFACTS}
    manifest, review = docs['code_manifest.json'], docs['root_review.json']
    execution, plan, receipt = (docs[name] for name in
                               ('execution_authorization.json', 'input_plan.json', 'successor_receipt.json'))
    expected_code = {str(base/name): sha for name, sha in HELPERS.items()}
    expected_code.update({str(q80/name): stage['reviewed_file_pins'][name]
                          for name in ('run.py', 'engine.py', 'plan.py', 'proof.py')})
    build_sha = hashlib.sha256(json.dumps(manifest['build_code_sha256'], sort_keys=True,
                               separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    require(manifest['schema'] == 'wizard-soccer-q80-code-manifest-v1'
            and manifest['code_sha256'] == expected_code and build_sha == BUILD_CODE_MAP_SHA
            and manifest['settings'] == SETTINGS
            and manifest['scope'] == dict(available=6178, held=12, batches=194, styles=['Wizard', 'Soccer player']),
            'Wizard/Soccer Q80 code, settings or scope differs')
    for path, sha in expected_code.items():
        bind(Path(path), sha, False)
    legacy_ref = manifest['legacy_finalization_authority']
    require(set(legacy_ref) == {'path', 'sha256'}
            and plan.get('legacy_authorization') == legacy_ref,
            'Wizard/Soccer Q80 plan names a different legacy finalization authority')
    legacy_path = Path(legacy_ref['path'])
    require(legacy_path.parent == base/'production_wizard_soccer/execution_approvals'
            and legacy_path.suffix == '.json', 'Unexpected legacy Q80 authority path')
    legacy = bind(legacy_path, legacy_ref['sha256'])
    require(legacy['approved'] is True and legacy['approved_by'] == 'root'
            and legacy['allowed_actions'] == ['finalize']
            and legacy['bundle_sha256'] == finalizer['legacy_bundle_sha256'],
            'Wizard/Soccer Q80 legacy finalization approval differs')
    require(review['approved'] is True and review['approved_by'] == 'root'
            and review['code_manifest_sha256'] == pins[str(q80/'code_manifest.json')]
            and set(review['allowed_actions']) == {'build-plan', 'run', 'verify'}
            and execution['approved'] is True and execution['approved_by'] == 'root'
            and execution['code_manifest_sha256'] == pins[str(q80/'code_manifest.json')]
            and execution['root_review_sha256'] == pins[str(q80/'root_review.json')]
            and execution['input_plan_sha256'] == pins[str(q80/'input_plan.json')]
            and set(execution['allowed_actions']) == {'run', 'verify'},
            'Wizard/Soccer Q80 root code or execution authority differs')
    expected_authority = dict(code_sha256=expected_code, build_code_sha256=manifest['build_code_sha256'],
                              settings=SETTINGS)
    for key, name in (('code_manifest', 'code_manifest.json'), ('root_review', 'root_review.json'),
                      ('input_plan', 'input_plan.json'), ('execution_authorization', 'execution_authorization.json')):
        expected_authority[key] = dict(path=str(q80/name), sha256=pins[str(q80/name)])
    require(plan['schema'] == 'wizard-soccer-current-q80-input-plan-v1'
            and (plan['available'], plan['generation_held'], plan['scope_total'], plan['published_batches'])
                == (6178, 12, 6190, 194)
            and len(plan['inputs']) == len(plan['original_people_proofs']) == 6178
            and len(set(plan['held'])) == 12
            and plan['code_sha256'] == expected_code
            and plan['build_code_sha256'] == manifest['build_code_sha256'],
            'Wizard/Soccer Q80 plan is not complete or code-bound')
    require(receipt['schema'] == 'wizard-soccer-q80-successor-receipt-v1'
            and receipt['complete'] is True and receipt['available'] == 6178 and receipt['generation_held'] == 12
            and receipt['settings'] == SETTINGS and receipt['authority'] == expected_authority
            and receipt['ledger'] == dict(path=str(q80/'compression.sqlite'),
                                         sha256=pins[str(q80/'compression.sqlite')])
            and set(receipt['entries']) == set(receipt['current_proof']['current']) == set(plan['inputs'])
            and set(receipt['current_proof']['originals']) == set(plan['original_people_proofs'])
            and all(row['state'] in ('replaced', 'retained') for row in receipt['entries'].values())
            and receipt['replaced'] == sum(row['state'] == 'replaced' for row in receipt['entries'].values())
            and receipt['retained'] == sum(row['state'] == 'retained' for row in receipt['entries'].values())
            and receipt['replaced'] + receipt['retained'] == 6178,
            'Wizard/Soccer Q80 receipt lacks complete terminal coverage')
    no_sidecars(base)
    for path, sha in pins.items():
        checked_bytes(Path(path), sha)
    return pins, {str(authority_path): pins[str(authority_path)], str(bridge): bridge_sha, **artifact_pins}


def bind_proof(supplemental, approval, proof_pins):
    require(supplemental.get('current_q80_target_count') == 6178
            and supplemental.get('current_q80_inputs_sha256') == proof_pins
            and all(approval.get('approved_inputs', {}).get(path) == sha for path, sha in proof_pins.items()),
            'Wizard/Soccer proof or gate approval omits exact completed Q80 inputs')
