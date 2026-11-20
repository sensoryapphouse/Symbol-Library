"""Bounded paired production batches. All population entry points are disabled.

Full prerequisite admission occurs once per batch, never once per image. Later
steps reuse the immutable ticket/capsule and exact per-operation source checks.
"""
import argparse
import io
import uuid
from contracts import *
import engine
import gates
import review_evidence as E
from workflow import unique,native_id,review_delivery,delivery_viewer

FROZEN=HERE/'population/frozen_sources.json'
PLAN=HERE/'population/batch_plan.json'
LATEST=HERE/'proofs/latest_status.json'
NP_BUNDLE=BASE/'production_non_people/code_bundle.json'
DEFAULT_CONCEPTS=16
MAX_CONCEPTS=32
_active_bundle=None


def bundle_id():
    return _active_bundle if _active_bundle is not None else check_bundle()


@contextlib.contextmanager
def use_bundle(digest):
    global _active_bundle
    previous=_active_bundle;_active_bundle=digest
    try:yield
    finally:_active_bundle=previous


def atomic(path,value):
    common=load('_ws_original_common',BASE/'production/common.py')
    common.atomic_json(inside(path),value)


def authorized(approval_path,action,operation,input_paths=()):
    """Invalidate current success before any prerequisite or input preflight."""
    with worker():
        approval=require_approval(approval_path,action)
        invocation=uuid.uuid4().hex
        atomic(LATEST,dict(status='running',completion_claim=False,action=action,invocation=invocation))
        try:
            require(isinstance(approval.get('execution_actor'),str) and approval['execution_actor'].strip(),'Accountable execution actor required')
            for path in input_paths:
                require(Path(path).suffix in ('.json','.jsonl'),'Population preflight inputs must be metadata')
                require(approval.get('approved_inputs',{}).get(str(Path(path).resolve()))==file_sha(path),'Operation input changed/unapproved')
            with use_bundle(approval['bundle_sha256']):
                result=operation(approval,invocation)
            if action!='finalize':
                atomic(LATEST,dict(status='production_in_progress',completion_claim=False,action=action,invocation=invocation))
            return result
        except BaseException as exc:
            atomic(LATEST,dict(status='failed_or_interrupted',completion_claim=False,action=action,invocation=invocation,error=str(exc)))
            raise


def make_plan(rows,concepts=DEFAULT_CONCEPTS,held=()):
    require(type(concepts) is int and 1<=concepts<=MAX_CONCEPTS,'Bounded concept batch size required')
    available_ids=set(unique(rows,'target_id'));held_ids=set(unique(held,'target_id'))
    require(available_ids.isdisjoint(held_ids),'Available and held target overlap')
    by_concept={}
    for row in [*rows,*held]:by_concept.setdefault(row['concept_id'],[]).append(row)
    ordered=[]
    for identity,pair in by_concept.items():
        require(len(pair)==2 and {r['style_queue'] for r in pair}=={106,107},'Every batch concept needs exact Wizard/Soccer pair')
        require(len({r['ordinal'] for r in pair})==len({r['category'] for r in pair})==len({r['word'] for r in pair})==1,'Pair concept metadata differs')
        require(any(r['target_id'] in available_ids for r in pair),'Every concept needs an available partner')
        ordered.append((pair[0]['ordinal'],identity,sorted(pair,key=lambda r:r['style_queue'])))
    ordered.sort();batches=[]
    for start in range(0,len(ordered),concepts):
        selected=ordered[start:start+concepts]
        expected_order=[r['target_id'] for _,_,pair in selected for r in pair]
        batches.append(dict(batch_id=f'batch-{len(batches)+1:04d}',concept_ids=[v[1] for v in selected],
            expected_target_order=expected_order,case_order=[i for i in expected_order if i in available_ids],
            held_target_order=[i for i in expected_order if i in held_ids]))
    return dict(schema='paired-batch-plan-v3',concepts_per_batch=concepts,max_concepts_per_batch=MAX_CONCEPTS,
        scope_total=len(rows)+len(held),available_total=len(rows),held_total=len(held),batches=batches)


def frozen_plan(gate=None):
    frozen=read(FROZEN);plan=read(PLAN)
    if gate is None:gate=frozen['gate']
    generation=gate['generation']
    rows=frozen['rows'];held=generation['held']
    generated=unique(generation['rows'],'target_id')
    require(frozen['gate']==gate and frozen['scope_total']==plan['scope_total']==SCOPE and
        len(rows)==len(generated)==AVAILABLE and len(held)==HELD and
        set(unique(rows,'target_id'))==set(generated),'Frozen available/held generation snapshot differs')
    require(all(row['true_original']['path']==generated[row['target_id']]['source'] and
        row['true_original']['sha256']==generated[row['target_id']]['source_sha256'] for row in rows),
        'Frozen true originals differ from current saved generation receipts')
    require(plan==make_plan(rows,plan['concepts_per_batch'],held),'Durable paired plan differs from exact generation partition')
    return rows,held,plan


def authority_capsule(gate):
    tokens={**gate['original_people']['authority_sha256'],**gate['generation']['metadata_sha256'],
        str(FROZEN):file_sha(FROZEN),str(PLAN):file_sha(PLAN)}
    # Verified once at admission, then stable dev/inode/size/mtime/ctime guards
    # around each bounded step. Global invocation never rehashes this entire
    # supplemental bundle once per target or once per prior closed batch.
    staged=read(HERE/'bundle.json') if (HERE/'bundle.json').exists() else {}
    for group in ('code_sha256','dependency_sha256'):merge(tokens,staged.get(group,{}))
    if (HERE/'bundle.json').exists():tokens[str(HERE/'bundle.json')]=bundle_id()
    generation=gate['generation'];closeout=gate['generation_closeout']
    merge(tokens,{closeout['path']:closeout['sha256']})
    absent=[generation['absent_generation_wal'],*(r['target'] for r in generation['held'])]
    for path in absent:require_absent(path)
    signatures={}
    for path,digest in tokens.items():
        if digest is not None:
            stable_bytes(path,digest);signatures[path]=metadata_signature(path)
    capsule=dict(schema='batch-authority-capsule-v2',bundle_sha256=bundle_id(),
        original_people=gate['original_people'],generation_sha256=sha(payload(gate['generation'])),
        generation_closeout_required=True,authority_sha256=tokens,absent_paths=absent,stable_metadata_signatures=signatures)
    path=HERE/'authorities'/(sha(payload(capsule))+'.json');immutable(path,payload(capsule))
    return dict(path=str(path),sha256=file_sha(path))


def guard(capsule_ref):
    require(file_sha(capsule_ref['path'])==capsule_ref['sha256'],'Authority capsule changed')
    capsule=read(capsule_ref['path']);require(capsule['bundle_sha256']==bundle_id(),'Batch code changed')
    for path,digest in capsule['authority_sha256'].items():
        require(metadata_signature(path)==capsule['stable_metadata_signatures'][path],
            'Prerequisite authority changed during/between batch steps: '+path)
    for path in capsule['absent_paths']:require_absent(path)
    return capsule


def metadata_signature(path):
    s=Path(path).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def approval_ref(path):
    return dict(path=str(Path(path).resolve()),sha256=file_sha(path))


def verify_approval_ref(ref,action):
    require(file_sha(ref['path'])==ref['sha256'],'Recorded root approval changed')
    doc=read(ref['path'])
    require(doc.get('approved') is True and doc.get('approved_by')=='root' and doc.get('bundle_sha256')==bundle_id() and
        action in doc.get('allowed_actions',[]),'Recorded root action approval missing')
    return doc


def approved_hashes(ref,action,wanted):
    doc=verify_approval_ref(ref,action)
    require(all(doc.get('approved_inputs',{}).get(str(Path(path).resolve()))==digest for path,digest in wanted.items()),
        'Recorded root approval input/source binding differs')


def batch_folder(batch_id):
    require(isinstance(batch_id,str) and batch_id.startswith('batch-') and batch_id[6:].isdigit() and len(batch_id)==10,'Unsafe batch ID')
    return HERE/'batches'/batch_id


def ticket(batch_id):
    path=batch_folder(batch_id)/'ticket.json';doc=read(path)
    require(doc['batch_id']==batch_id,'Batch ticket identity differs')
    verify_approval_ref(doc['root_execution_approval'],'prepare_batch')
    guard(doc['authority']);return path,doc


def validate_sources(rows):
    for row in rows:stable_bytes(row['true_original']['path'],row['true_original']['sha256'])


def paired_contexts(cases,held):
    by_id=unique(cases,'target_id');held_by_id=unique(held,'target_id');contexts={}
    for case in cases:
        identity=case['target_id'];concept=case['semantic_context']['concept_id']
        lane=identity.split(':')[0]
        require(lane in ('106','107') and identity==f'{lane}:{concept}','Invalid available concept identity')
        peer_id=f"{'107' if lane=='106' else '106'}:{concept}"
        partner=by_id.get(peer_id);hold=held_by_id.get(peer_id)
        require((partner is None)!=(hold is None),'Exact same-concept available or held partner required')
        context=dict(target_id=peer_id,concept_id=concept,pose_equivalence_assumed=False,mask_transfer_allowed=False)
        if hold is not None:
            require(hold['concept_id']==concept and hold['disposition']=='generation_held','Wrong held partner binding')
            context['held_disposition']=hold
        else:
            require(partner['semantic_context']['concept_id']==concept,'Wrong available partner binding')
            context.update(true_original=partner['true_original'],outer=partner['outer'],partner_source_required=partner['source_required'])
        contexts[identity]=context
    require({c['target_id'] for c in contexts.values() if 'held_disposition' in c}==set(held_by_id),'Held partner orphaned')
    return contexts


def validate_paired_assessment(case,choice):
    context=case['paired_context']
    assessments=(PARTNER_UNAVAILABLE,) if 'held_disposition' in context else ('supports_same_pose','different_pose','uncertain')
    require(choice.get('paired_context_sha256')==sha(payload(context)) and
        choice.get('same_pose_support') in assessments and
        isinstance(choice.get('same_pose_support_reason'),str) and choice['same_pose_support_reason'].strip(),
        'Actual paired-context binding and explicit pose or held-partner assessment required; no automatic mask sharing')


def freeze(approval_path,concepts=DEFAULT_CONCEPTS):
    def operation(approval,invocation):
        require(type(concepts) is int and 1<=concepts<=MAX_CONCEPTS and approval.get('concepts_per_batch')==concepts,
            'Root approval must bind bounded production concept batch size')
        gate=gates.enter(approval_path,'freeze');expected=inventory();mapping=unique(expected,'target_id');sources=[]
        actual={str(p) for style in ('Wizard','Soccer player') for p in (ROOT/'People'/style).rglob('*.webp')}
        held=gate['generation']['held']
        require(actual=={r['source'] for r in gate['generation']['rows']},'Missing/unexpected available saved paths')
        for generated in gate['generation']['rows']:
            raw,receipt=stable_bytes(generated['source'],generated['source_sha256']);a=engine.decode(raw)
            np,_,ndi,*_=engine.stack();rgb=a[:,:,:3].astype(np.int16)
            near=(rgb.min(2)>=245)&(np.ptp(rgb,axis=2)<=8)&(a[:,:,3]==255)
            seed=np.zeros(near.shape,bool);seed[0]=near[0];seed[-1]=near[-1];seed[:,0]|=near[:,0];seed[:,-1]|=near[:,-1]
            ext=ndi.binary_propagation(seed,mask=near);_,components=engine.components(a)
            sources.append(dict(mapping[generated['target_id']],true_original=receipt,original_rgba_sha256=sha(a.tobytes()),
                dimensions=[a.shape[1],a.shape[0]],alpha_extrema=[int(a[:,:,3].min()),int(a[:,:,3].max())],
                source_components=components,nearwhite_exterior_pixels=int(ext.sum()),enclosed_nearwhite_pixels=int((near&~ext).sum())))
        validate_sources(sources)
        require(len(sources)==AVAILABLE and len(held)==HELD,'Incomplete available freeze or held dispositions')
        require(gates.enter(approval_path,'freeze')==gate,'Prerequisites changed during complete freeze')
        immutable(FROZEN,payload(dict(schema='current-source-freeze-v3',scope_total=SCOPE,rows=sources,gate=gate,
            inventory_sha256=file_sha(PREP/'expected_targets_6190.jsonl'))))
        immutable(PLAN,payload(make_plan(sources,concepts,held)))
        return dict(status='frozen_complete',scope_total=SCOPE,available_total=AVAILABLE,held_total=HELD,batch_count=len(read(PLAN)['batches']))
    return authorized(approval_path,'freeze',operation)


def prepare_batch(approval_path,batch_id):
    folder=batch_folder(batch_id)
    def operation(approval,invocation):
        if (folder/'ticket.json').exists():
            _,existing=ticket(batch_id);validate_sources(existing['cases']);guard(existing['authority'])
            return dict(batch_id=batch_id,status='prepared_exact_replay',targets=len(existing['cases']))
        # Admit both the available source receipts and the absent held partition.
        gate=gates.enter(approval_path,'prepare_batch')
        population,held,plan=frozen_plan(gate)
        by_id=unique(population,'target_id');held_by_id=unique(held,'target_id')
        wanted=unique(plan['batches'],'batch_id')[batch_id]
        rows=[by_id[i] for i in wanted['case_order']]
        batch_held=[held_by_id[i] for i in wanted['held_target_order']]
        reference=authority_capsule(gate);guard(reference);validate_sources(rows)
        cases=[]
        for row in rows:
            raw,_=stable_bytes(row['true_original']['path'],row['true_original']['sha256']);a=engine.decode(raw);b,metrics=engine.outer(a)
            path=Path(row['true_original']['path']);digest=row['true_original']['sha256']
            if metrics['changed']:
                encoded=engine.exact_webp(b);path=folder/'stages'/native_id(row['target_id'])/'outer.webp';immutable(path,encoded);digest=sha(encoded)
            _,components=engine.components(b);proof=engine.no_inner_proof(b)
            cases.append(dict(target_id=row['target_id'],true_original=row['true_original'],relative_path=row['relative_target'],
                producer_actors=[approval['execution_actor']],
                semantic_context=dict(concept_id=row['concept_id'],category=row['category'],word=row['word'],
                    description=row.get('description'),declared_same_concept_links=row.get('same_latest_concept_links'),
                    context_is_not_automatic_pose_equivalence=True),
                outer=dict(path=str(path),sha256=digest,rgba_sha256=sha(b.tobytes())),outer_method=metrics,
                components=components,no_inner_proof=proof,source_required=not proof['no_eligible_inner']))
        contexts=paired_contexts(cases,batch_held)
        for case in cases:case['paired_context']=contexts[case['target_id']]
        renderer,catalog=E.render_cases(folder/'evidence/assets',cases,batch_held);assets=renderer.write()
        validate_sources(rows);verify_live({c['outer']['path']:c['outer']['sha256'] for c in cases});guard(reference)
        doc=dict(schema='paired-batch-ticket-v2',batch_id=batch_id,authority=reference,case_order=wanted['case_order'],cases=cases,
            root_execution_approval=approval_ref(approval_path),expected_target_order=wanted['expected_target_order'],held_dispositions=batch_held,
            source_catalog=catalog,source_asset_sha256=assets,source_case_order=[c['target_id'] for c in cases if c['source_required']],
            frozen_sha256=file_sha(FROZEN),plan_sha256=file_sha(PLAN))
        immutable(folder/'ticket.json',payload(doc));return dict(batch_id=batch_id,targets=len(cases),source_review_required=len(doc['source_case_order']))
    return authorized(approval_path,'prepare_batch',operation,[FROZEN,PLAN])


def finish_batch(approval_path,batch_id,decisions_path,source_events_path):
    folder=batch_folder(batch_id);ticket_path=folder/'ticket.json'
    def operation(approval,invocation):
        _,doc=ticket(batch_id);cases=doc['cases'];validate_sources(cases)
        E.journal_location(source_events_path,'source')
        if (folder/'finals.json').exists():
            previous=read(folder/'finals.json')
            require(previous['source_decisions_sha256']==file_sha(decisions_path) and previous['source_events_sha256']==file_sha(source_events_path) and
                previous['ticket_sha256']==file_sha(ticket_path),'Final-stage replay inputs changed')
            verify_live({c['final']['path']:c['final']['sha256'] for c in previous['cases']});guard(doc['authority'])
            return dict(batch_id=batch_id,status='finals_exact_replay',changed_final=len(previous['output_case_order']))
        verify_live(doc['source_asset_sha256'])
        choices=read(decisions_path);events=jsonl(source_events_path)
        require(set(choices)==set(doc['source_case_order']),'Source decisions must cover eligible stages exactly; no fabricated no-inner visual decisions')
        coverage=E.validate_journal(events,doc['source_case_order'],'source',doc['source_catalog'],batch_id,
            {i:sha(payload(d)) for i,d in choices.items()})
        finals=[]
        for case in cases:
            identity=case['target_id'];raw,_=stable_bytes(case['outer']['path'],case['outer']['sha256']);a=engine.decode(raw)
            final=dict(case['outer']);reviewer=None;hold=False;regions=[];run=None
            if case['source_required']:
                choice=choices[identity]
                require(choice.get('target_id')==identity and choice.get('true_original_sha256')==case['true_original']['sha256'] and
                    choice.get('stage_sha256')==case['outer']['sha256'] and choice.get('stage_rgba_sha256')==sha(a.tobytes()) and
                    choice.get('stage_component_inventory_sha256')==sha(payload(case['components'])) and choice.get('actually_viewed') is True,
                    'Actual source/display/stage binding differs')
                require(choice.get('reviewer')==coverage['checkpoints'][identity]['reviewer'],'Source reviewer differs from durable checkpoint')
                validate_paired_assessment(case,choice)
                choice=engine.normalize_regions(a,dict(choice,id=native_id(identity)));regions=choice['regions'];reviewer=choice['reviewer'];hold=choice['decision']=='uncertain'
                run=engine.strict(case['outer']['path'],case['outer']['sha256'],choice,folder/'strict_outputs',sha(payload(doc)))
                if run['status']=='changed':
                    path=folder/'strict_outputs'/native_id(identity)/'after.webp';out,_=stable_bytes(path,run['output_sha256'])
                    final=dict(path=str(path),sha256=sha(out),rgba_sha256=run['decoded_rgba_sha256'])
            else:
                measured=engine.no_inner_proof(a)
                require(measured==case['no_inner_proof'] and measured['no_eligible_inner'],'No-inner numeric proof no longer holds')
            original,_=stable_bytes(case['true_original']['path'],case['true_original']['sha256']);after,_=stable_bytes(final['path'],final['sha256'])
            changed=not engine.stack()[0].array_equal(engine.decode(original),engine.decode(after))
            finals.append(dict(case,source_required=False,was_source_required=case['source_required'],final=final,source_reviewer=reviewer,
                producer_actors=sorted(set(case['producer_actors']+[approval['execution_actor']])),
                source_hold=hold,inner_result=run,normalized_regions=regions,changed_vs_true_original=changed,
                mechanical_no_inner=not case['source_required'],duplicate_final_created=bool(run and run['status']=='changed')))
        renderer,catalog=E.render_cases(folder/'evidence/assets',finals);assets=renderer.write()
        for case in finals:
            roles=catalog[case['target_id']].get('output',{})
            case['review_assets_sha256']={r['path']:r['sha256'] for r in roles.values()}
        validate_sources(cases);verify_live({c['final']['path']:c['final']['sha256'] for c in finals});guard(doc['authority'])
        result=dict(schema='paired-batch-finals-v2',batch_id=batch_id,ticket_sha256=file_sha(ticket_path),case_order=doc['case_order'],cases=finals,
            root_execution_approval=approval_ref(approval_path),
            source_decisions_path=str(Path(decisions_path).resolve()),source_decisions_sha256=file_sha(decisions_path),
            source_events_path=str(Path(source_events_path).resolve()),source_events_sha256=file_sha(source_events_path),source_coverage=coverage,
            output_case_order=[c['target_id'] for c in finals if c['changed_vs_true_original']],output_catalog=catalog,output_asset_sha256=assets)
        immutable(folder/'finals.json',payload(result));return dict(batch_id=batch_id,changed_final=len(result['output_case_order']))
    return authorized(approval_path,'finish_batch',operation,[ticket_path,decisions_path,source_events_path])


def merge(destination,items):
    for path,digest in items.items():
        require(path not in destination or destination[path]==digest,'Conflicting dependency hash')
        destination[path]=digest


def verify_live(dependencies):
    for path,digest in dependencies.items():stable_bytes(path,digest)


def validate_closed(folder,verify_current=True):
    closed_path=folder/'closed_batch.json';closed=read(closed_path);doc=read(folder/'ticket.json');finals=read(folder/'finals.json')
    require(closed['schema']=='paired-batch-closeout-v2' and closed['batch_id']==doc['batch_id'] and
        closed['case_order']==doc['case_order']==finals['case_order']==[c['target_id'] for c in doc['cases']]==
        [c['target_id'] for c in finals['cases']], 'Batch closeout case identities differ')
    require(closed['ticket_sha256']==file_sha(folder/'ticket.json') and closed['finals_sha256']==file_sha(folder/'finals.json'),'Batch lineage changed')
    for record,action in ((doc,'prepare_batch'),(finals,'finish_batch'),(closed,'seal_batch')):
        verify_approval_ref(record['root_execution_approval'],action)
    approved_hashes(doc['root_execution_approval'],'prepare_batch',{str(FROZEN):doc['frozen_sha256'],str(PLAN):doc['plan_sha256']})
    approved_hashes(finals['root_execution_approval'],'finish_batch',{str(folder/'ticket.json'):finals['ticket_sha256'],
        finals['source_decisions_path']:finals['source_decisions_sha256'],finals['source_events_path']:finals['source_events_sha256']})
    approved_hashes(closed['root_execution_approval'],'seal_batch',{str(folder/'ticket.json'):closed['ticket_sha256'],
        str(folder/'finals.json'):closed['finals_sha256'],closed['output_reviews_path']:closed['output_reviews_sha256'],
        closed['output_events_path']:closed['output_events_sha256']})
    require(closed['expected_target_order']==doc['expected_target_order'] and closed['held_dispositions']==doc['held_dispositions'],
        'Closed batch held dispositions differ from admitted ticket')
    contexts=paired_contexts(doc['cases'],doc['held_dispositions'])
    for case in doc['cases']:
        identity=case['target_id'];context=contexts[identity]
        require(case['paired_context']==context,'Durable source partner context differs')
        if case['source_required']:
            E.validate_partner_roles(doc['source_catalog'][identity]['source'],context)
    choices=read(finals['source_decisions_path']);reviews=read(closed['output_reviews_path'])
    E.journal_location(finals['source_events_path'],'source');E.journal_location(closed['output_events_path'],'output')
    E.validate_exec_groups(jsonl(finals['source_events_path'])+jsonl(closed['output_events_path']))
    source_coverage=E.validate_journal(jsonl(finals['source_events_path']),doc['source_case_order'],'source',doc['source_catalog'],doc['batch_id'],
        {i:sha(payload(d)) for i,d in choices.items()})
    output_coverage=E.validate_journal(jsonl(closed['output_events_path']),finals['output_case_order'],'output',finals['output_catalog'],doc['batch_id'],
        {i:sha(payload(d)) for i,d in reviews.items()})
    require(source_coverage==finals['source_coverage'] and output_coverage==closed['output_coverage'],'Durable review coverage changed')
    expected=[];originals=unique(doc['cases'],'target_id')
    require(set(reviews)==set(finals['output_case_order']) and set(choices)==set(doc['source_case_order']),'Missing/extra source or output reviews')
    for case in finals['cases']:
        require(case['true_original']==originals[case['target_id']]['true_original'] and case['outer']==originals[case['target_id']]['outer'] and
            case['paired_context']==contexts[case['target_id']],
            'True original/outer lineage silently relabelled')
        if case['target_id'] in choices:validate_paired_assessment(originals[case['target_id']],choices[case['target_id']])
        selected=review_delivery(case,reviews.get(case['target_id']))
        expected.append(dict(target_id=case['target_id'],relative_path=case['relative_path'],true_original=case['true_original'],
            outer=case['outer'],final_candidate=case['final'],delivery=selected,final_case_sha256=sha(payload(case))))
    require(closed['rows']==expected,'Closed delivery rows differ from exact independently reviewed cases')
    guard(doc['authority'])
    if verify_current:verify_live(closed['live_dependencies_sha256'])
    return closed,doc,finals


def retired_assets(folder,closed):
    """Only a complete exact regeneration receipt excuses absent review PNGs."""
    complete_path=folder/'retirement_complete.json';intent_path=folder/'retirement_intent.json'
    if not complete_path.exists():return {}
    intent=read(intent_path);complete=read(complete_path)
    verify_approval_ref(intent['root_execution_approval'],'retire_batch')
    approved_hashes(intent['root_execution_approval'],'retire_batch',{str(folder/'closed_batch.json'):file_sha(folder/'closed_batch.json')})
    require(intent==dict(schema='batch-png-retirement-intent-v2',batch_id=closed['batch_id'],
        closed_batch_sha256=file_sha(folder/'closed_batch.json'),bundle_sha256=bundle_id(),
        temporary_png_sha256=closed['temporary_png_sha256'],regenerated_byte_exact=True,
        root_execution_approval=intent['root_execution_approval'],
        recipe='source+final nativeRGBA roles, exact selected-component crop geometry, equality aliases; pinned engine/environment'),
        'Retirement intent/recipe/complete batch binding differs')
    require(complete==dict(schema='batch-png-retirement-complete-v2',intent_sha256=file_sha(intent_path),
        closed_batch_sha256=file_sha(folder/'closed_batch.json'),retired_png_sha256=closed['temporary_png_sha256']),
        'Retirement completion scope differs')
    return intent['temporary_png_sha256']


def verify_temporary(folder,closed):
    allowed=retired_assets(folder,closed)
    for path,digest in closed['temporary_png_sha256'].items():
        if Path(path).exists():stable_bytes(path,digest)
        else:require(allowed.get(path)==digest,'Missing PNG lacks completed exact retirement receipt')
    if not allowed:return {}
    dependencies={str(folder/name):file_sha(folder/name) for name in ('retirement_intent.json','retirement_complete.json')}
    ref=read(folder/'retirement_intent.json')['root_execution_approval'];dependencies[ref['path']]=ref['sha256']
    return dependencies


def seal_batch(approval_path,batch_id,reviews_path,output_events_path):
    folder=batch_folder(batch_id)
    def operation(approval,invocation):
        _,doc=ticket(batch_id);finals=read(folder/'finals.json')
        E.journal_location(output_events_path,'output')
        require(finals['ticket_sha256']==file_sha(folder/'ticket.json'),'Finals ticket changed')
        reviews=read(reviews_path);events=jsonl(output_events_path)
        E.validate_exec_groups(jsonl(finals['source_events_path'])+events)
        require(set(reviews)==set(finals['output_case_order']),'Independent review coverage must match every changed FINAL exactly')
        coverage=E.validate_journal(events,finals['output_case_order'],'output',finals['output_catalog'],batch_id,
            {i:sha(payload(r)) for i,r in reviews.items()})
        dependencies={str(folder/'ticket.json'):file_sha(folder/'ticket.json'),str(folder/'finals.json'):file_sha(folder/'finals.json'),
            str(Path(reviews_path).resolve()):file_sha(reviews_path),str(Path(output_events_path).resolve()):file_sha(output_events_path),
            str(Path(finals['source_decisions_path'])):finals['source_decisions_sha256'],
            str(Path(finals['source_events_path'])):finals['source_events_sha256'],doc['authority']['path']:doc['authority']['sha256']}
        for ref in (doc['root_execution_approval'],finals['root_execution_approval'],approval_ref(approval_path)):
            dependencies[ref['path']]=ref['sha256']
        merge(dependencies,finals['source_coverage']['checkpoint_sha256']);merge(dependencies,coverage['checkpoint_sha256'])
        temporary=dict(doc['source_asset_sha256']);merge(temporary,finals['output_asset_sha256']);rows=[]
        for case in finals['cases']:
            review=reviews.get(case['target_id'])
            if review is not None:require(review['reviewer']==coverage['checkpoints'][case['target_id']]['reviewer'],'Output reviewer differs from displayed checkpoint')
            selected=review_delivery(case,review)
            rows.append(dict(target_id=case['target_id'],relative_path=case['relative_path'],true_original=case['true_original'],
                outer=case['outer'],final_candidate=case['final'],delivery=selected,final_case_sha256=sha(payload(case))))
            merge(dependencies,{case['true_original']['path']:case['true_original']['sha256'],case['outer']['path']:case['outer']['sha256'],case['final']['path']:case['final']['sha256']})
            run=case['inner_result']
            if run and run['status']=='changed':
                strictdir=folder/'strict_outputs'/native_id(case['target_id'])
                merge(dependencies,{str(strictdir/name):digest for name,digest in run['artifact_sha256'].items()})
                dependencies[str(strictdir/'result.json')]=file_sha(strictdir/'result.json')
        verify_live(dependencies)
        if (folder/'closed_batch.json').exists():
            old=read(folder/'closed_batch.json');verify_temporary(folder,old)
        else:verify_live(temporary)
        guard(doc['authority'])
        result=dict(schema='paired-batch-closeout-v2',batch_id=batch_id,case_order=doc['case_order'],rows=rows,
            expected_target_order=doc['expected_target_order'],held_dispositions=doc['held_dispositions'],
            root_execution_approval=approval_ref(approval_path),
            output_reviews_path=str(Path(reviews_path).resolve()),output_reviews_sha256=file_sha(reviews_path),
            output_events_path=str(Path(output_events_path).resolve()),output_events_sha256=file_sha(output_events_path),
            ticket_sha256=file_sha(folder/'ticket.json'),finals_sha256=file_sha(folder/'finals.json'),
            output_coverage=coverage,independent_changed_final_review_complete=True,
            live_dependencies_sha256=dependencies,temporary_png_sha256=temporary)
        immutable(folder/'closed_batch.json',payload(result))
        return dict(batch_id=batch_id,status='review_complete',targets=len(rows),physical_output_file_attempts=coverage['physical_file_attempts'],
            successful_output_displays=coverage['successful_displays'])
    return authorized(approval_path,'seal_batch',operation,[folder/'ticket.json',folder/'finals.json',reviews_path,output_events_path])


def retire_batch(approval_path,batch_id):
    folder=batch_folder(batch_id)
    def operation(approval,invocation):
        closed,doc,finals=validate_closed(folder)
        require(closed.get('independent_changed_final_review_complete') is True,'Complete independent batch review required before retirement')
        # Regenerate every role, checking byte equality and all aliases/crops.
        before,source_catalog=E.render_cases(folder/'evidence/assets',doc['cases'],doc['held_dispositions'])
        after,output_catalog=E.render_cases(folder/'evidence/assets',finals['cases'])
        E.verify_catalog(doc['source_catalog'],source_catalog);E.verify_catalog(finals['output_catalog'],output_catalog)
        regenerated={asset['path']:asset for renderer in (before,after) for asset in renderer.assets.values()}
        require({p:a['sha256'] for p,a in regenerated.items()}==closed['temporary_png_sha256'],'Regenerated PNG retirement scope/bytes differs')
        for path,asset in regenerated.items():
            require(Path(path).parent==folder/'evidence/assets' and Path(path).name==asset['sha256']+'.png','Retirement attempted non-review PNG/mask')
            require(sha(asset['bytes'])==closed['temporary_png_sha256'][path],'Regenerated PNG bytes differ')
        intent=dict(schema='batch-png-retirement-intent-v2',batch_id=batch_id,closed_batch_sha256=file_sha(folder/'closed_batch.json'),
            bundle_sha256=bundle_id(),temporary_png_sha256=closed['temporary_png_sha256'],regenerated_byte_exact=True,
            recipe='source+final nativeRGBA roles, exact selected-component crop geometry, equality aliases; pinned engine/environment')
        intent_path=folder/'retirement_intent.json'
        intent['root_execution_approval']=read(intent_path)['root_execution_approval'] if intent_path.exists() else approval_ref(approval_path)
        verify_approval_ref(intent['root_execution_approval'],'retire_batch')
        if not intent_path.exists():verify_live(closed['temporary_png_sha256'])
        immutable(intent_path,payload(intent))
        for path,digest in closed['temporary_png_sha256'].items():
            if Path(path).exists():stable_bytes(path,digest);Path(path).unlink()
        assetdir=folder/'evidence/assets'
        if assetdir.exists():
            fd=os.open(assetdir,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        verify_live(closed['live_dependencies_sha256']);guard(doc['authority'])
        complete=dict(schema='batch-png-retirement-complete-v2',intent_sha256=file_sha(intent_path),
            closed_batch_sha256=file_sha(folder/'closed_batch.json'),retired_png_sha256=closed['temporary_png_sha256'])
        immutable(folder/'retirement_complete.json',payload(complete));retired_assets(folder,closed)
        return dict(batch_id=batch_id,status='temporary_pngs_retired',pngs=len(regenerated))
    return authorized(approval_path,'retire_batch',operation,[folder/'closed_batch.json'])


def all_closed(verify_current=True,gate=None):
    frozen_rows,held,plan=frozen_plan(gate)
    frozen=unique(frozen_rows,'target_id');held_by_id=unique(held,'target_id')
    rows=[];live={};retirement={};temporary={};authorities={}
    frozen_sha,plan_sha=file_sha(FROZEN),file_sha(PLAN)
    for spec in plan['batches']:
        folder=batch_folder(spec['batch_id']);closed,doc,_=validate_closed(folder,verify_current)
        require(closed['case_order']==spec['case_order'] and closed['expected_target_order']==spec['expected_target_order'] and
            closed['held_dispositions']==[held_by_id[i] for i in spec['held_target_order']],
            'Closed batch differs from exact paired available/held plan')
        require(doc['frozen_sha256']==frozen_sha and doc['plan_sha256']==plan_sha,
            'Closed ticket was admitted against a different frozen population or plan')
        rows.extend(closed['rows']);merge(live,closed['live_dependencies_sha256'])
        live[str(folder/'closed_batch.json')]=file_sha(folder/'closed_batch.json')
        merge(retirement,verify_temporary(folder,closed));merge(temporary,closed['temporary_png_sha256'])
        authorities[doc['authority']['sha256']]=doc['authority']
    require(len(rows)==AVAILABLE and set(unique(rows,'target_id'))==set(frozen) and
        len(held)==HELD and len(rows)+len(held)==SCOPE, 'Final proof requires exact available and held dispositions')
    require(all(r['true_original']==frozen[r['target_id']]['true_original'] and r['relative_path']==frozen[r['target_id']]['relative_target'] for r in rows),
        'Final original/concept/path identity differs from frozen generation sources')
    return rows,live,retirement,temporary,list(authorities.values())


def completion_fields():
    return dict(status=PARTIAL_STATUS,completion_claim=False,available_cleanup_complete=True,
        full_generation_complete=False,scope_total=SCOPE,available_total=AVAILABLE,held_total=HELD)


def jsonl_payload(rows):
    return b''.join((json.dumps(row,sort_keys=True)+'\n').encode() for row in rows)


def finalize(approval_path):
    def operation(approval,invocation):
        gate=gates.enter(approval_path,'finalize')
        rows,live,retirement,temporary,authorities=all_closed(verify_current=False,gate=gate)
        checks=[]
        for row in rows:
            _,source=stable_bytes(row['true_original']['path'],row['true_original']['sha256'])
            _,delivered=stable_bytes(row['delivery']['path'],row['delivery']['sha256'])
            checks.append(dict(target_id=row['target_id'],invocation=invocation,source=source,delivery=delivered))
        checked={r[role]['path']:r[role]['sha256'] for r in checks for role in ('source','delivery')}
        verify_live({path:digest for path,digest in live.items() if checked.get(path)!=digest});verify_live(retirement)
        live[str(Path(approval_path).resolve())]=file_sha(approval_path)
        for reference in authorities:guard(reference)
        require(gates.enter(approval_path,'finalize')==gate,'Final prerequisite authorities changed')
        # No canonical artifacts are written until all current full-byte and
        # lineage checks above have succeeded in this invocation.
        manifest_raw=jsonl_payload(rows)
        held=gate['generation']['held'];held_raw=jsonl_payload(held)
        manifest=HERE/'delivery/final_delivery_manifest.jsonl';viewer=HERE/'delivery/index.html'
        held_artifact=HERE/'delivery/held_generation_dispositions.jsonl'
        viewer_raw=delivery_viewer(rows,checks)
        invocation_root=HERE/'proofs'/invocation
        checkpoint=invocation_root/'byte_checks.json';immutable(checkpoint,payload(checks))
        immutable(manifest,manifest_raw);immutable(held_artifact,held_raw);immutable(viewer,viewer_raw)
        fields=completion_fields()
        proof=dict(schema=PARTIAL_PROOF_SCHEMA,invocation=invocation,**fields,
            root_execution_approval=approval_ref(approval_path),
            originals_byte_checked_this_invocation=len(checks),deliveries_byte_checked_this_invocation=len(checks),
            held_absence_checked_this_invocation=len(held),held_path=str(held_artifact),held_sha256=sha(held_raw),
            bundle_sha256=bundle_id(),prerequisites=gate,manifest_path=str(manifest),manifest_sha256=sha(manifest_raw),
            viewer_path=str(viewer),viewer_sha256=sha(viewer_raw),viewer_exact_bindings_verified=True,
            checkpoint_path=str(checkpoint),checkpoint_sha256=file_sha(checkpoint),live_dependencies_sha256=live,
            retirement_dependencies_sha256=retirement,temporary_png_sha256=temporary,retired_pngs_allowed_only_by_complete_batch_receipts=True,
            library_written=False)
        proof_path=invocation_root/(PARTIAL_STATUS+'.json');immutable(proof_path,payload(proof))
        for reference in authorities:guard(reference)
        atomic(LATEST,dict(**fields,invocation=invocation,proof_path=str(proof_path),proof_sha256=file_sha(proof_path)))
        return dict(**fields,invocation=invocation)
    return authorized(approval_path,'finalize',operation,[FROZEN,PLAN])


def sequencing_authority(approval,pointer,proof):
    ref=approval.get('non_people_policy')
    require(isinstance(ref,dict),'Non-People waits for full generation unless separately authorized')
    path=Path(ref['path'])
    require(path.is_absolute() and path.suffix=='.json','Root sequencing policy must be absolute JSON metadata')
    raw,_=stable_bytes(path,ref['sha256']);policy=json.loads(raw)
    require(policy==dict(schema='root-non-people-sequencing-v1',approved_by='root',
        decision='proceed_after_available_cleanup',wizard_bundle_sha256=bundle_id(),
        non_people_bundle_sha256=file_sha(NP_BUNDLE),
        wizard_proof_sha256=pointer['proof_sha256'],held_sha256=proof['held_sha256']),
        'Root sequencing policy does not authorize this exact available proof and held partition')
    return ref


def _nonpeople_ready_locked(approval_path,approval):
    # Readiness never publishes or invalidates a completion pointer.
    raw=LATEST.read_bytes();pointer=json.loads(raw)
    fields=completion_fields()
    require(all(pointer.get(key)==value for key,value in fields.items()),'Current available cleanup proof is incomplete')
    invocation=pointer['invocation'];require(len(invocation)==32 and all(c in '0123456789abcdef' for c in invocation),'Unsafe proof invocation')
    path=HERE/'proofs'/invocation/(PARTIAL_STATUS+'.json')
    require(pointer['proof_path']==str(path),'Wrong available cleanup proof path')
    proof_raw,_=stable_bytes(path,pointer['proof_sha256']);proof=json.loads(proof_raw)
    require(proof['schema']==PARTIAL_PROOF_SCHEMA and proof['invocation']==invocation and
        all(proof.get(key)==value for key,value in fields.items()) and
        proof['originals_byte_checked_this_invocation']==proof['deliveries_byte_checked_this_invocation']==AVAILABLE and
        proof['held_absence_checked_this_invocation']==HELD and proof['bundle_sha256']==bundle_id() and
        proof['viewer_exact_bindings_verified'] is True,'Incomplete available byte and held coverage')
    policy_ref=sequencing_authority(approval,pointer,proof)
    gate=gates.enter(approval_path,'nonpeople_gate')
    require(proof['prerequisites']==gate,'Current available generation or original People prerequisite differs')
    rows,live,retirement,temporary,authorities=all_closed(verify_current=False,gate=gate)
    verify_approval_ref(proof['root_execution_approval'],'finalize')
    live[proof['root_execution_approval']['path']]=proof['root_execution_approval']['sha256']
    require(proof['live_dependencies_sha256']==live and proof['retirement_dependencies_sha256']==retirement and proof['temporary_png_sha256']==temporary,'Final live/retired dependencies differ')
    require(proof['manifest_path']==str(HERE/'delivery/final_delivery_manifest.jsonl') and proof['viewer_path']==str(HERE/'delivery/index.html') and
        proof['held_path']==str(HERE/'delivery/held_generation_dispositions.jsonl') and
        proof['checkpoint_path']==str(HERE/'proofs'/invocation/'byte_checks.json'),'Wrong canonical artifact paths')
    for key in ('manifest','viewer','held','checkpoint'):require(file_sha(proof[key+'_path'])==proof[key+'_sha256'],'Final artifact changed')
    require(jsonl(proof['manifest_path'])==rows and jsonl(proof['held_path'])==gate['generation']['held'],
        'Canonical delivery or held dispositions differ from exact current population')
    receipts=read(proof['checkpoint_path']);require(len(receipts)==len(rows),'Current byte checkpoint count differs')
    for row,receipt in zip(rows,receipts):
        require(receipt['target_id']==row['target_id'] and receipt['invocation']==invocation,'Wrong current byte invocation/case order')
        for role,expected in (('source',row['true_original']),('delivery',row['delivery'])):
            actual=receipt[role]
            require(actual['path']==expected['path'] and actual['sha256']==expected['sha256'] and actual['stable_during_read'] is True and actual['bytes']>0,'Wrong source/delivery byte receipt')
            stable_bytes(expected['path'],expected['sha256'])
    checked={r[role]['path']:r[role]['sha256'] for r in receipts for role in ('source','delivery')}
    verify_live({path:digest for path,digest in live.items() if checked.get(path)!=digest});verify_live(retirement)
    for reference in authorities:guard(reference)
    require(gates.enter(approval_path,'nonpeople_gate')==gate,'Final prerequisite authorities changed during readiness gate')
    stable_bytes(policy_ref['path'],policy_ref['sha256'])
    require(LATEST.read_bytes()==raw,'Latest supplemental pointer changed during gate')
    return dict(ready=True,original_phase3_complete=True,**fields,activation_performed=False)


def nonpeople_ready(approval_path):
    with worker():
        approval=require_approval(approval_path,'nonpeople_gate')
        with use_bundle(approval['bundle_sha256']):
            return _nonpeople_ready_locked(approval_path,approval)



def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',nargs='?',default='status',choices=['status','freeze','prepare_batch','finish_batch','seal_batch','retire_batch','finalize','nonpeople_gate'])
    p.add_argument('--approval',type=Path);p.add_argument('--batch');p.add_argument('--decisions',type=Path);p.add_argument('--source-events',type=Path);p.add_argument('--reviews',type=Path);p.add_argument('--output-events',type=Path);p.add_argument('--concepts-per-batch',type=int,default=DEFAULT_CONCEPTS)
    args=p.parse_args()
    if args.action=='status':print(json.dumps(dict(status='staged_disabled',population_work_started=False,bundle_sha256=bundle_id())));return
    require(args.approval is not None,'New root execution approval required')
    if args.action=='freeze':result=freeze(args.approval,args.concepts_per_batch)
    elif args.action=='prepare_batch':result=prepare_batch(args.approval,args.batch)
    elif args.action=='finish_batch':result=finish_batch(args.approval,args.batch,args.decisions,args.source_events)
    elif args.action=='seal_batch':result=seal_batch(args.approval,args.batch,args.reviews,args.output_events)
    elif args.action=='retire_batch':result=retire_batch(args.approval,args.batch)
    elif args.action=='finalize':result=finalize(args.approval)
    else:result=nonpeople_ready(args.approval)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
