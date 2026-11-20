"""Test four encoders with a single publisher, restart recovery and a failed input."""
import pipeline as P
import json,shutil,sqlite3
def main():
 realH=P.H;root=P.T/'parallel_test';root.mkdir(exist_ok=False)
 P.H=root/'run';P.H.mkdir();P.LIB=root/'Library';P.W=root;P.ENCODERS=4
 (root/'task11_preparation_20261119').mkdir()
 P.save(root/'task11_preparation_20261119/rename_plan.json',{'current_review_html':[]})
 P.save(P.H/'inventory.json',{'test':True});db=P.dbopen()
 try:
  expected={}
  for i in range(12):
   src=P.LIB/'Test/Plurals and tenses'/f'{i}.svg';src.parent.mkdir(parents=True,exist_ok=True)
   data=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><circle cx="{210+i*6}" cy="256" r="140" fill="#{50+i:02x}ba82"/><path d="M310 100L390 100L350 180Z" fill="red"/></svg>'.encode();src.write_bytes(data)
   encoded,metrics=P.encode(data,512,512);expected[str(src.with_suffix('.webp'))]=P.digest(encoded)
   db.execute('insert into conversions(source,destination,style,width,height,source_sha,old_bytes) values(?,?,?,?,?,?,?)',(str(src),str(src.with_suffix('.webp')),'Test',512,512,P.digest(data),len(data)))
  # One previously published output whose SVG had not yet been removed.
  r=db.execute('select * from conversions order by source limit 1').fetchone()
  out,metrics=P.encode(P.Path(r['source']).read_bytes(),512,512);P.Path(r['destination']).write_bytes(out)
  db.execute('update conversions set status="published",output_sha=?,new_bytes=?,metrics=? where source=?',(P.digest(out),len(out),json.dumps(metrics),r['source']));db.commit()
  bad=P.LIB/'Test/Plurals and tenses/bad.svg';bad.write_bytes(b'not svg')
  db.execute('insert into conversions(source,destination,style,width,height,source_sha,old_bytes) values(?,?,?,?,?,?,?)',(str(bad),str(bad.with_suffix('.webp')),'Test',512,512,P.sha(bad),bad.stat().st_size));db.commit()
  try:P.stage12(db);raise RuntimeError('Failure gate did not stop completion')
  except AssertionError as e:assert 'Conversion exceptions' in str(e)
  counts=dict(db.execute('select status,count(*) from conversions group by status'))
  assert counts=={'complete':12,'error':1},counts
  assert bad.exists() and not bad.with_suffix('.webp').exists()
  for path,digest in expected.items():assert P.sha(path)==digest and not P.Path(path).with_suffix('.svg').exists()
  assert not (P.H/'task12_completion.json').exists()
  db.execute('delete from conversions where status=?',('error',));db.commit();bad.unlink()
  P.stage12(db)
  assert (P.H/'task12_completion.json').exists()
  for path,digest in expected.items():assert P.sha(path)==digest
  P.save(realH/'parallel_verification.json',{'at':P.now(),'passed':True,'encoders':4,'publisher':1,'serial_parallel_byte_identical_outputs':12,'interrupted_publication_recovered':True,'bad_input_retained_and_completion_blocked':True,'completed_rerun_unchanged':True})
  print('Four-encoder publication, byte identity, recovery and failure gate verified',flush=True)
 finally:db.close();shutil.rmtree(root)
if __name__=='__main__':main()
