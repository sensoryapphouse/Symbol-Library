from pathlib import Path
import json,copy,hashlib,collections,re,io,subprocess,html
import xml.etree.ElementTree as E
from PIL import Image,ImageDraw,ImageFont
H=Path(__file__).resolve().parent;P=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/People');M=json.loads((H/'measurements.json').read_text());S='http://www.w3.org/2000/svg';E.register_namespace('',S)
CASES=[('cleaner','M','Dirt and odour marks on the faded figure; sparkles on the selected clean figure.'),('cleanest','F','Female figures, downward selector and superlative star; dirt and sparkles retained.'),('taller','M','Original height contrast and ground alignment retained.'),('wetter','F','Female figures, water drops and puddle; sun, crossed-out drop and dry ground on the comparison figure.')]
checks={};rows=[]
def source(p):checks[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return E.parse(p).getroot()
def prop_counts(root):
 c=collections.Counter()
 def walk(e,person=False):
  tag=e.tag.rsplit('}',1)[-1]
  if tag in ['defs','metadata','title','desc'] or e.get('data-preview-full-figure'):return
  if person and e.get('data-part'):return
  if tag in ['path','ellipse','circle','rect','polygon','polyline','line']:c[(tag,json.dumps(dict(e.attrib),sort_keys=True))]+=1
  for ch in e:walk(ch,person or bool(e.get('data-comparative-person')))
 walk(root);return c
for style in ['3D animated cartoon','Kawaii']:
 for concept,gender,note in CASES:
  src=P/style/'Comparatives'/(concept+(' (F)' if gender=='F' else '')+'.svg');base=P/style/'Pronouns'/('he.svg' if gender=='M' else 'she.svg');root=source(src);oldprops=prop_counts(root);broot=source(base);core=next(e for e in broot.iter() if e.get('data-core-figure'));metrics=M['bases'][style][gender];full=metrics['full'];bs=metrics['shirt'];bt=metrics['trousers'];people=[e for e in root.iter() if e.get('data-comparative-person')];changes=[]
  for i,g in enumerate(people):
   old=M['comparatives'][style][concept][i];body=old['body'];scale=body['h']/full['h'];tx=body['x']+body['w']/2-scale*(full['x']+full['w']/2);ty=body['y']+body['h']-scale*(full['y']+full['h']);new=copy.deepcopy(core);new.set('transform',f'matrix({scale:.9f} 0 0 {scale:.9f} {tx:.9f} {ty:.9f})');new.set('data-preview-full-figure','1')
   head=next(c for c in g if c.get('data-part')=='head');new.set('id',head.get('id',f'h{i+1}'));new.set('data-fig',head.get('data-fig',''));ids={e.get('id'):f'preview{i+1}-'+e.get('id') for e in new.iter() if e.get('id') and e is not new}
   for e in new.iter():
    if e is not new and e.get('id'):e.set('id',ids[e.get('id')])
    for k,v in list(e.attrib.items()):
     for oldid,newid in ids.items():v=v.replace('url(#'+oldid+')','url(#'+newid+')');v=newid if k.endswith('href') and v=='#'+oldid else v
     e.set(k,v)
   props=[e for e in list(g) if not e.get('data-part')]
   for ch in list(g):g.remove(ch)
   g.append(new)
   moved=[]
   for e in props:
    # Transfer dirt onto the corresponding part of the complete figure. Preserve the actual dirt shapes.
    if e.tag==f'{{{S}}}ellipse' and e.get('fill')=='#7a4a24':
     x=float(e.get('cx'));y=float(e.get('cy'));top=old['top'];leg=y>top['y']+top['h']
     if leg:
      targetx=tx+scale*(bt['x']+bt['w']*.35);targety=ty+scale*(bt['y']+bt['h']*.28)
     else:
      nx=max(.2,min(.8,(x-top['x'])/top['w']));ny=max(.18,min(.8,(y-top['y'])/top['h']));central=.75 if style=='3D animated cartoon' and gender=='F' else .58
      targetx=tx+scale*(bs['x']+bs['w']*(.5+(nx-.5)*central));targety=ty+scale*(bs['y']+bs['h']*ny)
     factor=.78;wrapper=E.Element(f'{{{S}}}g',{'data-preserved-prop':'dirt','transform':f'translate({targetx:.6f} {targety:.6f}) scale({factor}) translate({-x} {-y})'});wrapper.append(e);g.append(wrapper);moved.append('dirt repositioned onto shirt/trousers')
    elif e.get('stroke')=='#7a8b53':
     right=tx+scale*(full['x']+full['w']);dx=max(0,right+12-322);wrapper=E.Element(f'{{{S}}}g',{'data-preserved-prop':'odour','transform':f'translate({dx:.6f} 0)'});wrapper.append(e);g.append(wrapper);moved.append('odour marks beside wider full head')
    elif concept=='wetter' and i==1 and ((e.tag==f'{{{S}}}path' and e.get('fill')=='#7ec8f0') or (e.tag==f'{{{S}}}line' and e.get('x1')=='120' and e.get('y1')=='132')):
     wrapper=E.Element(f'{{{S}}}g',{'data-preserved-prop':'crossed-out-water-drop','transform':'translate(0 -65)'});wrapper.append(e);g.append(wrapper);moved.append('crossed-out water drop raised clear of wider head')
    else:g.append(e)
   changes.append({'person':i+1,'scale':scale,'translation':[tx,ty],'original_bbox':body,'new_full_bbox':[tx+scale*full['x'],ty+scale*full['y'],scale*full['w'],scale*full['h']],'prop_adjustments':sorted(set(moved))})
  root.set('data-review-status','preview-only-not-published');root.set('data-substitution','complete-existing-style-figure');root.set('data-preview-date','2026-11-19');after=prop_counts(root);missing=oldprops-after;extra=after-oldprops;assert not missing and not extra,(style,concept,missing,extra)
  ids=[e.get('id') for e in root.iter() if e.get('id')];assert len(ids)==len(set(ids))
  slug=('3d' if style.startswith('3D') else 'kawaii')+'_'+concept+'_'+gender.lower();out=H/(slug+'.svg');E.ElementTree(root).write(out,encoding='utf-8',xml_declaration=True)
  rows.append({'id':slug,'style':style,'concept':concept,'gender':gender,'note':note,'source':str(src),'base':str(base),'output':str(out),'people_replaced':len(people),'annotation_primitives':sum(oldprops.values()),'missing_annotation_primitives':0,'extra_annotation_primitives':0,'changes':changes})
(H/'previews.json').write_text(json.dumps(rows,indent=2));(H/'source_hashes.json').write_text(json.dumps(checks,indent=2));assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in checks.items())
# Compact display-only sheets; output SVGs are the review deliverables.
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',12)
def render(p):return Image.open(io.BytesIO(subprocess.check_output(['/opt/homebrew/bin/rsvg-convert','-w','512','-h','512',str(p)]))).convert('RGBA')
for style in ['3D animated cartoon','Kawaii']:
 rr=[r for r in rows if r['style']==style];sheet=Image.new('RGB',(1020,80+4*335),'white');d=ImageDraw.Draw(sheet);d.text((12,10),style+' — full-figure preview only',font=font,fill='black');d.text((190,42),'BEFORE — existing comparative',font=small,fill='black');d.text((600,42),'PREVIEW — complete figures',font=small,fill='black')
 for i,r in enumerate(rr):
  y=80+i*335;d.text((5,y+12),r['concept'],font=font,fill='black');d.text((5,y+37),r['gender'],font=small,fill='black')
  for j,key in enumerate(['source','output']):
   im=render(r[key]);im.thumbnail((315,315));x=185+j*415;sheet.paste('#e5edf5',(x,y,x+315,y+315));sheet.paste(im,(x,y),im)
 sheet.save(H/('3d_preview.jpg' if style.startswith('3D') else 'kawaii_preview.jpg'),quality=93)
print('Created',len(rows),'separate SVG previews; semantic annotation checks passed for all; originals unchanged.')
