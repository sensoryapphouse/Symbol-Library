"""Private metadata fixtures for the Q80 -> Non-People handover."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import wizard_q80_prerequisite as ws


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(case, base, finalizer_code, legacy_bundle='b'*64):
    """Real metadata files; no image or compressor execution, no production IO."""
    q80, pub = base/ws.Q80_DIR, base/ws.PUB_DIR
    helpers = {}
    for name in ws.HELPERS:
        p = base/name
        helpers[name] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.exists()
                         else write(p, {'fixture': name}))
    case.enterContext(mock.patch.object(ws, 'HELPERS', helpers))
    code = {str(base/name): sha for name, sha in helpers.items()}
    staged_files = {name: write(q80/name, {'fixture': name}) for name in
                    ('run.py', 'plan.py', 'engine.py', 'proof.py', 'successors.py')}
    code.update({str(q80/name): staged_files[name] for name in ('run.py', 'plan.py', 'engine.py', 'proof.py')})
    build = {'historical-only.py': 'a'*64}
    case.enterContext(mock.patch.object(ws, 'BUILD_CODE_MAP_SHA',
        hashlib.sha256(json.dumps(build, sort_keys=True, separators=(',', ':')).encode()).hexdigest()))
    stage_sha = write(q80/ws.STAGED_REVIEW, dict(reviewer='root',
        status='exact_staged_source_review_complete_no_live_adoption',
        reconstructed_future_source_sha256=finalizer_code, reviewed_file_pins=staged_files))
    case.enterContext(mock.patch.object(ws, 'STAGED_REVIEW_SHA', stage_sha))
    legacy_path = base/'production_wizard_soccer/execution_approvals/fixture-finalize.json'
    legacy_sha = write(legacy_path, dict(approved=True, approved_by='root',
                                       allowed_actions=['finalize'], bundle_sha256=legacy_bundle))
    legacy_ref = dict(path=str(legacy_path), sha256=legacy_sha)
    manifest = dict(schema='wizard-soccer-q80-code-manifest-v1', code_sha256=code,
        build_code_sha256=build, settings=ws.SETTINGS,
        legacy_finalization_authority=legacy_ref,
        scope=dict(available=6178, held=12, batches=194, styles=['Wizard', 'Soccer player']))
    manifest_sha = write(q80/'code_manifest.json', manifest)
    review_sha = write(q80/'root_review.json', dict(approved=True, approved_by='root',
        code_manifest_sha256=manifest_sha, allowed_actions=['build-plan', 'run', 'verify']))
    inputs = {f'Wizard/fixture-{i}.webp': {} for i in range(6178)}
    originals = {f'106:people-{i:05d}': {} for i in range(6178)}
    plan = dict(schema='wizard-soccer-current-q80-input-plan-v1', available=6178,
        generation_held=12, scope_total=6190, published_batches=194, inputs=inputs,
        original_people_proofs=originals, held=list(range(12)), code_sha256=code, build_code_sha256=build,
        legacy_authorization=legacy_ref)
    plan_sha = write(q80/'input_plan.json', plan)
    execution_sha = write(q80/'execution_authorization.json', dict(approved=True, approved_by='root',
        input_plan_sha256=plan_sha, code_manifest_sha256=manifest_sha,
        root_review_sha256=review_sha, allowed_actions=['run', 'verify']))
    ledger_sha = write(q80/'compression.sqlite', {'fixture': 'terminal ledger, never opened as SQLite'})
    authority = dict(code_sha256=code, build_code_sha256=build, settings=ws.SETTINGS)
    for key, name, sha in (('code_manifest', 'code_manifest.json', manifest_sha),
                           ('root_review', 'root_review.json', review_sha),
                           ('input_plan', 'input_plan.json', plan_sha),
                           ('execution_authorization', 'execution_authorization.json', execution_sha)):
        authority[key] = dict(path=str(q80/name), sha256=sha)
    write(q80/'successor_receipt.json', dict(schema='wizard-soccer-q80-successor-receipt-v1',
        complete=True, available=6178, generation_held=12, authority=authority, settings=ws.SETTINGS,
        ledger=dict(path=str(q80/'compression.sqlite'), sha256=ledger_sha),
        entries={key: dict(state='retained') for key in inputs},
        current_proof=dict(current=inputs, originals=originals), replaced=0, retained=6178))
    artifact_pins = {str(q80/name): hashlib.sha256((q80/name).read_bytes()).hexdigest() for name in ws.ARTIFACTS}
    authority_path = pub/'wizard_soccer_q80_authority.json'
    authority_sha = write(authority_path, dict(schema='root-bound-wizard-soccer-q80-finalizer-inputs-v1',
                                             artifact_sha256=artifact_pins))
    dependencies = {'publish_q80.py': helpers['wood_q80_delivery_20261106/publish_q80.py'],
        str(base/'current_version_candidate/resolver.py'): helpers['current_version_candidate/resolver.py'],
        str(q80/'successors.py'): staged_files['successors.py'], str(authority_path): authority_sha}
    finalizer = dict(code_sha256=finalizer_code, dependency_sha256=dependencies, legacy_bundle_sha256=legacy_bundle)
    review = dict(code_sha256=finalizer_code)
    pins, proof_pins = ws.closure(base, finalizer, review)
    return dict(finalizer=finalizer, review=review, pins=pins, proof_pins=proof_pins,
                dependencies=dependencies, stage_sha=stage_sha)


class WizardQ80Tests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        pub = self.base/ws.PUB_DIR
        code = {name: write(pub/name, {'fixture': name}) for name in ('publication.py', 'transaction.py')}
        self.fx = fixture(self, self.base, code)
        self.q80 = self.base/ws.Q80_DIR

    def run_closure(self):
        return ws.closure(self.base, self.fx['finalizer'], self.fx['review'])

    def rebind(self, name, doc):
        """Simulate root binding changed metadata: semantic checks must still fail."""
        sha = write(self.q80/name, doc)
        authority_path = self.base/ws.PUB_DIR/'wizard_soccer_q80_authority.json'
        authority = json.loads(authority_path.read_text())
        authority['artifact_sha256'][str(self.q80/name)] = sha
        authority_sha = write(authority_path, authority)
        self.fx['finalizer']['dependency_sha256'][str(authority_path)] = authority_sha

    def test_complete_closure_is_read_only_and_contains_runtime_and_ledger(self):
        before = {p: p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        pins, proof = self.run_closure()
        self.assertEqual((pins, proof), (self.fx['pins'], self.fx['proof_pins']))
        self.assertIn(str(self.q80/'compression.sqlite'), pins)
        self.assertIn(str(self.q80/'engine.py'), pins)
        self.assertEqual(before, {p: p.read_bytes() for p in self.base.rglob('*') if p.is_file()})

    def test_changed_artifact_or_runtime_code_fails(self):
        for name in (*ws.ARTIFACTS, 'engine.py', 'successors.py'):
            with self.subTest(name=name):
                p = self.q80/name; original = p.read_bytes(); p.write_bytes(original+b' ')
                with self.assertRaises(ValueError): self.run_closure()
                p.write_bytes(original)

    def test_missing_receipt_and_extra_authority_are_rejected(self):
        p = self.q80/'successor_receipt.json'; raw = p.read_bytes(); p.unlink()
        with self.assertRaises(FileNotFoundError): self.run_closure()
        p.write_bytes(raw)
        a = self.base/ws.PUB_DIR/'wizard_soccer_q80_authority.json'
        doc = json.loads(a.read_text()); doc['artifact_sha256']['/wrong/input.json'] = 'a'*64
        write(a, doc)
        with self.assertRaisesRegex(ValueError, 'artifact scope'): self.run_closure()

    def test_incomplete_nonterminal_wrong_ledger_and_wrong_authority_receipts_fail(self):
        original = json.loads((self.q80/'successor_receipt.json').read_text())
        for change in (dict(complete=False), dict(available=6177), dict(retained=6177),
                       dict(entries={}), dict(authority={}), dict(ledger=dict(path='wrong', sha256='a'*64))):
            with self.subTest(change=list(change)):
                self.rebind('successor_receipt.json', dict(original, **change))
                with self.assertRaisesRegex(ValueError, 'terminal coverage'): self.run_closure()
        changed = json.loads(json.dumps(original)); next(iter(changed['entries'].values()))['state']='intent'
        self.rebind('successor_receipt.json', changed)
        with self.assertRaisesRegex(ValueError, 'terminal coverage'): self.run_closure()

    def test_root_execution_cannot_name_different_plan(self):
        doc = json.loads((self.q80/'execution_authorization.json').read_text())
        self.rebind('execution_authorization.json', dict(doc, input_plan_sha256='f'*64))
        with self.assertRaisesRegex(ValueError, 'execution authority'): self.run_closure()

    def test_legacy_authority_cannot_be_swapped_or_drift(self):
        plan = json.loads((self.q80/'input_plan.json').read_text())
        changed = dict(plan, legacy_authorization=dict(path='/different.json', sha256='a'*64))
        self.rebind('input_plan.json', changed)
        with self.assertRaisesRegex(ValueError, 'different legacy finalization authority'): self.run_closure()
        self.rebind('input_plan.json', plan)
        path = Path(plan['legacy_authorization']['path'])
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError): self.run_closure()

    def test_stale_v2_finalizer_or_changed_dependency_fails(self):
        self.fx['finalizer']['code_sha256'] = dict(self.fx['finalizer']['code_sha256'], **{'publication.py': 'f'*64})
        with self.assertRaisesRegex(ValueError, 'reviewed Q80 v3'): self.run_closure()
        self.fx['finalizer']['code_sha256'] = self.fx['review']['code_sha256']
        self.fx['finalizer']['dependency_sha256'].pop(str(self.q80/'successors.py'))
        with self.assertRaisesRegex(ValueError, 'exact Q80 authority'): self.run_closure()

    def test_all_recovery_sidecars_including_dangling_symlink_fail(self):
        for suffix in ('-journal', '-wal', '-shm'):
            p = self.q80/('compression.sqlite'+suffix); p.write_text('recovery')
            with self.assertRaisesRegex(ValueError, 'recovery sidecar'): self.run_closure()
            p.unlink()
        p.symlink_to('missing')
        with self.assertRaisesRegex(ValueError, 'recovery sidecar'): self.run_closure()

    def test_proof_and_gate_both_require_exact_q80_inputs(self):
        proof = dict(current_q80_target_count=6178, current_q80_inputs_sha256=self.fx['proof_pins'])
        approval = dict(approved_inputs=self.fx['proof_pins'])
        ws.bind_proof(proof, approval, self.fx['proof_pins'])
        for bad_proof, bad_approval in ((dict(proof, current_q80_target_count=6177), approval),
                                       (dict(proof, current_q80_inputs_sha256={}), approval), (proof, {})):
            with self.assertRaisesRegex(ValueError, 'exact completed Q80 inputs'):
                ws.bind_proof(bad_proof, bad_approval, self.fx['proof_pins'])


if __name__ == '__main__': unittest.main()
