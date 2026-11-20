"""Synthetic trusted-attestation guard fixtures; no real approvals/audits/activation."""
import copy,hashlib,json,os,subprocess,tempfile,unittest,sys
from pathlib import Path
from unittest import mock
import active_attestation as a
import common as c
import activation,byte_proofs,verification
import prerequisites as gates
from prerequisites import completion_paths
from source_versions import PENDING

class ActiveAttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=(Path(self.temp.name)/'runtime').resolve();self.root.mkdir();self.pins={}
        def write(path,value):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return c.digest(path)
        self.write=write
        self.write(self.root/'protocol.json',{'execution_enabled':False,'activation_overlay_may_enable_execution':True})
        self.write(self.root/'capabilities.json',{'whole_scope_verifier_implemented':True,'delivery_builder_implemented':True,'activation_audit_implemented':True})
        self.write(self.root/'scope_contract.json',{'synthetic_guard_fixture':True})
        self.external=self.root/'immutable_input.json';self.write(self.external,{'fixture':'input'})
        bundle={'local_sha256':{name:c.digest(self.root/name) for name in ('protocol.json','capabilities.json','scope_contract.json')},'external_sha256':{str(self.external):c.digest(self.external)}}
        self.write(self.root/'code_bundle.json',bundle);code=c.digest(self.root/'code_bundle.json');scope=c.digest(self.root/'scope_contract.json')
        self.write(self.root/'root_runtime_review.json',{'approved':True,'allow_activation_audit':True,'code_bundle_sha256':code,'scope_sha256':scope})
        for path in [self.root/name for name in ('protocol.json','capabilities.json','scope_contract.json','code_bundle.json','root_runtime_review.json')]+[self.external]:self.pins[str(path)]=c.digest(path)
        patch=mock.patch.object(gates,'HERE',self.root);patch.start();self.addCleanup(patch.stop)
        self.q80_journal=self.root.parent/gates.Q80_DIR/'compression.sqlite'
        self.pins[str(self.q80_journal)]=self.write(self.q80_journal,{'journal_fixture':True})
        self.ws_q80_journal=self.root.parent/gates.ws_q80.Q80_DIR/'compression.sqlite'
        self.pins[str(self.ws_q80_journal)]=self.write(self.ws_q80_journal,{'journal_fixture':True})
        pointers=completion_paths(self.root)
        database=self.root/'fixture.sqlite';wal=self.root/'fixture.sqlite-wal'
        for name,path in (('GENERATION_DB',database),('GENERATION_WAL',wal)):
            patch=mock.patch.object(gates,name,path);patch.start();self.addCleanup(patch.stop)
        self.pins[str(database)]=self.write(database,{'generation_fixture':True})
        self.people=self.pointer(pointers['people_completion_pointer'].parent,'people_fixture')
        self.wizard=self.pointer(pointers['wizard_completion_pointer'].parent,'b'*32)
        self.wizard.update(gates.completion_fields(True))
        self.pins[self.wizard['path']]=self.write(Path(self.wizard['path']),self.wizard)
        library = self.root/'Library'
        patch = mock.patch.object(gates,'LIBRARY',library);patch.start();self.addCleanup(patch.stop)
        held_path=gates.held_path(self.root,self.wizard['invocation'])
        held_path.parent.mkdir(parents=True)
        people = self.root/'People/Soccer player'
        people.mkdir(parents=True)
        self.held_target=people/'held-0.webp'
        held_path.write_text(''.join(json.dumps(dict(target_id=f'107:fixture-{i}',target=str(people/f'held-{i}.webp'),
            relative_target=f'People/Soccer player/held-{i}.webp',
            disposition='generation_held',target_absent=True))+'\n' for i in range(gates.WIZARD_HELD)))
        self.pins[str(held_path)]=c.digest(held_path)
        policy=self.root/'sequencing.json'
        policy_sha=self.write(policy,{'fixture':'already approved by closure'})
        self.pins[str(policy)]=policy_sha
        self.audit=self.pointer(pointers['source_byte_audit_pointer'].parent,'audit_fixture')
        self.attested={'schema':3,'status':'exhaustively_validated_for_root_activation_review','pending_originals_exact_set':PENDING,'whole_people_exact_set':57073,
            'wizard_scope':gates.WIZARD_SCOPE_FIELDS,'sequencing_policy':{'path':str(policy),'sha256':policy_sha},
            'exhaustive_pending_receipts_validated':True,'original_people_and_authorized_wizard_scope_validated':True,'code_bundle_sha256':code,'scope_sha256':scope,
            'people_pointer':self.people,'wizard_pointer':self.wizard,'activation_audit_pointer':self.audit,'bound_metadata_sha256':self.pins}
        self.path=self.root/'activation_attestations/fixture.json';self.write(self.path,self.attested)
        self.approval={'approved':True,'attestation_path':str(self.path),'attestation_sha256':c.digest(self.path),'code_bundle_sha256':code,'scope_sha256':scope,
            'people_final_proof_sha256':self.people['proof_sha256'],'wizard_final_proof_sha256':self.wizard['proof_sha256'],'activation_audit_proof_sha256':self.audit['proof_sha256'],
            'non_people_policy_sha256':policy_sha}
        self.write(self.root/'root_activation_approval.json',self.approval)
        self.write(self.root/'activation.json',{'enabled':True,**{key:str(path) for key,path in pointers.items()}})
    def tearDown(self):self.temp.cleanup()
    def pointer(self,folder,invocation):
        directory=folder/'passes'/invocation;proof=directory/'proofs'/(invocation+'.json');proof.parent.mkdir(parents=True,exist_ok=True)
        # Opaque fixture bytes deliberately cannot be parsed as a population receipt/proof.
        proof.write_bytes(b'synthetic already-trusted proof blob');plan=directory/'plan.json';plan.write_bytes(b'synthetic already-trusted plan');checkpoint=directory/('byte_checks_'+invocation+'.jsonl');checkpoint.write_bytes(b'population rows are not parsed by the active guard\n')
        pointer=folder/'latest_status.json';value={'status':'complete','completion_claim':True,'pass_id':invocation,'invocation':invocation,'proof_path':str(proof),'proof_sha256':c.digest(proof)};self.write(pointer,value)
        for path in (proof,plan,checkpoint,pointer):self.pins[str(path)]=c.digest(path)
        return {'path':str(pointer),**value,'plan_path':str(plan),'plan_sha256':c.digest(plan),'checkpoint_path':str(checkpoint),'checkpoint_sha256':c.digest(checkpoint)}
    def test_guard_uses_only_digests_not_catalog_plan_or_receipt_population_parsing(self):
        with (mock.patch.object(activation,'audit_context',side_effect=AssertionError('no full audit context')),
             mock.patch.object(verification,'pending_audit_plan',side_effect=AssertionError('no scope population reconstruction')),
             mock.patch.object(byte_proofs,'load_complete',side_effect=AssertionError('no full receipt parsing')),
             mock.patch.object(subprocess,'run',side_effect=AssertionError('no helper subprocess'))):
            proof=a.require_active_attested(self.root)
        self.assertEqual(proof['activation_attestation_sha256'],self.approval['attestation_sha256'])
    def test_optimized_python_refused_even_for_otherwise_valid_attestation(self):
        # Establish validity first: refusal must be optimization, not disabled real activation.
        a.require_active_attested(self.root)
        code='import sys;sys.path.insert(0,'+repr(str(c.HERE))+');from active_attestation import require_active_attested;require_active_attested('+repr(str(self.root))+')'
        for flags,environment in [(['-O'],{}),([] ,{'PYTHONOPTIMIZE':'1'})]:
            result=subprocess.run([sys.executable,*flags,'-c',code],env={**os.environ,**environment},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('Optimized Python disables inherited mechanical assertions',result.stderr)
    def test_disabled_or_unapproved_never_activates(self):
        for file,field in [('activation.json','enabled'),('root_activation_approval.json','approved')]:
            old=json.loads((self.root/file).read_text());changed=copy.deepcopy(old);changed[field]=False;self.write(self.root/file,changed)
            with self.assertRaises(ValueError):a.require_active_attested(self.root)
            self.write(self.root/file,old)
    def test_changed_input_even_same_mtime_and_size_refused(self):
        stat=self.external.stat();raw=self.external.read_bytes();self.external.write_bytes(raw.replace(b'input',b'other'));os.utime(self.external,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'digest changed'):a.require_active_attested(self.root)
    def test_current_pointer_or_immutable_proof_plan_checkpoint_changes_refused(self):
        for filename in ('path','proof_path','plan_path','checkpoint_path'):
            path=Path(self.audit[filename]);raw=path.read_bytes();path.write_bytes(raw+b' ')
            with self.assertRaises(ValueError):a.require_active_attested(self.root)
            path.write_bytes(raw)
    def test_either_prerequisite_pointer_hold_or_digest_drift_refused(self):
        for descriptor in (self.people,self.wizard):
            path=Path(descriptor['path']);old=path.read_bytes();self.write(path,{**json.loads(old),'status':'running'})
            with self.assertRaisesRegex(ValueError,'Current prerequisite pointer'):
                a.require_active_attested(self.root)
            path.write_bytes(old)
            proof=Path(descriptor['proof_path']);old=proof.read_bytes();proof.write_bytes(old+b' ')
            with self.assertRaisesRegex(ValueError,'digest changed'):
                a.require_active_attested(self.root)
            proof.write_bytes(old)
    def test_tampered_attestation_or_partial_people_scope_refused(self):
        changed=copy.deepcopy(self.attested);changed['whole_people_exact_set']=47445;self.write(self.path,changed)
        with self.assertRaises(ValueError):a.require_active_attested(self.root)
        approved=copy.deepcopy(self.approval);approved['attestation_sha256']=c.digest(self.path);self.write(self.root/'root_activation_approval.json',approved)
        with self.assertRaisesRegex(ValueError,'exhaustive authorized scope'):a.require_active_attested(self.root)
    def test_active_guard_rejects_new_held_file_without_reading_its_bytes(self):
        self.held_target.write_bytes(b'synthetic unexpected held generation')
        with self.assertRaisesRegex(ValueError,'target appeared'):
            a.require_active_attested(self.root)
    def test_active_guard_rejects_q80_journal_drift_and_new_sidecars(self):
        sidecar=self.q80_journal.with_name('compression.sqlite-wal')
        sidecar.touch()
        with self.assertRaisesRegex(ValueError,'Q80 journal sidecar appeared'):
            a.require_active_attested(self.root)
        sidecar.unlink()
        self.q80_journal.write_bytes(b'changed journal fixture')
        with self.assertRaisesRegex(ValueError,'digest changed'):
            a.require_active_attested(self.root)
    def test_active_guard_rejects_wizard_q80_ledger_drift_and_sidecar(self):
        sidecar=self.ws_q80_journal.with_name('compression.sqlite-journal')
        sidecar.touch()
        with self.assertRaisesRegex(ValueError,'recovery sidecar'):
            a.require_active_attested(self.root)
        sidecar.unlink()
        self.ws_q80_journal.write_bytes(b'changed terminal ledger')
        with self.assertRaisesRegex(ValueError,'digest changed'):
            a.require_active_attested(self.root)
    def test_active_guard_rejects_source_image_paths_in_metadata_digest_map(self):
        path=self.root/'user_image.webp';path.write_bytes(b'not read as metadata')
        with self.assertRaisesRegex(ValueError,'metadata/code only'):a.verify_bound_files({str(path):c.digest(path)})
if __name__=='__main__':unittest.main()
