"""Isolated metadata contracts only: no source decoding or actual user-image output."""
import copy,subprocess,sys,tempfile,unittest
from pathlib import Path
import common as c
import contracts as k
import scope_metadata as s
from source_versions import source_id

class RuntimeCoreTests(unittest.TestCase):
    def fixtures(self):
        original={};versions=[]
        for number,style in enumerate(('3D animated cartoon','Flat outlined','Clay plasticine')):
            rel=style+'/Topic/concept.webp';sha=str(number+1)*64;sourceid=source_id(rel,sha);subject=number==0
            original[rel]={'source_sha256':sha,'dimensions':[512,512],'partition':'review_required' if subject else 'screened_original_unchanged','subject_id':'np00001' if subject else None}
            versions.append({'batch_id':'np00001' if subject else 'r_'+sourceid[:20],'production_source_id':sourceid,'source':str(c.LIBRARY/rel),'source_sha256':sha,'dimensions':[512,512],
                'role':'subject' if subject else 'reference','review_required':subject,'style':style})
        return original,[{'versions':versions}]
    def test_original_collection_anchors_ignore_visible_topic(self):
        self.assertTrue(s.original_collection('Second batch/Other/Non-people/People.webp'))
        self.assertFalse(s.original_collection('People/Non-people label.webp'))
        self.assertFalse(s.original_collection('Second batch/Other/People/object.webp'))
    def test_valid_isolated_roles_and_exact_original_identity(self):
        original,groups=self.fixtures();self.assertEqual(len(k.validate_versions(groups,original)),1)
        row=groups[0]['versions'][0];k.original_identity({'delivery':'original','path':row['source'],'sha256':row['source_sha256']},row)
    def test_wrong_scope_namespace_sha_dimensions(self):
        for field,value in [('batch_id','rp00001'),('batch_id','np99999'),('production_source_id','bad'),('source_sha256','f'*64),('dimensions',[1024,1024]),('source',str(c.LIBRARY/'Unknown/x.webp'))]:
            original,groups=self.fixtures();groups[0]['versions'][0][field]=value
            with self.assertRaises(ValueError):k.validate_versions(groups,original)
    def test_reference_sha_dimensions_style_or_subject_overlap(self):
        for field,value in [('source_sha256','e'*64),('dimensions',[1024,1024]),('style','wrong')]:
            original,groups=self.fixtures();groups[0]['versions'][1][field]=value
            with self.assertRaises(ValueError):k.validate_versions(groups,original)
        original,groups=self.fixtures();groups[0]['versions'][1]['source']=groups[0]['versions'][0]['source']
        with self.assertRaises(ValueError):k.validate_versions(groups,original)
    def test_duplicate_source_and_reference_paths(self):
        original,groups=self.fixtures();groups[0]['versions'].append(copy.deepcopy(groups[0]['versions'][1]))
        with self.assertRaises(ValueError):k.validate_versions(groups,original)
    def test_missing_duplicate_outputs_and_review_coverage(self):
        _,groups=self.fixtures();row=groups[0]['versions'][0];ident=row['batch_id']
        runs=[{'id':ident,'status':'changed','source_sha256':row['source_sha256'],'output_sha256':'a'*64}]
        decisions=[{'id':ident,'source_sha256':row['source_sha256'],'reviewer':'source'}]
        reviews=[{'id':ident,'source_sha256':row['source_sha256'],'output_sha256':'a'*64,'reviewer':'output','actually_viewed':True,'full_and_allregions_checked':True}]
        k.exact_outputs([row],runs,decisions,reviews)
        for mutated_runs,mutated_reviews in [([],reviews),(runs+runs,reviews),(runs,[]),(runs,reviews+reviews)]:
            with self.assertRaises(ValueError):k.exact_outputs([row],mutated_runs,decisions,mutated_reviews)
        reviews[0]['reviewer']='source'
        with self.assertRaises(ValueError):k.exact_outputs([row],runs,decisions,reviews)
    def test_skipped_original_identity_rejects_copy_or_new_sha(self):
        _,groups=self.fixtures();row=groups[0]['versions'][0]
        for delivery in [{'delivery':'original','path':'/tmp/copied.webp','sha256':row['source_sha256']},{'delivery':'original','path':row['source'],'sha256':'bad'}]:
            with self.assertRaises(ValueError):k.original_identity(delivery,row)
    def test_exact_resolution_overlay_no_trial_import_or_prior_review_claim(self):
        rows={};records=[]
        for n in range(7):
            rel=f'Any/Topic/{n}.webp';review=n<5;source=str(c.LIBRARY/rel);sha=str(n)*64;ident=f'np{n+1:05d}' if review else None
            rows[rel]={'relative_path':rel,'source_path':source,'source_sha256':sha,'lineage_hold':True,'partition':'review_required' if review else 'below_total_original_unchanged','proposed_subject_id':ident}
            records.append({'relative_path':rel,'source_path':source,'source_sha256':sha,'review_required':review,'trial_output_import_allowed':False,'completed_source_review_claimed':False,
                'resolution':'fresh_original_source_review_required' if review else 'original_retained_below_total_threshold_pending_final_byte_proof','proposed_subject_id':ident})
        doc={'status':'approved_for_new_cohort_preparation_only','records':records};self.assertEqual(len(s.resolution_overlay(rows,doc)),7)
        for changed in ('missing','duplicate','trial','prior_review'):
            bad=copy.deepcopy(doc)
            if changed=='missing':bad['records'].pop()
            elif changed=='duplicate':bad['records'].append(bad['records'][0])
            else:bad['records'][0]['trial_output_import_allowed' if changed=='trial' else 'completed_source_review_claimed']=True
            with self.assertRaises(ValueError):s.resolution_overlay(rows,bad)
    def test_no_actual_bootstrap_or_batch_materialization_permitted(self):
        protected=[c.HERE/name for name in ('inventory.json','queue.json','batch_index.json','ledger.jsonl','batches')]
        self.assertTrue(all(not p.exists() for p in protected))
        for script,args in [('bootstrap_inventory.py',['--initialize']),('prepare_batch.py',['--batch-id','batchN001']),('activation_gate.py',[])]:
            result=subprocess.run([sys.executable,str(c.HERE/script),*args],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
        self.assertTrue(all(not p.exists() for p in protected))
    def test_existing_component_catalogue_and_masks_match_frozen_people_method(self):
        import fcntl,os,ast
        current=os.getpriority(os.PRIO_PROCESS,0)
        if current<10:os.nice(10-current)
        with (c.HERE.parent/'production/image_worker.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            try:
                import numpy as np
                from scipy import ndimage as ndi
                from prepare_source_previews import component_inventory
                old=c.HERE.parent/'production_remaining_people/prepare_source_previews.py'
                import compile_decisions
                archive=c.HERE/'implementation_history/reviewed_cb8e820f3a365473/compile_decisions.py'
                baseline=archive.read_text()
                compiler=Path(compile_decisions.__file__).read_text()
                expected_body=baseline.split("    assert batch.is_relative_to",1)[1].split("\nif __name__",1)[0]
                actual_body=compiler.split("    assert batch.is_relative_to",1)[1].split("\nif __name__",1)[0]
                self.assertEqual(actual_body,expected_body.replace('args.approve','approve'))
                # Extract only this pure function; no legacy module/common import collision.
                def component_ast(path):
                    return next(n for n in ast.parse(path.read_text()).body
                                if isinstance(n,ast.FunctionDef) and n.name=='component_inventory')
                node=component_ast(old)
                current_source=Path(sys.modules['prepare_source_previews'].__file__)
                self.assertEqual(ast.dump(node),ast.dump(component_ast(current_source)))
                namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(old),'exec'),namespace)
                image=np.zeros((512,512,4),dtype=np.uint8);image[2:4,2:4]=255;image[10:20,10:20]=255
                current=component_inventory(np,ndi,image,[512,512]);prior=namespace['component_inventory'](np,ndi,image,[512,512])
                self.assertTrue(np.array_equal(current[0],prior[0]));self.assertTrue(np.array_equal(current[1],prior[1]));self.assertEqual(current[2:],prior[2:])
                self.assertEqual([r['area_pixels_native'] for r in current[2]],[100])
            finally:fcntl.flock(lock,fcntl.LOCK_UN)
    def test_stable_stat_sha_audit_primitive_uses_only_isolated_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.bin';p.write_bytes(b'isolated fixture')
            signature=c.stable_source_sha(p,c.digest(p));self.assertEqual(signature['bytes'],16)
            with self.assertRaises(ValueError):c.stable_source_sha(p,'0'*64)

if __name__=='__main__':unittest.main()
