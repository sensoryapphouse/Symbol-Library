#!/usr/bin/env python3
"""Finish a fully reviewed batch, verify its viewer, then prune its previews."""
import argparse
import subprocess
import sys
from pathlib import Path
from common import HERE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.resolve(strict=True)
    assert batch.parent == HERE / 'batches'
    for script in ('seal.py', 'build_review.py', 'commit_progress.py'):
        subprocess.run([sys.executable, str(HERE / script), '--batch', str(batch)], check=True)
    subprocess.run(['node', str(HERE / 'verify_viewer.cjs'), str(batch)], check=True)
    subprocess.run([sys.executable, str(HERE / 'compact_batch.py'), '--batch', str(batch)], check=True)
    subprocess.run([sys.executable, str(HERE / 'build_progress_index.py')], check=True)


if __name__ == '__main__':
    main()
