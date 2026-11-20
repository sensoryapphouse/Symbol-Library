from pathlib import Path
import os,re,json,sqlite3,collections,sys,hashlib,datetime
import inflect
H=Path(__file__).resolve().parent;PR=Path('/Users/paulblenkhorn/Desktop/picom_review');LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library');PEOPLE=LIB.parent/'People';FLUENT=Path('/Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Fluent Symbols/svgs');sys.path.insert(0,str(PR));import build_tenses as BT
P=inflect.engine();db=sqlite3.connect(H/'queue.sqlite');db.executescript('CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,style TEXT,kind TEXT,concept TEXT,source TEXT,relative_source TEXT,destination TEXT UNIQUE,reference TEXT,status TEXT DEFAULT "pending",source_sha TEXT,output_sha TEXT,scale REAL,note TEXT); CREATE TABLE IF NOT EXISTS inventory_notes(style TEXT,kind TEXT,concept TEXT,reason TEXT,detail TEXT);');assert not db.execute('SELECT count(*) FROM jobs').fetchone()[0], 'Existing queue: do not rebuild'
def norm(s):return re.sub(r'\s+',' ',s.replace('_',' ').replace('-',' ').casefold()).strip()
def pathkey(p):return '/'.join(norm(x) for x in Path(p).with_suffix('').parts)
def index(root):
 d=collections.defaultdict(list)
 for dp,dirs,files in os.walk(root):
  dirs[:]=[x for x in dirs if not x.startswith(('_','.')) and x!='Plurals and tenses']
  for f in files:
   p=Path(dp)/f
   if p.suffix.lower() in ['.svg','.webp']:d[pathkey(p.relative_to(root))].append(p)
 return d
# Resolve approved paths by exact category/subcategory plus normalized stem, never by an ambiguous bare word.
fi=index(FLUENT);verbs=[];notes=[]
F=json.loads((H.parent/'task10_preparation_20261119/existing_fluent_future_paths.json').read_text())
BAD={'don\'t','hugs','idea','ideas','in bed','lotus position','meditation pose','women holding hands','men holding hands','bunny ears','please','forgot','found','won','saw friends','went shopping','went swimming'}
BAD_PATHS={'Animals & Wildlife/Animals/duck','Animals & Wildlife/Animals/fly','Curriculum, Science & Literacy/Periodic Table/lead','Time, Calendar & Seasons/Telling Time/watch','Technology, Tools & Engineering/Tools/pick'}
# Compound phrase heads are exceptions already anticipated by the saved conjugator; explicit extensions preserve meaning.
COMPOUNDS={'bungee jump':'jump','role play':'play','fist bump':'bump','taste test':'test','pan fry':'fry','stir fry':'fry','body surf':'surf','double click':'click','double tap':'tap','left click':'click','right click':'click','long press':'press','screen record':'record','screen share':'share','doom scroll':'scroll','force close':'close','force quit':'quit','copy paste':'paste'}
IRREG_FIX={'rise':'rose','weave':'wove','lead':'led','undo':'undid','override':'overrode','wind':'wound'}
def forms(verb):
 if verb=='lie down':return [('past','lay down'),('cont','lying down'),('future','will lie down')]
 base=verb
 for prefix,last in COMPOUNDS.items():
  if base==prefix or base.startswith(prefix+' '):
   left=prefix[:-(len(last))];tail=base[len(prefix):];return [('past',left+BT.past_of(last)+tail),('cont',left+BT.cont_of(last)+tail),('future','will '+base)]
 head,rest=BT.split_head(base);return [('past',IRREG_FIX.get(head,BT.past_of(head))+rest),('cont',BT.cont_of(head)+rest),('future','will '+base)]
for rel in F:
 p=Path(rel);verb=p.stem[5:];base=p.parent/(verb+'.svg');reason=None
 if verb in BAD or str(base.with_suffix('')) in BAD_PATHS:reason='Not a base action or wrong word sense in saved reference'
 if reason:notes.append(('ALL','tense',verb,reason,str(base)));continue
 matches=fi.get(pathkey(base),[])
 if len(matches)!=1:notes.append(('ALL','tense',verb,'Reference base missing or ambiguous',str(base)));continue
 verbs.append({'word':verb,'path':str(matches[0].relative_to(FLUENT)),'reference':str(matches[0]),'forms':forms(verb)})
# The corrected, durable noun verdicts supersede the smaller historic Fleximbols candidate list.
verdicts=json.loads((PR/'fluent_plural_verdicts.json').read_text());nouns=[]
def plural(word):
 m=re.search(r'^(.*[\s\-_])?([A-Za-z]+)$',word)
 if not m:return None
 pre,last=m.group(1) or '',m.group(2);pl=P.plural(last.lower()) or last.lower()+'s'
 if last.isupper():pl=pl.upper()
 elif last[0].isupper():pl=pl[0].upper()+pl[1:]
 return pre+pl
for r in verdicts['pluralise']:
 pn=plural(r['word'])
 if not r.get('path') or not pn:notes.append(('ALL','plural',r['word'],'Missing approved path or unresolved spelling',str(r)));continue
 nouns.append(dict(r,plural=pn))
styles=sorted(p.name for p in LIB.iterdir() if p.is_dir() and not p.name.startswith(('_','.')))
counts={};misses={}
for st in styles:
 ix=index(LIB/st)
 if st=='Mulberry':
  for k,ps in index(PEOPLE/st).items():
   if k not in ix:ix[k]=ps
 c=collections.Counter();missing=collections.Counter()
 for kind,refs in [('plural',nouns),('tense',verbs)]:
  for r in refs:
   matches=ix.get(pathkey(r['path']),[])
   if not matches:missing[kind]+=1;continue
   if len(matches)!=1:
    notes.append((st,kind,r['word'],'Multiple source formats/variants at exact concept path',json.dumps([str(p) for p in matches])));c['ambiguous']+=1;continue
   src=matches[0];rel=src.relative_to(LIB/st) if src.is_relative_to(LIB/st) else src.relative_to(PEOPLE/st)
   if st=='Mulberry' and src.suffix.lower()!='.svg':raise AssertionError(src)
   fs=[('plural',r['plural'])] if kind=='plural' else r['forms']
   for form,name in fs:
    dest=LIB/st/'Plurals and tenses'/rel.parent/(name+'.svg')
    if dest.exists():notes.append((st,form,r['word'],'Existing derivative needs reuse check',str(dest)));c['existing']+=1;continue
    try:db.execute('INSERT INTO jobs(style,kind,concept,source,relative_source,destination,reference) VALUES(?,?,?,?,?,?,?)',(st,form,r['word'],str(src),str(rel),str(dest),str(FLUENT/r['path'])));c[form]+=1
    except sqlite3.IntegrityError:notes.append((st,form,r['word'],'Destination conflict held',str(dest)));c['conflicts']+=1
 counts[st]=dict(c);misses[st]=dict(missing);db.commit();print(st,dict(c),flush=True)
db.executemany('INSERT INTO inventory_notes VALUES(?,?,?,?,?)',notes);db.commit();total=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
summary={'prepared_at':datetime.datetime.now().astimezone().isoformat(),'styles':styles,'counts':counts,'planned_outputs':total,'reference_nouns':len(nouns),'reference_base_verbs':len(verbs),'notes':len(notes),'missing_reference_concepts_by_style':misses,'scope':'All current 20 Library styles, eligible matched concepts only; Mulberry fills unpublished SVG sources from People, preferring Library corrections.','selection':'Exact category/subcategory plus normalized stem; no bare-word cross-category guessing.','methods':'Original approved smart_shrink_plurals and tense_annotate engines; checked wrappers only; no alternate layout.','output':'Library/<style>/Plurals and tenses/<source-relative categories>/<form>.svg; Q80 later, Mulberry remains SVG.','worker_limit':1}
(H/'inventory.json').write_text(json.dumps(summary,indent=2));(H/'verb_decisions.json').write_text(json.dumps({'eligible':verbs,'excluded':[n for n in notes if n[0]=='ALL' and n[1]=='tense'],'compound_overrides':COMPOUNDS,'irregular_corrections':IRREG_FIX},indent=2));print('TOTAL',total,flush=True)
