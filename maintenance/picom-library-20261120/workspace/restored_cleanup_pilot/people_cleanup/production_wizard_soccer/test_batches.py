"""Synthetic fixtures only; original shared worker is held for every test."""
import contextlib,fcntl,json,sqlite3,tempfile,unittest
from unittest.mock import patch
import contracts as C
import engine,gates,batches as B,review_evidence as E,workflow as W

class Synthetic(unittest.TestCase):
 def setUp(self):
  self.lock=C.worker();self.lock.__enter__();self.temp=tempfile.TemporaryDirectory(prefix='fixture-',dir=C.HERE);self.root=C.Path(self.temp.name)
  self.np,self.Image,*_=engine.stack();self.ctx=contextlib.ExitStack();self.count=0
  self.ctx.enter_context(patch.multiple(B,HERE=self.root,FROZEN=self.root/'population/frozen_sources.json',PLAN=self.root/'population/batch_plan.json',LATEST=self.root/'proofs/latest_status.json',RUNTIME=self.root/'runtime',SCOPE=2,AVAILABLE=2,HELD=0))
  self.ctx.enter_context(patch.object(E,'HERE',self.root))
  self.ctx.enter_context(patch.object(W,'SCOPE',2));self.bundle_mock=self.ctx.enter_context(patch.object(C,'check_bundle',return_value='fixture-bundle'));self.ctx.enter_context(patch.object(B,'check_bundle',return_value='fixture-bundle'))
  self.ctx.enter_context(patch.object(B,'worker',side_effect=contextlib.nullcontext));self.gate=self.ctx.enter_context(patch.object(gates,'enter'))
 def tearDown(self):self.ctx.close();self.temp.cleanup();self.lock.__exit__(None,None,None)
 def write(self,path,value):
  path=C.Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(C.payload(value));return path
 def source(self,gap=False):
  a=self.np.full((512,512,4),255,dtype=self.np.uint8);a[100:410,100:410,:3]=[20,70,130]
  if gap:a[200:230,200:230,:3]=255
  return a
 def approval(self,action,inputs=()):
  self.count+=1
  return self.write(self.root/f'approval-{self.count}.json',dict(approved=True,approved_by='root',bundle_sha256='fixture-bundle',execution_actor='fixture-worker',allowed_actions=[action],approved_inputs={str(C.Path(p).resolve()):C.file_sha(p) for p in inputs}))
 def sequencing_approval(self):
  approval=self.approval('nonpeople_gate');pointer=C.read(B.LATEST);proof=C.read(pointer['proof_path'])
  np_bundle=self.write(self.root/'production_non_people/code_bundle.json',{})
  self.ctx.enter_context(patch.object(B,'NP_BUNDLE',np_bundle))
  policy=self.write(self.root/'sequencing.json',dict(schema='root-non-people-sequencing-v1',approved_by='root',
   decision='proceed_after_available_cleanup',wizard_bundle_sha256='fixture-bundle',non_people_bundle_sha256=C.file_sha(np_bundle),
   wizard_proof_sha256=pointer['proof_sha256'],held_sha256=proof['held_sha256']))
  return self.write(approval,dict(C.read(approval),non_people_policy=dict(path=str(policy),sha256=C.file_sha(policy))))
 def setup_population(self,gap=False):
  metadata=self.write(self.root/'authority.json',dict(status='fixture-complete'));rows=[];held=[]
  held_lane=getattr(self,'held_lane',None)
  for lane,style in ((106,'Wizard'),(107,'Soccer player')):
   path=self.root/'originals'/style/'fixture.webp'
   row=dict(target_id=f'{lane}:people-fixture',concept_id='people-fixture',style_queue=lane,style=style,category='Fixture',word='action',ordinal=0,relative_target=f'People/{style}/Fixture/action.webp',target=str(path))
   if lane==held_lane:
    held.append(dict(row,disposition='generation_held',target_absent=True))
    continue
   selected=gap[0 if lane==106 else 1] if isinstance(gap,tuple) else gap;a=self.source(selected)
   if lane==107 and getattr(self,'partner_different_pose',False):a[50:80,160:350,:3]=[20,70,130]
   C.immutable(path,engine.exact_webp(a));_,receipt=C.stable_bytes(path)
   rows.append(dict(row,true_original=receipt))
  closeout=dict(path=str(metadata),sha256=C.file_sha(metadata))
  self.gate.return_value=dict(original_people=dict(authority_sha256={str(metadata):C.file_sha(metadata)}),generation=dict(
   metadata_sha256={str(metadata):C.file_sha(metadata)},rows=[dict(target_id=r['target_id'],source=r['target'],source_sha256=r['true_original']['sha256'],job='fixture-saved') for r in rows],
   held=held,absent_generation_wal=str(self.root/'absent-wal')),generation_closeout=closeout,bundle_sha256='fixture-bundle')
  self.write(B.FROZEN,dict(scope_total=2,rows=rows,gate=self.gate.return_value));self.write(B.PLAN,B.make_plan(rows,1,held));return rows
 def prepare(self,gap=False):
  self.setup_population(gap);B.prepare_batch(self.approval('prepare_batch',[B.FROZEN,B.PLAN]),'batch-0001');folder=B.batch_folder('batch-0001');return folder,C.read(folder/'ticket.json')
 def journal(self,folder,phase,order,catalog,reviews,modify_displays=None):
  events=[];previous=None;seq=0;stamp='2026-11-05T22:00:00+00:00'
  for index,identity in enumerate(order):
   groups={}
   for role,asset in catalog[identity][phase].items():groups.setdefault(asset['path'],[]).append(role)
   displays=[]
   for path,roles in groups.items():
    asset=catalog[identity][phase][roles[0]]
    displays.append(dict(type='display',target_id=identity,phase=phase,utc=stamp,actually_displayed=True,native_resolution=True,outcome='complete',roles=roles,path=path,sha256=asset['sha256'],dimensions=asset['dimensions']))
   if modify_displays:displays=modify_displays(displays)
   for number,display in enumerate(displays):
    seq+=1;display=dict(display,sequence=seq,tool_event_reference=f'synthetic-fixture-{seq}',display_event_id=f'{phase}-{seq}')
    display.setdefault('exec_id',f'{phase}-fixture-{index}-{number//4}');display.setdefault('exec_file_index',number%4+1);events.append(display)
   seq+=1;reviewer=reviews[identity]['reviewer'];checkpoint=dict(schema='ordered-review-checkpoint-v1',batch_id='batch-0001',target_id=identity,phase=phase,case_index=index,event_sequence=seq,previous_checkpoint_sha256=previous,review_sha256=C.sha(C.payload(reviews[identity])),reviewer=reviewer,utc=stamp)
   path=self.write(folder/'review_metadata/checkpoints'/f'{phase}-{index}.json',checkpoint);previous=C.file_sha(path)
   events.append(dict(sequence=seq,type='checkpoint',target_id=identity,phase=phase,utc=stamp,reviewer=reviewer,checkpoint_path=str(path),checkpoint_sha256=previous))
  path=folder/'review_logs'/f'{phase}.jsonl';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(''.join(json.dumps(e)+'\n' for e in events));return path,events
 def finish(self,gap=False):
  folder,ticket=self.prepare(gap);choices={}
  for case in ticket['cases']:
   if not case['source_required']:continue
   raw,_=C.stable_bytes(case['outer']['path'],case['outer']['sha256']);labels,_=engine.components(engine.decode(raw))
   choices[case['target_id']]=dict(target_id=case['target_id'],true_original_sha256=case['true_original']['sha256'],stage_sha256=case['outer']['sha256'],stage_rgba_sha256=case['outer']['rgba_sha256'],stage_component_inventory_sha256=C.sha(C.payload(case['components'])),paired_context_sha256=C.sha(C.payload(case['paired_context'])),same_pose_support=C.PARTNER_UNAVAILABLE if 'held_disposition' in case['paired_context'] else ('different_pose' if getattr(self,'partner_different_pose',False) else 'supports_same_pose'),same_pose_support_reason='Synthetic paired comparison; components and masks selected independently for this stage.',actually_viewed=True,reviewer='fixture-source',decision='cleanup',regions=[dict(name='full enclosed component',component_labels=[int(labels[210,210])])])
  cp=self.write(folder/'source-decisions.json',choices);ep,_=self.journal(folder,'source',ticket['source_case_order'],ticket['source_catalog'],choices)
  B.finish_batch(self.approval('finish_batch',[folder/'ticket.json',cp,ep]),'batch-0001',cp,ep);return folder,ticket,C.read(folder/'finals.json')
 def close(self,gap=False):
  folder,ticket,finals=self.finish(gap);reviews={}
  for c in finals['cases']:
   if not c['changed_vs_true_original']:continue
   reviews[c['target_id']]=dict(target_id=c['target_id'],source_sha256=c['true_original']['sha256'],outer_sha256=c['outer']['sha256'],output_sha256=c['final']['sha256'],final_record_sha256=C.sha(C.payload(c)),reviewer='fixture-independent',actually_viewed=True,full_and_allregions_checked=True,true_original_native_viewed=True,final_native_viewed=True,blue_dark_and_alpha_native_viewed=True,reason='Synthetic safe modest benefit',review_assets_sha256=c['review_assets_sha256'],safety='clear',worthwhile='modest')
  rp=self.write(folder/'reviews.json',reviews);ep,_=self.journal(folder,'output',finals['output_case_order'],finals['output_catalog'],reviews)
  B.seal_batch(self.approval('seal_batch',[folder/'ticket.json',folder/'finals.json',rp,ep]),'batch-0001',rp,ep);return folder,C.read(folder/'closed_batch.json')
 def check_journal(self,folder,finals,mutate):
  order=finals['output_case_order'];reviews={i:dict(reviewer='fixture-independent') for i in order};_,events=self.journal(folder,'output',order,finals['output_catalog'],reviews);events=mutate(events)
  with self.assertRaises(ValueError):E.validate_journal(events,order,'output',finals['output_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in reviews.items()})
 def test_actual_lock_threads_and_exact_outer(self):
  with C.LOCK.open('a+') as second:
   with self.assertRaises(BlockingIOError):fcntl.flock(second,fcntl.LOCK_EX|fcntl.LOCK_NB)
  self.assertTrue(all(C.os.environ[k]=='1' for k in C.THREAD_KEYS));a=self.source(True);out,_=engine.outer(a);expected,_=engine.stack()[3].transform(a,manual_seeds=());self.assertTrue(self.np.array_equal(out,expected))
 def test_stack_preserves_import_precedence_without_growing_path(self):
  production = C.BASE / 'production'
  production_path = str(production)
  competing_path = str(self.root)
  (self.root / 'common.py').write_text("raise AssertionError('Wrong common module imported')\n")
  initial_path = [p for p in C.sys.path if p != production_path]
  with patch.object(C.sys, 'path', [competing_path, *initial_path]), patch.dict(C.sys.modules):
   C.sys.modules.pop('_ws_source_preview', None)
   C.sys.modules.pop('common', None)
   with patch.object(engine, 'runtime_versions', wraps=engine.runtime_versions) as versions:
    first_stack = engine.stack()
    self.assertEqual(C.sys.path, [production_path, competing_path, *initial_path])
    self.assertEqual(C.Path(C.sys.modules['common'].__file__), production / 'common.py')
    for _ in range(8):
     self.assertEqual(engine.stack(), first_stack)
     self.assertEqual(C.sys.path, [production_path, competing_path, *initial_path])
    self.assertEqual(versions.call_count, 9)
   C.sys.path.remove(competing_path)
   C.sys.path.insert(0, competing_path)
   a = self.source(True)
   pure = first_stack[3]
   expected, metrics = pure.transform(a, manual_seeds=())
   with patch.object(pure, 'transform', wraps=pure.transform) as transform:
    out, record = engine.outer(a)
   transform.assert_called_once_with(a, manual_seeds=())
   self.assertTrue(self.np.array_equal(out, expected))
   self.assertEqual(record['metrics'], metrics)
   self.assertEqual(C.sys.path, [production_path, competing_path, *initial_path])
 def test_transparent_identity_and_unexpected_opaque_hold(self):
  a=self.source();a[0,0,3]=128
  with patch.object(engine.stack()[3],'transform',side_effect=AssertionError('opaque called')):out,_=engine.outer(a)
  self.assertTrue(self.np.array_equal(a,out))
  with self.assertRaises(ValueError):engine.outer(self.np.full((64,64,4),255,dtype=self.np.uint8))
 def test_bounded_pairs_and_one_full_gate_per_batch_with_resume(self):
  folder,doc,finals=self.finish(True);self.assertEqual(self.gate.call_count,1);self.assertEqual(doc['case_order'],['106:people-fixture','107:people-fixture'])
  B.prepare_batch(self.approval('prepare_batch',[B.FROZEN,B.PLAN]),'batch-0001');cp=folder/'source-decisions.json';ep=folder/'review_logs/source.jsonl';B.finish_batch(self.approval('finish_batch',[folder/'ticket.json',cp,ep]),'batch-0001',cp,ep);self.assertEqual(self.gate.call_count,1)
  with self.assertRaises(ValueError):B.make_plan(C.read(B.FROZEN)['rows'],33)
 def test_omitted_roi_derives_correct_crop_without_mask_change(self):
  _,_,finals=self.finish(True)
  for c in finals['cases']:
   region=c['normalized_regions'][0];self.assertEqual(region['roi'],[200,200,230,230]);self.assertEqual(region['evidence_crop_roi'],[196,196,234,234]);self.assertEqual(c['inner_result']['changed_pixels'],900)
   roles=finals['output_catalog'][c['target_id']]['output'];self.assertEqual(roles['final-region-000.png']['dimensions'],[38,38])
   a=engine.decode(C.Path(c['outer']['path']).read_bytes());b=engine.decode(C.Path(c['final']['path']).read_bytes());self.assertTrue(self.np.array_equal(a[:,:,:3],b[:,:,:3]));self.assertEqual(int(self.np.any(a!=b,axis=2).sum()),900)
 def test_numeric_no_inner_has_no_fabricated_source_claim_but_changed_final_review(self):
  _,doc,finals=self.finish(False);self.assertEqual(doc['source_case_order'],[])
  for c in finals['cases']:
   self.assertIsNone(c['source_reviewer']);self.assertTrue(c['mechanical_no_inner']);self.assertFalse(c['no_inner_proof']['visual_review_claimed']);self.assertTrue(c['changed_vs_true_original']);self.assertEqual(c['outer']['path'],c['final']['path']);self.assertFalse(c['duplicate_final_created'])
 def test_no_inner_does_not_use_max_component_shortcut(self):
  a=self.np.zeros((512,512,4),dtype=self.np.uint8);a[:,:,3]=255
  for y in (10,30,50):a[y:y+10,10:20,:3]=255
  self.assertFalse(engine.no_inner_proof(a)['no_eligible_inner'])
 def test_aliases_are_pixel_proven_and_informative_final_roles_remain(self):
  _,_,f=self.finish(False);roles=f['output_catalog'][f['case_order'][0]]['output']
  for role in ('true-original-blue.png','true-original-dark.png'):self.assertEqual(roles[role]['sha256'],roles['true-original-native.png']['sha256']);self.assertTrue(roles[role]['equality_verified'])
  self.assertNotEqual(roles['final-blue.png']['sha256'],roles['final-native.png']['sha256']);self.assertIn('final-alpha.png',roles);self.assertLess(len(f['output_asset_sha256']),sum(len(x['output']) for x in f['output_catalog'].values()))
 def test_modest_policy_and_whole_true_original_hold(self):
  folder,closed=self.close(False);self.assertTrue(all(r['delivery']['delivery_kind']=='cleaned' for r in closed['rows']));c=C.read(folder/'finals.json')['cases'][0];r=C.read(folder/'reviews.json')[c['target_id']];r['safety']='uncertain';self.assertEqual(W.review_delivery(c,r)['path'],c['true_original']['path'])
 def test_omitted_crop_display_rejected(self):
  folder,_,f=self.finish(True)
  def change(events):
   event=next(e for e in events if e['type']=='display' and any('region-' in r for r in e['roles']));event['roles']=['final-native.png'];return events
  self.check_journal(folder,f,change)
 def test_wrong_role_binding_and_partial_display_rejected(self):
  folder,_,f=self.finish(False)
  def wrong(events):events[0]['path']='wrong.png';return events
  self.check_journal(folder,f,wrong);self.check_journal(folder,f,lambda events:events[:-1])
 def test_checkpoint_case_order_rejected(self):
  folder,_,f=self.finish(False)
  def wrong(events):events[0]['target_id']=f['case_order'][1];return events
  self.check_journal(folder,f,wrong)
 def test_durable_checkpoint_chain_tamper_rejected(self):
  folder,_,f=self.finish(False)
  def wrong(events):
   checkpoint=next(e for e in events if e['type']=='checkpoint');path=C.Path(checkpoint['checkpoint_path']);doc=C.read(path);doc['previous_checkpoint_sha256']='forged';self.write(path,doc);checkpoint['checkpoint_sha256']=C.file_sha(path);return events
  self.check_journal(folder,f,wrong)
 def test_durable_observation_writer_and_checkpoint_helper(self):
  folder,_,f=self.finish(False);order=f['output_case_order'];identity=order[0];roles=f['output_catalog'][identity]['output'];groups={};journal=folder/'review_logs/output.jsonl';sequence=0
  for role,asset in roles.items():groups.setdefault(asset['path'],[]).append(role)
  for path,names in groups.items():
   asset=roles[names[0]];sequence+=1;E.append_observed_display(journal,dict(type='display',sequence=sequence,target_id=identity,phase='output',utc='2026-11-05T22:00:00+00:00',actually_displayed=True,native_resolution=True,outcome='complete',exec_id=f'observed-{(sequence-1)//4}',exec_file_index=(sequence-1)%4+1,tool_event_reference=f'synthetic-observation-{sequence}',display_event_id=f'actual-fixture-{sequence}',roles=names,path=path,sha256=asset['sha256'],dimensions=asset['dimensions']))
  event=E.checkpoint_observed_case(journal,folder/'review_metadata/checkpoints','batch-0001','output',order,f['output_catalog'],dict(target_id=identity,reviewer='fixture-independent'),'2026-11-05T22:00:00+00:00')
  self.assertEqual(C.jsonl(journal)[-1],event);self.assertTrue(C.Path(event['checkpoint_path']).exists())
  with self.assertRaises(ValueError):E.checkpoint_observed_case(journal,folder/'review_metadata/checkpoints','batch-0001','output',order,f['output_catalog'],dict(target_id=order[1],reviewer='fixture-independent'),'2026-11-05T22:00:00+00:00')
 def test_source_display_checkpoint_binds_exact_decision(self):
  folder,ticket,_=self.finish(True);choices=C.read(folder/'source-decisions.json');events=C.jsonl(folder/'review_logs/source.jsonl');choices[ticket['source_case_order'][0]]['stage_sha256']='0'*64
  with self.assertRaises(ValueError):E.validate_journal(events,ticket['source_case_order'],'source',ticket['source_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in choices.items()})
 def test_source_and_authority_changes_are_detected_on_resume(self):
  folder,doc=self.prepare(False);self.write(self.root/'authority.json',dict(changed=True))
  with self.assertRaisesRegex(ValueError,'authority changed'):B.guard(doc['authority'])
 def test_current_source_change_invalidates_previous_status(self):
  _,doc=self.prepare(False);C.Path(doc['cases'][0]['true_original']['path']).write_bytes(b'changed')
  with self.assertRaises(ValueError):B.prepare_batch(self.approval('prepare_batch',[B.FROZEN,B.PLAN]),'batch-0001')
  self.assertFalse(C.read(B.LATEST)['completion_claim'])
 def test_previous_success_gate_failure_invalidates_before_preflight(self):
  self.setup_population();self.write(B.LATEST,dict(status='complete',completion_claim=True));self.gate.side_effect=ValueError('original proof pending')
  with self.assertRaises(ValueError):B.prepare_batch(self.approval('prepare_batch',[B.FROZEN,B.PLAN]),'batch-0001')
  self.assertEqual(C.read(B.LATEST)['status'],'failed_or_interrupted')
 def test_changed_approved_inputs_invalidate_before_gate(self):
  self.setup_population();approval=self.approval('prepare_batch',[B.FROZEN,B.PLAN]);B.PLAN.write_text('{}');self.write(B.LATEST,dict(status='complete',completion_claim=True))
  with self.assertRaises(ValueError):B.prepare_batch(approval,'batch-0001')
  self.assertEqual(self.gate.call_count,0);self.assertFalse(C.read(B.LATEST)['completion_claim'])
 def test_retirement_positive_preserves_masks_and_final_proof_consumes_missing_pngs(self):
  folder,closed=self.close(True);B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001');self.assertTrue(all(not C.Path(p).exists() for p in closed['temporary_png_sha256']));B.verify_temporary(folder,closed)
  rows,live,retired,_,_=B.all_closed();self.assertEqual(len(rows),2);self.assertEqual(len(retired),3);self.assertTrue(any('removed_core_mask.png' in p for p in live));self.assertTrue(all(C.Path(p).exists() for p in live if 'mask.png' in p))
 def test_retirement_interruption_resume_requires_completed_receipt(self):
  folder,closed=self.close(False);approval=self.approval('retire_batch',[folder/'closed_batch.json']);original=C.Path.unlink;count=[0]
  def interrupted(path,*args,**kwargs):
   if path.suffix=='.png':
    count[0]+=1
    if count[0]==2:raise KeyboardInterrupt('fixture interruption')
   return original(path,*args,**kwargs)
  with patch.object(C.Path,'unlink',interrupted),self.assertRaises(KeyboardInterrupt):B.retire_batch(approval,'batch-0001')
  self.assertTrue((folder/'retirement_intent.json').exists());self.assertFalse((folder/'retirement_complete.json').exists())
  with self.assertRaises(ValueError):B.verify_temporary(folder,closed)
  B.retire_batch(approval,'batch-0001');B.verify_temporary(folder,closed)
 def test_missing_png_before_intent_is_not_excused(self):
  folder,closed=self.close(False);C.Path(next(iter(closed['temporary_png_sha256']))).unlink()
  with self.assertRaises(ValueError):B.verify_temporary(folder,closed)
  with self.assertRaises(FileNotFoundError):B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001')
  self.assertFalse((folder/'retirement_intent.json').exists())
 def test_retirement_cannot_excuse_missing_mask(self):
  folder,closed=self.close(True);B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001');mask=next(p for p in closed['live_dependencies_sha256'] if 'removed_core_mask.png' in p);C.Path(mask).unlink()
  with self.assertRaises(FileNotFoundError):B.all_closed()
 def test_retirement_receipt_tamper_rejected(self):
  folder,closed=self.close(False);B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001');receipt=C.read(folder/'retirement_complete.json');receipt['retired_png_sha256']={};self.write(folder/'retirement_complete.json',receipt)
  with self.assertRaises(ValueError):B.verify_temporary(folder,closed)
 def test_final_failure_publishes_no_canonical_artifacts(self):
  folder,closed=self.close(False);C.Path(closed['rows'][0]['true_original']['path']).write_bytes(b'changed');self.write(B.LATEST,dict(status='complete',completion_claim=True))
  with self.assertRaises(ValueError):B.finalize(self.approval('finalize',[B.FROZEN,B.PLAN]))
  self.assertFalse((self.root/'delivery/final_delivery_manifest.jsonl').exists());self.assertFalse((self.root/'delivery/index.html').exists());self.assertFalse(C.read(B.LATEST)['completion_claim'])
 def test_final_dependency_failure_invalidates_old_success_before_publication(self):
  folder,closed=self.close(True);mask=next(p for p in closed['live_dependencies_sha256'] if 'removed_core_mask.png' in p);C.Path(mask).write_bytes(b'changed mask');self.write(B.LATEST,dict(status='complete',completion_claim=True))
  with self.assertRaises(ValueError):B.finalize(self.approval('finalize',[B.FROZEN,B.PLAN]))
  self.assertEqual(C.read(B.LATEST)['status'],'failed_or_interrupted');self.assertFalse((self.root/'delivery/final_delivery_manifest.jsonl').exists())
 def test_final_positive_full_bytes_with_retirement_then_np_gate(self):
  folder,_=self.close(False);B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001');B.finalize(self.approval('finalize',[B.FROZEN,B.PLAN]));proof=C.read(C.read(B.LATEST)['proof_path'])
  self.assertEqual(proof['originals_byte_checked_this_invocation'],2);self.assertEqual(proof['deliveries_byte_checked_this_invocation'],2);self.assertTrue(proof['retirement_dependencies_sha256']);self.assertTrue(B.nonpeople_ready(self.sequencing_approval())['ready'])
 def test_global_invocation_bundle_hash_validation_is_constant_not_per_target(self):
  self.close(False);approval=self.approval('finalize',[B.FROZEN,B.PLAN]);self.bundle_mock.reset_mock();B.finalize(approval);self.assertEqual(self.bundle_mock.call_count,1)
 def test_closed_delivery_tamper_cannot_change_true_original_or_fallback(self):
  folder,closed=self.close(False);closed['rows'][0]['delivery']=dict(delivery_kind='original',path=closed['rows'][0]['outer']['path'],sha256=closed['rows'][0]['outer']['sha256']);self.write(folder/'closed_batch.json',closed)
  with self.assertRaisesRegex(ValueError,'independently reviewed cases'):B.validate_closed(folder)
 def test_numeric_skip_still_requires_reviewer_independent_of_producer(self):
  folder,_,f=self.finish(False);c=f['cases'][0]
  review=dict(target_id=c['target_id'],source_sha256=c['true_original']['sha256'],outer_sha256=c['outer']['sha256'],output_sha256=c['final']['sha256'],final_record_sha256=C.sha(C.payload(c)),reviewer='fixture-worker')
  with self.assertRaisesRegex(ValueError,'independent of stage producers'):W.review_delivery(c,review)
 def test_interrupted_final_preserves_old_proof_not_old_success(self):
  self.close(False);approval=self.approval('finalize',[B.FROZEN,B.PLAN]);B.finalize(approval);old=C.read(B.LATEST);raw=C.Path(old['proof_path']).read_bytes()
  with patch.object(B,'all_closed',side_effect=KeyboardInterrupt('fixture interruption')),self.assertRaises(KeyboardInterrupt):B.finalize(approval)
  self.assertEqual(C.Path(old['proof_path']).read_bytes(),raw);self.assertEqual(C.read(B.LATEST)['status'],'failed_or_interrupted')
 def test_exact_generation_held_status_and_authority(self):
  runtime=self.root/'gen';prep=self.root/'prep';(runtime/'batch').mkdir(parents=True)
  registration=runtime/'wizard-soccer-registration-20261105/manifest.json'
  dbpath=runtime/'batch/wizard-soccer-inventory-20261105.sqlite'
  expected=[];hashes={};observed=[]
  with contextlib.closing(sqlite3.connect(dbpath)) as db, db:
   db.executescript('CREATE TABLE inventory(lane,id,entry,status,job,output_sha256);CREATE TABLE cleanup(job,receipt,status);')
   for lane,style in ((106,'Wizard'),(107,'Soccer player')):
    identity='people-fixture';target=str(self.root/f'People/{style}/Fixture/action.webp')
    job=f'fixture-{lane}';key=f'{lane}:{identity}'
    entry=json.dumps(dict(id=identity,target=target),sort_keys=True,separators=(',',':'))
    hashes[key]=C.sha(entry.encode())
    expected.append(dict(target_id=key,target=target,style=style,style_queue=lane,concept_id=identity,relative_target=f'People/{style}/Fixture/action.webp',ordinal=0,category='Fixture',word='action'))
    sp=runtime/'batch/specs'/(job+'.json')
    self.write(sp,dict(slots={'r0c0':dict(target=target,concept_id=identity,style_name=style,role='publish')}))
    if lane==106:
     digest='a'*64;rp=runtime/'batch/records'/(job+'.json')
     self.write(rp,dict(spec_sha256=C.file_sha(sp),targets={'r0c0':dict(path=target,sha256=digest)}))
     db.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?)',(lane,identity,entry,'saved',job,digest))
     db.execute('INSERT INTO cleanup VALUES(?,?,?)',(job,str(rp),'complete'))
    else:
     hold_path=runtime/'batch/holds'/(job+'.json');kind='KNOWN_OUTPUT_REJECTION'
     self.write(hold_path,dict(job=job,kind=kind,claim=dict(style_queue=lane,spec_sha256=C.file_sha(sp)),spec_sha256=C.file_sha(sp),
      remote_retry=False,rephrase=False,concept_ids=[identity],backend_outcome='completed'))
     observed.append(dict(lane=lane,id=identity,job=job,target=target,word='action',hold_kind=kind,hold_path=str(hold_path),hold_sha256=C.file_sha(hold_path),target_exists=False))
     db.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?)',(lane,identity,entry,'held',job,None))
  self.write(registration,dict(entry_sha256=hashes))
  self.write(prep/'scope_readiness_20261105.json',dict(registration_manifest=dict(path=str(registration),sha256=C.file_sha(registration))))
  reconciliation=registration.parent/'final-production-reconciliation-20261105.json'
  self.write(reconciliation,dict(saved=1,held_count=1,eligible_remaining=0,status='eligible_generation_complete_with_12_held',
   held=[dict(observed[0],kind=observed[0]['hold_kind'],style='Soccer player')]))
  closeout=registration.parent/'eligible-completion/closure.json'
  self.write(closeout,dict(saved=1,held=1,eligible_remaining=0,own_parent_lease=dict(status='released'),lease_session_exit_code=0,
   background_removal_complete=False,final_reconciliation_sha256=C.file_sha(reconciliation)))
  def observation():
   path=self.write(prep/'generation_completion_observation_20261106.json',dict(expected_total=2,saved=1,held=1,eligible_remaining=0,held_cases=observed,
    writers_released_per_generation_closeout=True,metadata_sha256={str(p):C.file_sha(p) for p in (dbpath,closeout,reconciliation)}))
   self.write(self.root/'bundle.json',dict(dependency_sha256={str(path):C.file_sha(path)}))
  observation()
  with patch.multiple(gates,RUNTIME=runtime,PREP=prep,HERE=self.root,SCOPE=2,AVAILABLE=1,HELD=1),patch.object(gates,'inventory',return_value=expected):
   reconciled=gates.generation()
   self.assertEqual(len(reconciled['rows']),1);self.assertEqual(reconciled['held'][0]['target_id'],'107:people-fixture')
   self.assertEqual(reconciled['metadata_sha256'][str(hold_path)],C.file_sha(hold_path))
   target=C.Path(observed[0]['target']);target.parent.mkdir(parents=True);target.symlink_to(self.root/'missing')
   with self.assertRaisesRegex(ValueError,'Held target'):gates.generation()
   target.unlink()
   with patch.object(C.Path,'lstat',side_effect=PermissionError('fixture path unreadable')):
    with self.assertRaises(PermissionError):C.require_absent(target)
   spec_before=sp.read_bytes();sp.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'Current source bytes changed'):gates.generation()
   sp.write_bytes(spec_before)
   hold_before=hold_path.read_bytes();hold_path.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'Current source bytes changed'):gates.generation()
   hold_path.write_bytes(hold_before)
   with contextlib.closing(sqlite3.connect(dbpath)) as db, db:db.execute("UPDATE inventory SET status='pending' WHERE lane=107")
   with self.assertRaisesRegex(ValueError,'Current source bytes changed'):gates.generation()
   observation()
   with self.assertRaisesRegex(ValueError,'held target DB status changed'):gates.generation()

 def test_held_partner_retirement_partial_proof_and_readiness(self):
  self.held_lane=107
  with patch.multiple(B,AVAILABLE=1,HELD=1):
   folder,closed=self.close(True)
   ticket=C.read(folder/'ticket.json');case=ticket['cases'][0];held=closed['held_dispositions'][0]
   self.assertEqual(ticket['expected_target_order'],['106:people-fixture','107:people-fixture'])
   self.assertEqual(case['paired_context']['held_disposition'],held)
   roles=ticket['source_catalog'][case['target_id']]['source']
   self.assertFalse(any(name.startswith('partner-') for name in roles))
   self.assertNotIn(held['target_id'],ticket['source_catalog'])
   choice=C.read(folder/'source-decisions.json')[case['target_id']]
   self.assertEqual(choice['same_pose_support'],C.PARTNER_UNAVAILABLE)
   with self.assertRaises(ValueError):B.validate_paired_assessment(case,dict(choice,same_pose_support='supports_same_pose'))
   with self.assertRaises(ValueError):E.validate_partner_roles(dict(roles,**{'partner-stage-native.png':next(iter(roles.values()))}),case['paired_context'])
   B.retire_batch(self.approval('retire_batch',[folder/'closed_batch.json']),'batch-0001')
   approval=self.approval('finalize',[B.FROZEN,B.PLAN]);B.finalize(approval)
   pointer=C.read(B.LATEST);proof=C.read(pointer['proof_path'])
   self.assertEqual(pointer['status'],C.PARTIAL_STATUS)
   self.assertFalse(pointer['completion_claim']);self.assertFalse(pointer['full_generation_complete'])
   self.assertEqual(proof['originals_byte_checked_this_invocation'],1);self.assertEqual(proof['deliveries_byte_checked_this_invocation'],1)
   self.assertEqual(proof['held_absence_checked_this_invocation'],1)
   self.assertEqual(C.jsonl(proof['held_path']),[held])
   self.assertEqual([row['target_id'] for row in C.jsonl(proof['manifest_path'])],[case['target_id']])
   with self.assertRaisesRegex(ValueError,'waits for full generation'):B.nonpeople_ready(self.approval('nonpeople_gate'))
   gate_approval=self.sequencing_approval()
   self.assertTrue(B.nonpeople_ready(gate_approval)['ready'])
   target=C.Path(held['target']);target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(self.root/'missing')
   with self.assertRaisesRegex(ValueError,'Held target'):B.nonpeople_ready(gate_approval)
   with self.assertRaisesRegex(ValueError,'Held target'):B.finalize(approval)
   self.assertEqual(C.read(B.LATEST)['status'],'failed_or_interrupted')

 def test_wizard_held_partner_is_ordered_before_saved_soccer_case(self):
  self.held_lane=106
  with patch.multiple(B,AVAILABLE=1,HELD=1):
   _,ticket=self.prepare(True)
   self.assertEqual(ticket['expected_target_order'],['106:people-fixture','107:people-fixture'])
   self.assertEqual(ticket['case_order'],['107:people-fixture'])
   self.assertEqual(ticket['cases'][0]['paired_context']['target_id'],'106:people-fixture')

 def test_eligible_source_has_actual_context_for_numeric_excluded_partner(self):
  folder,ticket,finals=self.finish((True,False));eligible=ticket['cases'][0];partner=ticket['cases'][1]
  self.assertEqual(ticket['source_case_order'],[eligible['target_id']]);self.assertFalse(partner['source_required']);self.assertEqual(set(C.read(folder/'source-decisions.json')),{eligible['target_id']})
  roles=ticket['source_catalog'][eligible['target_id']]['source']
  for field,role in (('outer','partner-stage-native.png'),('true_original','partner-original-native.png')):
   self.assertEqual(roles[role]['source_binding']['sha256'],partner[field]['sha256']);self.assertEqual(roles[role]['source_binding']['target_id'],partner['target_id'])
  self.assertIsNone(finals['cases'][1]['source_reviewer']);self.assertEqual(ticket['source_catalog'][partner['target_id']],{})
 def test_different_pose_assessment_is_explicit_not_mask_equivalence(self):
  self.partner_different_pose=True;folder,ticket,finals=self.finish(True);choices=C.read(folder/'source-decisions.json')
  self.assertNotEqual(ticket['cases'][0]['outer']['rgba_sha256'],ticket['cases'][1]['outer']['rgba_sha256'])
  self.assertTrue(all(c['same_pose_support']=='different_pose' for c in choices.values()));self.assertTrue(all(c['inner_result']['changed_pixels']==900 for c in finals['cases']))
  self.assertTrue(all(c['paired_context']['mask_transfer_allowed'] is False for c in ticket['cases']))
 def test_wrong_partner_context_and_unassessed_pose_are_rejected(self):
  folder,ticket=self.prepare((True,False));case=ticket['cases'][0]
  with self.assertRaises(ValueError):B.validate_paired_assessment(case,dict(paired_context_sha256='wrong',same_pose_support='supports_same_pose',same_pose_support_reason='wrong context'))
  with self.assertRaises(ValueError):B.validate_paired_assessment(case,dict(paired_context_sha256=C.sha(C.payload(case['paired_context']))))
  case['paired_context']['outer']=dict(case['outer'])
  with self.assertRaisesRegex(ValueError,'context binding differs'):E.render_cases(folder/'evidence/assets',ticket['cases'])
 def test_context_role_must_be_actually_displayed_before_source_checkpoint(self):
  folder,ticket,_=self.finish((True,False));choices=C.read(folder/'source-decisions.json');events=C.jsonl(folder/'review_logs/source.jsonl');role='partner-stage-native.png'
  for event in events:
   if event['type']=='display' and role in event['roles']:event['outcome']='incomplete';event['outcome_reason']='partner view clipped'
  with self.assertRaisesRegex(ValueError,'Missing native'):E.validate_journal(events,ticket['source_case_order'],'source',ticket['source_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in choices.items()})
 def test_clipped_crop_then_repeated_whole_then_full_crop_succeeds(self):
  folder,_,f=self.finish(True);order=f['output_case_order'][:1];reviews={i:dict(reviewer='fixture-independent') for i in order}
  def retry(displays):
   crop=next(d for d in displays if any('region-' in r for r in d['roles']));whole=next(d for d in displays if 'final-native.png' in d['roles']);index=displays.index(crop)
   return displays[:index]+[dict(crop,outcome='incomplete',outcome_reason='Tool clipped crop'),dict(whole),dict(crop)]+displays[index+1:]
  _,events=self.journal(folder,'output',order,f['output_catalog'],reviews,retry);coverage=E.validate_journal(events,order,'output',f['output_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in reviews.items()})
  self.assertEqual(coverage['unsuccessful_displays'],1);self.assertEqual(coverage['physical_file_attempts'],coverage['successful_displays']+1)
 def test_repeated_whole_views_do_not_replace_missing_crop(self):
  folder,_,f=self.finish(True);order=f['output_case_order'][:1];reviews={i:dict(reviewer='fixture-independent') for i in order}
  def retry(displays):
   whole=next(d for d in displays if 'final-native.png' in d['roles']);return [dict(whole) if any('region-' in r for r in d['roles']) else d for d in displays]
  _,events=self.journal(folder,'output',order,f['output_catalog'],reviews,retry)
  with self.assertRaisesRegex(ValueError,'Missing native'):E.validate_journal(events,order,'output',f['output_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in reviews.items()})
 def test_five_physical_files_per_outer_exec_rejected_across_inner_groups(self):
  folder,_,f=self.finish(False);order=f['output_case_order'][:1];reviews={i:dict(reviewer='fixture-independent') for i in order}
  def wrong(displays):
   result=[dict(displays[0]) for _ in range(5)]+displays[1:]
   for n,d in enumerate(result[:5]):d.update(exec_id='one-real-outer-exec',exec_file_index=n+1,inner_promise_group=n//4)
   return result
  _,events=self.journal(folder,'output',order,f['output_catalog'],reviews,wrong)
  with self.assertRaisesRegex(ValueError,'entire exec'):E.validate_journal(events,order,'output',f['output_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in reviews.items()})
 def test_exec_limit_is_shared_across_phase_journals_and_counts_failed_retries(self):
  events=[dict(type='display',display_event_id=f'event-{n}',exec_id='one-actual-exec',exec_file_index=n+1,phase='source' if n<2 else 'output',outcome='failed' if n==0 else 'complete') for n in range(5)]
  self.assertEqual(E.validate_exec_groups(events[:4]),{'one-actual-exec':4})
  with self.assertRaisesRegex(ValueError,'entire exec'):E.validate_exec_groups(events)
 def test_unsuccessful_attempt_has_zero_coverage_but_counts_exec_file(self):
  folder,_,f=self.finish(False);order=f['output_case_order'][:1];reviews={i:dict(reviewer='fixture-independent') for i in order}
  def failed(displays):return [dict(displays[0],outcome='failed',actually_displayed=False,native_resolution=False,outcome_reason='Tool error')]+displays
  _,events=self.journal(folder,'output',order,f['output_catalog'],reviews,failed);coverage=E.validate_journal(events,order,'output',f['output_catalog'],'batch-0001',{i:C.sha(C.payload(r)) for i,r in reviews.items()});self.assertEqual(coverage['unsuccessful_displays'],1)
 def test_capacity_default16_max32_preserves64_target_order(self):
  rows=[]
  for n in range(33):
   for lane in (106,107):rows.append(dict(concept_id=f'concept-{n:03d}',target_id=f'{lane}:concept-{n:03d}',style_queue=lane,ordinal=n,category='Fixture',word=f'word-{n}'))
  default=B.make_plan(rows);maximum=B.make_plan(rows,32)
  self.assertEqual([len(b['case_order']) for b in default['batches']],[32,32,2]);self.assertEqual([len(b['case_order']) for b in maximum['batches']],[64,2])
  self.assertEqual(maximum['batches'][0]['case_order'][:4],['106:concept-000','107:concept-000','106:concept-001','107:concept-001'])
  self.assertEqual(len(B.make_plan(rows,1)['batches']),33)
 def test_canonical_cache_contains_only_compressed_bytes_and_decodes_aliases(self):
  renderer=E.Renderer(self.root/'cache');roles=[]
  for n in range(64):
   a=self.np.zeros((16,16,4),dtype=self.np.uint8);a[:,:,3]=255;a[:,:,0]=n;stream=engine.io.BytesIO();self.Image.fromarray(a,'RGBA').save(stream,'PNG');raw=stream.getvalue()
   roles.append(renderer.add(f'case-{n}','output',{'one-native.png':raw,'same-blue.png':raw}))
  self.assertEqual(len(renderer.assets),64);self.assertEqual(renderer.alias_decodes,64);self.assertFalse(hasattr(renderer,'pixels'))
  self.assertTrue(all(isinstance(asset['bytes'],bytes) and all(not isinstance(v,self.np.ndarray) for v in asset.values()) for asset in renderer.assets.values()))
  self.assertTrue(all(isinstance(v,str) for v in renderer.pixel_assets.values()));self.assertLess(sum(len(a['bytes']) for a in renderer.assets.values()),64*16*16*4)
 def test_png_cannot_be_clobbered_by_any_review_log_helper(self):
  folder,_,f=self.finish(False);png=C.Path(next(iter(f['output_asset_sha256'])));before=png.read_bytes();event=dict(type='display',phase='output',sequence=1,outcome='complete',actually_displayed=True,tool_event_reference='synthetic-mistaken-log-path')
  for operation in (lambda:E.append_observed_display(png,event),lambda:E._append(png,event),lambda:E.checkpoint_observed_case(png,folder/'review_metadata/checkpoints','batch-0001','output',[],{},dict(target_id='wrong',reviewer='fixture'),'2026-11-05T22:00:00+00:00')):
   with self.assertRaises(ValueError):operation()
   self.assertEqual(png.read_bytes(),before)
  with self.assertRaises(ValueError):E.checkpoint_observed_case(folder/'review_logs/output.jsonl',png.parent,'batch-0001','output',[],{},dict(target_id='wrong',reviewer='fixture'),'2026-11-05T22:00:00+00:00')
  self.assertEqual(png.read_bytes(),before)

if __name__=='__main__':unittest.main(verbosity=2)
