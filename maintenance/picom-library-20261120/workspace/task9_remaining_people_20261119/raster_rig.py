from pathlib import Path
import json,base64,copy,math,io,xml.etree.ElementTree as E
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
from anchors import D
S='http://www.w3.org/2000/svg';X='http://www.w3.org/1999/xlink';E.register_namespace('',S);E.register_namespace('xlink',X)
def el(t,a=None):return E.Element('{'+S+'}'+t,{k:str(v) for k,v in (a or {}).items()})
def group(children=(),transform=None):
 g=el('g',{'transform':transform} if transform else {})
 for c in children:g.append(c)
 return g
def rot(deg,p):return f'rotate({deg} {p[0]} {p[1]})'
def matrixmap(start,end,target):
 # Map the native arm axis to the new shoulder-to-hand axis while retaining its transverse thickness.
 ux,uy=end[0]-start[0],end[1]-start[1];vx,vy=target[0]-start[0],target[1]-start[1];ul=math.hypot(ux,uy);vl=math.hypot(vx,vy);ux/=ul;uy/=ul;vx/=vl;vy/=vl;k=vl/ul
 a=k*vx*ux+vy*uy;b=k*vy*ux-vx*uy;c=k*vx*uy-vy*ux;d=k*vy*uy+vx*ux;e=start[0]-a*start[0]-c*start[1];f=start[1]-b*start[0]-d*start[1]
 return f'matrix({a} {b} {c} {d} {e} {f})'
def make(base,pose='stand',prefix='fig',book=None):
 cfg=D[(base['style'],base['gender'])];defs=el('defs');imageid=prefix+'-image';defs.append(el('image',{'id':imageid,'width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(Path(base['path']).read_bytes()).decode()}))
 def use(extra=None):return el('use',{'href':'#'+imageid,**(extra or {})})
 if pose=='stand':return defs,group([use()]),None,cfg
 lp=[(0,cfg['left_seam'][0][1]),*cfg['left_seam'],(0,cfg['left_seam'][-1][1])];rp=[*cfg['right_seam'],(cfg['right_outer'],cfg['right_seam'][-1][1]),(cfg['right_outer'],cfg['right_seam'][0][1])]
 cx=cfg['cx'];hy=cfg['hip'];lo=cfg['leg_left'];ro=cfg['leg_right'];ae=cfg['arm_end']
 ll=[(0,hy),(cx,hy),(cx,512),(0,512)];rl=[(cx,hy),(512,hy),(512,512),(cx,512)]
 polys={'leftarm':lp,'rightarm':rp,'leftleg':ll,'rightleg':rl}
 def points(pts):return ' '.join(f'{x},{y}' for x,y in pts)
 # Assign every original pixel to exactly one body part before any articulation.
 # This avoids leaving thin static strips of trousers or skirts behind when legs move.
 head_extra=[];tail=[]
 if base['style']=='Doll' and base['gender']=='F':
  head_extra=[[(140,115),(215,115),(209,214),(140,214)],[(300,110),(370,110),(370,220),(305,220)]]
 if base['style']=='Robot' and base['gender']=='F':
  head_extra=[[(298,160),(342,160),(342,220),(299,220)],[(173,160),(208,160),(208,216),(173,216)]]
 if base['style']=='Monkey':
  if base['gender']=='M':tail=[[(316,194),(386,194),(386,328),(327,328),(327,310),(330,290),(327,265),(328,238),(315,235)]]
  else:tail=[[(317,190),(370,190),(370,345),(310,345),(309,318),(317,290)]]
 def shape(pts):
  im=Image.new('L',(512,512));ImageDraw.Draw(im).polygon(pts,fill=255);return np.asarray(im)>0
 la=shape(lp);ra=shape(rp);protected=np.zeros((512,512),dtype=bool)
 for keep in head_extra+tail:protected|=shape(keep)
 rgba=np.array(Image.open(base['path']).convert('RGBA'));hsv=np.array(Image.fromarray(rgba[:,:,:3]).convert('HSV'));h,sat,val=hsv[:,:,0],hsv[:,:,1],hsv[:,:,2];yy,xx=np.indices((512,512));style=base['style']
 garment=np.zeros((512,512),dtype=bool)
 if style in ['Basic','Classic flat TV cartoon','Clay plasticine','Doll','Wood']:
  garment=(h>70)&(h<185)&(sat>55)
 elif style=='Friendly aliens':
  if base['gender']=='M':garment=(rgba[:,:,2]>rgba[:,:,1].astype(float)*1.13)&(h>130)&(h<180)&(yy>cfg['chest'][1]+15)
  else:garment=(h>175)&(h<230)&(sat>60)&(yy>cfg['ls'][1]+25)
 elif style=='Soccer player':garment=(h>130)&(h<190)&(sat>30)&(yy>hy-12)
 elif style=='Wizard':garment=(h>85)&(h<160)&(sat>50)
 garment&=(val>65);garment=ndi.binary_dilation(ndi.binary_opening(garment,iterations=1),iterations=3)
 la&=~(protected|garment);ra&=~(protected|garment)
 def main_arm(mask):
  support=mask&(rgba[:,:,3]>64);opened=ndi.binary_opening(support,iterations=1);lab,n=ndi.label(opened)
  if not n:return mask
  areas=np.bincount(lab.ravel());areas[0]=0;keep=lab==int(areas.argmax());return mask&ndi.binary_dilation(keep,iterations=3)
 la=main_arm(la);ra=main_arm(ra)
 lower=(yy>=hy)&~(la|ra|protected);ll=lower&(xx<cx);rl=lower&(xx>=cx);bodymask=~(la|ra|ll|rl)
 cap=Image.new('L',(512,512));dr=ImageDraw.Draw(cap)
 for sx,sy in [cfg['ls'],cfg['rs']]:dr.ellipse((sx-15,sy-15,sx+15,sy+15),fill=255)
 bodymask|=np.asarray(cap)>0
 masks={'leftarm':la,'rightarm':ra,'leftleg':ll,'rightleg':rl,'body-mask':bodymask}
 for name,arr in masks.items():
  im=Image.fromarray(arr.astype('uint8')*255);buf=io.BytesIO();im.save(buf,format='PNG');m=el('mask',{'id':prefix+'-'+name,'maskUnits':'userSpaceOnUse','x':0,'y':0,'width':512,'height':512,'style':'mask-type:luminance'});m.append(el('image',{'width':512,'height':512,'href':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}));defs.append(m)
 def piece(name,tr=None):return group([use({'mask':'url(#'+prefix+'-'+name+')'})],tr)
 body=use({'mask':'url(#'+prefix+'-body-mask)'})
 lhip=((lo+cx)/2,hy);rhip=((ro+cx)/2,hy)
 if pose=='hold':
  bx,by,bw,bh=book;ly=by+bh*.73;left=piece('leftarm',matrixmap(cfg['ls'],cfg['lh'],(bx+bw*.08,ly)));right=piece('rightarm',matrixmap(cfg['rs'],cfg['rh'],(bx+bw*.92,ly)))
  return defs,group([piece('leftleg'),piece('rightleg'),body]),group([left,right]),cfg
 la,ra,al,ar,lean=0,0,0,0,0
 if pose=='fast':la,ra,al,ar,lean=30,-34,-52,-30,8
 elif pose=='slow':la,ra,al,ar,lean=-10,10,6,-6,0
 elif pose=='strong':la,ra,al,ar,lean=8,-8,8,-8,0
 elif pose=='weak':la,ra,al,ar,lean=0,0,-8,8,10
 elif pose=='old':la,ra,al,ar,lean=0,0,0,-9,0
 left=piece('leftarm',rot(al,cfg['ls']));right=piece('rightarm',rot(ar,cfg['rs']))
 if pose=='weak':
  for obj,p in [(left,cfg['ls']),(right,cfg['rs'])]:obj.set('transform',rot(al if obj is left else ar,p)+f' translate({p[0]} {p[1]}) scale(1 1.12) translate({-p[0]} {-p[1]})')
 upper=group([body,right,left],rot(lean,(cx,hy)))
 return defs,group([piece('leftleg',rot(la,lhip)),piece('rightleg',rot(ra,rhip)),upper]),None,cfg
