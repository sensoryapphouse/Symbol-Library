"""Checkpointed handover from the current serial process to four encoders."""
from pathlib import Path
import os,signal,subprocess,sqlite3,json,time,fcntl,datetime,hashlib
H=Path(__file__).resolve().parent
def main():
 own=(H/'handover.lock').open('a');fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert json.loads((H/'parallel_verification.json').read_text())['passed']
 record=json.loads((H/'runner.json').read_text());old=record['pid']
 assert record.get('image_workers')==1,'Handover already performed or unexpected worker configuration'
 cmd=subprocess.check_output(['ps','-p',str(old),'-o','command='],text=True).strip()
 assert str(H/'pipeline.py') in cmd and os.getpgid(old)==old,(old,cmd)
 with sqlite3.connect('file:'+str(H/'delivery.sqlite')+'?mode=ro',uri=True) as db:
  before=dict(db.execute('select status,count(*) from conversions group by status'))
  assert not any(k not in ('complete','pending','ready','published') for k in before),before
 # Journal updates and filesystem publication are already interruption-safe.
 # Stop this dedicated process group, including its in-memory encoder child.
 os.killpg(old,signal.SIGTERM)
 lock=(H/'worker.lock').open('a')
 for attempt in range(100):
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:time.sleep(.1)
 else:raise RuntimeError('Previous writer did not release its lock; no second writer started')
 with sqlite3.connect('file:'+str(H/'delivery.sqlite')+'?mode=ro',uri=True) as db:
  checkpoint=dict(db.execute('select status,count(*) from conversions group by status'))
  assert checkpoint.get('complete',0)>=before.get('complete',0)
 fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',PICOM_Q80_WORKERS='4')
 with (H/'run.log').open('a') as log:
  log.write('\nFOUR-ENCODER HANDOVER '+datetime.datetime.now().astimezone().isoformat()+'\n');log.flush()
  p=subprocess.Popen(['/usr/bin/nice','-n','10','/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',str(H/'pipeline.py')],cwd=H.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 now=datetime.datetime.now().astimezone().isoformat()
 update={'pid':p.pid,'started_at':now,'command':str(H/'pipeline.py'),'stages':[12,5],'priority':'nice 10','image_workers':4,'publisher_workers':1,'licence_workers':1,'detached':True,'log':str(H/'run.log'),'script_sha256':hashlib.sha256((H/'pipeline.py').read_bytes()).hexdigest(),'previous_runner':record,'handover_counts':checkpoint}
 (H/'runner.json').write_text(json.dumps(update,indent=2))
 (H/'parallel_transition.json').write_text(json.dumps({'at':now,'old_pid':old,'new_pid':p.pid,'before_counts':before,'checkpoint_counts':checkpoint,'encoders':4,'single_publisher':True,'user_authorisation':'Run parallel conversions on more than one core, as previously','compression_settings_and_checks':'Unchanged','failure_recording_fix':'Use SQL parameter for error status; double-quoted error otherwise resolved to the error column'},indent=2))
 print('Parallel worker started',p.pid,'from checkpoint',checkpoint,flush=True)
if __name__=='__main__':main()
