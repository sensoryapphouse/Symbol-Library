from pathlib import Path
import base64,io,numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
from raster_rig import el,group,S
# Existing whole holding poses; only the held red ball is covered by the preserved book.
# Native gender, neck, ball rectangle. Other-gender heads come from the approved own-style base.
P={
'Basic':('M',194,(197,210,302,312)),
'Classic flat TV cartoon':('F',158,(220,178,291,249)),
'Clay plasticine':('F',169,(216,174,295,253)),
'Doll':('F',183,(216,189,296,273)),
'Friendly aliens':('M',200,(211,211,284,286)),
'Monkey':('M',212,(189,198,281,291)),
'Monster':('M',198,(197,203,312,326)),
'Robot':('M',191,(214,210,292,292)),
'Soccer player':('M',200,(209,219,290,304)),
'Teddy bear':('M',184,(203,187,296,280)),
'Wizard':('M',205,(208,214,290,300)),
'Wood':('M',181,(206,196,301,300))}
NECK={('Friendly aliens','F'):240,('Basic','F'):199,('Classic flat TV cartoon','M'):185,('Clay plasticine','M'):207,('Monkey','F'):209,('Monster','F'):214,('Robot','F'):216,('Soccer player','F'):216,('Teddy bear','F'):216,('Wizard','F'):235,('Wood','F'):205}
def make(base,prefix='held'):
 style=base['style'];gen,neck,ball=P[style];p=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')/style/'Grammar & Language/Verbs/hold.webp';im=Image.open(p).convert('RGBA');rgba=np.array(im);defs=el('defs')
 def embed(path,id):defs.append(el('image',{'id':id,'width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(Path(path).read_bytes()).decode()}))
 embed(p,prefix+'-native')
 def use(id,mask=None):return el('use',{'href':'#'+id,**({'mask':'url(#'+mask+')'} if mask else {})})
 def mask(arr,id):
  buf=io.BytesIO();Image.fromarray(arr.astype('uint8')*255).save(buf,format='PNG');m=el('mask',{'id':id,'maskUnits':'userSpaceOnUse','x':0,'y':0,'width':512,'height':512,'style':'mask-type:luminance'});m.append(el('image',{'width':512,'height':512,'href':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}));defs.append(m)
 body=group();yy,xx=np.indices((512,512))
 if base['gender']==gen:body.append(use(prefix+'-native'))
 else:
  mask((yy>=neck)|((xx>320)&(style=='Monkey')),prefix+'-body');body.append(use(prefix+'-native',prefix+'-body'));embed(base['path'],prefix+'-head');bn=NECK[(style,base['gender'])];mask(yy<bn,prefix+'-head-mask')
  head=Image.fromarray(np.where((yy<neck)[:,:,None],rgba,0).astype('uint8'));tb=head.getchannel('A').getbbox();bi=Image.open(base['path']).convert('RGBA');ar=np.array(bi);bb=Image.fromarray(np.where((yy<bn)[:,:,None],ar,0).astype('uint8')).getchannel('A').getbbox();s=(neck-tb[1])/(bn-bb[1]);cx=(tb[0]+tb[2])/2
  from anchors import D
  bcx=D[(style,base['gender'])]['cx'];tx=cx-s*bcx;ty=neck-s*bn
  body.append(group([use(prefix+'-head',prefix+'-head-mask')],f'matrix({s} 0 0 {s} {tx} {ty})'))
 # Restore original hands in front of the vector book, excluding the ball's red pixels.
 bx,by,br,bb=ball;hsv=np.array(im.convert('RGB').convert('HSV'));red=((hsv[:,:,0]<6)|(hsv[:,:,0]>249))&(hsv[:,:,1]>120);red=red
 roi=(((xx>bx-28)&(xx<bx+25))|((xx>br-25)&(xx<br+28)))&(yy>by+(bb-by)*.25)&(yy<by+(bb-by)*.87)
 h=hsv[:,:,0];sa=hsv[:,:,1];va=hsv[:,:,2]
 if style=='Monster':colour=(h>180)&(h<245)&(sa>45)&(va>45)
 elif style=='Robot':colour=(h>80)&(h<165)&(sa>25)&(va>45)
 elif style=='Friendly aliens':colour=(h>80)&(h<160)&(sa>45)&(va>65)
 else:colour=(h>9)&(h<48)&(sa>35)&(va>65)
 if style=='Monster':roi&=(yy>=220)&(yy<=292)
 if style=='Robot':roi&=(yy>=237)&(yy<=279)
 if style=='Monkey':roi&=(yy>=222)&(yy<=271)
 seed=ndi.binary_closing(roi&colour&(rgba[:,:,3]>32),iterations=3 if style=='Robot' else 1);lab,n=ndi.label(seed);sizes=np.bincount(lab.ravel());sizes[0]=0;keep=np.isin(lab,np.where(sizes>35)[0]);hand=ndi.binary_fill_holes(keep);hand=ndi.binary_dilation(hand,iterations=3 if style=='Robot' else 1)&roi
 mask(hand,prefix+'-hands');hands=group([use(prefix+'-native',prefix+'-hands')])
 return defs,body,hands,dict(path=str(p),ball=ball,bbox=im.getchannel('A').getbbox())
