"""Synthetic files and real Non-People seal, closeout, lineage and receipt parsers."""
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_review
import byte_proofs
import commit_progress
import compile_decisions
import common
import final_delivery
import finish_batch
import non_people_publication as np
import publication_transaction as tx
import seal
import run_selected


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(content, bytes):
        content = (json.dumps(content) + '\n').encode()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def lossless(payload=b'fixture!'):
    chunk = b'VP8L' + len(payload).to_bytes(4, 'little') + payload
    return b'RIFF' + (len(chunk) + 4).to_bytes(4, 'little') + b'WEBP' + chunk


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temp).resolve()
        self.runtime = self.root / 'production_non_people'
        self.library = self.root / 'Library'
        self.batch = self.runtime / 'batches/batchN001'
        for module, name, value in (
            (common, 'HERE', self.runtime), (np, 'HERE', self.runtime),
            (commit_progress, 'HERE', self.runtime), (byte_proofs, 'HERE', self.runtime),
            (np, 'LIBRARY', self.library), (byte_proofs, 'LIBRARY', self.library),
        ):
            self.enterContext(mock.patch.object(module, name, value))
        self.enterContext(mock.patch.object(common, 'verify_batch_scope', return_value=self.batch))
        self.enterContext(mock.patch.object(common, 'require_activation'))
        self.enterContext(mock.patch.object(seal,'POLICY_PATH',Path(common.__file__).parent/'acceptance_policy.json'))
        self.input = b'Library reviewed input fixture'
        self.output = lossless()
        self.source = self.library / 'Style/Topic/accepted.webp'
        self.before_sha = write(self.source, self.input)
        self.accepted = self.batch / 'accepted_outputs/np00001/after.webp'
        self.retained = self.library / 'Style/Topic/held.webp'
        self.held_sha = write(self.retained, b'held source fixture')
        self.raw = self.root / 'raw_originals/accepted.webp'
        write(self.raw, b'distinct raw fixture')
        self.fixture()

    def fixture(self):
        batch = self.batch
        engine = self.runtime / 'engine.py'
        engine_sha = write(engine, b'# test engine\n')
        protocol = {'engine': {'sha256': engine_sha, 'path': str(engine)}}
        protocol_path = Path(seal.__file__).parent / 'protocol.json'
        audit_path = Path(seal.__file__).parent / 'qa.py'
        self.enterContext(mock.patch.object(seal, 'sha', wraps=seal.sha))
        seal.sha.side_effect = lambda path: (
            common.digest(engine) if Path(path) == engine else
            hashlib.sha256((json.dumps(protocol) + '\n').encode()).hexdigest()
            if Path(path) == protocol_path else common.digest(path))
        actual_read = seal.read
        self.enterContext(mock.patch.object(seal, 'read', side_effect=lambda p: protocol if Path(p)==protocol_path else actual_read(p)))
        versions, decisions, runs, reviews, audits, evidence = [], [], [], [], [], []
        checkpoint_name = 'npg00001.json'
        checkpoint = {'reviewer': 'source reviewer', 'source_records': []}
        for n, source in enumerate((self.source, self.retained), 1):
            ident, sid = f'np{n:05}', f'source{n}'
            srcsha = common.digest(source)
            versions.append({'batch_id': ident, 'production_source_id': sid, 'source': str(source),
                             'source_sha256': srcsha, 'source_bytes': source.stat().st_size,
                             'dimensions': [512,512], 'role': 'subject', 'review_required': True, 'style': 'Style'})
            checkpoint['source_records'].append({'id': ident,'source_sha256': srcsha,'actually_viewed': True,
                                                 'dimensions':[512,512], 'classification':'cleanup','findings':'White fragments'})
            decisions.append({'id': ident,'source_sha256': srcsha,'reviewer': 'source reviewer'})
            for name, content in (('source_purple', b'preview'), ('strict_cc_overlay', b'overlay')):
                preview = batch / f'previews/sources/{ident}_{name}.png'
                write(preview, content)
            write(batch/'previews/checkpoints'/(ident+'.json'), {'source_sha256': srcsha,
                'source_png': f'previews/sources/{ident}_source_purple.png', 'source_png_sha256': hashlib.sha256(b'preview').hexdigest(),
                'strict_cc_overlay': f'previews/sources/{ident}_strict_cc_overlay.png', 'overlay_png_sha256': hashlib.sha256(b'overlay').hexdigest()})
        contact_path = batch/'previews/contact_sheets/npg00001_native512_01.png'
        contact_sha = write(contact_path,b'contact sheet')
        manifest = {'batch_id': batch.name, 'groups':[{'group_id':'npg00001','versions':versions}],
                    'preview_preparation': {'contact_sheets_512': [{'path':str(contact_path.relative_to(batch)), 'sha256': contact_sha}]}}
        manifest_sha = write(batch/'manifest.json',manifest)
        checkpoint_sha = write(batch/'source_reviews'/checkpoint_name, checkpoint)
        decisions_sha = write(batch/'approved_decisions.json', {'decisions': decisions, 'root_approval':{'approved':True},
                         'source_checkpoint_sha256':{checkpoint_name:checkpoint_sha}})
        for n,row in enumerate(versions,1):
            ident,srcsha=row['batch_id'],row['source_sha256']
            work=batch/'selected_outputs'/ident
            output=self.output if n==1 else lossless(b'reject!!')
            artifacts={'after.webp':write(work/'after.webp', output)}
            for name in sorted(np.ARTIFACTS-{'after.webp'}):
                artifacts[name]=write(work/name,b'mask '+name.encode())
            outsha=artifacts['after.webp']
            regions=[{'name':'fragment','roi':[0,0,32,32]}]
            result_sha=write(work/'result.json', {'source_sha256':srcsha,'output_sha256':outsha,'manifest_sha256':manifest_sha,
                'decision_sha256':decisions_sha,'cleaner_sha256':engine_sha,'output_bytes':len(output),'regions':regions})
            runs.append({'id':ident,'status':'changed','source_sha256':srcsha,'output_sha256':outsha})
            audits.append({'id':ident,'passed':True,'result_sha256':result_sha,'artifact_sha256':artifacts,'output_sha256':outsha})
            reviews.append({'id':ident,'source_sha256':srcsha,'output_sha256':outsha,'actually_viewed':True,
                            'full_and_allregions_checked':True,'reviewer':'independent reviewer','safety':'clear' if n==1 else 'unsafe',
                            'worthwhile':'modest','reason':'Reviewed output'})
            comparison=batch/'independent_output_review/evidence'/f'{ident}_full.png'
            cmp_sha=write(comparison,b'comparison')
            region=batch/'independent_output_review/evidence'/f'{ident}_region_01.png'
            region_sha=write(region,b'region comparison')
            reviews[-1]['evidence_paths']=[str(comparison),str(region)]
            evidence.append({'id':ident,'source_sha256':srcsha,'output_sha256':outsha,'dimensions':row['dimensions'],
                             'result_sha256':result_sha,'result_regions':regions,
                             'paths':{'full':str(comparison),'normal':str(comparison)},
                             'evidence_sha256':{'full':cmp_sha,'normal':cmp_sha},
                             'regions':[{**regions[0],'path':str(region),'sha256':region_sha}]})
        self.output_sha=runs[0]['output_sha256']
        run_sha=write(batch/'selected_run_state.json',{'status':'complete','cleaner_sha256':engine_sha,'images':runs})
        write(batch/'independent_output_review.json',{'images':reviews})
        write(batch/'independent_output_review/review_manifest.json',{'images':evidence})
        write(batch/'mechanical_audit.json',{'manifest_sha256':manifest_sha,'decisions_sha256':decisions_sha,
            'run_state_sha256':run_sha,'auditor_sha256':common.digest(audit_path),'protocol_sha256':seal.sha(protocol_path),
            'cleaner_sha256':engine_sha,'errors':[],'images':audits})
        write(batch/'previews/sources/np00001_source_purple.tmp-42.png', b'orphaned scratch')
        write(batch/'keep.png', b'outside producer scratch paths')
        write(self.runtime/'inventory.json',{'images':[{**r,'status':'pending','relative_path':str(Path(r['source']).relative_to(self.library))}
                                                         for r in versions]})
        write(self.runtime/'ledger.jsonl', b'')
        self.manifest = manifest

    def seal_and_commit(self):
        seal.seal(self.batch)
        with mock.patch.object(sys,'argv',['commit_progress.py','--batch',str(self.batch)]):
            commit_progress.main()
        np.require_committed(self.batch)
        return np.batch_publication(self.batch)

    def test_closeout_removes_every_scoped_image_and_preserves_metadata(self):
        pub=self.seal_and_commit()
        self.assertEqual(len(pub.intent['deliveries']),1)
        self.assertEqual(len(pub.intent['retire']),17)
        self.assertEqual(self.source.read_bytes(),self.input)
        pub.publish()
        self.assertEqual(self.source.read_bytes(),self.output)
        self.assertEqual(common.digest(self.retained),self.held_sha)
        self.assertEqual(self.raw.read_bytes(),b'distinct raw fixture')
        self.assertTrue((self.batch/'keep.png').is_file())
        self.assertTrue((self.accepted.parent/'result.json').is_file())
        self.assertEqual(np.media_files(self.batch),set())
        resumed=np.batch_publication(self.batch)
        self.assertEqual(resumed.intent,pub.intent)
        with mock.patch.object(tx,'replace',side_effect=AssertionError('already complete')):
            resumed.publish()
        self.assertEqual(resumed.phase(),'complete')

    def test_completed_finish_never_replays_old_source_or_work_files(self):
        pub=self.seal_and_commit()
        pub.publish()
        with (mock.patch.object(finish_batch,'verify_batch_scope',return_value=self.batch),
              mock.patch.object(finish_batch,'image_worker',side_effect=contextlib.nullcontext),
              mock.patch.object(finish_batch,'require_open_batch'),
              mock.patch.object(finish_batch.subprocess,'run') as run):
            finish_batch.finish(self.batch)
        scripts=[Path(call.args[0][1]).name for call in run.call_args_list]
        self.assertEqual(scripts,['build_review.py','verify_viewer.cjs','build_progress_index.py'])
        self.assertFalse(self.accepted.exists())

    def test_interruption_before_atomic_replace_then_after_then_during_retirement(self):
        pub=self.seal_and_commit()
        with mock.patch.object(tx,'replace',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): pub.publish()
        self.assertEqual(pub.phase(),'publishing')
        self.assertEqual(self.source.read_bytes(),self.input)
        actual=tx.replace
        def replace_then_interrupt(*args):
            actual(*args)
            raise KeyboardInterrupt
        with mock.patch.object(tx,'replace',side_effect=replace_then_interrupt):
            with self.assertRaises(KeyboardInterrupt): np.batch_publication(self.batch).publish()
        self.assertEqual(self.source.read_bytes(),self.output)
        self.assertFalse(self.accepted.exists())
        actual=tx.retire
        def retire_then_interrupt(*args):
            actual(*args)
            raise KeyboardInterrupt
        with mock.patch.object(tx,'retire',side_effect=retire_then_interrupt):
            with self.assertRaises(KeyboardInterrupt): np.batch_publication(self.batch).publish()
        self.assertEqual(pub.phase(),'retiring')
        np.batch_publication(self.batch).publish()
        self.assertEqual(pub.phase(),'complete')

    def test_stale_source_changed_output_or_review_and_changed_temp_fail_closed(self):
        pub=self.seal_and_commit()
        for path in (self.source,self.accepted,Path(next(iter(pub.intent['retire'])))):
            original=path.read_bytes()
            with self.subTest(path=path):
                write(path,b'replacement')
                with self.assertRaises(ValueError): pub.publish()
                self.assertEqual(pub.phase(),'pending')
                write(path,original)
        review=self.batch/'independent_output_review.json'
        write(review,{'images':[]})
        with self.assertRaises(ValueError): pub.publish()

    def test_stale_commit_is_not_proof_of_seal(self):
        self.seal_and_commit()
        ledger=self.runtime/'ledger.jsonl'
        write(ledger,b'')
        with self.assertRaisesRegex(ValueError,'missing ledger events'):
            np.require_committed(self.batch)

    def test_real_lineage_and_final_proof_after_workspace_consumption(self):
        pub=self.seal_and_commit()
        # A separate process lets the historical verifier load its original common,
        # just as the production verification bridge does.
        originals=Path(common.__file__).parent.parent
        for name in ('verify_all_people_completion.py','all_people_progress.py'):
            shutil.copyfile(originals/name,self.root/name)
        historical=self.root/'production'
        historical.mkdir()
        write(historical/'common.py',b'import contextlib\nimage_worker = contextlib.nullcontext\n')
        protocol_path=Path(seal.__file__).parent/'protocol.json'
        qa_path=Path(seal.__file__).parent/'qa.py'
        for target,source in (('acceptance_policy.json',seal.POLICY_PATH),('qa.py',qa_path)):
            shutil.copyfile(source,self.runtime/target)
        write(self.runtime/'protocol.json',seal.read(protocol_path))
        pub.publish()
        rows = []
        for row in self.manifest['groups'][0]['versions']:
            key=row['production_source_id']
            events=[json.loads(line) for line in (self.runtime/'ledger.jsonl').read_text().splitlines()]
            event=[event for event in events if event['production_source_id']==key][-1]
            rows.append({**row,'relative_path':str(Path(row['source']).relative_to(self.library)),
                         'production_queue_id':row['batch_id'],'cohort':str(self.runtime),'last_event':event,
                         'status':event['status_to'],'final_delivery':event['delivery']})
        script = ('import json,sys; from pathlib import Path; import legacy_lineage as l; '
                  'l.PARENT=Path(sys.argv[1]); print(json.dumps(l.queued_completed(json.load(sys.stdin))))')
        result=subprocess.run([sys.executable,'-B','-c',script,str(self.root)],input=json.dumps(rows),
                              text=True,capture_output=True,check=True)
        lineage=json.loads(result.stdout)
        self.assertEqual(lineage['issues'],[])
        rows=lineage['rows'];pins=lineage['metadata_sha256']
        np.overlay_rows(rows,np.batch_publication(self.batch,load_only=True),pins)
        audit=self.root/'audit'
        proof=byte_proofs.run_pass(rows,pins,audit,byte_proofs.FINAL_KIND,2,worker=contextlib.nullcontext)
        self.assertTrue(proof['completion_claim'])
        self.assertEqual(proof['published_library_rows_checked_this_invocation'],1)
        self.assertEqual(proof['originals_byte_checked_this_invocation'],1)
        self.assertEqual(proof['historical_input_receipts_bound'],1)
        self.assertEqual(proof['current_delivery_rows_checked_this_invocation'],2)
        catalog,_,proof_sha=byte_proofs.load_complete(audit,byte_proofs.FINAL_KIND,rows,2)
        accepted=catalog[0]
        self.assertEqual(accepted['source_sha256'],self.before_sha)
        self.assertEqual(accepted['delivery_sha256'],self.output_sha)
        self.assertEqual(accepted['source_byte_evidence'],'historical_publication_receipt')
        delivery=self.root/'final'
        self.assertTrue(final_delivery.build(catalog,proof,proof_sha,delivery)['library_written'])
        verifier=Path(final_delivery.__file__).with_name('verify_final_delivery.cjs')
        subprocess.run(['node',str(verifier),str(delivery)],check=True,capture_output=True)
        write(self.source,lossless(b'mutated!'))
        with self.assertRaisesRegex(ValueError,'changed after final verification'):
            byte_proofs.load_complete(audit,byte_proofs.FINAL_KIND,rows,2)
        bad=byte_proofs.run_pass(rows,pins,audit,byte_proofs.FINAL_KIND,2,worker=contextlib.nullcontext)
        self.assertFalse(bad['completion_claim'])

    def test_prior_publication_requires_the_governing_set_and_excludes_superseded_mum(self):
        from source_versions import EXTRA
        historical=self.root/'production/batches/batch001/accepted_outputs'
        accepted=historical/'p00001/after.webp'
        out_sha=write(accepted,self.output)
        mum=historical/'p00002/after.webp'
        write(mum,b'obsolete workspace result')
        relative=str(self.source.relative_to(self.library))
        prior_row={'source':str(self.source),'relative_path':relative,'source_id':'prior1','source_sha256':self.before_sha,
                   'source_bytes':len(self.input),'delivery_path':str(accepted),'delivery_sha256':out_sha,'delivery_kind':'cleaned'}
        self.enterContext(mock.patch.object(np,'PRIOR_COUNT',1))
        with self.assertRaisesRegex(ValueError,'count differs'):
            np.prior_publication([],{})
        with self.assertRaisesRegex(ValueError,'Superseded mum'):
            np.prior_publication([prior_row,{**prior_row,'relative_path':next(iter(EXTRA)),'delivery_path':str(mum)}],{})
        pub=np.prior_publication([prior_row],{})
        pub.publish()
        self.assertEqual(pub.phase(),'complete')
        self.assertFalse(accepted.exists())
        self.assertTrue(mum.is_file())
        self.assertEqual(self.source.read_bytes(),self.output)
        resumed=np.prior_publication([prior_row],{},load_only=True)
        resumed.publish()
        self.assertEqual(resumed.intent,pub.intent)

    def test_published_batch_viewer_uses_one_current_library_image(self):
        pub=self.seal_and_commit()
        pub.publish()
        with (mock.patch.object(sys,'argv',['build_review.py','--batch',str(self.batch)]),
              mock.patch.object(build_review,'verify_batch_scope',return_value=self.batch)):
            build_review.main()
        verifier=self.runtime/'verify_viewer.cjs'
        shutil.copyfile(Path(build_review.__file__).with_name('verify_viewer.cjs'),verifier)
        write(self.runtime/'activation_gate.py',b'# Synthetic gate fixture\n')
        result=subprocess.run(['node',str(verifier),str(self.batch)],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        verified=json.loads((self.batch/'viewer_verification.json').read_text())
        self.assertEqual(verified['publication_complete_sha256'],common.digest(pub.complete_path))

    def test_receipt_rename_interruption_syncs_recovered_journal_before_changes(self):
        pub=self.seal_and_commit()
        actual_sync=tx.io.sync_directory
        for receipt, mutation in ((pub.intent_path,'replace'),(pub.ready_path,'retire')):
            def interrupt(path):
                if path==pub.folder and receipt.exists():
                    raise KeyboardInterrupt
                actual_sync(path)
            with mock.patch.object(tx.io,'sync_directory',side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    pub.publish()
            self.assertTrue(receipt.exists())
            events=[]
            actual_mutation=getattr(tx,mutation)
            def synced(path):
                events.append(('sync',path))
                tx.io.sync_directory(path)
            def mutated(*args):
                self.assertIn(('sync',pub.folder),events)
                actual_mutation(*args)
            with (mock.patch.object(tx,'sync_directory',side_effect=synced),
                  mock.patch.object(tx,mutation,side_effect=mutated)):
                if mutation=='replace':
                    # Preserve the intermediate phase for the ready-receipt test.
                    with mock.patch.object(tx.io,'write_artifact',side_effect=KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            pub.publish()
                else:
                    pub.publish()
        self.assertEqual(pub.phase(),'complete')

    def test_atomic_ledger_recovers_interrupted_write_and_rename_without_duplicate_events(self):
        seal.seal(self.batch)
        ledger=self.runtime/'ledger.jsonl'
        def commit():
            with mock.patch.object(sys,'argv',['commit_progress.py','--batch',str(self.batch)]):
                commit_progress.main()
        def torn(_source,target):
            target.write(b'{"incomplete":')
            raise KeyboardInterrupt
        with mock.patch.object(commit_progress.shutil,'copyfileobj',side_effect=torn):
            with self.assertRaises(KeyboardInterrupt):
                commit()
        self.assertEqual(ledger.read_bytes(),b'')
        actual_replace=os.replace
        def interrupt_rename(source,dest,*args,**kwargs):
            actual_replace(source,dest,*args,**kwargs)
            if dest==ledger:
                raise KeyboardInterrupt
        with mock.patch.object(commit_progress.os,'replace',side_effect=interrupt_rename):
            with self.assertRaises(KeyboardInterrupt):
                commit()
        committed=ledger.read_bytes()
        commit()
        self.assertEqual(ledger.read_bytes(),committed)
        events=[json.loads(line) for line in committed.splitlines()]
        self.assertEqual(len(events),4)
        self.assertEqual(len({event['event_id'] for event in events}),4)
        np.require_committed(self.batch)

    def test_interrupted_producer_empty_mask_temp_is_retired_and_unknown_file_preserved(self):
        scratch=self.batch/'selected_outputs/.np00001.stage-abcdefgh'
        scratch.mkdir()
        mask=scratch/'removed_core_mask.png'
        def interrupted(path,**kwargs):
            Path(path).touch()
            raise KeyboardInterrupt
        fake=mock.Mock(save=interrupted)
        with self.assertRaises(KeyboardInterrupt):
            run_selected.save_image(None,fake,mask,format='PNG')
        temporary=mask.with_name(mask.name+f'.tmp-{os.getpid()}')
        unknown=scratch/'unrelated.png.tmp-42'
        write(unknown,b'outside the producer naming contract')
        pub=self.seal_and_commit()
        self.assertEqual(pub.intent['retire'][str(temporary)]['bytes'],0)
        pub.publish()
        self.assertFalse(temporary.exists())
        self.assertTrue(unknown.is_file())

    def test_final_proof_rejects_symlink_and_hardlink_images(self):
        relative=str(self.source.relative_to(self.library))
        row={'source':str(self.source),'relative_path':relative,'source_id':'fixture',
             'source_sha256':self.before_sha,'delivery_path':str(self.source),'delivery_sha256':self.before_sha,
             'status':'original_retained','delivery_kind':'original'}
        alternate=self.library/'alternate.webp'
        self.source.rename(alternate)
        for link in (Path.symlink_to,Path.hardlink_to):
            with self.subTest(link=link):
                link(self.source,alternate)
                proof=byte_proofs.run_pass([row],{},self.root/'links_audit',byte_proofs.FINAL_KIND,1,worker=contextlib.nullcontext)
                self.assertFalse(proof['completion_claim'])
                self.assertEqual(proof['failed_file_records'],1)
                self.source.unlink()
        alternate.rename(self.source)
        proof=byte_proofs.run_pass([row],{},self.root/'links_audit',byte_proofs.FINAL_KIND,1,worker=contextlib.nullcontext)
        self.assertTrue(proof['completion_claim'])

    def test_seal_refuses_missing_or_wrong_viewed_comparisons_for_held_output(self):
        path=self.batch/'independent_output_review.json'
        original=path.read_bytes()
        for wrong in (None,[],['wrong']):
            with self.subTest(wrong=wrong):
                value=json.loads(original)
                value['images'][1]['evidence_paths']=wrong
                write(path,value)
                with self.assertRaisesRegex(ValueError,'exact viewed'):
                    seal.seal(self.batch)
                self.assertFalse((self.batch/'accepted_delivery.json').exists())
        write(path,original)
        self.seal_and_commit().publish()

    def test_admission_blocks_unpublished_previous_batch(self):
        pub=self.seal_and_commit()
        prior=tx.Publication(self.runtime/'prior_publication',{'kind':'prior','metadata_sha256':{},'deliveries':[],'retire':{}})
        prior.publish()
        self.enterContext(mock.patch.object(np,'PRIOR_COUNT',0))
        with self.assertRaisesRegex(ValueError,'publication'):
            np.require_open_batch(self.runtime/'batches/batchN002')
        pub.publish()
        later=self.runtime/'batches/batchN002'
        later.mkdir()
        np.require_open_batch(later)
        original=pub.intent_path.read_bytes()
        value=json.loads(original)
        value['retire']={}
        write(pub.intent_path,value)
        with self.assertRaises(ValueError):
            np.require_open_batch(later)
        write(pub.intent_path,original)
        comparison=Path(next(iter(pub.intent['retire'])))
        write(comparison,b'reappeared')
        with self.assertRaisesRegex(ValueError,'Retired image reappeared'):
            np.require_open_batch(later)
        comparison.unlink()
        unplanned=self.batch/'previews/sources/np00002_source_purple.tmp-492.png'
        write(unplanned,b'unplanned producer scratch')
        with self.assertRaisesRegex(ValueError,'New producer scratch'):
            np.require_open_batch(later)
        with (mock.patch.object(common,'verify_batch_scope',return_value=later),
              mock.patch.object(compile_decisions,'image_worker',side_effect=AssertionError('worker was not admitted')),
              mock.patch.object(sys,'argv',['compile_decisions.py','--batch',str(later),'--approve'])):
            with self.assertRaisesRegex(ValueError,'New producer scratch'):
                compile_decisions.main()
        unplanned.unlink()
        write(self.accepted,self.output)
        with self.assertRaisesRegex(ValueError,'Consumed workspace image reappeared'):
            np.require_open_batch(later)
        self.accepted.unlink()
        with self.assertRaisesRegex(ValueError,'sealed'):
            np.require_open_batch(self.batch,allow_existing=False)


if __name__=='__main__':
    unittest.main()
