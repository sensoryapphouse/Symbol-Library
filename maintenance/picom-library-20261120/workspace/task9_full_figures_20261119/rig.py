from pathlib import Path
import copy,xml.etree.ElementTree as E,json,math
S='http://www.w3.org/2000/svg';E.register_namespace('',S)
def el(tag,attrs=None):return E.Element('{'+S+'}'+tag,attrs or {})
def clone(e):return copy.deepcopy(e)
def ident(e):return e.get('id','').replace('person1-','')
def find(root,id):return next(e for e in root.iter() if e.get('id')=='person1-'+id and not e.tag.endswith('Gradient'))
def rotate(deg,p):return f'rotate({deg} {p[0]} {p[1]})'
def stripids(root):
 for e in root.iter():e.attrib.pop('id',None)
 return root
def make(base,style,gender,pose):
 src=next(e for e in E.parse(base).getroot().iter() if e.get('data-core-figure'));src=clone(src);src.attrib.pop('transform',None)
 if pose=='stand':return src,None
 root=el('g',{'data-rig-pose':pose});defs=el('defs');root.append(defs)
 for e in src.iter():
  if e.tag.endswith('defs'):
   for c in e:defs.append(clone(c))
 num=0
 def clipped(nodes,points):
  nonlocal num
  num+=1;cid='rigclip'+str(num);cp=el('clipPath',{'id':cid,'clipPathUnits':'userSpaceOnUse'});cp.append(el('polygon',{'points':points}));defs.append(cp)
  g=el('g',{'clip-path':f'url(#{cid})'})
  for n in nodes:g.append(stripids(clone(n)))
  return g
 def group(nodes,transform=''):
  g=el('g',{'transform':transform} if transform else {})
  for n in nodes:g.append(n)
  return g
 def c(id):return clone(find(src,id))
 # The full head and facial detail stay native. Only body parts are rearticulated.
 items=list(next(e for e in src.iter() if any(ident(c)=='hair-back' for c in e)))
 if style=='3D animated cartoon' and gender=='M':
  begin=next(i for i,e in enumerate(items) if ident(e)=='hair-back');headitems=items[begin:]
 elif style=='3D animated cartoon':headitems=[items[i] for i in [0,16,17]]
 elif gender=='M':headitems=[items[0]]+items[6:]
 else:headitems=items[:2]+items[7:]
 back=group([clone(e) for e in headitems if ident(e)=='hair-back'])
 head=group([clone(e) for e in headitems if ident(e)!='hair-back'])
 if style=='3D animated cartoon' and gender=='M':
  cx,hip=94,254;mid=94;lp=(61,254);rp=(120,254);ls=(46,165);rs=(141,165)
  shirt=c('shirt');hands=c('hands');legnodes=[c('boots'),c('trousers')]
  torso=clipped([shirt],'40,140 146,140 140,183 147,264 40,264 48,183')
  left=clipped([hands,shirt],'-100,135 41,135 50,183 42,340 -100,340')
  right=clipped([hands,shirt],'145,135 300,135 300,340 145,340 138,183')
  neck=group([c('neck'),c('neck-outline')]);grip=(172,270)
 elif style=='3D animated cartoon':
  cx,hip=82,251;mid=81;lp=(54,251);rp=(105,251);ls=(39,163);rs=(115,164)
  torso=group([clone(items[i]) for i in [4,5,6]]);left=group([clone(items[i]) for i in [7,8,9,10]]);right=group([clone(items[i]) for i in [11,12,13,14,15]]);legnodes=[c('shoes'),c('trousers')];neck=c('neck');grip=(58,265)
 else:
  female=gender=='F';cx,hip=(111,284) if female else (101,292);mid=112 if female else 101;lp=(83,hip) if female else (75,hip);rp=(138,hip) if female else (126,hip);ls=(67,203) if female else (59,211);rs=(154,203) if female else (143,211)
  shirt=c('shirt');legnodes=[c('shoes'),clone(items[3 if female else 2]),c('trousers')];neck=c('neck')
  if female:
   torso=clipped([shirt],'64,182 158,182 154,220 157,295 57,295 60,220')
   left=clipped([c('hand-left'),shirt],'-100,180 65,180 62,220 57,340 -100,340');right=clipped([c('hand-right'),shirt],'157,180 350,180 350,340 155,340 152,220');grip=(177,296)
  else:
   torso=clipped([shirt],'58,190 144,190 143,229 148,302 52,302 57,229')
   left=clipped([c('hand-left'),shirt],'-100,185 59,185 59,229 52,340 -100,340');right=clipped([c('hand-right'),shirt],'143,185 350,185 350,340 147,340 141,229');grip=(168,298)
 legs=[clipped(legnodes,f'-100,{hip-15} {mid+1},{hip-15} {mid+1},500 -100,500'),clipped(legnodes,f'{mid-1},{hip-15} 400,{hip-15} 400,500 {mid-1},500')]
 a,b,la,ra,lean=0,0,0,0,0
 if pose=='fast':a,b,la,ra,lean=30,-34,-55,-30,9
 elif pose=='slow':a,b,la,ra,lean=-12,12,8,-8,0
 elif pose=='strong':a,b,la,ra,lean=8,-8,8,-8,0
 elif pose=='weak':a,b,la,ra,lean=0,0,-9,9,12
 elif pose=='old':a,b,la,ra,lean=0,0,0,-10,0
 if style=='3D animated cartoon' and gender=='F':la+=25;ra-=35
 if pose=='weak':
  left=group([left],f'translate({ls[0]} {ls[1]}) scale(1 1.26) translate({-ls[0]} {-ls[1]})');right=group([right],f'translate({rs[0]} {rs[1]}) scale(1 1.26) translate({-rs[0]} {-rs[1]})');head=group([head],'translate(0 7)');back=group([back],'translate(0 7)')
 root.append(group([legs[0]],rotate(a,lp)));root.append(group([legs[1]],rotate(b,rp)))
 upper=group([],rotate(lean,(cx,hip)))
 # Back arm, torso, front arm and neck retain a sensible joint overlap.
 upper.append(back);upper.append(group([right],rotate(ra,rs)));upper.append(torso);upper.append(group([left],rotate(la,ls)));upper.append(neck);upper.append(head);root.append(upper)
 if pose=='old':
  for e in defs.iter():
   if any(s in e.get('id','').lower() for s in ['hair','lock']):
    for q in e.iter():
     co=q.get('stop-color')
     if co and co.startswith('#') and len(co)==7:
      v=int(145+sum(int(co[j:j+2],16) for j in (1,3,5))/765*55);q.set('stop-color',f'#{v:02x}{v:02x}{v:02x}')
 def rotpoint(p,ang,pivot):
  x,y=p[0]-pivot[0],p[1]-pivot[1];a=math.radians(ang);return(pivot[0]+x*math.cos(a)-y*math.sin(a),pivot[1]+x*math.sin(a)+y*math.cos(a))
 grip=rotpoint(rotpoint(grip,ra,rs),lean,(cx,hip))
 # Shape ids aren't needed in the rig, but definition ids and references are.
 for e in root.iter():
  if e.tag not in ['{'+S+'}clipPath','{'+S+'}radialGradient','{'+S+'}linearGradient','{'+S+'}filter']:e.attrib.pop('id',None)
 return root,grip
if __name__=='__main__':
 H=Path(__file__).resolve().parent;P=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/People');manifest=[]
 for style in ['3D animated cartoon','Kawaii']:
  for gender in ['M','F']:
   base=P/style/'Pronouns'/('he.svg' if gender=='M' else 'she.svg')
   for pose in ['stand','fast','slow','strong','weak','old']:
    rig,grip=make(base,style,gender,pose);root=el('svg',{'viewBox':'-100 -20 450 520','width':'450','height':'520'});root.append(rig);name=('3d' if style.startswith('3D') else 'kawaii')+'_'+gender.lower()+'_'+pose;out=Path('/private/tmp/task9_full_figures_20261119')/(name+'.svg');E.ElementTree(root).write(out,encoding='utf-8',xml_declaration=True);manifest.append({'style':style,'gender':gender,'pose':pose,'path':str(out),'grip':grip,'name':name})
 (H/'rig_manifest.json').write_text(json.dumps(manifest,indent=2))
