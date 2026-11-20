#!/usr/bin/env python3
"""Publish the completed library to the existing private repository, one ZIP at a time.

Never edits Library or People. Resumable by server SHA-256; no token is saved.
"""
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
LIBRARY = Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
REVIEW = Path('/Users/paulblenkhorn/Desktop/picom_review')
REPO = 'sensoryapphouse/Symbol-Library'
TAG = 'library-2026-11-20'
CHECKOUT = HERE / 'checkout'
TEMP = HERE / 'temporary'
RECORD_DIR = 'maintenance/picom-library-20261120'
MAX_PART = 1_700_000_000
ENV = None


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def event(stage, **data):
    value = {'at': now(), 'stage': stage} | data
    save(HERE / 'progress.json', value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def run(args, cwd=None, timeout=3600):
    p = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{args[:3]} failed ({p.returncode}): {p.stderr[-2000:]}')
    return p.stdout


def api(endpoint, *args):
    return json.loads(run(['gh', 'api', endpoint, *args]))


def auth():
    global ENV
    token = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com', '--user', 'sensoryapphouse'],
                           capture_output=True, text=True, check=True).stdout.strip()
    if not token:
        raise RuntimeError('No existing Sensory App House authentication')
    ENV = os.environ.copy()
    ENV['GH_TOKEN'] = token
    ENV['GIT_TERMINAL_PROMPT'] = '0'
    if not api(f'repos/{REPO}')['private']:
        raise RuntimeError('Expected existing private repository')


def git(*args):
    return run(['git', '-c', 'credential.helper=', '-c',
                'credential.helper=!/opt/homebrew/bin/gh auth git-credential', *args], cwd=CHECKOUT)


def inventory():
    complete = json.loads((WORK / 'final_delivery_20261119/completion.json').read_text())
    assert complete['complete'] and complete['People_untouched']
    expected = {}
    with (LIBRARY / '_manifest/final-delivery-20261119.jsonl').open() as f:
        for line in f:
            row = json.loads(line)
            expected[str(Path(row['path']).relative_to(LIBRARY))] = row['after_sha']
    assert len(expected) == 289820
    actual = {str(p.relative_to(LIBRARY)) for p in LIBRARY.rglob('*')
              if p.is_file() and p.suffix.lower() in ('.webp', '.svg')}
    assert actual == set(expected), 'Current image paths differ from verified final manifest'
    groups = collections.defaultdict(list)
    for rel in sorted(actual):
        p = LIBRARY / rel
        st = p.stat()
        groups[Path(rel).parts[0]].append(dict(path=rel, size=st.st_size, mtime_ns=st.st_mtime_ns,
                                             sha256=expected[rel] or sha(p)))
    groups['_manifest'] = [dict(path=str(p.relative_to(LIBRARY)), size=p.stat().st_size,
                               mtime_ns=p.stat().st_mtime_ns, sha256=sha(p))
                           for p in sorted((LIBRARY / '_manifest').rglob('*'))
                           if p.is_file() and p.suffix in ('.json', '.jsonl', '.csv')]
    parts = []
    for style, files in sorted(groups.items()):
        batches = [[]]
        size = 0
        for row in files:
            # Conservative ZIP header allowance per entry.
            if batches[-1] and size + row['size'] + 2048 > MAX_PART:
                batches.append([])
                size = 0
            batches[-1].append(row)
            size += row['size'] + 2048
        slug = re.sub(r'[^a-z0-9]+', '-', style.lower()).strip('-')
        for i, batch in enumerate(batches, 1):
            parts.append(dict(name=f'{slug}-{i:02}.zip', style=style,
                              files=batch, source_bytes=sum(x['size'] for x in batch)))
    plan = dict(created=now(), repository=REPO, tag=TAG, images=len(actual),
                image_bytes=sum((LIBRARY / rel).stat().st_size for rel in actual),
                parts=parts, original_people_untouched=True)
    save(HERE / 'inventory.json', plan)
    return plan


def selected_sources():
    result = {}
    taskdirs = [p for p in WORK.iterdir() if p.is_dir() and
                (p.name.startswith('task') or p.name in ('comparative_arrow_audit_20261119',
                 'comparative_arrow_repairs_20261119', 'final_delivery_20261119'))]
    record_names = {'completion.json', 'final_audit.json', 'task12_completion.json',
                    'licence_exclusions.json', 'execution.json', 'authorised_sequence.json',
                    'acceptance_policy.json', 'protocol.json', 'scope_contract.json',
                    'visual_acceptance.json', 'verification.json', 'handoff_verification.json',
                    'parallel_verification.json', 'validation_report.json', 'summary.json'}
    cleanup = WORK / 'restored_cleanup_pilot/people_cleanup'
    dirs = taskdirs + [cleanup] + [cleanup / n for n in (
        'production', 'production_non_people', 'production_remaining_people', 'production_wizard_soccer')]
    for directory in dirs:
        for p in sorted(directory.iterdir()):
            if p.is_file() and (p.suffix == '.py' or p.name in record_names or p.name == 'RUNBOOK.md'):
                if p.stat().st_size > 2_000_000:
                    continue
                result['workspace/' + str(p.relative_to(WORK))] = p
    for name in ('LIBRARY_TASKS.md', 'CONSOLIDATION_PLAN.md', 'smart_shrink_plurals.py',
                 'make_plurals_flex.py', 'build_tenses.py', 'tense_annotate.py', 'det_auxiliaries.py',
                 'det_engine.py', 'stamp_copyright.py'):
        p = REVIEW / name
        if p.is_file():
            result['picom_review/' + name] = p
    result['publisher/publish.py'] = Path(__file__).resolve()
    return result


def prepare_repo(plan):
    if not CHECKOUT.exists():
        run(['git', '-c', 'credential.helper=', '-c',
             'credential.helper=!/opt/homebrew/bin/gh auth git-credential',
             'clone', '--depth', '1', '--filter=blob:none', '--sparse',
             f'https://github.com/{REPO}.git', str(CHECKOUT)])
    if git('status', '--porcelain').strip():
        raise RuntimeError('Publication checkout has uncommitted changes; inspect before resuming')
    if not (HERE / 'source_commit.json').exists():
        dest = CHECKOUT / RECORD_DIR
        dest.mkdir(parents=True, exist_ok=True)
        manifest = []
        for rel, src in selected_sources().items():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
            manifest.append(dict(path=rel, source=str(src), bytes=out.stat().st_size, sha256=sha(out)))
        save(dest / 'SOURCE_FILES.json', manifest)
        save(dest / 'release_inventory.json', {k: v for k, v in plan.items() if k != 'parts'} | {
            'archives': [dict(name=x['name'], style=x['style'], files=len(x['files']),
                              source_bytes=x['source_bytes']) for x in plan['parts']]})
        (dest / 'README.md').write_text(
            '# Completed PiCom Library work — 20 November 2026\n\n'
            'This is a selected source and audit snapshot for the completed background cleanup, '
            'comparative repairs, figure substitutions, plurals and tenses, style renaming, Q80 '
            'conversion, and final metadata pass. LIBRARY_TASKS.md retains the saved plan and '
            'separate historical backlog; completed delivery is not a claim that all backlog items are done.\n\n'
            'The image payload is in the matching GitHub release, not Git history. '
            'The final Library contains 289,820 images: 288,794 WebPs and 1,026 native Basic SVG files. '
            'The metadata pass verified 289,796 images and left 24 documented third-party sign-language '
            'chart exclusions untouched. Those exclusions are not relicensed.\n\n'
            'These are the actual production scripts and compact audit records, with their historical '
            'local paths retained. They are not a portable installer or a request to rerun completed work. '
            'Source hashes are in SOURCE_FILES.json. Large runtime databases, review images, temporary '
            'files and People originals are deliberately absent.\n')
        git('add', '--sparse', '--', RECORD_DIR)
        git('commit', '-m', 'Preserve completed PiCom Library production scripts, plan and audit')
        commit = git('rev-parse', 'HEAD').strip()
        git('push', 'origin', 'HEAD:main')
        save(HERE / 'source_commit.json', dict(commit=commit, files=len(manifest), at=now()))
    return json.loads((HERE / 'source_commit.json').read_text())['commit']


def release():
    return api(f'repos/{REPO}/releases/tags/{TAG}')


def ensure_release(commit):
    releases = api(f'repos/{REPO}/releases?per_page=100')
    if not any(r['tag_name'] == TAG for r in releases):
        run(['gh', 'release', 'create', TAG, '--repo', REPO, '--draft', '--target', commit,
             '--title', 'Completed Symbol Library — 20 November 2026', '--notes-file', str(HERE / 'release-notes.md')])
    current = release()
    assert current['draft'] or (HERE / 'completion.json').exists(), 'Existing published release; do not alter blindly'
    return current


def write_zip(part, target):
    before = time.monotonic()
    event('packaging', archive=part['name'], files=len(part['files']))
    with zipfile.ZipFile(target, 'w', allowZip64=True) as archive:
        for row in part['files']:
            p = LIBRARY / row['path']
            st = p.stat()
            if st.st_size != row['size'] or st.st_mtime_ns != row['mtime_ns']:
                raise RuntimeError(f'Source changed after inventory: {row["path"]}')
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise RuntimeError(f'Source differs from final audit: {row["path"]}')
            info = zipfile.ZipInfo('Library/' + row['path'], date_time=(2026, 11, 20, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_STORED if p.suffix == '.webp' else zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=1)
    with zipfile.ZipFile(target) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f'ZIP integrity failure: {bad}')
        assert len(archive.infolist()) == len(part['files'])
    assert target.stat().st_size < 2_000_000_000
    return dict(sha256=sha(target), bytes=target.stat().st_size, packaging_seconds=time.monotonic()-before)


def upload_verified(path, detail):
    before = time.monotonic()
    for attempt in range(1, 6):
        current = release()
        found = next((a for a in current['assets'] if a['name'] == path.name), None)
        if found:
            if found['state'] == 'uploaded' and found['size'] == detail['bytes'] and found.get('digest') == 'sha256:' + detail['sha256']:
                return dict(asset_id=found['id'], uploaded_at=found['updated_at'], seconds=time.monotonic()-before)
            # Never overwrite an asset whose checksum is unconfirmed.
            raise RuntimeError(f'Remote asset {path.name} exists but does not match verified local bytes')
        event('uploading', archive=path.name, bytes=detail['bytes'], attempt=attempt)
        try:
            run(['gh', 'release', 'upload', TAG, str(path), '--repo', REPO], timeout=7200)
            found = next((a for a in release()['assets'] if a['name'] == path.name), None)
            if found and found['state'] == 'uploaded' and found['size'] == detail['bytes'] and found.get('digest') == 'sha256:' + detail['sha256']:
                return dict(asset_id=found['id'], uploaded_at=found['updated_at'], seconds=time.monotonic()-before)
            raise RuntimeError('Uploaded asset could not be verified by server SHA-256')
        except Exception as exc:
            event('upload_retry', archive=path.name, attempt=attempt, error=str(exc))
            if attempt == 5:
                raise
            time.sleep(10 * attempt)
    raise RuntimeError('Could not verify upload')


def main():
    lock = (HERE / 'publisher.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (HERE / 'completion.json').exists():
        print('Already completed; no uploads repeated.', flush=True)
        return
    os.nice(10)
    auth()
    plan = json.loads((HERE / 'inventory.json').read_text()) if (HERE / 'inventory.json').exists() else inventory()
    (HERE / 'release-notes.md').write_text(
        'Completed Library snapshot: **289,820 images** in 20 style folders '
        '(288,794 WebP files and 1,026 native Basic SVG files).\n\n'
        'Includes the final background cleanup, comparative arrows, full-figure compositions, '
        'pronouns and contractions, plurals and tenses, agreed style names, Q80 conversion, and '
        'copyright/licence metadata completed on 20 November 2026.\n\n'
        'Extract all ZIPs into the same **empty destination** to reconstruct Library/. '
        'Do not overlay the earlier release: renamed styles and replaced SVGs could leave obsolete files. '
        'The SHA256SUMS.txt file verifies each archive. Library/_manifest/final-delivery-20261119.jsonl '
        'contains the final file and pixel hashes; paths in the historical audit are absolute source paths.\n\n'
        '**Licensing:** 289,796 files carry the agreed Sensory App House CC BY-NC 4.0 metadata. '
        'The 24 documented third-party sign-language chart exclusions are included unchanged and are '
        'not covered by that new licence claim; see the licence_exclusions.json audit in maintenance.\n\n'
        f'[Production scripts, saved plan and compact audit](https://github.com/{REPO}/tree/main/{RECORD_DIR}). '
        'The earlier release and the separate SVG collection are preserved. People originals are not included.\n')
    event('preparing_repository', images=plan['images'], archives=len(plan['parts']))
    commit = prepare_repo(plan)
    ensure_release(commit)
    TEMP.mkdir(exist_ok=True)
    uploaded_path = HERE / 'uploaded.json'
    uploaded = json.loads(uploaded_path.read_text()) if uploaded_path.exists() else {}
    for index, part in enumerate(plan['parts'], 1):
        path = TEMP / part['name']
        old = uploaded.get(part['name'])
        if old:
            found = next((a for a in release()['assets'] if a['name'] == path.name), None)
            assert found and found.get('digest') == 'sha256:' + old['sha256'] and found['size'] == old['bytes']
            path.unlink(missing_ok=True)
            continue
        detail = write_zip(part, path)
        detail.update(upload_verified(path, detail))
        detail.update(files=len(part['files']), source_bytes=part['source_bytes'])
        uploaded[part['name']] = detail
        save(uploaded_path, uploaded)
        path.unlink()
        event('archive_verified_and_deleted', completed=index, total=len(plan['parts']),
              archive=part['name'], detail=detail,
              uploaded_bytes=sum(x['bytes'] for x in uploaded.values()))
    sums = HERE / 'SHA256SUMS.txt'
    sums.write_text(''.join(f'{uploaded[p["name"]]["sha256"]}  {p["name"]}\n' for p in plan['parts']))
    upload_verified(sums, dict(sha256=sha(sums), bytes=sums.stat().st_size))
    current = release()
    expected_names = {p['name'] for p in plan['parts']} | {'SHA256SUMS.txt'}
    assert {a['name'] for a in current['assets']} == expected_names
    run(['gh', 'release', 'edit', TAG, '--repo', REPO, '--draft=false', '--latest'])
    # Update only the release link/summary in README; preserve the independent SVG collection.
    readme = CHECKOUT / 'README.md'
    text = readme.read_text()
    old = 'https://github.com/sensoryapphouse/Symbol-Library/releases/tag/webp-library-2026-11'
    new = f'https://github.com/{REPO}/releases/tag/{TAG}'
    text = text.replace(old, new).replace('[WebP Symbol Library release]', '[completed Symbol Library release]')
    text = text.replace('contains the WebP artwork, arranged by style, and its source manifests.',
                        'contains 289,820 finished images (WebP plus native Basic SVG), arranged by style, and the verified manifests.')
    text = text.replace('Extract the archives into the same destination', 'Extract the archives into the same empty destination')
    text += f'\nThe [production scripts, saved plan and compact audit]({RECORD_DIR}/README.md) record the completed 20 November 2026 update.\n'
    readme.write_text(text)
    git('add', '--', 'README.md')
    git('commit', '-m', 'Point to verified completed Library release of 20 November 2026')
    git('push', 'origin', 'HEAD:main')
    final_commit = git('rev-parse', 'HEAD').strip()
    assert not git('status', '--porcelain').strip()
    result = dict(at=now(), complete=True, repository=REPO, release_url=new,
                  source_commit=commit, readme_commit=final_commit, images=plan['images'],
                  archives=len(plan['parts']), asset_bytes=sum(a['size'] for a in release()['assets']),
                  all_remote_checksums_verified=True, People_untouched=True, Library_untouched=True)
    TEMP.rmdir()
    shutil.rmtree(CHECKOUT)
    result['temporary_checkout_and_archives_deleted'] = True
    save(HERE / 'completion.json', result)
    event('complete', **result)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        event('failed', error=repr(exc))
        raise
