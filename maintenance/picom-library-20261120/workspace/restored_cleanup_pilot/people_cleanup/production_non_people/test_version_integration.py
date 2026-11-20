"""Synthetic current-version and prerequisite closure fixtures."""
from contextlib import ExitStack
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import activation
import active_attestation
import common
import prerequisites as gates
import source_versions as versions
from test_wizard_q80_prerequisite import fixture as ws_fixture


class VersionOverlayTests(unittest.TestCase):
    def setUp(self):
        self.original, self.pending, self.prior, self.frozen = {}, {}, {}, {}
        self.plan, self.registry, self.metrics = [], [], []
        self.group = {
            'proposed_group_id': versions.GROUP, 'proposed_batch_id': versions.BATCH,
            'group_key': versions.GROUP_KEY, 'status': 'proposed_disabled',
            'subject_ids': ['np45228'], 'subject_relative_paths': [versions.COMPANION],
            'context_references': [], 'hold_subject_ids': [],
        }
        for n, (rel, ident) in enumerate(versions.SUBJECTS.items(), 1):
            old, current = str(n)*64, str(n+4)*64
            path = str(versions.LIBRARY/rel)
            self.original[rel] = {'source_sha256':old,'dimensions':[512,512]}
            row = {'source_sha256':old,'original_provenance':{'fixture':True}}
            lineage = []
            if rel == versions.COMPANION:
                self.pending[rel] = {**row,'partition':'review_required','proposed_subject_id':ident,
                    'proposed_batch_id':versions.BATCH,'proposed_group_id':versions.GROUP,'blob_metrics':{'old':True}}
            else:
                self.prior[rel] = {**row,'partition':'excluded_frozen_topic_inventory'}
                self.frozen[rel] = {'source':path,'source_sha256':old,'production_source_id':f'old_topic_{n}',
                    'production_queue_id':f'p{n}','production_batch_id':'batch020'}
                lineage = [{'category':'already_delivered','cohort':'production','status':'accepted','delivery':{
                    'delivery':'cleaned','source_path':path,'source_sha256':old,'id':f'p{n}',
                    'path':f'/fixture/old{n}.webp','sha256':'a'*64}}]
            self.plan.append({'relative_path':rel,'historical_sha256':old,'current_sha256':current})
            self.registry.append({'relative_path':rel,'path':path,'old_sha256':old,'new_sha256':current,
                'new_dimensions':[512,512],'new_bytes':22,'historical_dispositions':lineage})
            self.metrics.append({'path':path,'source_sha256':current,'source_bytes':22,'dimensions':[512,512],
                'simple_eligible':True,'strict_white_core_pixel_count_native':333,
                'strict_white_core_pixel_count_at_512':333.0,'strict_components':3,'largest_strict_component_at_512':172.0,
                'stable_byte_receipt':{'sha256':current,**{field:[1,1,22,1,1] for field in (
                    'stat_before','fstat_opened','fstat_closed','stat_after')}}})
        self.docs = {
            versions.DECISION:{'status':'root_design_decision_for_staged_code_only',
                'population_execution_authorized_by_this_file':False,'existing_group':self.group},
            versions.PLAN:{'revised_sources':self.plan},
            versions.REGISTRY:{'entries':self.registry},
            versions.MEASUREMENTS:{'entries':self.metrics,'status':'approved_current_version_measurements',
                'registry_sha256':versions.APPROVED_INPUTS[versions.REGISTRY]},
        }

    def overlay(self, resolutions=None):
        with (mock.patch.object(versions,'read',side_effect=self.docs.__getitem__),
              mock.patch.object(versions,'digest',side_effect=versions.APPROVED_INPUTS.__getitem__)):
            versions.apply_overlay(self.original,self.pending,self.prior,resolutions or {},self.frozen)

    def test_three_current_versions_preserve_old_ids_and_current_metrics(self):
        old = {rel:row['source_sha256'] for rel,row in self.original.items()}
        self.overlay()
        self.assertEqual(set(self.pending),set(versions.SUBJECTS))
        self.assertFalse(self.prior)
        for rel, row in self.pending.items():
            self.assertEqual(row['historical_source_sha256'],old[rel])
            identity = versions.logical_id(rel,row)
            if rel == versions.COMPANION:
                self.assertEqual(identity,versions.source_id(rel,old[rel]))
            else:
                self.assertEqual(identity,self.frozen[rel]['production_source_id'])
            self.assertNotEqual(row['source_version_id'],identity)
            self.assertEqual(row['source_bytes'],22)
            self.assertEqual(row['current_strict_metrics']['strict_components'],3)
            self.assertNotIn('blob_metrics',row)

    def test_exact_same_group_with_two_extra_subjects(self):
        updated = versions.queue_group(self.group,self.docs[versions.DECISION])
        self.assertEqual(updated['subject_ids'],['np45228','np66078','np66079'])
        self.assertEqual(updated['proposed_group_id'],versions.GROUP)
        self.assertEqual(updated['proposed_batch_id'],versions.BATCH)
        self.assertEqual(self.group['subject_ids'],['np45228'])
        with self.assertRaises(ValueError):
            versions.queue_group({**self.group,'hold_subject_ids':['np45228']},self.docs[versions.DECISION])
        with self.assertRaises(ValueError):
            versions.queue_group({**self.group,'proposed_group_id':'npg99999'},self.docs[versions.DECISION])

    def test_out_of_scope_missing_duplicate_or_unexpected_drift_rejected(self):
        for modify in (
            lambda: self.plan.append({'relative_path':'unknown.webp'}),
            lambda: self.registry.append(self.registry[0]),
            lambda: self.metrics.pop(),
            lambda: self.prior.pop(next(iter(self.prior))),
            lambda: self.original[versions.COMPANION].update(source_sha256='b'*64),
            lambda: self.pending[versions.COMPANION].update(lineage_hold=True),
        ):
            with self.subTest(modify=modify):
                self.setUp()
                modify()
                with self.assertRaises(ValueError):
                    self.overlay()
                self.assertEqual(set(self.pending),{versions.COMPANION})
        self.setUp()
        with self.assertRaises(ValueError):
            self.overlay({versions.COMPANION:{'resolved':True}})

    def test_stale_delivery_path_or_bytes_cannot_complete(self):
        self.overlay()
        source = self.pending[next(iter(versions.EXTRA))]
        stale = source['stale_cleaned_delivery']
        good = {'delivery_path':'/fixture/current.webp','delivery_sha256':'b'*64}
        versions.reject_stale_delivery(good,source)
        for key, value in stale.items():
            with self.assertRaises(ValueError):
                versions.reject_stale_delivery({**good,'delivery_'+key:value},source)


class PrerequisiteClosureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base/'np'
        self.phase3 = self.base/'source_revisions_20261105_phase3'
        self.wizard = self.base/'production_wizard_soccer'
        self.delivery = self.base/'final_people_delivery_source_revisions_20261105'
        self.paths = gates.completion_paths(self.root)
        self.inv = 'b'*32
        patch = mock.patch.object(gates, 'compact_transition', return_value=({}, {}))
        self.compact_transition = patch.start()
        self.addCleanup(patch.stop)
        self.library = self.base/'Library'
        self.publication = self.base/gates.PUBLICATION_DIR
        publication_code = {name: self.write(self.publication/name, {'fixture': name})
                            for name in ('publication.py', 'transaction.py')}
        loader = self.base/gates.ORIGINAL_OVERLAY_TOOL
        self.loader = loader
        loader_sha = self.write(loader, {'fixture': 'original overlay loader'})
        self.phase3_sha = self.write(self.phase3/'phase3_bundle.json',{'phase3_code_sha256':{},'frozen_dependencies_sha256':{}})
        self.wizard_sha = self.write(self.wizard/'bundle.json',{'code_sha256':{},'dependency_sha256':{}})
        self.wizard_review = self.wizard/gates.WIZARD_REVIEW_FILENAME
        self.wizard_review_sha = self.write(self.wizard_review,dict(reviewer='root',bundle_sha256=self.wizard_sha,
            status='revision4_code_approved_population_execution_still_disabled'))
        q80_dir = self.base/gates.Q80_DIR
        version_dir = self.base/gates.CURRENT_VERSION_DIR
        self.q80_runner = version_dir/'q80_current.py'
        self.q80_receipt = version_dir/gates.Q80_RECEIPT
        self.q80_extension = self.library/'_manifest'/gates.Q80_EXTENSION
        repair_paths = (q80_dir/'continue_unaffected.py', q80_dir/'semantic_revisions.json',
                        self.base/'workspace_cleanup_20261106/semantic_repair_overlap_reconciliation_20261106.json')
        self.q80_repair_pins = {str(path): self.write(path, {'fixture': path.name}) for path in repair_paths}
        resolver = version_dir/'resolver.py'
        self.wizard_repair_pins = {**self.q80_repair_pins, str(resolver): self.write(resolver, {'fixture': 'resolver'})}
        self.q80_pins = {**self.wizard_repair_pins, **{str(path): self.write(path, {'fixture': path.name})
            for path in (self.q80_runner, q80_dir/'compress.py', q80_dir/'readiness.json', self.q80_extension)}}
        self.q80_journal = q80_dir/'compression.sqlite'
        self.q80_report = q80_dir/'unaffected_progress.json'
        self.q80_journal_sha = self.write(self.q80_journal, {'fixture': 'journal'})
        self.q80_report_sha = self.write(self.q80_report, {'fixture': 'traversal'})
        successor_pins = {name: self.write(q80_dir/name, {'fixture': name}) for name in gates.Q80_SUCCESSOR_PINS}
        historical_receipt = version_dir/'q80_current_receipt.json'
        historical_sha = self.write(historical_receipt, {'fixture': 'historical v1 receipt'})
        self.successor_inputs = {str(q80_dir/name): sha for name, sha in successor_pins.items()}
        self.successor_inputs[str(historical_receipt)] = historical_sha
        self.q80_pins.update(self.successor_inputs)
        successor_module = version_dir/'q80_successors.py'
        self.q80_pins[str(successor_module)] = self.write(successor_module, {'fixture': 'successor module'})
        for key, value in (('Q80_SUCCESSOR_PINS', successor_pins), ('Q80_HISTORICAL_RECEIPT_SHA', historical_sha),
                           ('Q80_HISTORICAL_JOURNAL_SHA', self.q80_journal_sha),
                           ('Q80_HISTORICAL_REPORT_SHA', self.q80_report_sha)):
            patch = mock.patch.object(gates, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.ws = ws_fixture(self, self.base, publication_code, self.wizard_sha)
        self.q80_pins.update(self.ws['pins'])
        publication_bundle = self.publication/'bundle.json'
        self.publication_sha = self.write(publication_bundle, dict(
            schema='ws-library-publication-bundle-v1', legacy_bundle_sha256=self.wizard_sha,
            code_sha256=publication_code, dependency_sha256=self.ws['dependencies']))
        self.publication_review = self.publication/'root_review.json'
        publication_review_sha = self.write(self.publication_review, dict(
            schema='root-wizard-library-publication-review-v1', reviewed_by='root',
            publication_bundle_sha256=self.publication_sha, code_sha256=publication_code,
            approved_for_finalization_and_nonpeople_gate=True, approved_for_bounded_batch_publication=False,
            allowed_actions=['finalize', 'nonpeople_gate']))
        self.publication_review_ref = {'path': str(self.publication_review), 'sha256': publication_review_sha}
        self.publication_pins = {str(publication_bundle): self.publication_sha,
                                 str(self.publication_review): publication_review_sha}
        for key, value in (('PHASE3_SHA',self.phase3_sha),('WIZARD_SHA',self.wizard_sha),
                           ('WIZARD_REVIEW_SHA',self.wizard_review_sha), ('LIBRARY',self.library),
                           ('HERE',self.root), ('Q80_EXTENSION_SHA', self.q80_pins[str(self.q80_extension)]),
                           ('ORIGINAL_OVERLAY_TOOL_SHA',loader_sha)):
            patch = mock.patch.object(gates,key,value)
            patch.start()
            self.addCleanup(patch.stop)
        database = self.wizard/'fixture.sqlite'
        wal = self.wizard/'fixture.sqlite-wal'
        for key,path in (('GENERATION_DB',database),('GENERATION_WAL',wal)):
            patch = mock.patch.object(gates,key,path)
            patch.start()
            self.addCleanup(patch.stop)
        self.wal = wal
        people_dir = self.base/'People/Soccer player'
        people_dir.mkdir(parents=True)
        self.held=[dict(target_id=f'107:fixture-{i}',target=str(people_dir/f'fixture-{i}.webp'),
                        relative_target=f'People/Soccer player/fixture-{i}.webp',
                        disposition='generation_held',target_absent=True) for i in range(gates.WIZARD_HELD)]
        self.held_path=gates.held_path(self.root,self.inv)
        self.held_path.parent.mkdir(parents=True)
        self.held_path.write_text(''.join(json.dumps(row)+'\n' for row in self.held))
        self.held_sha=common.digest(self.held_path)
        capsule = self.wizard/'authorities/fixture.json'
        database_sha=self.write(database,{})
        capsule_sha = self.write(capsule,{'authority_sha256':{str(database):database_sha},
                                          'absent_paths':[str(wal),*(row['target'] for row in self.held)]})
        self.approval = self.wizard/'approval.json'
        gen = self.wizard/'generation_closeout.json'
        gen_sha = self.write(gen,{'fixture':True})
        self.gen_closeout={'path':str(gen),'sha256':gen_sha}
        self.policy=self.root/'sequencing_policy.json'
        self.write(self.phase3/'root_execution_approval.json',{'approved':True,'approved_by':'root','phase3_bundle_sha256':self.phase3_sha})
        self.people_pointer = self.paths['people_completion_pointer']
        people_pass = self.people_pointer.parent/'passes'/'fixture'
        self.people_proof = people_pass/'proofs'/(self.inv+'.json')
        source_checks = people_pass/('byte_checks_'+self.inv+'.jsonl')
        dependency_checks = people_pass/('dependency_checks_'+self.inv+'.jsonl')
        source_sha = self.write(source_checks,{})
        csvs = {str(self.library/'_manifest'/f'style-{i}.csv'): self.write(
                self.library/'_manifest'/f'style-{i}.csv', {}) for i in range(17)}
        people = self.proof(57073, phase3_bundle_sha256=self.phase3_sha,
            schema='source-version-aware-people-proof-v1', pass_id='fixture', immutable_proof_path=str(self.people_proof),
            failed_file_records=0,failed_dependencies=0,checkpoint_path=str(source_checks),checkpoint_sha256=source_sha,
            dependency_checkpoint_path=str(dependency_checks),dependency_checkpoint_sha256=self.write(dependency_checks,{}),
            plan_sha256=self.write(people_pass/'plan.json',{}),planned_rows_sha256=self.write(people_pass/'planned_rows.jsonl',{}),
            metadata_sha256=csvs)
        self.people_sha = self.write(self.people_proof,people)
        self.write(self.people_pointer,self.pointer(self.people_proof,self.people_sha,pass_id='fixture'))
        artifacts = {name:self.write(self.delivery/name,{}) for name in (
            'all_people_dispositions.jsonl','accepted_deliveries.json','index.html')}
        summary_sha = self.write(self.delivery/'summary.json',{'scope_total':57073,'phase3_bundle_sha256':self.phase3_sha,
            'verification_proof_sha256':self.people_sha,'verification_proof_path':str(self.people_proof),
            'source_checkpoint_sha256':source_sha,'artifacts_sha256':artifacts})
        self.write(self.delivery/'viewer_verification.json',{'summary_sha256':summary_sha,'exact_bindings_files_and_artifact_hashes':True,'errors':[]})
        self.wizard_pointer = self.paths['wizard_completion_pointer']
        self.wizard_proof = self.wizard_pointer.parent/self.inv/(gates.WIZARD_STATUS+'.json')
        self.publication_approval = self.publication/'np_gate_approval.json'
        self.original_overlay = gates.original_overlay_path()
        original_evidence = {
            'historical_people_proof': {'path': str(self.people_proof), 'sha256': self.people_sha},
            'historical_accepted_catalog': {'path': str(self.delivery/'accepted_deliveries.json'),
                                            'sha256': artifacts['accepted_deliveries.json']},
        }
        for key, path in (
            ('nonwood_publication_summary', self.base/'workspace_cleanup_20261106/finished_people_publication_summary.json'),
            ('wood_q80_publication_summary', self.base/'wood_q80_delivery_20261106/publication_summary.json'),
            ('wood_q80_publication_manifest', self.base/'wood_q80_delivery_20261106/publication_manifest.jsonl'),
        ):
            original_evidence[key] = {'path': str(path), 'sha256': self.write(path, {})}
        header = dict(schema=gates.ORIGINAL_OVERLAY_SCHEMA, publication_counts=gates.ORIGINAL_OVERLAY_COUNTS,
                      path_count=sum(gates.ORIGINAL_OVERLAY_COUNTS.values()), evidence=original_evidence,
                      historical_csv_sha256={Path(path).name: digest for path, digest in csvs.items()})
        self.original_overlay.write_text(json.dumps(header)+'\n'+'{}\n'*header['path_count'])
        self.original_overlay_sha = common.digest(self.original_overlay)
        patch = mock.patch.object(gates, 'Q80_OVERLAY_SHA', self.original_overlay_sha)
        patch.start()
        self.addCleanup(patch.stop)
        self.q80_doc = dict(schema=gates.Q80_RECEIPT_SCHEMA, traversal_finished=True,
            full_q80_compression_complete=False, historical_overlay_sha256=self.original_overlay_sha,
            phase1_receipt_sha256=self.q80_pins[str(self.q80_extension)], repair_authority=self.q80_repair_pins,
            historical_overlay_rows=12081, q80_phase1_rows=1599, q80_plan_rows=27596,
            q80_counts=dict(replaced=27549, retained=41, reviewed_repair_q80_successor=6),
            q80_successor_inputs_sha256=self.successor_inputs,
            q80_successors={rel: {} for rel in gates.Q80_SUCCESSOR_SCOPE},
            historical_q80_deferrals={rel: {} for rel in gates.Q80_SUCCESSOR_SCOPE}, q80_deferrals={},
            current_library_byte_checks=38085, repaired_original_people_byte_checks=3,
            q80_journal_sha256=self.q80_journal_sha, traversal_report_sha256=self.q80_report_sha)
        self.q80_receipt_sha = self.write(self.q80_receipt, self.q80_doc)
        self.q80_pins[str(self.q80_receipt)] = self.q80_receipt_sha
        self.write_bundle(self.q80_pins)
        current_original = {str(self.original_overlay): self.original_overlay_sha, str(loader): loader_sha,
                            **csvs, **{ref['path']: ref['sha256'] for ref in original_evidence.values()}}
        artifact_pins = {name: self.write(self.wizard_proof.parent/name, {})
                         for name in gates.PUBLICATION_ARTIFACTS if name != self.held_path.name}
        artifact_pins[self.held_path.name] = self.held_sha
        refs = {}
        for field in ('approval', 'legacy_finalization_approval'):
            path = self.publication/(field+'.json')
            refs[field] = {'path': str(path), 'sha256': self.write(path, {})}
        receipt = self.publication/'batches/batch-0001/complete.json'
        receipt_sha = self.write(receipt, {'fixture': 'completed publication'})
        self.wizard_doc = dict(gates.completion_fields(True),invocation=self.inv,schema=gates.WIZARD_PROOF_SCHEMA,
            legacy_bundle_sha256=self.wizard_sha,publication_bundle_sha256=self.publication_sha,
            library_root=str(self.library),library_written=True,
            originals_byte_checked_this_invocation=gates.WIZARD_AVAILABLE,deliveries_byte_checked_this_invocation=gates.WIZARD_AVAILABLE,
            held_absence_checked_this_invocation=gates.WIZARD_HELD,held_sha256=self.held_sha,
            viewer_exact_bindings_verified=True,prerequisites={'original_people':{'proof_sha256':self.people_sha,
            'phase3_bundle_sha256':self.phase3_sha,'summary_sha256':summary_sha,'catalog_sha256':artifacts['all_people_dispositions.jsonl'],
            'authority_sha256':{str(self.people_proof):self.people_sha}},'generation':{'metadata_sha256':{str(database):database_sha},'held':self.held,
            'absent_generation_wal':str(wal),'full_generation_complete':False},'bundle_sha256':self.wizard_sha,
            'generation_closeout':self.gen_closeout}, artifacts_sha256=artifact_pins,
            publication_receipts_sha256={str(receipt):receipt_sha},retained_dependencies_sha256={str(capsule):capsule_sha},
            current_original_people_publication_sha256=current_original,
            current_q80_target_count=6178, current_q80_inputs_sha256=self.ws['proof_pins'],
            root_review=self.publication_review_ref, reviewed_semantic_repair_count=11,
            reviewed_semantic_repair_inputs_sha256=self.wizard_repair_pins,
            historical_batch_publication_bundle_sha256=gates.HISTORICAL_PUBLICATION_SHA, **refs)
        self.publish_wizard()

    @staticmethod
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value))
        return common.digest(path)

    def proof(self,scope,**fields):
        return dict(status='complete',completion_claim=True,invocation=self.inv,scope_total=scope,
                    originals_byte_checked_this_invocation=scope,deliveries_byte_checked_this_invocation=scope,**fields)

    def pointer(self,path,sha,**fields):
        return dict(status='complete',completion_claim=True,invocation=self.inv,proof_path=str(path),proof_sha256=sha,**fields)

    def write_bundle(self, q80_pins):
        self.np_bundle_sha = self.write(self.root/'code_bundle.json',
                                        {'external_sha256': {**self.publication_pins, **q80_pins}})

    def publish_wizard(self,decision='proceed_after_available_cleanup'):
        wizard_proof_sha=self.write(self.wizard_proof,self.wizard_doc)
        self.write(self.wizard_pointer,dict(gates.completion_fields(True),invocation=self.inv,
            proof_path=str(self.wizard_proof),proof_sha256=wizard_proof_sha))
        policy_sha=self.write(self.policy,dict(schema='root-non-people-sequencing-v1',approved_by='root',
            decision=decision,wizard_bundle_sha256=self.wizard_sha,non_people_bundle_sha256=self.np_bundle_sha,
            wizard_proof_sha256=wizard_proof_sha,held_sha256=self.held_sha))
        pub_approval_sha = self.write(self.publication_approval, dict(
            approved=True, approved_by='root', execution_actor='fixture-root',
            publication_bundle_sha256=self.publication_sha, allowed_actions=['nonpeople_gate'],
            root_review=self.publication_review_ref,
            approved_inputs={**self.ws['proof_pins'], str(self.loader):common.digest(self.loader),str(self.original_overlay):self.original_overlay_sha}))
        self.write(self.approval,{'approved':True,'approved_by':'root','bundle_sha256':self.wizard_sha,
            'allowed_actions':['nonpeople_gate'],'generation_closeout':self.gen_closeout,
            'approved_inputs': {str(self.q80_receipt): self.q80_receipt_sha},
            'non_people_policy':{'path':str(self.policy),'sha256':policy_sha},
            'wizard_publication_approval':{'path':str(self.publication_approval),'sha256':pub_approval_sha}})

    def test_both_authoritative_closures_are_bound(self):
        result = gates.closure(self.root,self.approval)
        active_attestation.verify_bound_files(result['metadata_sha256'])
        self.assertEqual(result['people_pointer']['proof_sha256'],self.people_sha)
        self.assertEqual(result['wizard_pointer']['proof_sha256'],common.digest(self.wizard_proof))
        for path in (self.people_pointer,self.wizard_pointer,self.wizard_review,self.publication_review,
                     self.approval,self.publication_approval,self.original_overlay,self.held_path,
                     self.delivery/'all_people_dispositions.jsonl'):
            self.assertEqual(result['metadata_sha256'][str(path)],common.digest(path))
        for path, checksum in self.q80_pins.items():
            self.assertEqual(result['metadata_sha256'][path],checksum)
            self.assertNotIn(path, self.wizard_doc['current_original_people_publication_sha256'])

    def test_wizard_review_digest_drift_rejected_with_same_review_fields(self):
        original = self.wizard_review.read_bytes()
        self.wizard_review.write_bytes(original + b'\n')
        self.assertEqual(common.read(self.wizard_review), json.loads(original))
        with self.assertRaisesRegex(ValueError, 'Prerequisite metadata digest differs: .*parent_revision4_review'):
            gates.closure(self.root,self.approval)

    def test_available_scope_requires_explicit_exact_proceed_policy(self):
        approval=common.read(self.approval)
        approval.pop('non_people_policy')
        self.write(self.approval,approval)
        with self.assertRaisesRegex(ValueError,'waits for full generation'):
            gates.closure(self.root,self.approval)
        self.publish_wizard(decision='wait_for_full_generation')
        with self.assertRaisesRegex(ValueError,'does not authorize'):
            gates.closure(self.root,self.approval)
        self.wizard_doc['originals_byte_checked_this_invocation']=gates.WIZARD_SCOPE
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError,'exact available byte and held coverage'):
            gates.closure(self.root,self.approval)

    def test_held_target_appearance_invalidates_metadata_without_db_change(self):
        result=gates.closure(self.root,self.approval)
        target=Path(self.held[0]['target'])
        target.symlink_to(self.wizard/'missing-fixture')
        with self.assertRaisesRegex(ValueError,'target appeared'):
            gates.verify_generation_metadata(result['metadata_sha256'],self.root)
        with self.assertRaisesRegex(ValueError,'target appeared'):
            gates.closure(self.root,self.approval)
        target.unlink()
        with mock.patch.object(Path,'lstat',side_effect=PermissionError('fixture path unreadable')):
            with self.assertRaises(PermissionError):
                gates.verify_generation_metadata(result['metadata_sha256'],self.root)

    def test_missing_and_held_either_stage_fail_closed(self):
        for path in (self.people_pointer,self.wizard_pointer):
            raw = path.read_bytes()
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                gates.closure(self.root,self.approval)
            self.write(path,{**json.loads(raw),'status':'hold'})
            with self.assertRaisesRegex(ValueError,'on hold'):
                gates.closure(self.root,self.approval)
            path.write_bytes(raw)

    def test_unexpected_generation_wal_refused(self):
        self.wal.write_bytes(b'fixture WAL drift')
        with self.assertRaisesRegex(ValueError,'WAL presence changed'):
            gates.closure(self.root,self.approval)

    def test_stale_cross_gate_proof_rejected(self):
        self.wizard_doc['prerequisites']['original_people']['proof_sha256'] = 'e'*64
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError,'stale against current original People'):
            gates.closure(self.root,self.approval)

    def test_explicit_retired_original_pin_is_not_reopened_or_rebound(self):
        plan = self.people_proof.parent.parent/'plan.json'
        checksum = common.digest(plan)
        plan.unlink()
        self.compact_transition.return_value = ({str(plan):checksum}, {})
        result = gates.closure(self.root,self.approval)
        active_attestation.verify_bound_files(result['metadata_sha256'])
        self.assertNotIn(str(plan),result['metadata_sha256'])
        self.compact_transition.return_value = ({str(plan):'f'*64}, {})
        with self.assertRaisesRegex(ValueError, 'exact historical pin'):
            gates.closure(self.root,self.approval)

    def test_workspace_only_proof_and_wrong_publication_root_refused(self):
        self.wizard_doc['schema'] = 'paired-supplemental-available-proof-v1'
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError, 'Wizard/Soccer proof is incompatible'):
            gates.closure(self.root,self.approval)
        self.wizard_doc['schema'] = gates.WIZARD_PROOF_SCHEMA
        self.wizard_doc['library_written'] = False
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError, 'Wizard/Soccer proof is incompatible'):
            gates.closure(self.root,self.approval)

    def test_missing_publication_receipts_refused(self):
        self.wizard_doc['publication_receipts_sha256'] = {}
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError, 'lacks completion receipts'):
            gates.closure(self.root,self.approval)

    def test_current_original_overlay_and_required_publication_summary_drift(self):
        result = gates.closure(self.root,self.approval)
        original = self.original_overlay.read_bytes()
        self.original_overlay.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError, 'Prerequisite metadata digest differs'):
            gates.closure(self.root,self.approval)
        self.original_overlay.write_bytes(original)
        q80 = self.base/'wood_q80_delivery_20261106/publication_summary.json'
        q80.write_bytes(b'changed publication summary')
        with self.assertRaisesRegex(ValueError, 'Attested metadata/code/proof digest changed'):
            active_attestation.verify_bound_files(result['metadata_sha256'])

    def test_held_library_target_appearance_invalidates_gate(self):
        path = self.library/'Soccer player/fixture-0.webp'
        path.parent.mkdir(parents=True)
        path.symlink_to(path.parent/'missing')
        with self.assertRaisesRegex(ValueError, 'target appeared'):
            gates.closure(self.root,self.approval)

    def test_q80_extension_pin_is_required_and_cannot_drift(self):
        result = gates.closure(self.root,self.approval)
        self.q80_extension.write_bytes(b'changed Q80 extension')
        with self.assertRaisesRegex(ValueError, 'Attested metadata/code/proof digest changed'):
            active_attestation.verify_bound_files(result['metadata_sha256'])
        pins = {name: checksum for name, checksum in self.q80_pins.items()
                if name != str(self.q80_extension)}
        self.write_bundle(pins)
        self.publish_wizard()
        with self.assertRaisesRegex(KeyError, self.q80_extension.name):
            gates.closure(self.root,self.approval)

    def test_gate_approval_binding_cannot_be_omitted_or_swapped(self):
        approval = common.read(self.approval)
        approval.pop('wizard_publication_approval')
        self.write(self.approval,approval)
        with self.assertRaisesRegex(ValueError, 'omits the explicit Wizard publication'):
            gates.closure(self.root,self.approval)
        self.publish_wizard()
        self.publication_approval.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'Prerequisite metadata digest differs'):
            gates.closure(self.root,self.approval)

    def test_audit_runs_both_reviewed_helpers_in_order(self):
        wizard = dict(ready=True,original_phase3_complete=True,activation_performed=False,
                      **gates.completion_fields(True))
        runtime_review = self.write(self.root/'root_runtime_review.json',{})
        with (mock.patch.object(gates,'validate_bundle'),
              mock.patch.object(gates.os,'getpriority',return_value=10),
              mock.patch.object(activation,'reviewed_context',return_value=({'enabled':False},runtime_review)),
              mock.patch.object(gates.subprocess,'run',return_value=mock.Mock(
                  returncode=0, stdout=json.dumps(self.q80_doc), stderr='')) as q80,
              mock.patch.object(gates,'run_helper',return_value=wizard) as helper):
            order = mock.Mock()
            order.attach_mock(q80, 'q80')
            order.attach_mock(helper, 'wizard')
            result = gates.audit_prerequisites(self.approval)
            self.assertEqual(order.mock_calls,[
                mock.call.q80(['/usr/bin/nice','-n','9',sys.executable,'-B',str(self.q80_runner),
                    '--receipt',str(self.q80_receipt),'--receipt-sha256',self.q80_receipt_sha],
                    capture_output=True,text=True),
                mock.call.wizard(self.base/gates.PUBLICATION_DIR/gates.HISTORICAL_BRIDGE,'publish','nonpeople_gate',
                                 '--approval',str(self.publication_approval),'--legacy-approval',str(self.approval))])
            self.assertEqual(result['q80_subset_receipt'], self.q80_doc)
            helper.reset_mock()
            q80.return_value = mock.Mock(returncode=1, stderr='fixture unknown current version')
            with self.assertRaisesRegex(ValueError, 'Q80 subset check failed'):
                gates.audit_prerequisites(self.approval)
            helper.assert_not_called()

    def test_receipt_must_be_root_bound_and_must_not_claim_full_q80_completion(self):
        approval = common.read(self.approval)
        self.write(self.approval, dict(approval, approved_inputs={}))
        with self.assertRaisesRegex(ValueError, 'exact current Q80 subset receipt'):
            gates.closure(self.root,self.approval)
        self.q80_receipt_sha = self.write(self.q80_receipt, dict(self.q80_doc, full_q80_compression_complete=True))
        self.q80_pins[str(self.q80_receipt)] = self.q80_receipt_sha
        self.write_bundle(self.q80_pins)
        self.publish_wizard()
        with self.assertRaisesRegex(ValueError, 'wrong authority or scope'):
            gates.closure(self.root,self.approval)

    def replace_q80_receipt(self, document):
        self.q80_receipt_sha = self.write(self.q80_receipt, document)
        self.q80_pins[str(self.q80_receipt)] = self.q80_receipt_sha
        self.write_bundle(self.q80_pins)
        self.publish_wizard()

    def test_successor_scope_cannot_be_swapped_for_same_count(self):
        doc = dict(self.q80_doc)
        wrong = dict(doc['q80_successors'])
        wrong['Wood/09 Pronouns/his.webp'] = wrong.pop(sorted(wrong)[0])
        self.replace_q80_receipt(dict(doc, q80_successors=wrong))
        with self.assertRaisesRegex(ValueError, 'wrong authority or scope'):
            gates.closure(self.root, self.approval)

    def test_successor_pin_cannot_be_omitted_or_changed(self):
        for altered in ({}, dict(self.successor_inputs, **{next(iter(self.successor_inputs)): 'f'*64})):
            self.replace_q80_receipt(dict(self.q80_doc, q80_successor_inputs_sha256=altered))
            with self.assertRaisesRegex(ValueError, 'exact reviewed successor authority'):
                gates.closure(self.root, self.approval)

    def test_stale_v1_or_different_historical_journal_rejected(self):
        for alteration in (dict(schema='picom-original-people-current-q80-subset-v1'),
                           dict(q80_journal_sha256='f'*64), dict(traversal_report_sha256='f'*64),
                           dict(q80_counts=dict(replaced=27590, deferred_reviewed_raw_repair=6))):
            self.replace_q80_receipt(dict(self.q80_doc, **alteration))
            with self.assertRaisesRegex(ValueError, 'wrong authority or scope'):
                gates.closure(self.root, self.approval)

    def test_successor_authority_remains_in_active_attestation(self):
        result = gates.closure(self.root, self.approval)
        path = Path(next(iter(self.successor_inputs)))
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Attested metadata/code/proof digest changed'):
            active_attestation.verify_bound_files(result['metadata_sha256'])

    def test_cli_does_not_change_pointer_without_current_root_code_review(self):
        latest=self.root/'activation_audit/latest_status.json'
        self.write(latest,{'status':'complete','completion_claim':True})
        raw=latest.read_bytes()
        with (mock.patch.object(activation,'HERE',self.root),
              mock.patch.object(sys,'argv',['activation.py','--audit','--wizard-approval',str(self.approval)]),
              mock.patch.object(activation,'reviewed_context',side_effect=ValueError('unapproved'))):
            with self.assertRaisesRegex(ValueError,'unapproved'):
                activation.main()
        self.assertEqual(latest.read_bytes(),raw)

    def test_authorized_cli_prerequisite_failure_invalidates_latest_before_pending_plan(self):
        latest=self.root/'activation_audit/latest_status.json'
        self.write(latest,{'status':'complete','completion_claim':True})
        def fail(_):
            self.assertEqual(common.read(latest)['status'],'running')
            raise ValueError('Wizard gate failed')
        with (mock.patch.object(activation,'HERE',self.root),
              mock.patch.object(sys,'argv',['activation.py','--audit','--wizard-approval',str(self.approval)]),
              mock.patch.object(activation,'reviewed_context',return_value=({'enabled':False},'review_sha')),
              mock.patch.object(activation,'audit_prerequisites',side_effect=fail),
              mock.patch.object(activation,'pending_audit_plan') as plan):
            with self.assertRaisesRegex(ValueError,'Wizard gate failed'):
                activation.main()
            plan.assert_not_called()
        self.assertEqual(common.read(latest)['status'],'failed_preflight_or_audit')
        self.assertFalse(common.read(latest)['completion_claim'])

    def test_actual_gate_failure_prevents_pending_plan_and_byte_audit(self):
        with (mock.patch.object(activation,'reviewed_context',return_value=({'enabled':False},{})),
              mock.patch.object(activation,'audit_prerequisites',side_effect=ValueError('Wizard gate failed')),
              mock.patch.object(activation,'pending_audit_plan') as plan):
            with self.assertRaisesRegex(ValueError,'Wizard gate failed'):
                activation.audit_context(self.approval)
            plan.assert_not_called()





class FreezeClosureTests(unittest.TestCase):
    def setUp(self):
        self.stack = self.enterContext(ExitStack())
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.runtime = self.base/'production_non_people'
        self.library = self.base/'Library'
        import freeze_core as freeze
        self.freeze = freeze
        for key, value in (('HERE', self.runtime), ('LIBRARY', self.library)):
            self.stub(key, value)
        baseline_input = self.base/'historical.json'
        self.historical_sha = self.write(baseline_input, {'fixture': 'historical'})
        original_code = 'common.py'
        local = {name: self.write(self.runtime/name, {'fixture': name}) for name in (
            original_code, 'scope_contract.json', 'prerequisites.py', 'freeze_core.py')}
        self.live = dict(local_sha256=local, external_sha256={str(baseline_input): self.historical_sha})
        self.target = self.runtime/'code_bundle.json'
        self.live_sha = self.write(self.target, self.live)
        self.stub('LIVE_BUNDLE', self.live_sha)
        self.old_review = self.runtime/'root_runtime_review.json'
        self.write(self.old_review, {'code_bundle_sha256': self.live_sha})
        overlay = self.runtime/'activation.json'
        self.write(overlay, {'enabled': False, **{name: str(path) for name, path in
                   gates.completion_paths(self.runtime).items()}})

        compact = self.base/gates.COMPACT_DIR
        self.adapter = compact/'adapter.py'
        self.adapter_sha = self.write(self.adapter, {'fixture': 'compact adapter'})
        publication = self.base/gates.PUBLICATION_DIR
        code = {name: self.write(publication/name, {'fixture': name}) for name in ('publication.py', 'transaction.py')}
        self.finalizer_path = publication/'bundle.json'
        self.historical_bundle = publication/'implementation_history'/'bundle.json'
        self.historical_pub_sha = self.write(self.historical_bundle, {'fixture': 'historical publisher'})
        archived = self.historical_bundle.parent/self.historical_pub_sha/'bundle.json'
        archived.parent.mkdir()
        self.historical_bundle.rename(archived)
        self.historical_bundle = archived
        self.bridge = publication/freeze.HISTORICAL_BRIDGE
        self.bridge_sha = self.write(self.bridge, {'fixture': 'historical publication bridge'})
        self.stub('HISTORICAL_BRIDGE_SHA', self.bridge_sha)
        self.historical_pub = {str(publication/name): self.historical_pub_sha for name in (
            'bundle.json','root_review.json','publication.py','transaction.py')}
        compact_sha = self.write(compact/'non_people/code_bundle.json', {'external_sha256': {
            **self.live['external_sha256'], str(self.adapter): self.adapter_sha, **self.historical_pub}})
        self.stub('COMPACT_CANDIDATE', compact_sha)
        self.stub('HISTORICAL_PUBLICATION_SHA', self.historical_pub_sha)

        version = self.base/gates.CURRENT_VERSION_DIR
        version_files = {name: self.write(version/name, {'fixture': name}) for name in ('resolver.py','q80_current.py')}
        helper = self.base/'publish_q80.py'
        helper_sha = self.write(helper, {'fixture': 'shared helper'})
        self.stub('HELPER', helper)
        self.stub('HELPER_SHA', helper_sha)
        self.finalizer_sha = self.write(self.finalizer_path, dict(schema='ws-library-publication-bundle-v1',
            legacy_bundle_sha256=freeze.WIZARD_SHA, code_sha256=code,
            dependency_sha256={'publish_q80.py': helper_sha, str(version/'resolver.py'):version_files['resolver.py']}))
        version_manifest_sha = self.write(version/'SHA256SUMS', {'fixture': 'version manifest'})
        self.stub('VERSION_MANIFEST', version_manifest_sha)
        version_review_sha = self.write(version/'root_staged_review.json', dict(
            manifest_sha256=version_manifest_sha, files_sha256=version_files,
            prospective_wizard_bundle_sha256=self.finalizer_sha))
        self.stub('VERSION_REVIEW', version_review_sha)
        self.version_review_sha = version_review_sha
        self.version_manifest_sha = version_manifest_sha
        self.version_files = version_files
        self.finalizer_review = publication/'root_review.json'
        self.finalizer_review_sha = self.write(self.finalizer_review, dict(
            schema='root-wizard-library-publication-review-v1', reviewed_by='root',
            publication_bundle_sha256=self.finalizer_sha, code_sha256=code,
            allowed_actions=['finalize','nonpeople_gate'], approved_for_finalization_and_nonpeople_gate=True,
            approved_for_bounded_batch_publication=False))

        compression = self.base/gates.Q80_DIR
        q80 = {name: self.write(compression/name, {'fixture': name}) for name in freeze.Q80_PINS}
        self.stub('Q80_PINS', q80)
        audit = self.base/'workspace_cleanup_20261106/semantic_repair_overlap_reconciliation_20261106.json'
        audit_sha = self.write(audit, {'fixture': 'repair audit'})
        self.stub('AUDIT_SHA', audit_sha)
        self.extension = self.library/'_manifest'/gates.Q80_EXTENSION
        extension_sha = self.write(self.extension, {'fixture': 'extension'})
        overlay_sha = self.write(self.library/'_manifest/current-delivery.jsonl', {'fixture': 'historical overlay'})
        self.stub('Q80_EXTENSION_SHA', extension_sha)
        self.stub('Q80_OVERLAY_SHA', overlay_sha)
        self.report = compression/'unaffected_progress.json'
        report_sha = self.write(self.report, {'fixture': 'traversal'})
        journal_sha = self.write(compression/'compression.sqlite', {'fixture': 'journal'})
        successor_pins = {name: self.write(compression/name, {'fixture': name}) for name in freeze.Q80_SUCCESSOR_PINS}
        self.stub('Q80_SUCCESSOR_PINS', successor_pins)
        historical = version/'q80_current_receipt.json'
        historical_sha = self.write(historical, {'fixture': 'historical v1 receipt'})
        self.stub('Q80_HISTORICAL_RECEIPT_SHA', historical_sha)
        self.stub('Q80_HISTORICAL_JOURNAL_SHA', journal_sha)
        self.stub('Q80_HISTORICAL_REPORT_SHA', report_sha)
        self.successor_inputs = {str(compression/name): sha for name, sha in successor_pins.items()}
        self.successor_inputs[str(historical)] = historical_sha
        successor_code = {'q80_current.py': version_files['q80_current.py'],
                          'q80_successors.py': self.write(version/'q80_successors.py', {'fixture': 'successor'})}
        self.stub('Q80_SUCCESSOR_CODE', successor_code)
        self.successor_review = version/'q80_successor_root_review.json'
        self.successor_review_sha = self.write(self.successor_review, dict(
            schema='picom-six-q80-successor-root-review-v1', reviewer='root',
            approved_for_current_q80_successor_reconciliation=True,
            base_version_review_sha256=self.version_review_sha,
            base_version_manifest_sha256=self.version_manifest_sha,
            base_q80_current_sha256=version_files['q80_current.py'], files_sha256=successor_code,
            approved_inputs=self.successor_inputs))
        self.receipt = version/gates.Q80_RECEIPT
        self.receipt_sha = self.write(self.receipt, dict(schema=gates.Q80_RECEIPT_SCHEMA,
            traversal_finished=True, full_q80_compression_complete=False,
            original_plan_sha256=freeze.ORIGINAL_PLAN_SHA, phase1_receipt_sha256=extension_sha,
            historical_overlay_sha256=overlay_sha, historical_overlay_rows=12081, q80_phase1_rows=1599,
            q80_plan_rows=27596, current_library_byte_checks=38085, repaired_original_people_byte_checks=3,
            q80_counts=dict(replaced=27549, retained=41, reviewed_repair_q80_successor=6),
            q80_successor_inputs_sha256=self.successor_inputs,
            q80_successors={rel: {} for rel in gates.Q80_SUCCESSOR_SCOPE},
            historical_q80_deferrals={rel: {} for rel in gates.Q80_SUCCESSOR_SCOPE}, q80_deferrals={}, current_byte_map_sha256='b'*64,
            repair_authority={str(audit):audit_sha, **{str(compression/name):q80[name]
                for name in ('continue_unaffected.py','semantic_revisions.json')}},
            q80_journal_sha256=journal_sha, traversal_report_sha256=report_sha))

        self.ws = ws_fixture(self, self.base, code, freeze.WIZARD_SHA)
        finalizer = common.read(self.finalizer_path)
        self.finalizer_sha = self.write(self.finalizer_path, dict(finalizer, dependency_sha256=self.ws['dependencies']))
        review = common.read(self.finalizer_review)
        self.finalizer_review_sha = self.write(self.finalizer_review, dict(review, publication_bundle_sha256=self.finalizer_sha))
        names = freeze.NEW_LOCAL | {'activation.json','scope_contract.json','prerequisites.py','freeze_core.py'}
        for name in names - {'activation.json','scope_contract.json'}:
            self.write(self.runtime/name, {'fixture': name})
        self.write(self.runtime/'scope_contract.json', dict(original_paths=versions.TOTAL, pending_paths=versions.PENDING,
            prior_paths=versions.PRIOR, review_subjects=versions.REVIEW, wizard_final_proof_gate={
                'bundle_sha256':None, 'bundle_binding':'exact_root_review_and_external_sha256',
                'staged_q80_review_sha256':self.ws['stage_sha'], 'proof_schema':gates.WIZARD_PROOF_SCHEMA}))
        self.manifest = self.base/freeze.MERGE_MANIFEST
        self.manifest_sha = self.write(self.manifest, dict(schema='picom-non-people-merged-changed-code-v1',
            live_bundle_sha256=self.live_sha, replacements={name: {'sha256':common.digest(self.runtime/name)}
                for name in names}))

    def stub(self, name, value):
        self.stack.enter_context(mock.patch.object(self.freeze, name, value))

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return common.digest(path)

    def run_freeze(self):
        return self.freeze.freeze(self.finalizer_review_sha, self.receipt_sha, self.manifest_sha, self.successor_review_sha)

    def test_exact_freeze_keeps_compact_and_current_receipt_dependencies_while_disabled(self):
        bundle = self.run_freeze()
        pins = bundle['external_sha256']
        self.assertEqual(pins[str(self.adapter)], self.adapter_sha)
        self.assertEqual(pins[str(self.historical_bundle)], self.historical_pub_sha)
        self.assertEqual(pins[str(self.bridge)], self.bridge_sha)
        self.assertEqual(pins[str(self.finalizer_path)], self.finalizer_sha)
        self.assertEqual(pins[str(self.finalizer_review)], self.finalizer_review_sha)
        self.assertEqual(pins[str(self.receipt)], self.receipt_sha)
        self.assertEqual(pins[str(self.successor_review)], self.successor_review_sha)
        self.assertTrue(all(pins[path] == sha for path, sha in self.successor_inputs.items()))
        self.assertEqual(pins[str(self.manifest)], self.manifest_sha)
        self.assertTrue(set(self.live['external_sha256']) <= set(pins))
        self.assertTrue(all(pins[path] != sha for path, sha in self.historical_pub.items()))
        self.assertNotIn('activation.json', bundle['local_sha256'])
        self.assertFalse(common.read(self.runtime/'activation.json')['enabled'])
        self.assertEqual(common.read(self.old_review)['code_bundle_sha256'], self.live_sha)
        archive = self.runtime/'implementation_history'/self.live_sha
        self.assertEqual(common.digest(archive/'code_bundle.json'), self.live_sha)
        self.assertEqual((archive/'root_runtime_review.json').read_bytes(), self.old_review.read_bytes())

    def test_successor_review_cannot_omit_exact_code_or_input_authority(self):
        doc = common.read(self.successor_review)
        for alteration in (dict(approved_inputs={}), dict(files_sha256={}),
                           dict(base_version_review_sha256='f'*64), dict(reviewer='unreviewed')):
            self.successor_review_sha = self.write(self.successor_review, dict(doc, **alteration))
            with self.assertRaisesRegex(ValueError, 'Exact independent root review'):
                self.run_freeze()
            self.assertEqual(common.digest(self.target), self.live_sha)

    def test_freeze_rejects_same_count_wrong_scope_or_changed_journal(self):
        doc = common.read(self.receipt)
        wrong = dict(doc['q80_successors'])
        wrong['Wood/09 Pronouns/his.webp'] = wrong.pop(sorted(wrong)[0])
        for alteration in (dict(q80_successors=wrong), dict(q80_journal_sha256='f'*64),
                           dict(schema='picom-original-people-current-q80-subset-v1')):
            self.receipt_sha = self.write(self.receipt, dict(doc, **alteration))
            with self.assertRaisesRegex(ValueError, 'reviewed current subset'):
                self.run_freeze()
            self.assertEqual(common.digest(self.target), self.live_sha)

    def test_missing_or_stale_receipt_or_code_drift_changes_no_runtime_metadata(self):
        review_before = self.finalizer_review.read_bytes()
        review = common.read(self.finalizer_review)
        self.finalizer_review_sha = self.write(self.finalizer_review, dict(review, approved_for_bounded_batch_publication=True))
        with self.assertRaisesRegex(ValueError, 'finalization-only bundle'):
            self.run_freeze()
        self.finalizer_review.write_bytes(review_before)
        self.finalizer_review_sha = common.digest(self.finalizer_review)
        saved = self.receipt.read_bytes()
        self.receipt.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_freeze()
        self.receipt.write_bytes(saved)
        self.report.write_text('stale traversal metadata')
        with self.assertRaisesRegex(ValueError, 'Unexpected SHA-256'):
            self.run_freeze()
        (self.runtime/'common.py').write_text('different unchanged code')
        with self.assertRaisesRegex(ValueError, 'Unexpected SHA-256: .*common.py'):
            self.run_freeze()
        self.assertEqual(common.digest(self.target), self.live_sha)
        self.assertFalse((self.runtime/'implementation_history').exists())


if __name__ == '__main__':
    unittest.main()
