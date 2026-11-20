"""Execute the complete stage handoff and rerun it against an isolated tiny Library."""
import pipeline as P
import sqlite3,json,shutil
def main():
 root=P.T/'handoff_test';root.mkdir(exist_ok=True);realH=P.H
 P.W=root;P.H=root/'run';P.H.mkdir(exist_ok=True);P.LIB=root/'Library'
 ten=root/'task10_production_20261119';eleven=root/'task11_preparation_20261119'
 ten.mkdir();eleven.mkdir()
 P.save(ten/'completion.json',{'task10_complete':True});P.save(ten/'auxiliary_modal_reconciliation.json',{})
 P.save(eleven/'execution.json',{'state':'complete'})
 P.save(eleven/'rename_plan.json',{'confirmed_names':{'Test':'Test','Mulberry':'Basic SVG'}})
 svg=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M70 100H400V400H70Z" fill="#ae9238"/></svg>'
 src=P.LIB/'Test/Plurals and tenses/examples.svg';src.parent.mkdir(parents=True);src.write_bytes(svg)
 vector=P.LIB/'Basic SVG/Pronouns/it.svg';vector.parent.mkdir(parents=True);vector.write_bytes(svg)
 original=root/'People/original.svg';original.parent.mkdir();original.write_bytes(svg)
 with sqlite3.connect(ten/'queue.sqlite') as db:
  db.execute('create table jobs(destination text,source text,status text)')
  db.execute('insert into jobs values(?,?,?)',(str(src),str(original),'published'))
 try:
  P.main()
  assert (P.H/'task12_completion.json').exists() and (P.H/'completion.json').exists()
  assert not src.exists() and src.with_suffix('.webp').exists()
  assert vector.exists() and not vector.with_suffix('.webp').exists()
  assert original.read_bytes()==svg
  before={str(p):P.sha(p) for p in P.LIB.rglob('*') if p.is_file()}
  P.main();after={str(p):P.sha(p) for p in P.LIB.rglob('*') if p.is_file()};assert before==after
  P.save(realH/'handoff_verification.json',{'at':P.now(),'passed':True,'actual_stage12_to_stage5_handoff':True,'completed_rerun_unchanged':True,'native_svg_preserved':True,'People_unchanged':True,'no_duplicate_svg_export':True})
  print('Complete sequential handoff and idempotent rerun verified',flush=True)
 finally:shutil.rmtree(root)
if __name__=='__main__':main()
