"""Immutable current-invocation source/delivery byte receipts. Resumes reread every byte."""
import collections,contextlib,datetime,fcntl,hashlib,json,os,stat,time,uuid
from pathlib import Path
from common import HERE,LIBRARY,require,read,digest,atomic_json,utc
from source_versions import VERSION_KEYS,version_fields
from publication_transaction import Publication, checked_bytes, directory_fd

FINAL_KIND='whole_original_non_people_final'
PUBLICATION_KEYS=('publication_intent_path','publication_intent_sha256',
                  'publication_complete_path','publication_complete_sha256')


def hash_bytes(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def receipt(path,expected,require_lossless=False,*,image=True):
    path=Path(path);h=hashlib.sha256();size=0
    def sig(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    def safe(info):
        return stat.S_ISREG(info.st_mode) and (not image or info.st_nlink==1)
    if image:
        with directory_fd(path.parent) as parent:
            before=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
            require(safe(before),f'Expected regular single-link image: {path}')
            fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        stream=os.fdopen(fd,'rb')
    else:
        before=path.stat()
        stream=path.open('rb')
    with stream as f:
        opened=os.fstat(f.fileno())
        require(safe(opened) and sig(before)==sig(opened),f'File changed while opening: {path}')
        for chunk in iter(lambda:f.read(524288),b''):h.update(chunk);size+=len(chunk)
        encoded_lossless=False
        if require_lossless:
            f.seek(0);header=f.read(12);require(header[:4]==b'RIFF' and header[8:12]==b'WEBP' and int.from_bytes(header[4:8],'little')+8==size,'Accepted delivery is not a complete WebP container')
            tags=[];at=12
            while at<size:
                f.seek(at);chunk=f.read(8);require(len(chunk)==8,'Truncated accepted WebP chunk');n=int.from_bytes(chunk[4:8],'little');tags.append(chunk[:4]);at+=8+n+(n%2);require(at<=size,'Invalid accepted WebP chunk size')
            require(at==size and b'VP8L' in tags and b'VP8 ' not in tags and b'ANIM' not in tags,'Accepted delivery must be exact lossless WebP, never Q80/lossy')
            encoded_lossless=True
        closed=os.fstat(f.fileno())
    if image:
        with directory_fd(path.parent) as parent:
            after=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
    else:
        after=path.stat()
    stable=(safe(closed) and safe(after) and (not image or size>0)
            and size==after.st_size and sig(before)==sig(opened)==sig(closed)==sig(after))
    return {'path':str(path),'expected_sha256':expected,'actual_sha256':h.hexdigest(),'bytes':size,'stable_during_read':stable,
        'matches':stable and h.hexdigest()==expected,'encoded_lossless_webp':encoded_lossless,'stat_signature':list(sig(after)),'verified_utc':utc()}

@contextlib.contextmanager
def audit_worker():
    # Activation byte auditing must run before runtime activation, so this uses the SAME
    # shared lock without calling common.image_worker's runtime-activation gate.
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    current=os.getpriority(os.PRIO_PROCESS,0)
    if current<10:os.nice(10-current)
    require(os.getpriority(os.PRIO_PROCESS,0)>=10,'Byte audits require actual nice>=10')
    with (HERE.parent/'production/image_worker.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def validate_rows(rows,expected_count):
    paths=set();ids=set();versions=set()
    for row in rows:
        rel=Path(row['relative_path']);require(not rel.is_absolute() and '..' not in rel.parts,'Unsafe relative source path')
        require(str(row['relative_path']) not in paths and row['source_id'] not in ids,'Duplicate planned source identity')
        paths.add(row['relative_path']);ids.add(row['source_id'])
        require(row['source']==str(LIBRARY/rel),'Source outside exact original Library path')
        require(row['delivery_kind'] in ('original','cleaned','repair'),'Unknown delivery kind')
        published='publication_intent_sha256' in row
        require(all(k in row for k in PUBLICATION_KEYS) if published else not any(k in row for k in PUBLICATION_KEYS),
                'Incomplete publication receipt identity')
        if published:
            require(row['delivery_kind']!='original' and row['delivery_path']==row['source']
                    and row['source_sha256']!=row['delivery_sha256']
                    and all(type(row.get(k)) is int and row[k]>0 for k in ('expected_source_bytes','expected_delivery_bytes')),
                    'Invalid in-place publication row')
        elif row['delivery_kind']=='original':require(row['delivery_path']==row['source'] and row['delivery_sha256']==row['source_sha256'],'Original-only row is not source identity')
        else:require(row['delivery_path']!=row['source'] and 'after_q80' not in row['delivery_path'],'Invalid accepted delivery path')
        if any(k in row for k in VERSION_KEYS):
            fields=version_fields(row['relative_path'],row['source_id'],row['historical_source_sha256'],row['source_sha256'])
            require(all(row.get(k)==fields[k] for k in VERSION_KEYS) and row['source_version_id'] not in versions,
                    'Invalid or duplicate current source-version identity')
            versions.add(row['source_version_id'])
        if 'expected_source_bytes' in row:
            require(type(row['expected_source_bytes']) is int and row['expected_source_bytes']>0,'Invalid expected source byte size')
        for key in ('source_sha256','delivery_sha256','historical_source_sha256'):
            if key=='historical_source_sha256' and key not in row:continue
            require(len(row[key])==64 and all(c in '0123456789abcdef' for c in row[key]),'Invalid planned SHA')
    require(len(paths)==expected_count,'Incomplete/extra planned source population')
    return paths

def validate_publications(rows, metadata, kind):
    cache={}
    selected=0
    for row in rows:
        if 'publication_intent_sha256' not in row:
            require(kind!=FINAL_KIND or row['delivery_kind']=='original',
                    'Final accepted result lacks completed Library publication')
            continue
        require(kind==FINAL_KIND, 'Publication receipts belong to the final Library proof')
        intent=Path(row['publication_intent_path'])
        complete=Path(row['publication_complete_path'])
        require(intent.is_absolute() and intent.name=='intent.json' and complete==intent.with_name('complete.json')
                and metadata.get(str(intent))==row['publication_intent_sha256']
                and metadata.get(str(complete))==row['publication_complete_sha256'], 'Unpinned publication receipt')
        if intent not in cache:
            tx=Publication(intent.parent,json.loads(checked_bytes(intent,row['publication_intent_sha256'])[0]))
            require(all(metadata.get(name)==sha for name,sha in tx.completed_pins().items()),
                    'Publication receipt chain differs from final metadata')
            require(all(metadata.get(name)==sha for name,sha in tx.intent['metadata_sha256'].items()),
                    'Publication lineage differs from final metadata')
            by_rel={item['relative_path']:item for item in tx.intent['deliveries']}
            require(len(by_rel)==len(tx.intent['deliveries']), 'Duplicate publication receipt row')
            cache[intent]=by_rel
        item=cache[intent].pop(row['relative_path'],None)
        require(item is not None and item['source_id']==row['source_id'] and item['library']==row['delivery_path']
                and item['before']=={'sha256':row['source_sha256'],'bytes':row['expected_source_bytes']}
                and item['output']=={'sha256':row['delivery_sha256'],'bytes':row['expected_delivery_bytes']},
                'Published receipt does not bind the exact planned Library row')
        selected+=1
    require(not any(cache.values()), 'Publication receipt includes unplanned deliveries')
    return selected


def immutable_write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():require(path.read_bytes()==raw,'Refusing to overwrite immutable audit evidence');return
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def publish(root,folder,proof):
    immutable=folder/'proofs'/(proof['invocation']+'.json');document={**proof,'immutable_proof_path':str(immutable.resolve())}
    raw=(json.dumps(document,indent=2,ensure_ascii=False)+'\n').encode();immutable_write(immutable,raw)
    atomic_json(root/'latest_status.json',{'status':document['status'],'completion_claim':document['completion_claim'],'pass_id':proof['pass_id'],'invocation':proof['invocation'],
        'proof_path':str(immutable.resolve()),'proof_sha256':hash_bytes(raw),'updated_utc':utc()})
    return document

@contextlib.contextmanager
def begin_pass(root, resume_pass=None):
    """Once explicitly authorized, replace current status before any preflight."""
    root = Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    with (root/'audit.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pass_id = resume_pass or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        invocation = uuid.uuid4().hex
        started = utc()
        status = {'status':'running','completion_claim':False,'pass_id':pass_id,'invocation':invocation,
                  'updated_utc':started,'proof_path':None,'proof_sha256':None}
        atomic_json(root/'latest_status.json',status)
        try:
            require(Path(pass_id).name==pass_id and pass_id not in ('.','..'),'Unsafe audit pass ID')
            yield root,pass_id,invocation,started
        except Exception as error:
            atomic_json(root/'latest_status.json',{**status,'status':'failed_preflight_or_audit',
                        'updated_utc':utc(),'error':str(error)})
            raise


def run_pass(rows,metadata,root,kind,expected_count,resume_pass=None,chunk_size=5,worker=audit_worker,metadata_guard=None,admission=None):
    """CLI callers authorize and admit before building the current plan."""
    context = begin_pass(root,resume_pass) if admission is None else contextlib.nullcontext(admission)
    with context as (admitted_root,pass_id,invocation,started):
        require(admitted_root==Path(root).resolve() and (not resume_pass or pass_id==resume_pass),
                'Byte pass does not match its admission')
        root=admitted_root;folder=root/'passes'/pass_id
        require(1<=chunk_size<=50,'Audit chunk size must be1..50');validate_rows(rows,expected_count)
        published=validate_publications(rows,metadata,kind)
        if metadata_guard:metadata_guard(metadata)
        rows=sorted(rows,key=lambda r:r['relative_path']);rowbytes=b''.join(canonical(r)+b'\n' for r in rows)
        signature=hash_bytes(canonical({'kind':kind,'metadata_sha256':metadata,'rows_sha256':hash_bytes(rowbytes),'expected_count':expected_count}))
        plan={'schema':1,'kind':kind,'scope_total':expected_count,'signature_sha256':signature,'rows_sha256':hash_bytes(rowbytes),'metadata_sha256':metadata}
        if resume_pass:require(read(folder/'plan.json')==plan,'Resume metadata/source set changed; preserve prior pass and start a new one')
        else:
            folder.mkdir(parents=True,exist_ok=False);immutable_write(folder/'planned_rows.jsonl',rowbytes);immutable_write(folder/'plan.json',(json.dumps(plan,indent=2)+'\n').encode())
        require(digest(folder/'planned_rows.jsonl')==plan['rows_sha256'],'Planned source set changed')
        checkpoint=folder/('byte_checks_'+invocation+'.jsonl');failed=0;checked=0
        # A fresh checkpoint is ALWAYS created; old successes/stat/SHA caches never skip a read.
        with checkpoint.open('x') as f:
            for start in range(0,len(rows),chunk_size):
                with worker():
                    for row in rows[start:start+chunk_size]:
                        record={**{k:row[k] for k in VERSION_KEYS if k in row},'invocation':invocation,'relative_path':row['relative_path'],'source_id':row['source_id'],'status':row['status'],'delivery_kind':row['delivery_kind']}
                        try:
                            if 'publication_intent_sha256' in row:
                                delivery=receipt(row['delivery_path'],row['delivery_sha256'],require_lossless=True)
                                require(delivery['bytes']==row['expected_delivery_bytes'],'Current Library delivery size differs')
                                record.update(historical_input={k:row[k] for k in PUBLICATION_KEYS},
                                              delivery=delivery,passed=delivery['matches'])
                            else:
                                source=receipt(row['source'],row['source_sha256'])
                                require(source['bytes']==row.get('expected_source_bytes',source['bytes']),'Current source byte size differs')
                                delivery=source if row['delivery_kind']=='original' else receipt(row['delivery_path'],row['delivery_sha256'],require_lossless=True)
                                record.update(source=source,delivery=delivery,passed=source['matches'] and delivery['matches'])
                        except Exception as error:record.update(passed=False,error_type=type(error).__name__,error=str(error))
                        f.write(json.dumps(record,separators=(',',':'))+'\n');checked+=1;failed+=not record['passed']
                    f.flush();os.fsync(f.fileno())
                atomic_json(folder/'progress.json',{'status':'running','completion_claim':False,'invocation':invocation,'checked_this_invocation':checked,'failed':failed,'scope_total':expected_count,'updated_utc':utc()});time.sleep(.1)
        changed=[]
        for path,expected in metadata.items():
            try:
                actual=receipt(path,expected,image=False)
                if not actual['matches']:changed.append(actual)
            except Exception as error:changed.append({'path':path,'error':str(error)})
        if metadata_guard:
            try:metadata_guard(metadata)
            except Exception as error:changed.append({'metadata_guard_error':str(error)})
        complete=checked==expected_count and failed==0 and not changed
        proof={'schema':1,'kind':kind,'status':'complete' if complete else 'failed','completion_claim':complete,'pass_id':pass_id,'invocation':invocation,
            'scope_total':expected_count,'originals_byte_checked_this_invocation':checked-published,
            'published_library_rows_checked_this_invocation':published,
            'current_delivery_rows_checked_this_invocation':checked,'historical_input_receipts_bound':published,
            'files_verified_read_only':True,'failed_file_records':failed,'changed_lineage':changed,'started_utc':started,'completed_utc':utc(),
            'checkpoint_path':str(checkpoint),'checkpoint_sha256':digest(checkpoint),'plan_sha256':digest(folder/'plan.json'),'rows_sha256':plan['rows_sha256'],
            'metadata_sha256':metadata,'signature_sha256':signature,'status_counts':dict(collections.Counter(r['status'] for r in rows)),
            'resume_policy':'Every invocation rereads current delivery bytes and any still-live source bytes. For in-place publications, historical input hashes and sizes come from completed receipts.',
            'earlier_checkpoint_files':[p.name for p in folder.glob('byte_checks_*.jsonl') if p!=checkpoint],
            'library_written':False,'images_decoded_or_changed':False,'stable_stat_verified':True,'exact_source_set_verified':True}
        return publish(root,folder,proof)

def load_complete(root,kind,expected_rows,expected_count):
    root=Path(root).resolve();pointer_path=root/'latest_status.json';pointer_raw=pointer_path.read_bytes();pointer=json.loads(pointer_raw)
    require(pointer.get('status')=='complete' and pointer.get('completion_claim') is True,'Authoritative byte-proof pointer is not complete')
    require(all(Path(pointer[k]).name==pointer[k] and pointer[k] not in ('.','..') for k in ('pass_id','invocation')),'Unsafe authoritative proof identity')
    proofpath=Path(pointer['proof_path']).resolve();require(proofpath==root/'passes'/pointer['pass_id']/'proofs'/(pointer['invocation']+'.json'),'Non-authoritative immutable proof path')
    raw=proofpath.read_bytes();require(hash_bytes(raw)==pointer['proof_sha256'],'Immutable proof SHA differs');proof=json.loads(raw)
    published=validate_publications(expected_rows,proof['metadata_sha256'],kind)
    require(proof.get('published_library_rows_checked_this_invocation',0)==published,'Incorrect publication byte-check count')
    if kind==FINAL_KIND:
        require(proof.get('current_delivery_rows_checked_this_invocation')==expected_count
                and proof.get('historical_input_receipts_bound')==published, 'Incorrect current or historical final verification count')
    require(proof.get('kind')==kind and proof.get('status')=='complete' and proof.get('completion_claim') is True and proof.get('scope_total')==expected_count and proof.get('originals_byte_checked_this_invocation')==expected_count-published and proof.get('failed_file_records')==0 and proof.get('changed_lineage')==[],'Incomplete or wrong-scope immutable proof')
    require(proof['invocation']==pointer['invocation'] and proof['pass_id']==pointer['pass_id'] and proof['immutable_proof_path']==str(proofpath),'Immutable proof identity differs')
    require(proof.get('library_written') is False and proof.get('images_decoded_or_changed') is False,'Byte proof permits image writes')
    folder=proofpath.parent.parent;planpath=folder/'plan.json';require(digest(planpath)==proof['plan_sha256'],'Audit plan SHA differs');plan=read(planpath)
    validate_rows(expected_rows,expected_count);expectedbytes=b''.join(canonical(r)+b'\n' for r in sorted(expected_rows,key=lambda r:r['relative_path']))
    require(hash_bytes(expectedbytes)==plan['rows_sha256']==proof['rows_sha256']==digest(folder/'planned_rows.jsonl'),'Exact audited source/output set differs')
    require(plan['metadata_sha256']==proof['metadata_sha256'] and plan['signature_sha256']==proof['signature_sha256'] and plan['kind']==kind and plan['scope_total']==expected_count,'Plan/proof binding differs')
    require(hash_bytes(canonical({'kind':kind,'metadata_sha256':plan['metadata_sha256'],'rows_sha256':plan['rows_sha256'],'expected_count':expected_count}))==proof['signature_sha256'],'Audit signature differs')
    for path,expected in proof['metadata_sha256'].items():require(digest(path)==expected,'Audited metadata/code changed: '+path)
    checkpoint=Path(proof['checkpoint_path']).resolve();require(checkpoint==folder/('byte_checks_'+proof['invocation']+'.jsonl') and digest(checkpoint)==proof['checkpoint_sha256'],'Audit checkpoint binding differs')
    planned={r['relative_path']:r for r in expected_rows};seen=set();catalog=[]
    with checkpoint.open() as f:
        for line in f:
            require(line.endswith('\n'),'Incomplete byte checkpoint tail');record=json.loads(line);rel=record['relative_path']
            require(rel in planned and rel not in seen,'Unexpected/duplicate byte receipt');seen.add(rel);row=planned[rel]
            require(record['source_id']==row['source_id'] and record['status']==row['status'] and record['delivery_kind']==row['delivery_kind'] and record['invocation']==proof['invocation'] and record['passed'] is True,'Byte receipt identity/status differs')
            require(all(record.get(k)==row.get(k) for k in VERSION_KEYS),'Byte receipt current source version differs')
            historical='publication_intent_sha256' in row
            receipts=[('delivery',row['delivery_path'],row['delivery_sha256'])]
            if historical:
                require('source' not in record and record.get('historical_input')=={k:row[k] for k in PUBLICATION_KEYS},
                        'Historical input was not bound by its publication receipt')
                require(record['delivery']['bytes']==row['expected_delivery_bytes'],'Current Library receipt size differs')
                source_bytes=row['expected_source_bytes']
            else:
                source_bytes=record['source']['bytes']
                require(source_bytes==row.get('expected_source_bytes',source_bytes),'Byte receipt source size differs')
                receipts.append(('source',row['source'],row['source_sha256']))
            for name,path,sha in receipts:
                r=record[name];require(r['path']==path and r['expected_sha256']==r['actual_sha256']==sha and r['matches'] is True and r['stable_during_read'] is True and isinstance(r['bytes'],int) and r['bytes']>0,'Incomplete/failed byte receipt')
                signature=r.get('stat_signature');require(isinstance(signature,list) and len(signature)==5 and all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in signature) and signature[2]==r['bytes'],'Incomplete stable-stat receipt fields')
            if row['delivery_kind']=='original':require(record['source']==record['delivery'],'Skipped original lost exact identity')
            else:require(record['delivery'].get('encoded_lossless_webp') is True,'Accepted delivery lacks lossless WebP receipt')
            if historical:
                state=Path(row['delivery_path']).lstat()
                current=[state.st_dev,state.st_ino,state.st_size,state.st_mtime_ns,state.st_ctime_ns]
                require(stat.S_ISREG(state.st_mode) and state.st_nlink==1 and current==record['delivery']['stat_signature'],'Published Library file changed after final verification')
            catalog.append({**{k:row[k] for k in (*VERSION_KEYS,*PUBLICATION_KEYS) if k in row},'relative_path':rel,'source_id':row['source_id'],'status':row['status'],'delivery_kind':row['delivery_kind'],
                'source_path':row['source'],'source_sha256':row['source_sha256'],'source_bytes':source_bytes,
                'source_byte_evidence':'historical_publication_receipt' if historical else 'verified_current_file',
                'delivery_path':row['delivery_path'],'delivery_sha256':row['delivery_sha256'],'delivery_bytes':record['delivery']['bytes']})
    require(seen==set(planned) and dict(collections.Counter(r['status'] for r in catalog))==proof['status_counts'],'Incomplete exact receipt set/status counts')
    require(pointer_path.read_bytes()==pointer_raw,'Authoritative pointer changed during validation')
    return sorted(catalog,key=lambda r:r['relative_path']),proof,pointer['proof_sha256']
