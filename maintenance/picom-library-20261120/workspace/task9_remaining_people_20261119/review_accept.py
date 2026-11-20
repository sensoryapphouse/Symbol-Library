from pathlib import Path
import json,sys,datetime
H=Path(__file__).resolve().parent;kind=sys.argv[1];nums=[int(x) for x in sys.argv[2].split(',')];pages=json.loads((H/(kind+'_review_pages.json')).read_text());f=H/'visual_review_log.json';log=json.loads(f.read_text()) if f.exists() else []
for p in pages:
 if p['page'] in nums and not any(x['kind']==kind and x['page']==p['page'] for x in log):log.append(dict(p,kind=kind,status='accepted',reviewed_at=datetime.datetime.now().astimezone().isoformat(),checks=['Every output viewed against reference on same-concept cross-style sheet','Full figure and intended figure count','Arrows, punctuation and object visibility','No new clipping or detached parts']))
f.write_text(json.dumps(log,indent=2));print('Accepted visual pages',kind,nums)
