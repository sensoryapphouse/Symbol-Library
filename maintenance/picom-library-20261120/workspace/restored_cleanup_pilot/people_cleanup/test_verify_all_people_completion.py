"""Focused fixtures: current bytes, exact coverage, unfinished work and repair precedence."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('final_people_verifier',Path(__file__).with_name('verify_all_people_completion.py'))
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

class CompletionInvariants(unittest.TestCase):
    def test_same_size_same_mtime_source_mutation_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.bin';path.write_bytes(b'first');expected=hashlib.sha256(b'first').hexdigest();stamp=path.stat()
            self.assertTrue(helper.verify_bytes(path,expected)['matches'])
            path.write_bytes(b'other');os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            measured=helper.verify_bytes(path,expected)
            self.assertTrue(measured['stable_during_read'])
            self.assertEqual(measured['actual_sha256'],hashlib.sha256(b'other').hexdigest())
            self.assertFalse(measured['matches'])
            self.assertEqual(path.read_bytes(),b'other')
    def test_coverage_and_required_review_gate(self):
        row={'relative_path':'A/a.webp','production_source_id':'one','status':'eligible_unprocessed','production_queue_id':'rp1','simple_eligible':True}
        helper.validate_scope([row],{'A/a.webp'})
        for rows,wanted in [([row,row],{'A/a.webp'}),([row],{'A/a.webp','B/b.webp'}),([row],{'B/b.webp'})]:
            with self.assertRaises(ValueError):helper.validate_scope(rows,wanted)
        self.assertEqual(len(helper.unfinished([row])),1)
        with self.assertRaises(ValueError):helper.run_verification([row],{'status':'blocked'},None)
        row={**row,'status':'below_eligibility_unprocessed','production_queue_id':None,'simple_eligible':False}
        self.assertEqual(helper.unfinished([row]),[])
        self.assertEqual(len(helper.unfinished([{**row,'simple_eligible':True}])),1)
    def test_authorized_closeout_supersession_and_unsafe_review_rejection(self):
        import copy,json
        folder=Path(__file__).parent/'batch002'
        closeout=json.loads((folder/'completion.json').read_bytes())
        delivery=json.loads((folder/'accepted_delivery.json').read_bytes())
        actual=hashlib.sha256((folder/'completion.json').read_bytes()).hexdigest()
        delivery_sha=hashlib.sha256((folder/'accepted_delivery.json').read_bytes()).hexdigest()
        review_sha=hashlib.sha256((folder/'independent_output_review/independent_output_review.json').read_bytes()).hexdigest()
        helper.validate_legacy_closeout(closeout,actual,delivery,delivery_sha,review_sha)
        with self.assertRaises(ValueError):helper.validate_legacy_closeout(closeout,'0'*64,delivery,delivery_sha,review_sha)
        for value in (None,'0'*64):
            wrong=copy.deepcopy(closeout)
            if value is None:wrong['sealed_artifact_sha256'].pop('independent_output_review/independent_output_review.json')
            else:wrong['sealed_artifact_sha256']['independent_output_review/independent_output_review.json']=value
            with self.assertRaises(ValueError):helper.validate_legacy_closeout(wrong,actual,delivery,delivery_sha,review_sha)
        row={'source_sha256':'a'*64,'output_sha256':'b'*64,'review_status':'clear','decision':'accept_lossless_output'}
        helper.validate_prior_review_row(row,'a'*64,'b'*64)
        with self.assertRaises(ValueError):helper.validate_prior_review_row({**row,'review_status':'uncertain'},'a'*64,'b'*64)
        with self.assertRaises(ValueError):helper.validate_prior_review_row(row,'c'*64,'b'*64)

    def test_remaining_frozen_pins_reject_changed_or_missing(self):
        good=dict(helper.FROZEN_REMAINING_SHA256)
        helper.validate_remaining_frozen_pins(good)
        for name in good:
            with self.subTest(name=name),self.assertRaises(ValueError):helper.validate_remaining_frozen_pins({**good,name:'0'*64})
        with self.assertRaises(ValueError):helper.validate_remaining_frozen_pins({})

    def test_historical_exact_review_source_mismatch(self):
        row={'source':'/tmp/source.webp','source_sha256':'a'*64}
        item={'source_path':row['source'],'source_sha256':'a'*64}
        review={'source':row['source'],'source_sha256':'a'*64}
        helper.validate_historical_source_binding(row,item,review)
        with self.assertRaises(ValueError):helper.validate_historical_source_binding(row,{**item,'source_sha256':'b'*64},review)
        with self.assertRaises(ValueError):helper.validate_historical_source_binding(row,item,{**review,'source_sha256':'b'*64})
        with self.assertRaises(ValueError):helper.validate_historical_source_binding(row,item,{**review,'source':'/tmp/different.webp'})

    def test_previous_failed_proof_is_immutable_after_resume(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'passes'/'same-pass'
            failed={'invocation':'first','pass_id':'same-pass','status':'failed','completion_claim':False,
                'changed_lineage':[{'path':'metadata.json','actual_sha256':'b'*64,'expected_sha256':'a'*64}]}
            first=helper.publish_final_proof(folder,failed,root)
            receipt=Path(first['immutable_proof_path']);original_bytes=receipt.read_bytes()
            success={'invocation':'second','pass_id':'same-pass','status':'complete','completion_claim':True,'changed_lineage':[]}
            second=helper.publish_final_proof(folder,success,root)
            self.assertEqual(receipt.read_bytes(),original_bytes)
            self.assertEqual(json.loads(receipt.read_bytes())['changed_lineage'],failed['changed_lineage'])
            self.assertEqual(json.loads((folder/'final_proof.json').read_bytes())['invocation'],'second')
            self.assertEqual(json.loads((root/'latest_status.json').read_bytes())['proof_path'],second['immutable_proof_path'])
            with self.assertRaises(ValueError):helper.publish_final_proof(folder,{**failed,'changed_lineage':[]},root)
            self.assertEqual(receipt.read_bytes(),original_bytes)
            self.assertEqual(json.loads((root/'latest_status.json').read_bytes())['invocation'],'second')

    def test_batch003_exact_review_rows_reject_unsafe_or_wrong_hash(self):
        row={'source_sha256':'a'*64,'output_sha256':'b'*64,'foreground_safety':'clear','review_status':'clear','worthwhile':'yes'}
        helper.validate_batch003_review_row(row,'a'*64,'b'*64)
        for change in ({'source_sha256':'c'*64},{'output_sha256':'c'*64},{'foreground_safety':'uncertain'},{'review_status':'hold'},{'worthwhile':'no'}):
            with self.subTest(change=change),self.assertRaises(ValueError):helper.validate_batch003_review_row({**row,**change},'a'*64,'b'*64)

    def test_interrupted_new_or_resumed_pass_invalidates_old_success_pointer(self):
        import json
        from types import SimpleNamespace
        from unittest import mock
        for resume in (False,True):
            with self.subTest(resume=resume),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);folder=root/'passes'/'old-pass'
                prior=helper.publish_final_proof(folder,{'invocation':'old-invocation','pass_id':'old-pass',
                    'status':'complete','completion_claim':True,'changed_lineage':[]},root)
                receipt=Path(prior['immutable_proof_path']);old_bytes=receipt.read_bytes()
                preflight={'status':'ready_for_full_hash_verification','metadata_sha256':{},'verifier_sha256':'a'*64}
                signature=helper.digest(json.dumps({'pins':{},'verifier':'a'*64},sort_keys=True).encode())
                helper.atomic(folder/'plan.json',{'signature_sha256':signature})
                args=SimpleNamespace(resume_pass='old-pass' if resume else None,chunk_size=1)
                with mock.patch.object(helper,'OUT',root),mock.patch.object(helper,'image_worker',side_effect=RuntimeError('fixture interruption')):
                    with self.assertRaisesRegex(RuntimeError,'fixture interruption'):
                        helper.run_verification([{'relative_path':'fixture.bin'}],preflight,args)
                pointer=json.loads((root/'latest_status.json').read_bytes())
                self.assertEqual(pointer['status'],'running');self.assertIs(pointer['completion_claim'],False)
                self.assertNotIn('proof_sha256',pointer);self.assertNotEqual(pointer['invocation'],'old-invocation')
                self.assertEqual(receipt.read_bytes(),old_bytes)

    def test_concurrent_verification_is_refused_before_changing_authority(self):
        import fcntl,json
        from unittest import mock
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);helper.atomic(root/'latest_status.json',{'status':'running','invocation':'first'})
            before=(root/'latest_status.json').read_bytes()
            with (root/'verification.lock').open('a+') as lock,mock.patch.object(helper,'OUT',root):
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    helper.run_verification([],{'status':'ready_for_full_hash_verification'},None)
            self.assertEqual((root/'latest_status.json').read_bytes(),before)

    def test_governing_prior_repair_binding(self):
        row={'source':'/tmp/original-robot.webp','source_sha256':'a'*64,'status':'accepted_prior_repair'}
        governing={'source_path':row['source'],'source_sha256':'a'*64,'path':'/tmp/accepted-wood.webp','sha256':'b'*64}
        delivery={'delivery':'separate_repair','path':governing['path'],'sha256':'b'*64}
        self.assertEqual(helper.validate_delivery_binding(row,delivery,governing)['sha256'],'b'*64)
        for bad in [{**delivery,'path':row['source']},{**delivery,'sha256':'c'*64},{'delivery':'original','path':row['source'],'sha256':'a'*64}]:
            with self.assertRaises(ValueError):helper.validate_delivery_binding(row,bad,governing)
        with self.assertRaises(ValueError):helper.validate_delivery_binding(row,delivery,None)

if __name__=='__main__':unittest.main()
