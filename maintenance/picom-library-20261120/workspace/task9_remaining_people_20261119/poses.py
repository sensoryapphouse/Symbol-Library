from pathlib import Path
import json,base64,io,numpy as np
from PIL import Image
from scipy import ndimage as ndi
from raster_rig import el,group
from anchors import D
LIB=Path('/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/Library')
FILES={'fast':'Grammar & Language/Verbs/run.webp','slow':'People & Relationships/People - Verbs and Actions/walk.webp','strong':'07 Opposites/strong.webp','weak':'07 Opposites/weak.webp'}
BNECK={'Basic':(200,199),'Classic flat TV cartoon':(185,177),'Clay plasticine':(208,199),'Doll':(184,187),'Friendly aliens':(211,240),'Monkey':(196,209),'Monster':(216,214),'Robot':(199,216),'Soccer player':(214,216),'Teddy bear':(216,216),'Wizard':(235,235),'Wood':(210,205)}
BOX={'fast':(170,0,390,235),'slow':(160,0,365,215),'strong':(174,0,340,190),'weak':(130,0,330,235)}
OV={
('Basic','fast'):(205,0,380,239),('Basic','slow'):(170,0,370,214),('Basic','strong'):(174,0,342,196),('Basic','weak'):(160,0,330,228),
('Doll','strong'):(170,0,350,222),('Doll','slow'):(170,0,365,219),
('Friendly aliens','strong'):(180,0,339,218),('Friendly aliens','weak'):(140,0,315,253),
('Monkey','fast'):(202,0,397,228),('Monkey','slow'):(168,0,375,227),('Monkey','strong'):(177,0,343,218),('Monkey','weak'):(130,0,325,241),
('Monster','fast'):(185,0,401,243),('Monster','slow'):(180,0,391,229),('Monster','strong'):(180,0,350,220),('Monster','weak'):(130,0,338,244),
('Robot','fast'):(185,0,393,220),('Robot','slow'):(168,0,366,204),('Robot','strong'):(181,0,337,204),('Robot','weak'):(158,0,344,256),
('Teddy bear','fast'):(191,0,390,247),('Teddy bear','slow'):(175,0,373,217),('Teddy bear','strong'):(185,0,337,210),('Teddy bear','weak'):(143,0,327,248),
('Wizard','fast'):(190,0,390,256),('Wizard','slow'):(162,0,366,243),('Wizard','strong'):(170,0,340,239),('Wizard','weak'):(130,0,331,275),
('Wood','fast'):(180,0,385,245),('Wood','slow'):(173,0,364,219),('Wood','strong'):(176,0,339,222),('Wood','weak'):(145,0,330,239)}
def make(base,pose,prefix):
 style=base['style'];gender=base['gender'];p=LIB/style/(('People & Relationships/People - Roles and Relationships/old '+('man' if gender=='M' else 'woman')+'.webp') if pose=='old' else FILES[pose]);im=Image.open(p).convert('RGBA');a=np.array(im);yy,xx=np.indices((512,512));defs=el('defs')
 def embed(path,id):defs.append(el('image',{'id':id,'width':512,'height':512,'href':'data:image/webp;base64,'+base64.b64encode(Path(path).read_bytes()).decode()}))
 def use(id,mask=None):return el('use',{'href':'#'+id,**({'mask':'url(#'+mask+')'} if mask else {})})
 def mask(ar,id):
  buf=io.BytesIO();Image.fromarray(ar.astype('uint8')*255).save(buf,format='PNG');m=el('mask',{'id':id,'maskUnits':'userSpaceOnUse','x':0,'y':0,'width':512,'height':512,'style':'mask-type:luminance'});m.append(el('image',{'width':512,'height':512,'href':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}));defs.append(m)
 embed(p,prefix+'-native');body=group();native='F' if style in ['Classic flat TV cartoon','Clay plasticine','Doll'] else 'M'
 if style=='Doll' and pose=='fast':native='M'
 if pose=='old' or gender==native:body.append(use(prefix+'-native'))
 else:
  xl,yt,xr,yb=OV.get((style,pose),BOX[pose]);roi=(xx>=xl)&(xx<xr)&(yy>=yt)&(yy<yb);support=roi&(a[:,:,3]>32);lab,n=ndi.label(support);areas=np.bincount(lab.ravel());areas[0]=0;head=lab==areas.argmax();head=ndi.binary_dilation(head,iterations=2)&roi;mask(~head,prefix+'-body-mask');body.append(use(prefix+'-native',prefix+'-body-mask'));pts=np.where(head&(a[:,:,3]>32));tb=(pts[1].min(),pts[0].min(),pts[1].max()+1,pts[0].max()+1)
  bn=BNECK[style][0 if gender=='M' else 1];ba=np.array(Image.open(base['path']).convert('RGBA'));bmask=yy<bn;mask(bmask,prefix+'-head-mask');embed(base['path'],prefix+'-head');pts=np.where(bmask&(ba[:,:,3]>32));bb=(pts[1].min(),pts[0].min(),pts[1].max()+1,pts[0].max()+1);s=(tb[3]-tb[1])/(bn-bb[1]);cx=(tb[0]+tb[2])/2;bcx=D[(style,gender)]['cx'];tx=cx-s*bcx;ty=tb[3]-s*bn;body.append(group([use(prefix+'-head',prefix+'-head-mask')],f'matrix({s} 0 0 {s} {tx} {ty})'))
 return defs,body,{'path':str(p),'native_gender':native,'gender':gender,'pose':pose,'bbox':im.getchannel('A').getbbox()}
