"""Regenerate either complete catalogue into a new directory; standard library only."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from render_visual_master import compile_svg
from tactile_master import write_export
p=argparse.ArgumentParser();p.add_argument('track',choices=['visual','tactile']);p.add_argument('destination',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/a.track/'catalogue.json').read_text())['exports']
a.destination.mkdir(parents=True,exist_ok=False)
for row in rows:
 master=root/row['master_path']
 assert hashlib.sha256(master.read_bytes()).hexdigest()==row['master_sha256'],master
 out=a.destination/Path(row['source_path']).relative_to(a.track+'/exports')
 if a.track=='visual':compile_svg(master,root/'visual/profiles'/(row['profile']+'.json'),out)
 else:write_export(master,row['profile'],out)
 assert hashlib.sha256(out.read_bytes()).hexdigest()==row['sha256'],out
print('Verified byte-identical SVG exports:',len(rows))
