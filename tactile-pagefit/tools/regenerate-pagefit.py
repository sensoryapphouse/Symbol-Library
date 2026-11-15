#!/usr/bin/env python3
"""Reproduce current page-fit exports from authored masters, with exact hashes.

Run: python3 -B tactile-pagefit/tools/regenerate-pagefit.py /new/output/folder
The output folder must not exist. This reproduces only currently catalogued
exports; it does not assess pending meanings or resize/generate new designs.
This folder is self-contained; keep its tools, catalogue and masters together.
"""
from pathlib import Path
import argparse, hashlib, json, sys
COLLECTION = Path(__file__).resolve().parents[1]
ROOT = COLLECTION.parent
sys.path.insert(0, str(COLLECTION / 'tools'))
from tactile_master import write_export

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--profile', help='Optional exact profile ID')
    args = parser.parse_args()
    catalogue = json.loads((COLLECTION / 'catalogue.json').read_text())
    rows = [r for r in catalogue['exports'] if not args.profile or r['profile'] == args.profile]
    if not rows:
        parser.error('No matching current exports')
    dest = args.destination.resolve()
    if dest.exists():
        parser.error('Destination must not already exist')
    if dest == COLLECTION or COLLECTION in dest.parents or dest in COLLECTION.parents:
        parser.error('Choose a destination outside this collection')
    seen = set()
    for row in rows:
        identity = (row['concept_id'], row['profile'])
        if identity in seen:
            raise ValueError(f'Duplicate catalogue row: {identity}')
        seen.add(identity)
        for key, hash_key in [('source_path', 'sha256'), ('master_path', 'master_sha256')]:
            path = (COLLECTION / Path(row[key]).relative_to('tactile-pagefit')).resolve()
            if COLLECTION not in path.parents:
                raise ValueError(f'Path is outside page-fit collection: {path}')
            if sha(path) != row[hash_key]:
                raise ValueError(f'Current hash mismatch: {path}')
    dest.mkdir(parents=True)
    for row in rows:
        relative = Path(row['source_path']).relative_to('tactile-pagefit')
        target = dest / relative
        write_export(COLLECTION / Path(row['master_path']).relative_to('tactile-pagefit'), row['profile'], target)
        if sha(target) != row['sha256']:
            raise ValueError(f'Reproduction mismatch: {relative}')
    print(f'{len(rows)} exports reproduced byte-identically. Source masters and current exports unchanged.')

if __name__ == '__main__':
    main()
