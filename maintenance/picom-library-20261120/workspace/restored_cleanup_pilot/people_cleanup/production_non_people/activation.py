"""Gate original People and explicitly authorized Wizard/Soccer scope before the pending byte audit."""
import argparse,json
from pathlib import Path
from common import HERE,require,read,digest,atomic_json,utc
from byte_proofs import begin_pass,run_pass,hash_bytes,canonical
from verification import pending_audit_plan,merge_pins
from prerequisites import audit_prerequisites,validate_overlay_paths,verify_generation_metadata
from source_versions import PENDING

def reviewed_context():
    caps=read(HERE/'capabilities.json');protocol=read(HERE/'protocol.json');overlay=read(HERE/'activation.json')
    require(all(caps.get(k) is True for k in ('whole_scope_verifier_implemented','delivery_builder_implemented','activation_audit_implemented')),'Final implementation capabilities are incomplete')
    require(protocol.get('execution_enabled') is False and protocol.get('activation_overlay_may_enable_execution') is True,'Protocol must remain default-disabled with only reviewed overlay activation')
    require(type(overlay.get('enabled')) is bool,'Invalid activation overlay flag')
    validate_overlay_paths(HERE,overlay)
    require((HERE/'root_runtime_review.json').is_file(),'Root runtime code review is absent; actual auditing/execution is disabled')
    raw=(HERE/'root_runtime_review.json').read_bytes();review=json.loads(raw);require(review.get('approved') is True and review.get('allow_activation_audit') is True and review.get('code_bundle_sha256')==digest(HERE/'code_bundle.json') and review.get('scope_sha256')==digest(HERE/'scope_contract.json'),'Root code/scope review does not approve this exact implementation/audit')
    return overlay,hash_bytes(raw)

def audit_context(wizard_approval):
    prerequisite=audit_prerequisites(wizard_approval)
    rows,pins=pending_audit_plan()
    merge_pins(pins,prerequisite['metadata_sha256'])
    return rows,pins


def require_active():
    from active_attestation import require_active_attested
    return require_active_attested()


def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group();mode.add_argument('--audit',action='store_true');mode.add_argument('--prepare-approval',action='store_true');parser.add_argument('--resume-pass');parser.add_argument('--chunk-size',type=int,default=5);parser.add_argument('--wizard-approval',type=Path);args=parser.parse_args()
    if args.audit or args.prepare_approval:require(args.wizard_approval is not None,'Explicit --wizard-approval is required')
    if args.prepare_approval:
        from active_attestation import prepare_attestation
        print(json.dumps(prepare_attestation(args.wizard_approval)));return
    if args.audit:
        overlay,_=reviewed_context()
        require(overlay['enabled'] is False,'Preactivation byte auditing requires the runtime overlay disabled')
        root=HERE/'activation_audit'
        with begin_pass(root,args.resume_pass) as admission:
            rows,pins=audit_context(args.wizard_approval)
            proof=run_pass(rows,pins,root,'pending_non_people_activation',PENDING,args.resume_pass,args.chunk_size,
                           metadata_guard=verify_generation_metadata,admission=admission)
        print(json.dumps({k:proof[k] for k in ('status','completion_claim','scope_total','originals_byte_checked_this_invocation','failed_file_records')}))
    else:
        rows,pins=pending_audit_plan();report={'created_utc':utc(),'status':'metadata_preflight_only','completion_claim':False,'pending_originals':len(rows),
            'exact_source_sha_set_sha256':hash_bytes(canonical(sorted((r['relative_path'],r['source_sha256']) for r in rows))),
            'source_bytes_read':0,'full_audit_run':False,'actual_audit_requires':'Root reviewed code/scope, current full original People proof, and explicitly authorized current Wizard/Soccer available proof and held dispositions.'}
        atomic_json(HERE/'activation_preflight.json',report);print(json.dumps(report))
if __name__=='__main__':main()
