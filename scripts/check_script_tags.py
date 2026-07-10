#!/usr/bin/env python3
import os
root='templates/reservations'
errors=[]
for dirpath,dirs,files in os.walk(root):
    for f in files:
        if not f.endswith('.html'): continue
        p=os.path.join(dirpath,f)
        with open(p,'r',encoding='utf-8') as fh:
            s=fh.read()
        open_tags = s.count('<script')
        close_tags = s.count('</script>')
        if open_tags != close_tags:
            errors.append((p, open_tags, close_tags))

if not errors:
    print('All reservation templates have matching <script> tags')
else:
    print('Mismatched script tags found:')
    for p,o,c in errors:
        print(p, 'open=',o,'close=',c)
