#!/usr/bin/env python3
"""Publish exactly the independently reviewed, governing prior Non-People outputs."""
from common import image_worker, require, require_activation
from non_people_publication import operator_lock, prior_publication
from verification import prior_lineage


def main():
    # Active attestation binds the earlier frozen pending-source audit. Prior
    # publication is intentionally an explicit, separate postactivation step.
    require_activation()
    with operator_lock(), image_worker():
        rows, pins, issues = prior_lineage()
        require(not issues, 'Governing prior lineage has unresolved dispositions')
        tx = prior_publication(rows, pins)
        tx.publish()
        print({'status': tx.phase(), 'accepted': len(tx.intent['deliveries']),
               'complete_sha256': tx.completed_pins()[str(tx.complete_path)]})


if __name__ == '__main__':
    main()
