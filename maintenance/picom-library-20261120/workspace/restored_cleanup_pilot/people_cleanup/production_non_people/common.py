"""Isolated Non-People cohort guards and the single original image-worker lock."""
import contextlib,datetime,fcntl,hashlib,json,os,re,time,sys
from pathlib import Path
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
HERE=Path(__file__).resolve().parent
LIBRARY=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
def require(ok,message):
    if not ok:raise ValueError(message)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    with temp.open('w') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def validate_bundle():
    require(not sys.flags.optimize,'Optimized Python disables inherited mechanical assertions; runtime forbidden')
    bundle=read(HERE/'code_bundle.json')
    for name,expected in bundle['local_sha256'].items():require(digest(HERE/name)==expected,'Runtime code/policy drift: '+name)
    for name,expected in bundle['external_sha256'].items():require(digest(name)==expected,'Frozen input/dependency drift: '+name)
    return bundle

def stable_source_sha(path,expected):
    def signature(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    path=Path(path);before=path.stat();h=hashlib.sha256()
    with path.open('rb') as f:
        opened=os.fstat(f.fileno())
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
        closed=os.fstat(f.fileno())
    after=path.stat();require(signature(before)==signature(opened)==signature(closed)==signature(after),'Source changed during byte audit')
    require(h.hexdigest()==expected,'Original source SHA changed')
    return dict(zip(('device','inode','bytes','mtime_ns','ctime_ns'),signature(after)))

def require_activation():
    from activation import require_active
    return require_active()


def verify_batch_scope(batch):
    require_activation();batch=Path(batch).resolve(strict=True)
    require(batch.parent==HERE/'batches' and re.fullmatch(r'batchN\d{3,}',batch.name),'Batch outside Non-People cohort')
    from contracts import validate_manifest
    manifest=read(batch/'manifest.json');queue=read(HERE/'queue.json');index=read(HERE/'batch_index.json')
    require(manifest['queue_sha256']==index['queue_sha256']==digest(HERE/'queue.json'),'Frozen queue binding differs')
    validate_manifest(manifest,queue,batch.name)
    return batch

@contextlib.contextmanager
def image_worker():
    require_activation()
    current=os.getpriority(os.PRIO_PROCESS,0)
    if current<10:os.nice(10-current)
    require(os.getpriority(os.PRIO_PROCESS,0)>=10,'Image work requires nice10')
    # Existing workflow stages are bounded by150 subjects+50 references, with per-image checkpoints.
    # No second lock or worker namespace is introduced.
    with (HERE.parent/'production/image_worker.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)
    time.sleep(.1)
