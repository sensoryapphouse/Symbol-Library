"""Small byte-only fixtures: no image decoding, editing, or production sealing."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import seal
from qa import read,sha


class AcceptanceTests(unittest.TestCase):
 def fixture(self,root):
  batch=Path(root)/'batch';batch.mkdir()
  protocol=read(Path(seal.__file__).parent/'protocol.json')
  cleaner=protocol['engine']['sha256']
  rows=[];runs=[];checks=[];reviews=[];decisions=[]
  def write(path,data):path.write_text(json.dumps(data))
  for n,worth in enumerate(('clear','modest','uncertain')):
   id='p'+str(n);source=Path(root)/(id+'.source');source.write_bytes(b'original'+id.encode())
   row={'batch_id':id,'source':str(source),'source_sha256':sha(source)};rows.append(row)
   decisions.append({'id':id,'reviewer':'source'})
   f=batch/'selected_outputs'/id;f.mkdir(parents=True);(f/'after.webp').write_bytes(b'output'+id.encode())
   runs.append({'id':id,'status':'changed','output_sha256':sha(f/'after.webp')})
   reviews.append({'id':id,'source_sha256':sha(source),'output_sha256':sha(f/'after.webp'),'reviewer':'output','actually_viewed':True,'full_and_allregions_checked':True,'safety':'clear','worthwhile':worth,'reason':'Small real benefit; retain original.' if worth=='modest' else 'Reviewed benefit.'})
  checkpoints=batch/'source_reviews';checkpoints.mkdir()
  write(checkpoints/'g1.json',{'source_records':[{'id':row['batch_id']} for row in rows]})
  write(batch/'manifest.json',{'groups':[{'group_id':'g1','versions':rows}]});write(batch/'approved_decisions.json',{'decisions':decisions,'source_checkpoint_sha256':{'g1.json':sha(checkpoints/'g1.json')}})
  write(batch/'selected_run_state.json',{'status':'complete','cleaner_sha256':cleaner,'images':runs})
  for row,run in zip(rows,runs):
   f=batch/'selected_outputs'/row['batch_id']
   write(f/'result.json',{'manifest_sha256':sha(batch/'manifest.json'),'decision_sha256':sha(batch/'approved_decisions.json'),'cleaner_sha256':cleaner,'source_sha256':row['source_sha256'],'output_sha256':run['output_sha256']})
   checks.append({'id':row['batch_id'],'passed':True,'result_sha256':sha(f/'result.json'),'artifact_sha256':{'after.webp':sha(f/'after.webp')},'output_sha256':run['output_sha256']})
  audit={k:sha(batch/v) for k,v in [('manifest_sha256','manifest.json'),('decisions_sha256','approved_decisions.json'),('run_state_sha256','selected_run_state.json')]}
  audit.update(auditor_sha256=sha(Path(seal.__file__).parent/'qa.py'),protocol_sha256=sha(Path(seal.__file__).parent/'protocol.json'),cleaner_sha256=cleaner,errors=[],images=checks)
  write(batch/'mechanical_audit.json',audit);write(batch/'independent_output_review.json',{'images':reviews})
  return batch
 def run_seal(self,batch,adopt=False):
  with contextlib.redirect_stdout(io.StringIO()):seal.seal(batch,adopt)
 def legacy(self,batch):
  self.run_seal(batch)
  target=batch/'accepted_delivery.json';d=read(target)
  d.pop('acceptance_policy_sha256');d.pop('acceptance_policy_version')
  for row in d['images']:
   if row['id']=='p1':
    f=batch/'accepted_outputs'/'p1';f.rename(batch/'selected_outputs'/'p1')
    row.update(delivery='original',path=row['source_path'],sha256=row['source_sha256'],reason='Original retained: Small real benefit; retain original.');row.pop('reviewer')
  d['cleaned']=1;d['originals_retained']=2;target.write_text(json.dumps(d))
  return target.read_bytes()
 def test_truth_table(self):
  policy=seal.load_policy()
  for safety in ('clear','uncertain','unsafe'):
   for worth in ('clear','modest','negligible','uncertain'):
    self.assertEqual(seal.accepts({'safety':safety,'worthwhile':worth},policy),safety=='clear' and worth in ('clear','modest'))
 def test_fresh_and_noop(self):
  with tempfile.TemporaryDirectory() as root:
   batch=self.fixture(root);self.run_seal(batch);target=batch/'accepted_delivery.json';before=target.read_bytes();self.run_seal(batch)
   self.assertEqual(target.read_bytes(),before);d=read(target);self.assertEqual(d['cleaned'],2)
   self.assertEqual(d['acceptance_policy_sha256'],sha(seal.POLICY_PATH));self.assertNotIn('retain original',d['images'][1]['reason'])
 def test_legacy_noop_adoption_archive_and_resume(self):
  with tempfile.TemporaryDirectory() as root:
   batch=self.fixture(root);before=self.legacy(batch);target=batch/'accepted_delivery.json';self.run_seal(batch)
   self.assertEqual(target.read_bytes(),before);self.assertTrue((batch/'selected_outputs'/'p1').exists())
   # Simulate interruption after folder moves but before delivery replacement.
   (batch/'selected_outputs'/'p1').rename(batch/'accepted_outputs'/'p1')
   self.run_seal(batch,True)
   self.assertEqual((batch/'delivery_history'/(hashlib.sha256(before).hexdigest()+'.json')).read_bytes(),before)
   self.assertEqual(read(target)['cleaned'],2);after=target.read_bytes();self.run_seal(batch,True);self.assertEqual(after,target.read_bytes())
 def test_whole_batch_validation_before_moves(self):
  with tempfile.TemporaryDirectory() as root:
   batch=self.fixture(root);(batch/'selected_outputs'/'p2'/'after.webp').write_bytes(b'tamper')
   with self.assertRaises(AssertionError):self.run_seal(batch)
   self.assertFalse((batch/'accepted_outputs').exists());self.assertFalse((batch/'accepted_delivery.json').exists())
 def test_source_amendment_rejected_before_any_delivery_mutation(self):
  with tempfile.TemporaryDirectory() as root:
   batch=self.fixture(root)
   checkpoint=batch/'source_reviews'/'g1.json'
   checkpoint.write_text(checkpoint.read_text()+'\n')
   with self.assertRaisesRegex(AssertionError,'Source decisions changed'):
    self.run_seal(batch)
   self.assertFalse((batch/'accepted_outputs').exists());self.assertFalse((batch/'accepted_delivery.json').exists())
   self.assertTrue(all((batch/'selected_outputs'/('p'+str(n))).is_dir() for n in range(3)))
 def test_source_checkpoint_coverage_is_exact(self):
  for mutation in ('missing_pin','extra_pin','missing_file'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as root:
    batch=self.fixture(root);target=batch/'approved_decisions.json';d=read(target)
    if mutation=='missing_file':(batch/'source_reviews'/'g1.json').unlink()
    else:
     if mutation=='missing_pin':d['source_checkpoint_sha256'].clear()
     else:d['source_checkpoint_sha256']['unrelated.json']='0'*64
     target.write_text(json.dumps(d))
    with self.assertRaisesRegex(AssertionError,'source checkpoint|Source decisions changed'):
     self.run_seal(batch)
    self.assertFalse((batch/'accepted_outputs').exists());self.assertFalse((batch/'accepted_delivery.json').exists())
 def test_migration_rejects_prior_delivery_mutation_without_moves(self):
  with tempfile.TemporaryDirectory() as root:
   batch=self.fixture(root);self.legacy(batch);target=batch/'accepted_delivery.json';d=read(target);d['images'][0]['reason']='Tampered';target.write_text(json.dumps(d));before=target.read_bytes()
   with self.assertRaises(AssertionError):self.run_seal(batch,True)
   self.assertEqual(target.read_bytes(),before);self.assertTrue((batch/'selected_outputs'/'p1').exists());self.assertFalse((batch/'delivery_history').exists())

if __name__=='__main__':unittest.main()
