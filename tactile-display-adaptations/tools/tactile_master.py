#!/usr/bin/env python3
"""Export a profile from a self-contained tagged tactile SVG master.
Only the master is read. Historical sources and manifests are not export inputs.
"""
import argparse,copy,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from svg_notice import ensure_notice
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def local(tag):return tag.split('}')[-1]
def export_tree(master,profile):
 root=ET.parse(master).getroot()
 if root.get('data-master-schema')!='tactile-shared-v1':raise ValueError('Unsupported master schema')
 ids={}
 for n in root.iter():
  if n.get('id'):
   if n.get('id') in ids:raise ValueError('Duplicate ID')
   ids[n.get('id')]=n
  if local(n.tag) in {'image','script','foreignObject','style','text','filter'}:raise ValueError('Unsupported master content')
  for k,v in n.attrib.items():
   if k.startswith('on') or 'url(' in v:raise ValueError('Executable/external content')
   if local(k) in {'href','src'} and not (local(n.tag)=='use' and v.startswith('#') and v[1:] in {e.get('id') for e in root.iter()}):raise ValueError('Nonlocal reference')
 layers=[n for n in root if n.get('data-output-profile')==profile]
 if len(layers)!=1:raise ValueError('Profile not authored in this master: '+profile)
 layer=layers[0];out=ET.Element('{'+NS+'}svg',json.loads(layer.get('data-export-root')))
 def expand(n):
  if local(n.tag)=='use':
   target=ids[n.get('href')[1:]]
   if local(target.tag) not in {'path','rect','circle','ellipse','polygon','polyline','line'}:raise ValueError('Reference must resolve directly to geometry')
   result=copy.deepcopy(target);result.attrib.pop('id',None);result.attrib.pop('data-part',None)
   for k,v in n.attrib.items():
    if k not in {'href','id','data-export-id','data-shared-geometry'}:result.set(k,v)
   result.set('id',n.get('data-export-id'))
  else:
   result=ET.Element(n.tag,{k:v for k,v in n.attrib.items() if k not in {'id','data-export-id','data-geometry-exception','data-exception-reason'}})
   if n.get('data-export-id'):result.set('id',n.get('data-export-id'))
   elif n.get('id'):result.set('id',n.get('id'))
   for child in n:result.append(expand(child))
  return result
 for n in layer:out.append(expand(n))
 ensure_notice(out)
 return ET.ElementTree(out)
def write_export(master,profile,destination):
 p=Path(destination);p.parent.mkdir(parents=True,exist_ok=True);export_tree(master,profile).write(p,encoding='utf-8',xml_declaration=True)
def signature(node):
 attrs=dict(node.attrib)
 if 'd' in attrs:attrs['d']=' '.join(re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?',attrs['d']))
 return (local(node.tag),sorted(attrs.items()),[signature(c) for c in node])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('master');p.add_argument('--profile',required=True);p.add_argument('--output',required=True);a=p.parse_args();write_export(a.master,a.profile,a.output)
