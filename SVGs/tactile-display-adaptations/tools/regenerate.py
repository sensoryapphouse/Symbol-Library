#!/usr/bin/env python3
"""Verify, or export to a new folder, without changing the retained collection."""
import argparse,hashlib,json,io,xml.etree.ElementTree as ET
from pathlib import Path
from tactile_master import export_tree
D=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def checked(p,digest):
 assert p.is_file(),str(p)
 assert sha(p)==digest,'Hash mismatch: '+str(p)
def grid(root,frame_id,profile):
 width=96 if profile=='monarch-display-v1' else 60
 assert root.get('viewBox')==f'0 0 {width} 40'
 assert root.get('data-concept-id')==frame_id
 rows=root.get('data-pins','').split(' ')
 assert len(rows)==40 and all(len(s)==width and set(s)<={'0','1'} for s in rows)
 expected={(x,y) for y,s in enumerate(rows) for x,c in enumerate(s) if c=='1'};seen=set();ids=set()
 for n in root.iter():
  local=n.tag.split('}')[-1]
  assert local not in {'image','script','text','foreignObject','path','circle','ellipse','polygon','polyline','line','filter','style'}
  if n.get('id'):assert n.get('id') not in ids;ids.add(n.get('id'))
  if local=='rect':
   x,y=int(n.get('x')),int(n.get('y'));assert 0<=x<width and 0<=y<40
   assert n.get('width')=='1' and n.get('height')=='1' and n.get('fill')=='#000000'
   assert (x,y) not in seen;seen.add((x,y))
 assert seen==expected and seen
 assert 'Copyright Sensory App House Ltd' in ET.tostring(root,encoding='unicode')
 return len(seen)
def main():
 parser=argparse.ArgumentParser(description=__doc__);g=parser.add_mutually_exclusive_group(required=True);g.add_argument('--verify',action='store_true');g.add_argument('--output',type=Path);args=parser.parse_args()
 if args.output and args.output.exists():parser.error('--output must be a new folder')
 c=json.loads((D/'catalogue.json').read_text());scope=json.loads((D/'scope.json').read_text());ids={m['parent_concept_id'] for m in c['meanings']}
 assert len(c['meanings'])==len(ids)==42 and ids=={m['concept_id'] for m in scope['records']}
 frames=c['frames'];assert len({f['frame_id'] for f in frames})==len(frames)
 for m in c['meanings']:
  checked(D/m['recipe_path'],m['recipe_sha256']);ff=[f for f in frames if f['parent_concept_id']==m['parent_concept_id']]
  assert len(ff)==m['frame_count']
  assert sorted(f['frame_number'] for f in ff)==list(range(1,len(ff)+1))
  assert all(set(e['profile'] for e in f['exports'])==set(m['profiles']) for f in ff)
 n=0
 for f in frames:
  mp=D/f['master_path'];checked(mp,f['master_sha256'])
  for e in f['exports']:
   ep=D/e['source_path'];checked(ep,e['sha256']);tree=export_tree(mp,e['profile']);buf=io.BytesIO();tree.write(buf,encoding='utf-8',xml_declaration=True);raw=buf.getvalue()
   assert raw==ep.read_bytes(),'Reproduction mismatch: '+str(ep)
   assert grid(tree.getroot(),f['frame_id'],e['profile'])==e['raised_pins']
   assert e['review_png_sha256'] and e['screen_observation'] and e['physical_evaluation']=='pending'
   if args.output:
    target=args.output/Path(e['source_path']).relative_to('exports');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
   n+=1
 print(json.dumps({'meanings':len(ids),'frames':len(frames),'exports':n,'hashes':'verified','master_reproduction':'byte-identical','native_grids':'verified','physical_evaluation':'pending'}))
if __name__=='__main__':main()
