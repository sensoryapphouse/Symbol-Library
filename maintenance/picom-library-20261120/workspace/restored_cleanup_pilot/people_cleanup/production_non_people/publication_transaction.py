"""Journaled in-place publication of exact reviewed bytes. No image decoding or copies."""
import hashlib
import json
import os
import stat
from pathlib import Path
import importlib.util

# Use the reviewed byte and durable-file primitives already shared by Wizard/Soccer.
HELPER = Path(__file__).resolve().parent.parent / 'wood_q80_delivery_20261106/publish_q80.py'
HELPER_SHA = '028d3b465feb033decac37127d93efeb2375eef7a308790e23693920a24baf2d'
if HELPER.is_symlink() or hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA:
    raise ValueError('Publication helper differs from its reviewed SHA')
spec = importlib.util.spec_from_file_location('_np_publication_io', HELPER)
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)
checked_bytes, directory_fd, exists = io.checked_bytes, io.directory_fd, io.exists
require, signature, sync_directory = io.require, io.signature, io.sync_directory


def payload(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document(path):
    return json.loads(checked_bytes(path)[0])


def bound(path, file, allow_empty=False):
    _, _, identity = checked_bytes(path, file['sha256'], file['bytes'])
    require((allow_empty or file['bytes'] > 0) and path.lstat().st_nlink == 1, f'Empty or linked image: {path}')
    return identity


def fingerprint(path, expected=None, size=None, allow_empty=False):
    raw, digest, _ = checked_bytes(path, expected, size)
    require((allow_empty or raw) and path.lstat().st_nlink == 1, f'Empty or linked image: {path}')
    return {'sha256': digest, 'bytes': len(raw)}


def guard(fd, path, identity):
    current = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
    require(signature(current) == identity and current.st_nlink == 1,
            f'File changed immediately before mutation: {path}')


def sync_file(path):
    with directory_fd(path.parent) as parent:
        with os.fdopen(os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent), 'rb') as handle:
            os.fsync(handle.fileno())


def replace(workspace, target, before, output):
    after_id = bound(workspace, output)
    before_id = bound(target, before)
    require(before_id[0] == after_id[0], f'Cross-volume publication refused: {target}')
    sync_file(workspace)
    with directory_fd(workspace.parent) as origin, directory_fd(target.parent) as dest:
        guard(origin, workspace, after_id)
        guard(dest, target, before_id)
        # The workspace file is already the reviewed final image. Move its inode directly
        # into place, without creating a second image or storing the old Library bytes.
        os.replace(workspace.name, target.name, src_dir_fd=origin, dst_dir_fd=dest)
        os.fsync(dest)
        os.fsync(origin)
    bound(target, output)


def retire(path, file):
    identity = bound(path, file, allow_empty=True)
    with directory_fd(path.parent) as parent:
        guard(parent, path, identity)
        os.unlink(path.name, dir_fd=parent)
        os.fsync(parent)


class Publication:
    def __init__(self, folder, intent):
        self.folder = folder
        self.intent = intent
        self.intent_path = folder / 'intent.json'
        self.ready_path = folder / 'retirement_ready.json'
        self.complete_path = folder / 'complete.json'
        intent_sha = sha(payload(intent))
        self.ready = {'schema': 'non-people-retirement-ready-v1', 'intent_sha256': intent_sha}
        self.complete = {'schema': 'non-people-publication-complete-v1', 'intent_sha256': intent_sha,
                         'retirement_ready_sha256': sha(payload(self.ready)), 'kind': intent['kind'],
                         'accepted_updates': len(intent['deliveries']), 'retired_files': len(intent['retire'])}

    def phase(self):
        phase = 'pending'
        for path, expected, prior, following in (
            (self.intent_path, self.intent, 'pending', 'publishing'),
            (self.ready_path, self.ready, 'publishing', 'retiring'),
            (self.complete_path, self.complete, 'retiring', 'complete'),
        ):
            if exists(path):
                require(phase == prior and checked_bytes(path)[0] == payload(expected),
                        f'Publication receipt differs or is out of order: {path}')
                phase = following
        return phase

    def verify_pins(self):
        for name, digest in self.intent['metadata_sha256'].items():
            checked_bytes(Path(name), digest)

    def observe(self, phase):
        ready = phase in ('retiring', 'complete')
        for row in self.intent['deliveries']:
            workspace, library = Path(row['workspace']), Path(row['library'])
            if exists(workspace):
                require(not ready, f'Accepted work file still present: {workspace}')
                after_id = bound(workspace, row['output'])
                before_id = bound(library, row['before'])
                require(before_id[0] == after_id[0], f'Cross-volume publication refused: {library}')
            else:
                require(phase != 'pending', f'Accepted work file missing before intent: {workspace}')
                bound(library, row['output'])
        for name, file in self.intent['retire'].items():
            path = Path(name)
            if exists(path):
                require(phase != 'complete', f'Retired artifact reappeared: {path}')
                bound(path, file, allow_empty=True)
            else:
                require(ready, f'Artifact vanished before retirement authorization: {path}')

    def publish(self):
        phase = self.phase()
        self.verify_pins()
        self.observe(phase)
        if phase != 'pending':
            # A prior writer may have renamed the receipt and been interrupted
            # before its directory sync. Make the validated chain durable first.
            sync_directory(self.folder)
        if phase == 'complete':
            return
        if phase == 'pending':
            paths = [Path(name) for name in (*self.intent['metadata_sha256'], *self.intent['retire'])]
            paths.extend(Path(row['workspace']) for row in self.intent['deliveries'])
            directories = set()
            for path in paths:
                sync_file(path)
                directory = path.parent
                while directory.is_relative_to(self.folder.parent) and directory not in directories:
                    directories.add(directory)
                    directory = directory.parent
                directories.add(path.parent)
            for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
                sync_directory(directory)
            self.folder.mkdir(exist_ok=True)
            sync_directory(self.folder.parent)
            io.write_artifact(self.intent_path, payload(self.intent))
        if phase in ('pending', 'publishing'):
            for row in self.intent['deliveries']:
                workspace, library = Path(row['workspace']), Path(row['library'])
                if exists(workspace):
                    replace(workspace, library, row['before'], row['output'])
                else:
                    sync_directory(library.parent)
                    sync_directory(workspace.parent)
            self.observe('retiring')
            for name, file in self.intent['retire'].items():
                bound(Path(name), file, allow_empty=True)
            self.verify_pins()
            io.write_artifact(self.ready_path, payload(self.ready))
        for name, file in self.intent['retire'].items():
            path = Path(name)
            if exists(path):
                retire(path, file)
            else:
                sync_directory(path.parent)
        self.observe('complete')
        self.verify_pins()
        io.write_artifact(self.complete_path, payload(self.complete))

    def completed_pins(self):
        require(self.phase() == 'complete', f'Publication and retirement incomplete: {self.folder}')
        return {str(path): checked_bytes(path)[1]
                for path in (self.intent_path, self.ready_path, self.complete_path)}
