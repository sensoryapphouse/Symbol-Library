"""Bind both authoritative People completion closures before the Non-People byte audit."""
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

from common import HERE, LIBRARY, read, require, validate_bundle
import wizard_q80_prerequisite as ws_q80

PHASE3_SHA = 'f251c68e3175c6a6f09c1ec398da32cc8d2a9e1cf7f02f65d992b3838cc1d85a'
WIZARD_SHA = '5a30d21d4072043d12965eaec288407d65207a643c2a54aa533a53758a5a71a5'
WIZARD_REVIEW_FILENAME = 'parent_revision4_review.json'
WIZARD_REVIEW_SHA = '7e42976f59278cacc08752268b24ae42214a4a46b8a1eb27f6604233186b836d'
PHASE3_SCOPE = 57073
WIZARD_SCOPE = 6190
WIZARD_AVAILABLE = 6178
WIZARD_HELD = 12
WIZARD_STATUS = 'available_cleanup_complete'
WIZARD_PROOF_SCHEMA = 'paired-supplemental-library-publication-proof-v3'
PUBLICATION_DIR = 'wizard_soccer_library_publication'
HISTORICAL_BRIDGE = 'historical_publication_bridge.py'
HISTORICAL_BRIDGE_SHA = '3c78b19f711683a61b58f27bb86ab820660a69dd8c6acb13c7721073a3d8a34e'
COMPACT_DIR = 'original_people_compact_authority_candidate'
HISTORICAL_PUBLICATION_SHA = 'cb541f4d2e240ba81d8049a760801fc4ef5e8bd0709d44c1997b2dba8180c65e'
CURRENT_VERSION_DIR = 'current_version_candidate'
Q80_DIR = 'eligible_styles_q80_candidate'
Q80_RECEIPT = 'q80_current_successor_receipt.json'
Q80_RECEIPT_SCHEMA = 'picom-original-people-current-q80-subset-v2'
Q80_SUCCESSOR_SCOPE = {style + '/09 Pronouns/his.webp' for style in (
    'Doll', 'Friendly aliens', 'Monkey', 'Monster', 'Robot', 'Teddy bear')}
Q80_SUCCESSOR_PINS = {
    'repaired_six_q80.py': 'fb6ad5f9ef71f248fcb84ec7cd2590d29d865a279df4a672a6680a509b2b646b',
    'repaired_six_input_plan.json': 'dd14829c71c1247bd1a0ce0d63e1fad0d8d54ceb938800e122638cd18266cbd1',
    'repaired_six_successor_receipt.json': 'cc3b07c65143ae9febcaf363daaaaf67d858166904b2060547c04fbd0b2e86d8',
}
Q80_HISTORICAL_RECEIPT_SHA = 'cd43c2a28904d182b2a3cdd070fda39e8ef45dcd4792ff460ce98482f4d727a0'
Q80_HISTORICAL_JOURNAL_SHA = '897f4271c20c54a636d3f20669f04aabacb52cb284749c502d7e661c2d613517'
Q80_HISTORICAL_REPORT_SHA = '78f8f14c7ff8de4968fdbb2037142274d4887da86255741956a222ead2fecfc6'
Q80_EXTENSION = 'current-delivery-q80-extension.jsonl'
Q80_OVERLAY_SHA = 'c6b88dc52e5aa36661e4007825b7ed88c26df51556ef7c7952deb98204e8ca25'
Q80_EXTENSION_SHA = 'dd97231d1456bff084bb220cc8875901a5ca0c4b62d3b7d8488f7cd3d9f42a81'
ORIGINAL_OVERLAY_TOOL = 'workspace_cleanup_20261106/current_delivery_overlay.py'
ORIGINAL_OVERLAY_TOOL_SHA = 'c001b3bb6f9fcf8ae1fabfb22f54c839f76c7ba881ffda9845129af23a7c23e8'
ORIGINAL_OVERLAY_SCHEMA = 'picom-library-current-delivery-overlay-v1'
ORIGINAL_OVERLAY_COUNTS = {'original_people_accepted': 8987, 'wood_q80': 3094}
PUBLICATION_ARTIFACTS = {'final_delivery_manifest.jsonl', 'index.html',
                         'held_generation_dispositions.jsonl', 'byte_checks.json'}
WIZARD_SCOPE_FIELDS = dict(scope_total=WIZARD_SCOPE, available_total=WIZARD_AVAILABLE, held_total=WIZARD_HELD,
                           available_cleanup_complete=True, full_generation_complete=False)
GENERATION_DB = LIBRARY.parent/'Second batch/_runtime/batch/wizard-soccer-inventory-20261105.sqlite'
GENERATION_WAL = Path(str(GENERATION_DB)+'-wal')
METADATA_SUFFIXES = {'.json', '.jsonl', '.py', '.txt', '.md', '.cjs', '.html', '.patch', '.csv'}


def completion_paths(root):
    base = root.parent
    return {
        'people_completion_pointer': base/'final_people_verification_source_revisions_20261105/latest_status.json',
        'wizard_completion_pointer': base/PUBLICATION_DIR/'proofs/latest_status.json',
        'source_byte_audit_pointer': root/'activation_audit/latest_status.json',
    }


def validate_overlay_paths(root, overlay):
    require(all(overlay.get(key) == str(path) for key, path in completion_paths(root).items()),
            'Activation overlay uses alternate proof pointers')


def is_metadata(path):
    historical_logs = HERE.parent/'source_revisions_20261105'
    return path.suffix in METADATA_SUFFIXES or path in (
        historical_logs/'parent_phase1_tests.log', historical_logs/'test_results.log',
        GENERATION_DB, GENERATION_WAL, HERE.parent/Q80_DIR/'compression.sqlite',
        HERE.parent/ws_q80.Q80_DIR/'compression.sqlite')


def bind_metadata(pins, path, expected):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and is_metadata(path), 'Expected metadata closure path')
    require(isinstance(expected, str) and re.fullmatch(r'[a-f0-9]{64}', expected), 'Invalid metadata SHA-256')
    require(pins.get(str(path), expected) == expected, 'Conflicting prerequisite metadata digest')
    pins[str(path)] = expected


def bound_bytes(path, pins, expected=None):
    require(not any(parent.is_symlink() for parent in path.parents)
            and stat.S_ISREG(path.lstat().st_mode), 'Unsafe prerequisite metadata path: '+str(path))
    raw = path.read_bytes()
    from byte_proofs import hash_bytes
    digest = hash_bytes(raw)
    require(expected is None or digest == expected, 'Prerequisite metadata digest differs: '+str(path))
    bind_metadata(pins, path, digest)
    return raw


def read_bound(path, pins, expected=None):
    return json.loads(bound_bytes(path, pins, expected))


def completion_fields(wizard):
    if wizard:
        return dict(status=WIZARD_STATUS, completion_claim=False, **WIZARD_SCOPE_FIELDS)
    return dict(status='complete', completion_claim=True)


def matches(document, fields):
    return all(document.get(key) == value for key, value in fields.items())


def read_pointer(path, pins, wizard=False):
    pointer = read_bound(path, pins)
    fields = completion_fields(wizard)
    require(matches(pointer, fields), 'Authoritative People prerequisite is missing, failed or on hold: '+str(path))
    invocation = pointer['invocation']
    require(re.fullmatch(r'[a-f0-9]{32}', invocation), 'Unsafe prerequisite proof invocation')
    if wizard:
        expected = path.parent/invocation/(WIZARD_STATUS+'.json')
    else:
        pass_id = pointer['pass_id']
        require(Path(pass_id).name == pass_id and pass_id not in ('.', '..'), 'Unsafe prerequisite pass ID')
        expected = path.parent/'passes'/pass_id/'proofs'/(invocation+'.json')
    require(pointer['proof_path'] == str(expected), 'Wrong prerequisite immutable proof path')
    proof = read_bound(expected, pins, pointer['proof_sha256'])
    require(matches(proof, fields) and proof.get('invocation') == invocation,
            'Stale or incomplete prerequisite proof invocation')
    return {'path': str(path), **pointer}, proof


def verify_current_pointer(root, descriptor, key, pins):
    expected = completion_paths(root)[key]
    require(descriptor['path'] == str(expected) and str(expected) in pins,
            'Attestation omits authoritative prerequisite pointer')
    current = read(expected)
    require(matches(current, completion_fields(key=='wizard_completion_pointer'))
            and all(current.get(k) == descriptor[k] for k in ('invocation', 'proof_path', 'proof_sha256'))
            and pins.get(descriptor['proof_path']) == descriptor['proof_sha256'],
            'Current prerequisite pointer no longer names the attested completion')


def held_path(root, invocation):
    require(isinstance(invocation, str) and re.fullmatch(r'[a-f0-9]{32}', invocation),
            'Unsafe Wizard publication invocation')
    return completion_paths(root)['wizard_completion_pointer'].parent/invocation/'held_generation_dispositions.jsonl'


def original_overlay_path():
    return LIBRARY/'_manifest/current-delivery.jsonl'


def publication_approval(root, legacy, supplemental, pins):
    ref = legacy.get('wizard_publication_approval')
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'},
            'Legacy sequencing approval omits the explicit Wizard publication gate approval')
    path = Path(ref['path'])
    require(path.is_absolute() and path.suffix == '.json', 'Wizard publication approval must be absolute JSON')
    approval = read_bound(path, pins, ref['sha256'])
    require(approval.get('approved') is True and approval.get('approved_by') == 'root'
            and approval.get('publication_bundle_sha256') == pins[str(root.parent/PUBLICATION_DIR/'bundle.json')]
            and 'nonpeople_gate' in approval.get('allowed_actions', [])
            and isinstance(approval.get('execution_actor'), str) and approval['execution_actor'].strip(),
            'Wizard publication gate needs its explicit root execution approval')
    review = root.parent/PUBLICATION_DIR/'root_review.json'
    require(approval.get('root_review') == supplemental.get('root_review') ==
            {'path': str(review), 'sha256': pins[str(review)]},
            'Wizard gate approval and proof must bind the same exact finalization review')
    reviewed_inputs = approval.get('approved_inputs', {})
    current = supplemental['current_original_people_publication_sha256']
    loader = str(root.parent/ORIGINAL_OVERLAY_TOOL)
    overlay = str(original_overlay_path())
    require(current.get(loader) == reviewed_inputs.get(loader) == ORIGINAL_OVERLAY_TOOL_SHA
            and overlay in current and current[overlay] == reviewed_inputs.get(overlay),
            'Wizard publication gate approval omits the reviewed original-People publication inputs')
    ws_pins, proof_pins = ws_q80.closure(root.parent,
        read(root.parent/PUBLICATION_DIR/'bundle.json'), read(review))
    external = read(root/'code_bundle.json')['external_sha256']
    require(all(external.get(path) == sha for path, sha in ws_pins.items()),
            'Non-People bundle omits completed Wizard/Soccer Q80 authority')
    for path, sha in ws_pins.items():
        bind_metadata(pins, path, sha)
    ws_q80.bind_proof(supplemental, approval, proof_pins)
    return ref


def compact_transition(root, pins):
    folder = root.parent/COMPACT_DIR
    path = folder/'receipts.py'
    bundle = read(root/'code_bundle.json')
    expected = bundle['external_sha256'][str(path)]
    bound_bytes(path, pins, expected)
    spec = importlib.util.spec_from_file_location('_compact_original_people_receipts', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bridge_path = root.parent/PUBLICATION_DIR/HISTORICAL_BRIDGE
    bound_bytes(bridge_path, pins, HISTORICAL_BRIDGE_SHA)
    require(bundle['external_sha256'][str(bridge_path)] == HISTORICAL_BRIDGE_SHA,
            'Runtime bundle does not bind the historical publication bridge')
    bridge_spec = importlib.util.spec_from_file_location('_historical_publication_bridge', bridge_path)
    bridge = importlib.util.module_from_spec(bridge_spec)
    bridge_spec.loader.exec_module(bridge)
    _, retired, receipts, archive_bindings = bridge.completed(module, folder)
    for name, checksum in archive_bindings.items():
        require(bundle['external_sha256'][name] == checksum, 'Runtime bundle omits the exact publication binding')
        bind_metadata(pins, name, checksum)
    for name, checksum in receipts.items():
        bind_metadata(pins, name, checksum)
    return retired, receipts


def bind_historical_metadata(pins, retired, path, checksum):
    if str(path) in retired:
        require(retired[str(path)] == checksum, 'Retirement does not bind the exact historical pin')
    else:
        bind_metadata(pins, path, checksum)


def bind_original_publication(root, supplemental, people_pointer, historical_csvs, receipts, pins):
    current = supplemental['current_original_people_publication_sha256']
    path = original_overlay_path()
    loader = root.parent/ORIGINAL_OVERLAY_TOOL
    raw = bound_bytes(path, pins, current[str(path)])
    header = json.loads(raw.split(b'\n', 1)[0])
    require(header['schema'] == ORIGINAL_OVERLAY_SCHEMA and header['publication_counts'] == ORIGINAL_OVERLAY_COUNTS
            and header['path_count'] == sum(ORIGINAL_OVERLAY_COUNTS.values()) == len(raw.splitlines())-1,
            'Current original-People overlay schema or coverage differs')
    csv_pins = {str(path.parent/name): digest for name, digest in header['historical_csv_sha256'].items()}
    require(len(csv_pins) == 17 and csv_pins == historical_csvs,
            'Current original-People overlay differs from the 17 historical CSV pins')
    evidence = header['evidence']
    expected_paths = {
        'historical_people_proof': Path(people_pointer['proof_path']),
        'nonwood_publication_summary': root.parent/'workspace_cleanup_20261106/finished_people_publication_summary.json',
        'wood_q80_publication_summary': root.parent/'wood_q80_delivery_20261106/publication_summary.json',
        'wood_q80_publication_manifest': root.parent/'wood_q80_delivery_20261106/publication_manifest.jsonl',
        'historical_accepted_catalog': root.parent/'final_people_delivery_source_revisions_20261105/accepted_deliveries.json',
    }
    require(set(evidence) == set(expected_paths), 'Current original-People publication evidence set differs')
    historical = evidence['historical_people_proof']
    require(historical['sha256'] == people_pointer['proof_sha256'],
            'Current original-People overlay names a different historical proof')
    for name, expected in expected_paths.items():
        require(evidence[name]['path'] == str(expected), 'Unexpected original publication evidence path: '+name)
    expected = {str(path): pins[str(path)], str(loader): ORIGINAL_OVERLAY_TOOL_SHA, **csv_pins,
                **{ref['path']: ref['sha256'] for ref in evidence.values()}}
    expected.update(receipts)
    require(current == expected, 'Current original-People publication dependency closure differs')
    for name, digest in expected.items():
        bind_metadata(pins, name, digest)


def policy_binding(root, approval, wizard_pointer, supplemental, pins):
    ref = approval.get('non_people_policy')
    require(isinstance(ref,dict),'Non-People waits for full generation unless separately authorized')
    path = Path(ref['path'])
    require(path.is_absolute() and path.suffix=='.json','Root sequencing policy must be absolute JSON metadata')
    policy = read_bound(path,pins,ref['sha256'])
    require(policy==dict(schema='root-non-people-sequencing-v1',approved_by='root',
        decision='proceed_after_available_cleanup',wizard_bundle_sha256=WIZARD_SHA,
        non_people_bundle_sha256=pins[str(root/'code_bundle.json')],
        wizard_proof_sha256=wizard_pointer['proof_sha256'],held_sha256=supplemental['held_sha256']),
        'Root sequencing policy does not authorize this exact available proof and held partition')
    return ref


def current_q80_evidence(root, approval, supplemental, external, pins):
    base = root.parent
    candidate = base/CURRENT_VERSION_DIR
    compression = base/Q80_DIR
    extension = LIBRARY/'_manifest'/Q80_EXTENSION
    evidence = (candidate/'q80_current.py', candidate/'resolver.py',
                compression/'compress.py', compression/'readiness.json',
                compression/'continue_unaffected.py', compression/'semantic_revisions.json',
                base/'workspace_cleanup_20261106/semantic_repair_overlap_reconciliation_20261106.json',
                extension)
    for path in evidence:
        bind_metadata(pins, path, external[str(path)])
    repair_pins = {str(path): pins[str(path)] for path in (evidence[1], *evidence[4:7])}
    require(supplemental.get('reviewed_semantic_repair_count') == 11
            and supplemental.get('historical_batch_publication_bundle_sha256') == HISTORICAL_PUBLICATION_SHA
            and supplemental.get('reviewed_semantic_repair_inputs_sha256') == repair_pins,
            'Wizard/Soccer proof omits the current reviewed repair versions')
    receipt_path = candidate/Q80_RECEIPT
    expected = external[str(receipt_path)]
    require(approval.get('approved_inputs', {}).get(str(receipt_path)) == expected,
            'Root gate approval must bind the exact current Q80 subset receipt')
    receipt = read_bound(receipt_path, pins, expected)
    expected_successor_pins = {str(compression/name): sha for name, sha in Q80_SUCCESSOR_PINS.items()}
    expected_successor_pins[str(candidate/'q80_current_receipt.json')] = Q80_HISTORICAL_RECEIPT_SHA
    require(receipt['q80_successor_inputs_sha256'] == expected_successor_pins
            and all(external.get(path) == sha for path, sha in expected_successor_pins.items()),
            'Current Q80 proof omits exact reviewed successor authority')
    bind_metadata(pins, candidate/'q80_successors.py', external[str(candidate/'q80_successors.py')])
    for path, sha in expected_successor_pins.items():
        bind_metadata(pins, path, sha)
    counts = receipt['q80_counts']
    require(receipt['schema'] == Q80_RECEIPT_SCHEMA and receipt['traversal_finished'] is True
            and receipt['full_q80_compression_complete'] is False
            and receipt['historical_overlay_sha256'] == pins[str(original_overlay_path())] == Q80_OVERLAY_SHA
            and receipt['phase1_receipt_sha256'] == pins[str(extension)] == Q80_EXTENSION_SHA
            and receipt['repair_authority'] == {k: v for k, v in repair_pins.items() if k != str(evidence[1])}
            and receipt['historical_overlay_rows'] == 12081 and receipt['q80_phase1_rows'] == 1599
            and receipt['q80_plan_rows'] == sum(counts.values()) == 27596
            and counts == {'replaced': 27549, 'retained': 41, 'reviewed_repair_q80_successor': 6}
            and set(receipt['q80_successors']) == set(receipt['historical_q80_deferrals']) == Q80_SUCCESSOR_SCOPE
            and receipt['q80_deferrals'] == {}
            and receipt['q80_journal_sha256'] == Q80_HISTORICAL_JOURNAL_SHA
            and receipt['traversal_report_sha256'] == Q80_HISTORICAL_REPORT_SHA
            and receipt['current_library_byte_checks'] == 38085
            and receipt['repaired_original_people_byte_checks'] == 3,
            'Current original-People Q80 subset proof has wrong authority or scope')
    bind_metadata(pins, compression/'unaffected_progress.json', receipt['traversal_report_sha256'])
    bind_metadata(pins, compression/'compression.sqlite', receipt['q80_journal_sha256'])
    return receipt


def closure(root, wizard_approval_path):
    """Metadata only. The authoritative Wizard gate performs both exhaustive checks."""
    paths = completion_paths(root)
    base = root.parent
    phase3 = base/'source_revisions_20261105_phase3'
    wizard = base/'production_wizard_soccer'
    publication = base/PUBLICATION_DIR
    pins = {}
    bind_metadata(pins, phase3/'phase3_bundle.json', PHASE3_SHA)
    bind_metadata(pins, wizard/'bundle.json', WIZARD_SHA)
    review = read_bound(wizard/WIZARD_REVIEW_FILENAME, pins, WIZARD_REVIEW_SHA)
    require(review.get('reviewer')=='root' and review.get('bundle_sha256')==WIZARD_SHA and
            review.get('status')=='revision4_code_approved_population_execution_still_disabled',
            'Wizard held-scope code needs current independent root review')
    external = read(root/'code_bundle.json')['external_sha256']
    publication_bundle_path, publication_review_path = publication/'bundle.json', publication/'root_review.json'
    publication_sha = external[str(publication_bundle_path)]
    publication_bundle = read_bound(publication_bundle_path, pins, publication_sha)
    publication_review = read_bound(publication_review_path, pins, external[str(publication_review_path)])
    require(publication_bundle['schema'] == 'ws-library-publication-bundle-v1'
            and publication_bundle['legacy_bundle_sha256'] == WIZARD_SHA
            and set(publication_bundle['code_sha256']) == {'publication.py', 'transaction.py'}
            and publication_review['schema'] == 'root-wizard-library-publication-review-v1'
            and publication_review['reviewed_by'] == 'root'
            and publication_review['publication_bundle_sha256'] == publication_sha
            and publication_review['code_sha256'] == publication_bundle['code_sha256']
            and publication_review['allowed_actions'] == ['finalize', 'nonpeople_gate']
            and publication_review['approved_for_finalization_and_nonpeople_gate'] is True
            and publication_review['approved_for_bounded_batch_publication'] is False,
            'Wizard publication code needs the exact independent root review')
    for name, digest in publication_bundle['code_sha256'].items():
        bind_metadata(pins, publication/name, digest)
    from common import digest
    bind_metadata(pins, root/'code_bundle.json', digest(root/'code_bundle.json'))
    people_pointer, people = read_pointer(paths['people_completion_pointer'], pins)
    wizard_pointer, supplemental = read_pointer(paths['wizard_completion_pointer'], pins, wizard=True)
    approval_path = Path(wizard_approval_path).resolve(strict=True)
    approval = read_bound(approval_path, pins)
    require(approval.get('approved') is True and approval.get('approved_by') == 'root'
            and approval.get('bundle_sha256') == WIZARD_SHA
            and 'nonpeople_gate' in approval.get('allowed_actions', []),
            'Wizard available cleanup byte gate needs its explicit root execution approval')
    policy_ref = policy_binding(root, approval, wizard_pointer, supplemental, pins)
    original_approval = read_bound(phase3/'root_execution_approval.json', pins)
    require(original_approval.get('approved') is True and original_approval.get('approved_by') == 'root'
            and original_approval.get('phase3_bundle_sha256') == PHASE3_SHA,
            'Original People execution approval changed')
    require(people['schema'] == 'source-version-aware-people-proof-v1' and people['phase3_bundle_sha256'] == PHASE3_SHA
            and people['pass_id'] == people_pointer['pass_id'] and people['immutable_proof_path'] == people_pointer['proof_path']
            and people['failed_file_records'] == people['failed_dependencies'] == 0,
            'Original People proof is incompatible or has failed checks')
    require(supplemental['schema'] == WIZARD_PROOF_SCHEMA
            and supplemental['legacy_bundle_sha256'] == WIZARD_SHA
            and supplemental['publication_bundle_sha256'] == publication_sha
            and supplemental['library_root'] == str(LIBRARY) and supplemental['library_written'] is True
            and supplemental['viewer_exact_bindings_verified'] is True
            and supplemental['originals_byte_checked_this_invocation']==supplemental['deliveries_byte_checked_this_invocation']==WIZARD_AVAILABLE
            and supplemental['held_absence_checked_this_invocation']==WIZARD_HELD,
            'Wizard/Soccer proof is incompatible or lacks exact available byte and held coverage')
    retired, compact_receipts = compact_transition(root, pins)
    require(people['scope_total']==people['originals_byte_checked_this_invocation']
            ==people['deliveries_byte_checked_this_invocation']==PHASE3_SCOPE,
            'Incomplete original People prerequisite source/delivery coverage')
    people_pass = Path(people_pointer['proof_path']).parent.parent
    bind_historical_metadata(pins, retired, people_pass/'plan.json', people['plan_sha256'])
    bind_historical_metadata(pins, retired, people_pass/'planned_rows.jsonl', people['planned_rows_sha256'])
    for field, prefix in (('checkpoint', 'byte_checks_'), ('dependency_checkpoint', 'dependency_checks_')):
        expected = people_pass/(prefix+people['invocation']+'.jsonl')
        require(people[field+'_path'] == str(expected), 'Original People receipt is outside its invocation')
        bind_historical_metadata(pins, retired, expected, people[field+'_sha256'])
    for path, sha in people['metadata_sha256'].items():
        bind_historical_metadata(pins, retired, path, sha)

    delivery = base/'final_people_delivery_source_revisions_20261105'
    summary = read_bound(delivery/'summary.json', pins)
    require(summary['scope_total'] == PHASE3_SCOPE and summary['phase3_bundle_sha256'] == PHASE3_SHA
            and summary['verification_proof_sha256'] == people_pointer['proof_sha256']
            and summary['verification_proof_path'] == people_pointer['proof_path']
            and summary['source_checkpoint_sha256'] == people['checkpoint_sha256'],
            'Original People catalog is stale or bound to another proof')
    artifacts = summary['artifacts_sha256']
    require(set(artifacts) == {'all_people_dispositions.jsonl', 'accepted_deliveries.json', 'index.html'},
            'Original People delivery artifact set differs')
    for name, sha in artifacts.items():
        bind_historical_metadata(pins, retired, delivery/name, sha)
    viewer = read_bound(delivery/'viewer_verification.json', pins)
    require(viewer['summary_sha256'] == pins[str(delivery/'summary.json')]
            and viewer['exact_bindings_files_and_artifact_hashes'] is True and not viewer['errors'],
            'Original People viewer verification is missing or stale')

    prerequisites = supplemental['prerequisites']
    original = prerequisites['original_people']
    require(original['proof_sha256'] == people_pointer['proof_sha256']
            and original['phase3_bundle_sha256'] == PHASE3_SHA
            and original['summary_sha256'] == pins[str(delivery/'summary.json')]
            and original['catalog_sha256'] == artifacts['all_people_dispositions.jsonl']
            and prerequisites['bundle_sha256'] == WIZARD_SHA,
            'Wizard proof is stale against current original People completion')
    artifact_pins = supplemental['artifacts_sha256']
    require(set(artifact_pins) == PUBLICATION_ARTIFACTS
            and artifact_pins['held_generation_dispositions.jsonl'] == supplemental['held_sha256'],
            'Wizard publication catalog/checkpoint set differs')
    invocation_root = Path(wizard_pointer['proof_path']).parent
    for name, digest in artifact_pins.items():
        bind_metadata(pins, invocation_root/name, digest)
    for key in ('approval', 'legacy_finalization_approval'):
        ref = supplemental[key]
        bind_metadata(pins, ref['path'], ref['sha256'])
    publication_ref = publication_approval(root, approval, supplemental, pins)
    historical_csvs = {name: digest for name, digest in people['metadata_sha256'].items()
                       if Path(name).parent == LIBRARY/'_manifest' and Path(name).suffix == '.csv'}
    bind_original_publication(root, supplemental, people_pointer, historical_csvs, compact_receipts, pins)
    receipt = current_q80_evidence(root, approval, supplemental, external, pins)

    generation = prerequisites['generation']
    held = read_held(root,pins)
    require(generation['held']==held and generation['absent_generation_wal']==str(GENERATION_WAL) and
            generation['full_generation_complete'] is False,
            'Wizard held artifact differs from the proof generation snapshot')
    require(supplemental['publication_receipts_sha256'] and supplemental['retained_dependencies_sha256'],
            'Wizard publication proof lacks completion receipts or retained dependencies')
    for name, checksum in original['authority_sha256'].items():
        bind_historical_metadata(pins, retired, name, checksum)
    for group in (generation['metadata_sha256'], supplemental['publication_receipts_sha256'],
                  supplemental['retained_dependencies_sha256']):
        for path, digest in group.items():
            # The reviewed Wizard subprocess freshly verifies the image files.
            # Active Non-People guards bind only immutable metadata.
            if is_metadata(Path(path)):
                bind_metadata(pins, path, digest)
    database_bound = False
    for path in sorted(pins):
        artifact = Path(path)
        if artifact.parent == wizard/'authorities':
            capsule = read_bound(artifact, pins, pins[path])
            authorities = capsule['authority_sha256']
            require(authorities.get(str(GENERATION_DB))==generation['metadata_sha256'][str(GENERATION_DB)] and
                    capsule['absent_paths']==[str(GENERATION_WAL),*(r['target'] for r in held)],
                    'Wizard authority omits the exact generation DB, WAL state or held target absences')
            database_bound = True
            for name, sha in authorities.items():
                if sha is not None and is_metadata(Path(name)):
                    bind_historical_metadata(pins, retired, name, sha)
    require(database_bound, 'Wizard proof omits generation authority capsules')
    verify_generation_metadata(pins,root)
    generation_closeout = approval['generation_closeout']
    require(generation_closeout==prerequisites['generation_closeout'],'Wizard approval names a different generation closeout')
    bind_metadata(pins, generation_closeout['path'], generation_closeout['sha256'])
    for path, expected in ((phase3/'phase3_bundle.json', PHASE3_SHA), (wizard/'bundle.json', WIZARD_SHA)):
        bundle = read_bound(path, pins, expected)
        groups = ('phase3_code_sha256', 'frozen_dependencies_sha256') if path.parent == phase3 else ('code_sha256', 'dependency_sha256')
        for group in groups:
            for name, sha in bundle[group].items():
                bound = Path(name)
                if not bound.is_absolute():
                    bound = path.parent/bound
                if bound.suffix in METADATA_SUFFIXES:
                    bind_metadata(pins, bound, sha)
    return {'people_pointer': people_pointer, 'wizard_pointer': wizard_pointer, 'sequencing_policy': policy_ref,
            'wizard_publication_approval': publication_ref,
            'wizard_scope': WIZARD_SCOPE_FIELDS, 'q80_subset_receipt': receipt, 'metadata_sha256': pins}


def read_held(root,pins):
    pointer_path = completion_paths(root)['wizard_completion_pointer']
    pointer_pin = pins.get(str(pointer_path))
    require(isinstance(pointer_pin, str), 'Attestation omits Wizard publication pointer')
    pointer = read_bound(pointer_path, {}, pointer_pin)
    path = held_path(root, pointer['invocation'])
    expected = pins.get(str(path))
    require(isinstance(expected,str),'Attestation omits Wizard held disposition artifact')
    raw = bound_bytes(path, {}, expected)
    held=[json.loads(line) for line in raw.splitlines()]
    require(len(held)==len({r['target_id'] for r in held})==len({r['target'] for r in held})==WIZARD_HELD and
        all(r['disposition']=='generation_held' and r['target_absent'] is True for r in held),
        'Attested Wizard held disposition scope differs')
    return held


def held_destinations(row):
    relative = Path(row['relative_target'])
    style = {'106': 'Wizard', '107': 'Soccer player'}.get(row['target_id'].partition(':')[0])
    require(style is not None and relative.parts[:2] == ('People', style)
            and len(relative.parts) >= 3 and '..' not in relative.parts and relative.suffix == '.webp'
            and str(relative) == row['relative_target'], 'Unsafe held Wizard/Soccer relative target')
    original = LIBRARY.parent/relative
    require(row['target'] == str(original), 'Held Wizard/Soccer People path differs')
    return original, LIBRARY.joinpath(*relative.parts[1:])


def require_absent(path, message):
    try:
        Path(path).lstat()
    except FileNotFoundError:
        return
    raise ValueError(message)


def verify_generation_metadata(pins,root=HERE):
    require(str(GENERATION_DB) in pins, 'Attestation omits the Wizard generation DB digest')
    require(str(GENERATION_WAL) not in pins, 'Wizard generation DB WAL presence changed')
    require_absent(GENERATION_WAL, 'Wizard generation DB WAL presence changed')
    journal = root.parent/Q80_DIR/'compression.sqlite'
    require(str(journal) in pins, 'Attestation omits the Q80 journal')
    for suffix in ('-journal', '-wal', '-shm'):
        require_absent(journal.with_name(journal.name + suffix), 'Q80 journal sidecar appeared')
    require(str(root.parent/ws_q80.Q80_DIR/'compression.sqlite') in pins,
            'Attestation omits the Wizard/Soccer Q80 ledger')
    ws_q80.no_sidecars(root.parent)
    for row in read_held(root,pins):
        for target in held_destinations(row):
            require(not any(path.is_symlink() for path in target.parents),
                    'Held Wizard/Soccer target has a symlink ancestor: '+str(target))
            require_absent(target, 'Held Wizard/Soccer target appeared: '+str(target))


def audit_prerequisites(wizard_approval_path):
    # Wizard runs in its own interpreter and acquires the shared worker outside the NP worker.
    from activation import reviewed_context
    overlay, review_sha = reviewed_context()
    require(overlay['enabled'] is False, 'Prerequisite byte validation requires runtime disabled')
    validate_bundle()
    result = closure(HERE, wizard_approval_path)
    bind_metadata(result['metadata_sha256'], HERE/'root_runtime_review.json', review_sha)
    from active_attestation import verify_bound_files
    verify_bound_files(result['metadata_sha256'])
    priority = os.getpriority(os.PRIO_PROCESS, 0)
    if priority < 10:
        os.nice(10-priority)
    require(os.getpriority(os.PRIO_PROCESS, 0) == 10, 'Run both prerequisite byte verifiers at actual nice 10')
    # Neither helper is called with the worker held by Non-People.
    candidate = HERE.parent/CURRENT_VERSION_DIR
    receipt_path = candidate/Q80_RECEIPT
    q80 = subprocess.run(['/usr/bin/nice', '-n', '9', sys.executable, '-B', str(candidate/'q80_current.py'),
                          '--receipt', str(receipt_path), '--receipt-sha256', result['metadata_sha256'][str(receipt_path)]],
                         capture_output=True, text=True)
    require(q80.returncode == 0, 'Current original-People Q80 subset check failed: '+q80.stderr[-3000:])
    require(json.loads(q80.stdout) == result['q80_subset_receipt'], 'Current Q80 proof differs from approved receipt')
    executable = HERE.parent/PUBLICATION_DIR/HISTORICAL_BRIDGE
    checked = run_helper(executable, 'publish', 'nonpeople_gate',
                         '--approval', result['wizard_publication_approval']['path'],
                         '--legacy-approval', str(Path(wizard_approval_path).resolve()))
    require(checked == dict(ready=True, original_phase3_complete=True, activation_performed=False, **completion_fields(True)),
            'Authoritative original People and Wizard/Soccer Library cleanup checks did not pass')
    verify_bound_files(result['metadata_sha256'])
    verify_generation_metadata(result['metadata_sha256'], HERE)
    return result



def run_helper(executable, *arguments):
    run = subprocess.run([sys.executable, '-B', str(executable), *arguments],
                         capture_output=True, text=True)
    require(run.returncode == 0, f'Authoritative prerequisite failed ({executable.name}): '+run.stderr[-3000:])
    return json.loads(run.stdout)
