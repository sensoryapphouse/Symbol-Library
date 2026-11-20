#!/usr/bin/env python3
"""Seal, commit, publish and retire one independently reviewed batch."""
import argparse
import subprocess
import sys
from pathlib import Path
from common import HERE, image_worker, verify_batch_scope
from non_people_publication import batch_publication, operator_lock, require_committed, require_open_batch
from publication_transaction import exists


def finish(batch):
    batch = verify_batch_scope(batch)
    with operator_lock():
        require_open_batch(batch, closing=True)
        def run(script):
            subprocess.run([sys.executable, str(HERE / script), '--batch', str(batch)], check=True)

        # Once a durable intent exists, old source and accepted workspace bytes
        # may already have been consumed. Resume exclusively from that receipt.
        with image_worker():
            if not exists(batch / 'publication' / 'intent.json'):
                run('seal.py')
                run('commit_progress.py')
            require_committed(batch)
            batch_publication(batch).publish()
            run('build_review.py')
            subprocess.run(['node', str(HERE / 'verify_viewer.cjs'), str(batch)], check=True)
        subprocess.run([sys.executable, str(HERE / 'build_progress_index.py')], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    finish(parser.parse_args().batch)


if __name__ == '__main__':
    main()
