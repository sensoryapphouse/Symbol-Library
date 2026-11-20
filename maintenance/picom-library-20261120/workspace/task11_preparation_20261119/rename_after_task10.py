"""In-place Library renames, gated on verified Task 10 completion. No image copies."""
from pathlib import Path
import datetime,fcntl,json,os,re,sqlite3,sys,time,unicodedata
from urllib.parse import quote
H=Path(__file__).resolve().parent
def stamp():return datetime.datetime.now().astimezone().isoformat()
def write(p,data):
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(data,indent=2));t.replace(p)
def translator(root,mapping):
    subs={}
    for old,new in mapping.items():
        a=str(root/old)+'/';b=str(root/new)+'/'
        subs[a]=b
        # URI prefixes must be distinct from plain paths when the old style
        # has no spaces (Basic -> Basic 1; Mulberry -> Basic SVG).
        subs['file://'+quote(a,safe='/')]='file://'+quote(b,safe='/')
    rx=re.compile('|'.join(re.escape(k) for k in sorted(subs,key=len,reverse=True)))
    return lambda s:rx.sub(lambda m:subs[m.group()],s)
def gate(plan):
    t=Path(plan['task10_root']);p=t/'completion.json'
    if not p.exists():return False,'Waiting for Task 10 final verification, not just queue exhaustion'
    d=json.loads(p.read_text())
    for key in ('task10_complete','checks_complete','held_cases_disposed','auxiliary_modal_reconciled'):
        if d.get(key) is not True:return False,'Waiting for completion evidence: '+key
    with sqlite3.connect(t/'queue.sqlite') as db:
        counts=dict(db.execute('select status,count(*) from jobs group by status'))
    if any(counts.get(k,0) for k in ('pending','review','checked','processing')):return False,'Task 10 still has unfinished jobs'
    if d.get('queue_counts')!=counts:return False,'Task 10 completion counts do not match queue'
    return True,'Final Task 10 completion evidence matches queue'
def apply(plan):
    root=Path(plan['library_root']);mapping=plan['mapping'];names=plan['confirmed_names']
    c=json.loads((H/'naming_choices.json').read_text())
    assert c['confirmed']==names==c['draft'],'Names changed; reprepare the plan before renaming'
    assert len(set(unicodedata.normalize('NFD',v).casefold() for v in names.values()))==len(names)
    assert names['Flat outlined']!=names['Classic flat TV cartoon'],'Keep both outlined sets separate'
    ep=H/'execution.json';state=json.loads(ep.read_text()) if ep.exists() else {'state':'prepared','started_at':stamp(),'directories':{},'renamed':[]}
    if state['state']=='complete':return
    if not state['directories']:
        for old in names:
            p=root/old;assert p.is_dir() and not p.is_symlink(),str(p)
            st=p.stat();state['directories'][old]={'inode':st.st_ino,'device':st.st_dev}
        for old,new in mapping.items():
            p=root/new;assert not p.exists() or new in mapping,'Destination already exists: '+str(p)
        state['state']='renaming';write(ep,state)
    for old,new in plan['rename_order']:
        before=root/old;after=root/new;expected=state['directories'][old]
        # Recover safely if interrupted immediately after an atomic rename.
        if after.exists() and after.stat().st_ino==expected['inode'] and after.stat().st_dev==expected['device']:pass
        else:
            assert before.is_dir() and before.stat().st_ino==expected['inode'],str(before)
            assert not after.exists(),'Never overwrite '+str(after)
            before.rename(after)
        if old not in state['renamed']:state['renamed'].append(old)
        write(ep,state)
    for old,new in names.items():
        p=root/new;e=state['directories'][old];assert p.stat().st_ino==e['inode'] and p.stat().st_dev==e['device']
    tx=translator(root,mapping);task10=Path(plan['task10_root'])
    with sqlite3.connect(task10/'queue.sqlite') as db:
        db.execute('create table if not exists task11_original_job_paths(job_id integer primary key,style text,source text,destination text)')
        existing=db.execute('select count(*) from task11_original_job_paths').fetchone()[0]
        if not existing:
            rows=db.execute('select id,style,source,destination from jobs').fetchall()
            db.executemany('insert into task11_original_job_paths values(?,?,?,?)',rows)
            db.executemany('update jobs set style=?,source=?,destination=? where id=?',[(names.get(st,st),tx(src),tx(dst),i) for i,st,src,dst in rows])
        else:assert existing==db.execute('select count(*) from jobs').fetchone()[0]
    for file in plan['current_review_html']:
        p=Path(file)
        if p.exists():
            old=p.read_text();new=tx(old)
            if new!=old:
                tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(new);tmp.replace(p)
    # Frozen delivery records retain their provenance and original checksums.
    # The current registry explicitly resolves those old style IDs to new folders.
    registry={'schema':'picom-current-style-names-v1','renamed_at':stamp(),'historical_records_unchanged':True,'path_rule':'Translate original Library style IDs exactly once; People and other source paths are unchanged.','styles':[{'original_style_id':old,'current_name':new,'library_folder':str(root/new),'historical_manifest':str(root/'_manifest'/(old+'.csv')),'preserve_svg':old=='Mulberry'} for old,new in names.items()]}
    write(root/'_manifest'/'current-style-names.json',registry)
    catalog=H/'catalog.json'
    if catalog.exists():
        rows=json.loads(catalog.read_text())
        for row in rows:row['sample']=tx(row['sample'])
        write(catalog,rows)
    state.update(state='complete',completed_at=stamp(),people_originals_untouched=True,image_copies_created=0,registry=str(root/'_manifest'/'current-style-names.json'),next_task=12)
    write(ep,state)
    d=json.loads((H/'decision.json').read_text());d.update(state='renaming_complete',completed_at=state['completed_at']);write(H/'decision.json',d)
def main(wait=False):
    own=(H/'rename.lock').open('a');fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        plan=json.loads((H/'rename_plan.json').read_text());ok,reason=gate(plan)
        write(H/'rename_wait.json',{'pid':os.getpid(),'updated_at':stamp(),'state':'ready' if ok else 'waiting_task10','reason':reason})
        if ok:
            with (Path(plan['task10_root'])/'worker.lock').open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    if not wait:return
                    time.sleep(30);continue
                ok,reason=gate(plan)
                if ok:apply(plan);return
        if not wait:return
        time.sleep(30)
if __name__=='__main__':
    try:main('--wait' in sys.argv)
    except BaseException as e:
        write(H/'rename_wait.json',{'pid':os.getpid(),'updated_at':stamp(),'state':'stopped_error','error':str(e)})
        raise
