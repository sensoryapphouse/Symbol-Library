"""Isolated receipt/activation/final-delivery fixtures. No actual user images or full audits."""
import collections,contextlib,copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
import byte_proofs as b
import common as c
import final_delivery as delivery
from source_versions import version_fields

def fake_lossless(payload=b'fixture'):
    chunk=b'VP8L'+len(payload).to_bytes(4,'little')+payload+(b'\0' if len(payload)%2 else b'')
    return b'RIFF'+(len(chunk)+4).to_bytes(4,'little')+b'WEBP'+chunk

class FinalPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.library=self.root/'Library';self.library.mkdir();self.patch=mock.patch.object(b,'LIBRARY',self.library);self.patch.start()
        self.meta=self.root/'metadata.json';self.meta.write_text('{"fixture":true}');self.pins={str(self.meta):c.digest(self.meta)};self.rows=[]
        for n in range(2):
            rel=f'Style/Topic/{n}.webp';source=self.library/rel;source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(b'source fixture '+bytes([n]));sha=c.digest(source)
            self.rows.append({'relative_path':rel,'source_id':str(n),'source':str(source),'source_sha256':sha,'status':'screened_original_unchanged','delivery_kind':'original','delivery_path':str(source),'delivery_sha256':sha})
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def run_pass(self,**kwargs):return b.run_pass(self.rows,self.pins,self.root/'audit','fixture_only',2,chunk_size=1,**kwargs)
    def test_success_exact_set_and_immutable_pointer(self):
        proof=self.run_pass();catalog,loaded,sha=b.load_complete(self.root/'audit','fixture_only',self.rows,2)
        self.assertEqual(len(catalog),2);self.assertEqual(loaded['invocation'],proof['invocation']);self.assertEqual(catalog[0]['source_path'],catalog[0]['delivery_path'])
        self.assertTrue(Path(proof['immutable_proof_path']).is_file())
        with self.assertRaises(ValueError):b.load_complete(self.root/'audit','fixture_only',self.rows[:-1],2)
    def test_current_version_receipts_and_catalog_bind_historical_identity(self):
        row=self.rows[0]
        version=version_fields(row['relative_path'],row['source_id'],'f'*64,row['source_sha256'])
        row.update(version,expected_source_bytes=Path(row['source']).stat().st_size)
        self.assertTrue(self.run_pass()['completion_claim'])
        catalog,_,_=b.load_complete(self.root/'audit','fixture_only',self.rows,2)
        self.assertEqual({key:catalog[0][key] for key in version},version)
        bad=copy.deepcopy(self.rows);bad[0]['source_version_id']='e'*64
        with self.assertRaisesRegex(ValueError,'source-version identity'):
            b.validate_rows(bad,2)
        row['expected_source_bytes']+=1
        self.assertFalse(self.run_pass()['completion_claim'])
    def test_resume_rereads_all_bytes_and_preserves_old_success_and_failure(self):
        first=self.run_pass();source=Path(self.rows[0]['source']);old=source.stat();original=source.read_bytes();source.write_bytes(b'changed fixture!');os.utime(source,ns=(old.st_atime_ns,old.st_mtime_ns))
        with mock.patch.object(b,'receipt',wraps=b.receipt) as spy:failed=self.run_pass(resume_pass=first['pass_id']);self.assertEqual(collections.Counter(str(call.args[0]) for call in spy.call_args_list if str(call.args[0]) in {r['source'] for r in self.rows}),collections.Counter(r['source'] for r in self.rows))
        self.assertFalse(failed['completion_claim']);self.assertEqual(failed['failed_file_records'],1)
        self.assertTrue(Path(first['immutable_proof_path']).exists())
        with self.assertRaises(ValueError):b.load_complete(self.root/'audit','fixture_only',self.rows,2)
        source.write_bytes(original);last=self.run_pass(resume_pass=first['pass_id']);self.assertTrue(last['completion_claim'])
        self.assertEqual(len(last['earlier_checkpoint_files']),2)
    def test_interrupted_resume_invalidates_old_current_success_but_preserves_it(self):
        first=self.run_pass()
        with mock.patch.object(b,'receipt',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.run_pass(resume_pass=first['pass_id'])
        current=json.loads((self.root/'audit/latest_status.json').read_text());self.assertEqual(current['status'],'running');self.assertFalse(current['completion_claim'])
        self.assertTrue(Path(first['immutable_proof_path']).is_file())
        with self.assertRaises(ValueError):b.load_complete(self.root/'audit','fixture_only',self.rows,2)
        resumed=self.run_pass(resume_pass=first['pass_id']);self.assertTrue(resumed['completion_claim']);self.assertEqual(len(resumed['earlier_checkpoint_files']),2)
    def test_changed_metadata_invalidates_receipt_and_resume(self):
        first=self.run_pass();self.meta.write_text('{"changed":true}')
        with self.assertRaises(ValueError):b.load_complete(self.root/'audit','fixture_only',self.rows,2)
        self.pins[str(self.meta)]=c.digest(self.meta)
        with self.assertRaises(ValueError):self.run_pass(resume_pass=first['pass_id'])
    def test_authorized_preflight_failure_supersedes_old_pointer(self):
        first=self.run_pass();old=Path(first['immutable_proof_path']);old_bytes=old.read_bytes()
        pointer=self.root/'audit/latest_status.json'
        with self.assertRaisesRegex(ValueError,'prerequisite changed'):
            with b.begin_pass(self.root/'audit'):
                self.assertEqual(c.read(pointer)['status'],'running')
                raise ValueError('prerequisite changed')
        self.assertEqual(c.read(pointer)['status'],'failed_preflight_or_audit')
        self.assertFalse(c.read(pointer)['completion_claim'])
        self.assertEqual(old.read_bytes(),old_bytes)
        with self.assertRaises(ValueError):
            b.load_complete(self.root/'audit','fixture_only',self.rows,2)
    def test_guard_failure_and_resume_metadata_mismatch_invalidate_previous_success(self):
        for failure in ('metadata guard','resume mismatch'):
            with self.subTest(failure=failure):
                first=self.run_pass()
                if failure=='metadata guard':
                    guard=mock.Mock(side_effect=ValueError('WAL appeared'))
                    with self.assertRaisesRegex(ValueError,'WAL appeared'):
                        self.run_pass(resume_pass=first['pass_id'],metadata_guard=guard)
                else:
                    self.pins[str(self.meta)]='c'*64
                    with self.assertRaisesRegex(ValueError,'Resume metadata/source set changed'):
                        self.run_pass(resume_pass=first['pass_id'])
                    self.pins[str(self.meta)]=c.digest(self.meta)
                current=c.read(self.root/'audit/latest_status.json')
                self.assertFalse(current['completion_claim'])
                self.assertNotEqual(current['invocation'],first['invocation'])
                self.assertTrue(Path(first['immutable_proof_path']).exists())
    def test_missing_duplicate_original_or_wrong_original_identity_rejected(self):
        for bad in [self.rows[:-1],[self.rows[0],self.rows[0]]]:
            with self.assertRaises(ValueError):b.validate_rows(bad,2)
        bad=copy.deepcopy(self.rows);bad[0]['delivery_path']=str(self.root/'copy.webp')
        with self.assertRaises(ValueError):b.validate_rows(bad,2)
    def test_tampered_pointer_or_checkpoint_refused(self):
        proof=self.run_pass();pointer=self.root/'audit/latest_status.json';document=json.loads(pointer.read_text());document['proof_sha256']='0'*64;pointer.write_text(json.dumps(document))
        with self.assertRaises(ValueError):b.load_complete(self.root/'audit','fixture_only',self.rows,2)
    def test_current_invocation_record_completeness_not_count_only(self):
        proof=self.run_pass();checkpoint=Path(proof['checkpoint_path']);lines=checkpoint.read_text().splitlines();checkpoint.write_text(lines[0]+'\n'+lines[0]+'\n')
        proof['checkpoint_sha256']=c.digest(checkpoint);immutable=Path(proof['immutable_proof_path']);immutable.write_text(json.dumps(proof));pointer=self.root/'audit/latest_status.json';p=json.loads(pointer.read_text());p['proof_sha256']=c.digest(immutable);pointer.write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError,'duplicate byte receipt'):b.load_complete(self.root/'audit','fixture_only',self.rows,2)
    def test_lossless_delivery_required_and_output_bytes_read(self):
        out=self.root/'accepted.webp';out.write_bytes(fake_lossless());row=self.rows[0];row.update(status='accepted',delivery_kind='cleaned',delivery_path=str(out),delivery_sha256=c.digest(out))
        proof=self.run_pass();self.assertTrue(proof['completion_claim']);catalog,_,_=b.load_complete(self.root/'audit','fixture_only',self.rows,2);self.assertEqual(catalog[0]['delivery_kind'],'cleaned')
        raw=b'RIFF'+(12).to_bytes(4,'little')+b'WEBPVP8 '+(0).to_bytes(4,'little');out.write_bytes(raw);row['delivery_sha256']=c.digest(out)
        with self.assertRaises(ValueError):b.receipt(out,row['delivery_sha256'],require_lossless=True)
    def test_stable_stat_failure_even_when_sha_matches(self):
        from types import SimpleNamespace
        actual=os.fstat;calls=0
        def altered(fd):
            nonlocal calls
            stat=actual(fd);calls+=1
            return stat if calls==1 else SimpleNamespace(st_dev=stat.st_dev,st_ino=stat.st_ino,st_size=stat.st_size,st_mtime_ns=stat.st_mtime_ns,st_ctime_ns=stat.st_ctime_ns+1,st_mode=stat.st_mode,st_nlink=stat.st_nlink)
        with b.audit_worker():
            with mock.patch.object(b.os,'fstat',side_effect=altered):record=b.receipt(self.rows[0]['source'],self.rows[0]['source_sha256'])
        self.assertFalse(record['stable_during_read']);self.assertFalse(record['matches'])
    def test_concurrent_pass_refused_before_authority_or_source_reads(self):
        import fcntl
        first=self.run_pass();pointer=self.root/'audit/latest_status.json';before=pointer.read_bytes()
        with (self.root/'audit/audit.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with mock.patch.object(b,'receipt',side_effect=AssertionError('concurrent pass must not read sources')):
                with self.assertRaises(BlockingIOError):self.run_pass()
        self.assertEqual(pointer.read_bytes(),before);self.assertTrue(Path(first['immutable_proof_path']).is_file())
    def test_immutable_receipt_never_overwritten(self):
        path=self.root/'immutable';b.immutable_write(path,b'one');b.immutable_write(path,b'one')
        with self.assertRaises(ValueError):b.immutable_write(path,b'two')
    def test_builder_viewer_uses_linked_original_and_lossless_with_sizes(self):
        out=self.root/'accepted.webp';out.write_bytes(fake_lossless());self.rows[0].update(status='accepted',delivery_kind='cleaned',delivery_path=str(out),delivery_sha256=c.digest(out))
        proof=self.run_pass();catalog,_,sha=b.load_complete(self.root/'audit','fixture_only',self.rows,2);target=self.root/'delivery';summary=delivery.build(catalog,proof,sha,target)
        self.assertEqual(summary['scope_total'],2);self.assertFalse(summary['images_copied_or_changed'])
        self.assertEqual({p.suffix for p in target.iterdir()},{'.json','.jsonl','.html'})
        result=subprocess.run(['node',str(c.HERE/'verify_final_delivery.cjs'),str(target)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);verification=json.loads((target/'viewer_verification.json').read_text());self.assertTrue(verification['exact_bindings_files_and_artifact_hashes'])
    def test_builder_refuses_noncomplete_audit(self):
        with self.assertRaises(ValueError):delivery.build([],{'status':'blocked','completion_claim':False},'0'*64,self.root/'not_created')
        self.assertFalse((self.root/'not_created').exists())
if __name__=='__main__':unittest.main()
