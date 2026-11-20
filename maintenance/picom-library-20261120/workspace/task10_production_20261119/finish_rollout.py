"""Continue the same queued job after its current plural phase, with one image worker."""
import fcntl,json,os,sys
from pathlib import Path
H=Path(__file__).resolve().parent
# The waiting process performs no image work. The shared lock serialises phases.
with (H/'worker.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    progress=json.loads((H/'progress.json').read_text())
    if progress['state']=='stopped_error':
        raise RuntimeError('Earlier phase stopped with an error; do not silently retry')
import run
sys.argv=[str(H/'run.py'),'all']
run.main()
