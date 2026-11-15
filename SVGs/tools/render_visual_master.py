#!/usr/bin/env python3
"""Compile a tagged native SVG into a profile-specific native SVG.
No drawing geometry is generated; data-* paint declarations drive presentation.
"""
from pathlib import Path
from svg_notice import ensure_notice
import argparse,hashlib,json,xml.etree.ElementTree as ET
PAINT=('fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','fill-opacity','stroke-opacity')
ET.register_namespace('','http://www.w3.org/2000/svg')
def compile_svg(master,profile,dest):
 master,profile,dest=map(Path,(master,profile,dest));spec=json.loads(profile.read_text());prefix=spec['paint_prefix'];rt=ET.parse(master).getroot()
 if prefix not in rt.get('data-available-palettes','hc paper screen').split():raise ValueError('Profile unavailable on this geometry variant')
 for el in rt.iter():
  for key in PAINT:
   value=el.get(f'data-{prefix}-{key}')
   if value is not None:el.set(key,value)
 rt.set('data-profile',spec['profile_id']);rt.set('data-collection','visual-export');rt.set('data-master-sha256',hashlib.sha256(master.read_bytes()).hexdigest());rt.set('data-profile-sha256',hashlib.sha256(profile.read_bytes()).hexdigest())
 ensure_notice(rt)
 dest.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(rt).write(dest,encoding='utf-8',xml_declaration=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('master');p.add_argument('profile');p.add_argument('output');a=p.parse_args();compile_svg(a.master,a.profile,a.output)
