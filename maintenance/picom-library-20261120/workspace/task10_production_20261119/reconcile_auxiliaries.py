"""Fill the saved schematic auxiliary paradigm; retain existing style modals."""
import sys, re, json, hashlib, datetime, fcntl, os
from pathlib import Path
import compose as C
sys.path.insert(0,str(C.PR))
import det_auxiliaries as A, det_modals_extra as M
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(s):return re.sub(r'\s*\([^)]*\)$','',s.replace('-',' ')).strip()
def main():
 lock=(C.H/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 masters=A.masters(); report={'at':datetime.datetime.now().astimezone().isoformat(),'method':str(C.PR/'det_auxiliaries.py'),'method_sha256':sha(C.PR/'det_auxiliaries.py'),'visual_review':'All 17 unchanged schematic masters inspected on auxiliaries_review.jpg; per-file byte and render validation','styles':{},'published':[]}
 for st in sorted(p for p in LIB.iterdir() if p.is_dir() and not p.name.startswith('_')):
  hits={}
  for root in ([st,LIB.parent/'People'/st.name] if st.name=='Mulberry' else [st]):
   for parent,dirs,files in os.walk(root):
    dirs[:]=[d for d in dirs if d not in ('Plurals and tenses','Pronouns','Contractions','Comparatives')]
    for name in sorted(files):
     p=Path(parent)/name
     if p.suffix not in ('.svg','.webp'):continue
     rel=p.relative_to(root);n=norm(p.stem)
     if not ('Grammar' in str(rel) or 'Modals' in rel.parts or '05 Modals' in rel.parts or 'Core Words' in rel.parts):continue
     if n in set(masters)|set(M.SPEC):hits.setdefault(n,p)
  details={'auxiliaries':{},'modals':{}}
  for n,s in masters.items():
   if n in hits:
    p=hits[n];details['auxiliaries'][n]={'disposition':'reuse existing','path':str(p),'sha256':sha(p)};continue
   # Exact saved figure-free paradigm, no ad-hoc figure replacements.
   dest=st/'Plurals and tenses'/'04 Grammar'/'Tenses'/(n+'.svg')
   C.render(s);dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():assert dest.read_text()==s, str(dest)
   else:
    with dest.open('x') as f:f.write(s)
   item={'style':st.name,'name':n,'destination':str(dest),'sha256':sha(dest),'method':'saved det_auxiliaries schematic; all 17 masters visually checked'}
   report['published'].append(item);details['auxiliaries'][n]={'disposition':'filled missing schematic form',**item}
  for n in M.SPEC:
   if n in hits:details['modals'][n]={'disposition':'reuse existing; no second clock','path':str(hits[n]),'sha256':sha(hits[n])}
   else:
    assert st.name=='Sommi companion objects',(st.name,n)
    details['modals'][n]={'disposition':'not applicable: object-only style has no corresponding person-modal source; do not introduce stick figures'}
  # Partial Mulberry Library: reuse the already-generated native SVGs from
  # People into this task's separate delivery tree, leaving People untouched.
  external={Path(v['path']) for group in details.values() for v in group.values() if 'path' in v and not Path(v['path']).is_relative_to(LIB)}
  for p in sorted(external):
   rel=p.relative_to(LIB.parent/'People'/st.name);dest=st/'Plurals and tenses'/rel
   data=p.read_bytes();assert p.suffix=='.svg';C.render(data.decode())
   dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():assert dest.read_bytes()==data
   else:dest.write_bytes(data)
   report['published'].append({'style':st.name,'destination':str(dest),'sha256':sha(dest),'source':str(p),'source_sha256':sha(p),'method':'reuse existing People SVG without alteration'})
   for group in details.values():
    for v in group.values():
     if v.get('path')==str(p):v['library_delivery']=str(dest)
  report['styles'][st.name]=details
 report['complete']=True;report['published_count']=len(report['published'])
 (C.H/'auxiliary_modal_reconciliation.json').write_text(json.dumps(report,indent=2));print('Auxiliary/modal reconciliation complete; new deliveries',len(report['published']),flush=True)
if __name__=='__main__':main()
