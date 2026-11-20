#!/usr/bin/env python3
"""Bounded cohort progress page; never claims final whole-scope completion."""
import html
from common import HERE,read,digest,require,require_activation

def main():
    require_activation();progress=read(HERE/'progress.json');rows=[]
    for item in progress['sealed_batches']:
        folder=HERE/'batches'/item['batch_id'];verification=read(folder/'viewer_verification.json')
        require(verification['all_bindings_and_files_valid'] and not verification['errors'],'Unverified viewer')
        require(verification['delivery_sha256']==digest(folder/'accepted_delivery.json') and verification['html_sha256']==digest(folder/'review.html'),'Viewer proof changed')
        require(verification['publication_complete_sha256']==digest(folder/'publication'/'complete.json'),'Publication proof changed')
        rows.append('<li><a href="batches/'+html.escape(item['batch_id'])+'/review.html">'+html.escape(item['batch_id'])+'</a></li>')
    (HERE/'index.html').write_text('<!doctype html><title>Non-People cleanup</title><h1>Non-People batch progress</h1><p>Batch progress is separate from final whole-scope verification and delivery.</p><ul>'+''.join(rows)+'</ul>')
if __name__=='__main__':main()
