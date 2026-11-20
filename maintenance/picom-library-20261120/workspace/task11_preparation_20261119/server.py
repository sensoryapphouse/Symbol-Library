"""Local naming sheet. Reads whitelisted samples; saves choices, never renames images."""
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import json,datetime,unicodedata,os,sys
H=Path(__file__).resolve().parent
CAT=json.loads((H/'catalog.json').read_text())
STYLES=[r['style'] for r in CAT]
CHOICES=H/'naming_choices.json'
def now():return datetime.datetime.now().astimezone().isoformat()
def atomic(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def state():
    return json.loads(CHOICES.read_text()) if CHOICES.exists() else {'draft':dict(zip(STYLES,STYLES)),'confirmed':None,'confirmed_at':None}
def validate(names):
    if not isinstance(names,dict) or set(names)!=set(STYLES):raise ValueError('All 20 current styles must be included.')
    cleaned={};seen={}
    for old,new in names.items():
        if not isinstance(new,str):raise ValueError('Each name must be text.')
        new=unicodedata.normalize('NFC',new.strip())
        if not new or new.startswith('.') or any(ch in new for ch in '/\\:') or any(ord(ch)<32 for ch in new):raise ValueError(f'Choose a valid folder name for {old}; no slashes, colons or hidden names.')
        if len(new.encode('utf-8'))>240:raise ValueError(f'The name for {old} is too long.')
        key=unicodedata.normalize('NFD',new).casefold()
        if key in seen:raise ValueError(f'“{new}” is used twice ({seen[key]} and {old}). Each style needs a different name.')
        seen[key]=old;cleaned[old]=new
    return cleaned
class Handler(BaseHTTPRequestHandler):
    def send(self,code,data,mime='application/json'):
        if isinstance(data,(dict,list)):data=json.dumps(data).encode()
        elif isinstance(data,str):data=data.encode()
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(data)
    def do_GET(self):
        p=self.path.split('?',1)[0]
        if p=='/api/state':return self.send(200,{'catalog':[{k:v for k,v in r.items() if k!='sample'} for r in CAT],**state()})
        if p.startswith('/sample/'):
            ident=p.split('/')[-1];r=next((r for r in CAT if r['id']==ident),None)
            if not r:return self.send(404,{'error':'Unknown sample'})
            path=Path(r['sample']);return self.send(200,path.read_bytes(),'image/svg+xml' if path.suffix=='.svg' else 'image/webp')
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if p in files:
            file,mime=files[p];return self.send(200,(H/file).read_bytes(),mime)
        return self.send(404,{'error':'Not found'})
    def do_POST(self):
        if self.headers.get('Origin')!=self.server.origin:return self.send(403,{'error':'Save from the local naming sheet.'})
        if self.path not in ('/api/draft','/api/confirm','/api/validate'):return self.send(404,{'error':'Not found'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<20000:raise ValueError('Invalid request size')
            body=json.loads(self.rfile.read(n));names=body.get('names')
            if self.path=='/api/validate':return self.send(200,{'names':validate(names)})
            if not isinstance(names,dict) or set(names)!=set(STYLES) or not all(isinstance(v,str) and len(v)<1000 for v in names.values()):raise ValueError('All styles require a text name.')
            s=state();s['draft']=names;s['updated_at']=now()
            if self.path=='/api/confirm':
                names=validate(names);s.update(draft=names,confirmed=names,confirmed_at=now())
            elif s.get('confirmed')!=names:s.update(confirmed=None,confirmed_at=None)
            atomic(CHOICES,s)
            d=json.loads((H/'decision.json').read_text());d['updated_at']=now();d['choices_file']=str(CHOICES)
            if s.get('confirmed'):
                d.update(state='names_agreed_waiting_for_task10',mapping={old:new for old,new in names.items() if old!=new},all_names=names,names_confirmed_at=s['confirmed_at'],automation_status='Names confirmed for Task 11 after Task 10 fully completes. No renaming performed by this sheet.')
            else:d.update(state='draft_names_not_confirmed',mapping={},automation_status='Draft editing; wait for Save names for Task 11 before applying names.')
            d['timing_instruction']='User confirmed: renaming after current run, to avoid confusion; wait for final checks and no active writer.'
            atomic(H/'decision.json',d)
            self.send(200,s)
        except (ValueError,TypeError,json.JSONDecodeError) as e:self.send(400,{'error':str(e)})
    def log_message(self,fmt,*args):
        if args and str(args[1]) not in ('200','304'):super().log_message(fmt,*args)
if __name__=='__main__':
    server=HTTPServer(('127.0.0.1',0),Handler);server.origin=f'http://127.0.0.1:{server.server_port}'
    atomic(H/'server_state.json',{'pid':os.getpid(),'url':server.origin+'/', 'started_at':now()})
    print(server.origin+'/',flush=True);server.serve_forever()
