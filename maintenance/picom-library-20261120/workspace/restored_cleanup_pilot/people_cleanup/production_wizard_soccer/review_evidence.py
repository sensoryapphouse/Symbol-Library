"""Native evidence, equality-proven aliases and ordered durable display coverage."""
import datetime
import io
from contracts import *
import engine


class Renderer:
    def __init__(self,folder):
        require_worker();self.folder=inside(folder);self.assets={};self.pixel_assets={};self.first_role={};self.alias_decodes=0

    def add(self,identity,phase,files):
        np,Image,*_=engine.stack();roles={}
        for role,raw in sorted(files.items(),key=lambda item:(0 if item[0].endswith('-native.png') else 1,item[0])):
            with Image.open(io.BytesIO(raw)) as image:
                a=np.array(image.convert('RGBA'));dims=[image.width,image.height]
            pixel_sha=sha(payload(dims)+a.tobytes());key=f'{identity}:{phase}:{role}'
            if pixel_sha in self.pixel_assets:
                encoded=self.assets[self.pixel_assets[pixel_sha]]['bytes']
                with Image.open(io.BytesIO(encoded)) as canonical:
                    decoded=np.array(canonical.convert('RGBA'))
                self.alias_decodes+=1
                require(np.array_equal(decoded,a),'Decoded canonical visual equality failed')
            else:
                stream=io.BytesIO();Image.fromarray(a,'RGBA').save(stream,'PNG');encoded=stream.getvalue()
            digest=sha(encoded);self.pixel_assets.setdefault(pixel_sha,digest)
            asset=dict(path=str(self.folder/(digest+'.png')),sha256=digest,pixel_sha256=pixel_sha,dimensions=dims)
            require(digest not in self.assets or self.assets[digest]['bytes']==encoded,'PNG collision')
            self.assets[digest]=dict(asset,bytes=encoded)
            canonical=self.first_role.setdefault(pixel_sha,key)
            roles[role]=dict(asset,alias_of=None if canonical==key else canonical,
                equality_verified=True,physical_display_role=canonical)
        return roles

    def write(self):
        for asset in self.assets.values():immutable(asset['path'],asset['bytes'])
        return {asset['path']:asset['sha256'] for asset in self.assets.values()}


PARTNER_ROLES=(('outer','partner-stage-native.png'),('true_original','partner-original-native.png'))


def validate_partner_roles(roles,context):
    wanted={}
    if 'held_disposition' not in context:
        for field,role in PARTNER_ROLES:
            wanted[role]=dict(concept_id=context['concept_id'],target_id=context['target_id'],
                source_role=field,path=context[field]['path'],sha256=context[field]['sha256'])
    actual={name:role.get('source_binding') for name,role in roles.items() if name.startswith('partner-') or 'source_binding' in role}
    require(actual==wanted,'Available partner evidence bindings differ or held partner has fabricated evidence')


def source_context_files(case):
    raw,_=stable_bytes(case['outer']['path'],case['outer']['sha256'])
    files=engine.source_evidence(engine.decode(raw));context=case['paired_context']
    require(context['concept_id']==case['semantic_context']['concept_id'] and context['target_id']!=case['target_id'] and
        {context['target_id'].split(':')[0],case['target_id'].split(':')[0]}=={'106','107'} and
        context['mask_transfer_allowed'] is False and context['pose_equivalence_assumed'] is False,'Wrong paired source context')
    if 'held_disposition' not in context:
        for field,role in PARTNER_ROLES:
            raw,_=stable_bytes(context[field]['path'],context[field]['sha256']);a=engine.decode(raw)
            _,Image,*_=engine.stack();stream=io.BytesIO();Image.fromarray(a,'RGBA').save(stream,'PNG');files[role]=stream.getvalue()
    return files


def render_cases(folder,cases,held=()):
    renderer=Renderer(folder);catalog={};by_id={c['target_id']:c for c in cases};held_by_id={h['target_id']:h for h in held}
    for case in cases:
        identity=case['target_id'];catalog[identity]={}
        if case.get('source_required'):
            context=case['paired_context'];partner=by_id.get(context['target_id'])
            if 'held_disposition' in context:
                hold=held_by_id.get(context['target_id'])
                require(partner is None and hold is not None and hold==context['held_disposition'] and
                    hold['concept_id']==context['concept_id'] and not any(field in context for field,_ in PARTNER_ROLES),
                    'Held partner context binding differs from admitted disposition')
            else:
                require(partner is not None and partner['semantic_context']['concept_id']==context['concept_id'] and
                    partner['true_original']==context['true_original'] and partner['outer']==context['outer'] and
                    partner['source_required']==context['partner_source_required'],'Partner original/stage context binding differs from actual paired case')
            roles=renderer.add(identity,'source',source_context_files(case))
            for field,role in PARTNER_ROLES:
                if role in roles:
                    roles[role]['source_binding']=dict(concept_id=context['concept_id'],target_id=context['target_id'],
                        source_role=field,path=context[field]['path'],sha256=context[field]['sha256'])
            validate_partner_roles(roles,context)
            catalog[identity]['source']=roles
        if case.get('changed_vs_true_original'):
            before,_=stable_bytes(case['true_original']['path'],case['true_original']['sha256'])
            after,_=stable_bytes(case['final']['path'],case['final']['sha256'])
            files=engine.evidence(engine.decode(before),engine.decode(after),case.get('normalized_regions',[]))
            catalog[identity]['output']=renderer.add(identity,'output',files)
    return renderer,catalog


def verify_catalog(catalog,expected):
    require(catalog==expected,'Evidence roles, crop geometry, aliases or source/display bindings differ')


def validate_exec_groups(events):
    counts={};ids=set()
    for event in events:
        if event.get('type')!='display':continue
        eid=event.get('display_event_id');execution=event.get('exec_id')
        require(isinstance(eid,str) and eid.strip() and eid not in ids,'Unique actual display event ID required');ids.add(eid)
        require(isinstance(execution,str) and execution.strip(),'Actual whole-exec grouping required')
        counts[execution]=counts.get(execution,0)+1
        require(event.get('exec_file_index')==counts[execution] and counts[execution]<=4,
            'At most4 physical file attempts per entire exec, including retries/inner groups')
    return counts


def journal_location(path,phase=None):
    path=inside(path);base=HERE/'batches'
    require(path.is_relative_to(base),'Review journal must use intended batch review-log location')
    parts=path.relative_to(base).parts
    require(len(parts)==3 and len(parts[0])==10 and parts[0].startswith('batch-') and parts[0][6:].isdigit() and
        parts[1]=='review_logs' and parts[2] in ('source.jsonl','output.jsonl') and (phase is None or parts[2]==phase+'.jsonl'),
        'Review journal must be review_logs/source.jsonl or output.jsonl; images/stages forbidden')
    return path


def checkpoint_location(path,phase=None):
    path=inside(path);base=HERE/'batches'
    require(path.is_relative_to(base),'Checkpoint must use intended review metadata location')
    parts=path.relative_to(base).parts
    require(len(parts)==4 and len(parts[0])==10 and parts[0].startswith('batch-') and parts[0][6:].isdigit() and
        parts[1:3]==('review_metadata','checkpoints') and path.suffix=='.json' and
        (phase is None or path.name.startswith(phase+'-')),'Checkpoint destination must be review_metadata/checkpoints/*.json')
    return path


def validate_journal(events,cases,phase,catalog,batch_id,review_digests):
    """No broad flag can stand in for exact file/role display and checkpoint order.

    Display events are accountable actual-tool observations, supplied by the
    reviewer. This validator does not invent displays or infer them from PNGs.
    """
    require_worker();expected=list(cases);position=0;seen=set();dependencies={};previous=None;last_time=None
    executions=validate_exec_groups(events);checkpoints={};physical_attempts=0;successful_displays=0;unsuccessful_displays=0
    for sequence,event in enumerate(events,1):
        require(event.get('sequence')==sequence and position<len(expected),'Event sequence/extra case differs')
        identity=expected[position]
        require(event.get('target_id')==identity and event.get('phase')==phase,'Durable case ordering differs')
        stamp=datetime.datetime.fromisoformat(event['utc'].replace('Z','+00:00'))
        require(stamp.tzinfo is not None and (last_time is None or stamp>=last_time),'Display/checkpoint timestamps regress')
        last_time=stamp
        roles=catalog[identity][phase]
        if event['type']=='display':
            outcome=event.get('outcome');require(outcome in ('complete','incomplete','failed'),'Faithful display attempt outcome required')
            require(isinstance(event.get('tool_event_reference'),str) and event['tool_event_reference'].strip(),'Actual tool attempt reference required')
            if outcome=='complete':require(event.get('actually_displayed') is True and event.get('native_resolution') is True,'Actual complete native view required')
            else:require(isinstance(event.get('outcome_reason'),str) and event['outcome_reason'].strip(),'Record why display attempt gave no coverage')
            displayed=event.get('roles');require(isinstance(displayed,list) and displayed and len(displayed)==len(set(displayed)),'Exact displayed roles required')
            for role in displayed:
                require(role in roles,'Unknown display role')
                asset=roles[role]
                require(event.get('path')==asset['path'] and event.get('sha256')==asset['sha256'] and
                    event.get('dimensions')==asset['dimensions'] and asset['equality_verified'] is True,
                    'Mistaken file/role/native-size binding')
                if outcome=='complete':seen.add(role)
            physical_attempts+=1
            successful_displays+=outcome=='complete';unsuccessful_displays+=outcome!='complete'
        elif event['type']=='checkpoint':
            require(seen==set(roles),'Missing native/crop/blue/dark/alpha display coverage')
            path=checkpoint_location(event['checkpoint_path'],phase);raw,receipt=stable_bytes(path,event['checkpoint_sha256']);checkpoint=json.loads(raw)
            require(checkpoint==dict(schema='ordered-review-checkpoint-v1',batch_id=batch_id,target_id=identity,
                phase=phase,case_index=position,event_sequence=sequence,previous_checkpoint_sha256=previous,
                review_sha256=review_digests[identity],reviewer=event['reviewer'],utc=event['utc']),
                'Durable checkpoint order/review/source binding differs')
            require(event['reviewer'] and isinstance(event['reviewer'],str),'Actual checkpoint reviewer required')
            previous=receipt['sha256'];dependencies[str(path)]=previous;checkpoints[identity]=checkpoint
            seen=set();position+=1
        else:raise ValueError('Unknown review event type')
    require(position==len(expected) and not seen,'Incomplete durable case review coverage')
    return dict(checkpoint_sha256=dependencies,case_order=expected,checkpoints=checkpoints,physical_file_attempts=physical_attempts,
        successful_displays=successful_displays,unsuccessful_displays=unsuccessful_displays,exec_physical_files=executions)


def append_observed_display(journal_path,event):
    """Persist caller-supplied actual-tool observations; never create a view claim."""
    require_worker();journal_path=journal_location(journal_path,event.get('phase'))
    require(event.get('type')=='display' and event.get('phase') in ('source','output') and
        event.get('outcome') in ('complete','incomplete','failed') and event.get('tool_event_reference'),
        'Supply an actual display observation')
    previous=jsonl(journal_path) if journal_path.exists() else []
    require(event.get('sequence')==len(previous)+1,'Display sequence must continue durable journal')
    validate_exec_groups(previous+[event])
    _append(journal_path,event)


def _append(path,event):
    path=journal_location(path,event.get('phase'))
    require(event.get('phase') in ('source','output') and event.get('type') in ('display','checkpoint'),'Review-log events require explicit phase/type')
    if path.exists():jsonl(path)  # A misnamed image/non-JSON file is never appended to.
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('ab') as stream:
        stream.write((json.dumps(event,sort_keys=True)+'\n').encode());stream.flush();os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def checkpoint_observed_case(journal_path,checkpoint_folder,batch_id,phase,case_order,catalog,review,utc):
    """Validate covered roles, durably commit this case, then permit the next."""
    require_worker();journal_path=journal_location(journal_path,phase)
    checkpoint_location(Path(checkpoint_folder)/(phase+'-guard.json'),phase)
    events=jsonl(journal_path);done=[e for e in events if e['type']=='checkpoint'];index=len(done)
    require(index<len(case_order),'All required cases already checkpointed')
    identity=case_order[index];require(review['target_id']==identity,'Checkpoint review/case ordering differs')
    previous=done[-1]['checkpoint_sha256'] if done else None;sequence=len(events)+1
    doc=dict(schema='ordered-review-checkpoint-v1',batch_id=batch_id,target_id=identity,phase=phase,case_index=index,
        event_sequence=sequence,previous_checkpoint_sha256=previous,review_sha256=sha(payload(review)),reviewer=review['reviewer'],utc=utc)
    path=checkpoint_location(Path(checkpoint_folder)/(phase+f'-{index:03d}-'+sha(payload(doc))+'.json'),phase);immutable(path,payload(doc))
    event=dict(type='checkpoint',sequence=sequence,target_id=identity,phase=phase,utc=utc,reviewer=review['reviewer'],
        checkpoint_path=str(path),checkpoint_sha256=file_sha(path))
    digests={e['target_id']:read(e['checkpoint_path'])['review_sha256'] for e in done};digests[identity]=doc['review_sha256']
    validate_journal(events+[event],case_order[:index+1],phase,catalog,batch_id,digests)
    _append(journal_path,event)
    return event
