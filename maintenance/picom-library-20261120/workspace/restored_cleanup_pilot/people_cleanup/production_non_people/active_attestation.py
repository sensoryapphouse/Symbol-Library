"""Exhaustive approval-time receipt validation and digest-only runtime guard."""
import hashlib
import json
import sys
import uuid
from pathlib import Path

from common import HERE, atomic_json, digest, read, require, stable_source_sha, utc
from byte_proofs import immutable_write, load_complete
from prerequisites import (PHASE3_SCOPE, WIZARD_SCOPE_FIELDS, completion_paths, closure,
                           validate_overlay_paths, verify_current_pointer, verify_generation_metadata, is_metadata)
from source_versions import PENDING
from verification import merge_pins, pending_audit_plan


def verify_bound_files(pins):
    for filename, expected in pins.items():
        path = Path(filename)
        require(is_metadata(path), 'Runtime guard may hash metadata/code only, never source images')
        try:
            stable_source_sha(path, expected)
        except Exception as error:
            raise ValueError('Attested metadata/code/proof digest changed or unstable: '+filename) from error


def prepare_attestation(wizard_approval):
    """Validate frozen prerequisite metadata and all pending receipts; no image reads."""
    from activation import reviewed_context
    overlay, review_sha = reviewed_context()
    require(overlay['enabled'] is False, 'Disable runtime before preparing activation approval')
    prerequisites = closure(HERE, wizard_approval)
    rows, pins = pending_audit_plan()
    merge_pins(pins, prerequisites['metadata_sha256'])
    pins[str(HERE/'root_runtime_review.json')] = review_sha
    _, proof, proof_sha = load_complete(HERE/'activation_audit','pending_non_people_activation',rows,PENDING)
    require(proof['metadata_sha256'] == pins, 'Activation audit is not bound to both current People completions and exact code/scope')
    bound = dict(pins)
    folder = Path(proof['immutable_proof_path']).parent.parent
    audit_path = HERE/'activation_audit/latest_status.json'
    pointer_raw = audit_path.read_bytes()
    audit_pointer = json.loads(pointer_raw)
    require(audit_pointer['proof_sha256'] == proof_sha, 'Pending proof pointer changed during attestation')
    bound.update({str(audit_path):hashlib.sha256(pointer_raw).hexdigest(),
                  proof['immutable_proof_path']:proof_sha,str(folder/'plan.json'):proof['plan_sha256'],
                  str(folder/'planned_rows.jsonl'):proof['rows_sha256'],proof['checkpoint_path']:proof['checkpoint_sha256']})
    descriptor = {'path':str(audit_path),**audit_pointer,'plan_path':str(folder/'plan.json'),
                  'plan_sha256':proof['plan_sha256'],'checkpoint_path':proof['checkpoint_path'],
                  'checkpoint_sha256':proof['checkpoint_sha256']}
    check_audit_pointer(descriptor, audit_path, bound)
    verify_bound_files(bound)
    verify_generation_metadata(bound)
    document = {
        'schema':3,'created_utc':utc(),'status':'exhaustively_validated_for_root_activation_review',
        'runtime_overlay_disabled_during_attestation':True,
        'code_bundle_sha256':digest(HERE/'code_bundle.json'),'scope_sha256':digest(HERE/'scope_contract.json'),
        'pending_originals_exact_set':PENDING,'whole_people_exact_set':PHASE3_SCOPE,'wizard_scope':prerequisites['wizard_scope'],
        'exhaustive_pending_receipts_validated':True,'original_people_and_authorized_wizard_scope_validated':True,
        'sequencing_policy':prerequisites['sequencing_policy'],
        'people_pointer':prerequisites['people_pointer'],'wizard_pointer':prerequisites['wizard_pointer'],
        'activation_audit_pointer':descriptor,'bound_metadata_sha256':bound,
        'bound_metadata_files':len(bound),'bound_metadata_bytes':sum(Path(p).stat().st_size for p in bound),
        'source_bytes_read_during_attestation':0,
    }
    path = HERE/'activation_attestations'/(uuid.uuid4().hex+'.json')
    raw = (json.dumps(document,indent=2,ensure_ascii=False)+'\n').encode()
    immutable_write(path,raw)
    candidate = {'approved':False,'code_bundle_sha256':document['code_bundle_sha256'],
                 'scope_sha256':document['scope_sha256'],'attestation_path':str(path),
                 'attestation_sha256':hashlib.sha256(raw).hexdigest(),'activation_audit_proof_sha256':proof_sha,
                 'people_final_proof_sha256':prerequisites['people_pointer']['proof_sha256'],
                 'wizard_final_proof_sha256':prerequisites['wizard_pointer']['proof_sha256'],
                 'non_people_policy_sha256':prerequisites['sequencing_policy']['sha256'],
                 'root_review_required':True}
    atomic_json(HERE/'activation_approval_candidate.json',candidate)
    return candidate


def check_audit_pointer(descriptor, expected_path, pins):
    require(descriptor['path']==str(expected_path) and str(expected_path) in pins,
            'Non-authoritative attested audit pointer')
    pointer = read(expected_path)
    require(pointer.get('status')=='complete' and pointer.get('completion_claim') is True,
            'Current authoritative audit proof is incomplete')
    for key in ('proof_path','proof_sha256','invocation','pass_id'):
        require(pointer[key]==descriptor[key], 'Current audit pointer no longer names the attested invocation')
    require(all(Path(pointer[k]).name==pointer[k] and pointer[k] not in ('.','..') for k in ('pass_id','invocation')),
            'Unsafe audit proof identity')
    expected_proof = expected_path.parent/'passes'/pointer['pass_id']/'proofs'/(pointer['invocation']+'.json')
    require(Path(pointer['proof_path']).resolve()==expected_proof and pins.get(str(expected_proof))==pointer['proof_sha256'],
            'Attested immutable audit proof binding differs')
    require(descriptor['plan_path']==str(expected_proof.parent.parent/'plan.json')
            and pins.get(descriptor['plan_path'])==descriptor['plan_sha256'], 'Attested audit plan binding differs')
    require(descriptor['checkpoint_path']==str(expected_proof.parent.parent/('byte_checks_'+pointer['invocation']+'.jsonl'))
            and pins.get(descriptor['checkpoint_path'])==descriptor['checkpoint_sha256'], 'Attested audit checkpoint binding differs')


def activation_approval_context(root=HERE):
    """Check explicit root authority before invalidating a prior verification pointer."""
    require(not sys.flags.optimize,'Optimized Python disables inherited mechanical assertions; runtime forbidden')
    root = Path(root).resolve()
    overlay = read(root/'activation.json')
    require(overlay.get('enabled') is True,'Non-People activation overlay is disabled')
    validate_overlay_paths(root,overlay)
    approval = read(root/'root_activation_approval.json')
    require(approval.get('approved') is True,'Root activation approval is absent')
    path = Path(approval['attestation_path']).resolve()
    require(path.parent==root/'activation_attestations' and path.suffix=='.json',
            'Activation approval names an invalid immutable attestation')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==approval['attestation_sha256'],'Root-approved activation attestation SHA changed')
    attested = json.loads(raw)
    require(attested.get('schema')==3 and attested.get('status')=='exhaustively_validated_for_root_activation_review'
            and attested.get('pending_originals_exact_set')==PENDING
            and attested.get('whole_people_exact_set')==PHASE3_SCOPE and attested.get('wizard_scope')==WIZARD_SCOPE_FIELDS
            and attested.get('exhaustive_pending_receipts_validated') is True
            and attested.get('original_people_and_authorized_wizard_scope_validated') is True,
            'Root approval is not based on exhaustive authorized scope validation')
    require(approval['code_bundle_sha256']==attested['code_bundle_sha256']==digest(root/'code_bundle.json')
            and approval['scope_sha256']==attested['scope_sha256']==digest(root/'scope_contract.json'),
            'Attested code/scope authority differs')
    for key, descriptor in (('people_final_proof_sha256','people_pointer'),('wizard_final_proof_sha256','wizard_pointer'),
                            ('activation_audit_proof_sha256','activation_audit_pointer')):
        require(approval[key]==attested[descriptor]['proof_sha256'],'Root approval names different completion proofs')
    protocol = read(root/'protocol.json')
    caps = read(root/'capabilities.json')
    review = read(root/'root_runtime_review.json')
    require(protocol.get('execution_enabled') is False and protocol.get('activation_overlay_may_enable_execution') is True,
            'Protocol must remain default-disabled with reviewed overlay only')
    require(all(caps.get(k) is True for k in ('whole_scope_verifier_implemented','delivery_builder_implemented','activation_audit_implemented')),
            'Unimplemented final capability cannot activate')
    require(review.get('approved') is True and review.get('allow_activation_audit') is True
            and review.get('code_bundle_sha256')==approval['code_bundle_sha256']
            and review.get('scope_sha256')==approval['scope_sha256'],'Root code review does not bind this implementation')
    pins = attested['bound_metadata_sha256']
    policy = attested['sequencing_policy']
    require(pins.get(policy['path'])==policy['sha256']==approval['non_people_policy_sha256'],
            'Root approval omits the attested sequencing policy')
    bundle = read(root/'code_bundle.json')
    for name, sha in bundle['local_sha256'].items():
        require(pins.get(str(root/name))==sha,'Attestation omits a frozen code/policy input')
    for name, sha in bundle['external_sha256'].items():
        require(pins.get(name)==sha,'Attestation omits a frozen external input')
    for name in ('code_bundle.json','scope_contract.json','root_runtime_review.json','protocol.json','capabilities.json'):
        require(str(root/name) in pins,'Attestation omits runtime authority metadata')
    return root,approval,attested,pins


def require_active_attested(root=HERE):
    """No population reconstruction, image reads or helper subprocess in this guard."""
    root,approval,attested,pins = activation_approval_context(root)
    verify_current_pointer(root,attested['people_pointer'],'people_completion_pointer',pins)
    verify_current_pointer(root,attested['wizard_pointer'],'wizard_completion_pointer',pins)
    check_audit_pointer(attested['activation_audit_pointer'],completion_paths(root)['source_byte_audit_pointer'],pins)
    verify_bound_files(pins)
    verify_generation_metadata(pins,root)
    return {'people_proof_sha256':approval['people_final_proof_sha256'],
            'wizard_proof_sha256':approval['wizard_final_proof_sha256'],
            'activation_audit_proof_sha256':approval['activation_audit_proof_sha256'],
            'activation_attestation_sha256':approval['attestation_sha256']}
