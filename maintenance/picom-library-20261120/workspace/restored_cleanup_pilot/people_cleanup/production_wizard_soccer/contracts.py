"""Supplemental contracts; metadata imports only, no activation on import."""
import contextlib
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys

if sys.flags.optimize:
    raise RuntimeError('Optimized Python is forbidden')
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREP = BASE / 'wizard_soccer_preparation'
PHASE3 = BASE / 'source_revisions_20261105_phase3'
ROOT = Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols')
RUNTIME = ROOT / 'Second batch/_runtime'
LOCK = BASE / 'production/image_worker.lock'
SCOPE = 6190
AVAILABLE = 6178
HELD = 12
PARTIAL_STATUS = "available_cleanup_complete"
PARTIAL_PROOF_SCHEMA = "paired-supplemental-available-proof-v1"
PARTNER_UNAVAILABLE = "partner_unavailable_generation_held"
PHASE3_SHA = 'f251c68e3175c6a6f09c1ec398da32cc8d2a9e1cf7f02f65d992b3838cc1d85a'
THREAD_KEYS = ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')
_held = False


def runtime_versions():
    return dict(python=sys.version, packages={name:importlib.metadata.version(name) for name in ('numpy','Pillow','scipy')})


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(524288), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def payload(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_worker():
    require(_held and all(os.environ.get(k) == '1' for k in THREAD_KEYS), 'Shared original image worker and threads1 required')


@contextlib.contextmanager
def worker():
    global _held
    require(not _held, 'Nested acquisition would deadlock the original worker')
    for key in THREAD_KEYS:
        os.environ[key] = '1'
    common = load('_ws_original_common', BASE / 'production/common.py')
    require(common.HERE / 'image_worker.lock' == LOCK, 'Different worker lock')
    with common.image_worker():
        _held = True
        try:
            yield
        finally:
            _held = False


def stable_bytes(path, expected=None):
    require_worker()
    path = Path(path)
    require(not any(p.is_symlink() for p in (path,*path.parents)), 'Symlink byte source/ancestor refused')
    def sig(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    before = sig(path.stat())
    with path.open('rb') as stream:
        opened = sig(os.fstat(stream.fileno()))
        raw = stream.read()
        closed = sig(os.fstat(stream.fileno()))
    require(before == opened == closed == sig(path.stat()), 'Source unstable during full read')
    digest = sha(raw)
    require(expected is None or digest == expected, 'Current source bytes changed: ' + str(path))
    return raw, dict(path=str(path), sha256=digest, bytes=len(raw), stable_during_read=True)


def inside(path):
    path = Path(path).absolute()
    require(path.is_relative_to(HERE), 'Write escaped supplemental namespace')
    cursor = path
    while cursor != HERE.parent:
        require(not cursor.is_symlink(), 'Symlink write ancestor')
        cursor = cursor.parent
    require('..' not in path.parts, 'Traversal write path')
    return path


def immutable(path, raw):
    path = inside(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes()==raw,'Immutable replay differs: '+str(path))
        return
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def check_bundle():
    bundle = read(HERE / 'bundle.json')
    for group in ('code_sha256','dependency_sha256'):
        for path, expected in bundle[group].items():
            require(file_sha(path) == expected, 'Pinned code/metadata changed: ' + path)
    return file_sha(HERE / 'bundle.json')


def require_approval(path, action):
    bundle_sha = check_bundle()
    approval = read(path)
    require(approval.get('approved') is True and approval.get('approved_by') == 'root' and
            approval.get('bundle_sha256') == bundle_sha and action in approval.get('allowed_actions', []),
            'Supplemental root code/execution approval remains disabled')
    return approval


def require_absent(path):
    try:
        Path(path).lstat()
    except FileNotFoundError:
        return
    raise ValueError("Held target or unexpected generation WAL appeared: " + str(path))


def inventory():
    rows = jsonl(PREP / 'expected_targets_6190.jsonl')
    require(len(rows) == len({r['target_id'] for r in rows}) == len({r['target'] for r in rows}) == SCOPE, 'Exact supplemental inventory required')
    require({r['style'] for r in rows} == {'Wizard','Soccer player'}, 'Wrong styles')
    return rows
