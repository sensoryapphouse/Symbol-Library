"""Resumable single-worker Task 10 rollout; never overwrites a Library file."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,sqlite3,sys,time,traceback
import compose as C
H=C.H
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library').resolve()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def publish(db,r):
    dest=Path(r['destination']);stage=H/'staging'/str(r['id'])/dest.name
    assert dest.resolve().is_relative_to(LIB) and dest.relative_to(LIB).parts[1]=='Plurals and tenses'
    assert sha(r['source'])==r['source_sha'],'Source changed since composition'
    assert r['output_sha']
    if dest.exists():
        assert sha(dest)==r['output_sha'],'Existing destination differs; never overwrite'
    else:
        assert sha(stage)==r['output_sha'],'Staged output hash mismatch'
        dest.parent.mkdir(parents=True,exist_ok=True)
        # Hard-link is atomic, no-clobber and does not create a second data copy.
        os.link(stage,dest)
    assert sha(dest)==r['output_sha']
    db.execute('update jobs set status="published" where id=?',(r['id'],));db.commit()
    stage.unlink(missing_ok=True)
    if stage.parent.exists():stage.parent.rmdir()
    for k in ('before','after'):(C.T/f"{r['id']}_{k}.png").unlink(missing_ok=True)
def main():
    lock=(H/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(H/'queue.sqlite',timeout=30);db.row_factory=sqlite3.Row
    db.execute('create table if not exists events(at text, job_id integer, event text, detail text)');db.commit()
    mode=sys.argv[1] if len(sys.argv)>1 else 'plurals'
    start=time.time();processed=0
    def progress(state,current=None):
        data={'updated_at':datetime.datetime.now().astimezone().isoformat(),'pid':os.getpid(),'mode':mode,'state':state,'current_id':current,'session_processed':processed,'session_seconds':round(time.time()-start,2),'counts':dict(db.execute('select status,count(*) from jobs group by status').fetchall()),'worker_limit':1}
        p=H/'progress.json';tmp=H/'progress.json.tmp';tmp.write_text(json.dumps(data,indent=2));tmp.replace(p)
    try:
        # Publish the individually viewed first batch first. SQL acceptance is mandatory.
        rs=db.execute('select j.* from jobs j join checks c on c.job_id=j.id where j.status="review"').fetchall()
        for r in rs:publish(db,dict(r))
        # Resume a verified file interrupted between composition and publication.
        for r in db.execute('select * from jobs where status="checked"').fetchall():
            publish(db,dict(r))
        # If publication committed just before interruption, discard its leftover
        # staging link only after checking that the Library file is identical.
        for stage_dir in (H/'staging').iterdir():
            if not stage_dir.is_dir() or not stage_dir.name.isdigit():continue
            r=db.execute('select * from jobs where id=?',(int(stage_dir.name),)).fetchone()
            if r and r['status']=='published':publish(db,dict(r))
        for p in C.T.glob('review_*.jpg'):p.unlink()
        if mode=='publish-sample':progress('sample_published');return
        assert mode in ('plurals','tenses','all')
        clause={'plurals':'kind="plural"','tenses':'kind!="plural"','all':'1=1'}[mode]
        rows=db.execute('select * from jobs where status="pending" and '+clause+' order by id').fetchall()
        progress('running')
        for row in rows:
            r=dict(row);progress('running',r['id'])
            try:receipt=C.compose(r,False)
            except (AssertionError,ValueError,TimeoutError) as e:
                db.execute('update jobs set status="held",note=? where id=?',(str(e),r['id']));db.commit()
                db.execute('insert into events values(?,?,?,?)',(datetime.datetime.now().astimezone().isoformat(),r['id'],'held',str(e)));db.commit()
            else:
                r.update(receipt)
                db.execute('update jobs set status="checked",source_sha=?,output_sha=?,scale=?,note=? where id=?',(receipt['source_sha'],receipt['output_sha'],receipt['scale'],json.dumps(receipt),r['id']));db.commit()
                # Every file gets render/overlap/source-integrity checks. Visual acceptance
                # applies only to the recorded validation sample, not the entire rollout.
                publish(db,r)
                db.execute('insert into events values(?,?,?,?)',(datetime.datetime.now().astimezone().isoformat(),r['id'],'published','independent render, overlap, clipping and source-integrity checks'));db.commit()
            processed+=1
            if processed%100==0:print('processed',processed,'seconds',round(time.time()-start),'remaining',db.execute('select count(*) from jobs where status="pending" and '+clause).fetchone()[0],flush=True)
        progress('mode_complete');print('MODE COMPLETE',mode,processed,flush=True)
    except BaseException:
        progress('stopped_error');traceback.print_exc();raise
if __name__=='__main__':main()
