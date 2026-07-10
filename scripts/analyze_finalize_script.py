import re
p='templates/reservations/partials/_finalize_delivery_modal.html'
s=open(p,'r',encoding='utf-8').read()
scripts=re.findall(r'<script[^>]*>(.*?)</script>', s, flags=re.S)
if not scripts:
    print('No scripts')
    raise SystemExit(0)
code=scripts[0]
print('Length:', len(code))
print('\n---TAIL 1000 chars---')
print(code[-1000:])
# Remove Django tags
stripped=re.sub(r"\{\%.*?\%\}|\{\{.*?\}\}", '', code, flags=re.S)
print('\n---STRIPPED TAIL 1000 chars---')
print(stripped[-1000:])
print('\nCounts:')
print('braces', stripped.count('{'), stripped.count('}'), 'diff', stripped.count('{')-stripped.count('}'))
print('paren', stripped.count('('), stripped.count(')'), 'diff', stripped.count('(')-stripped.count(')'))
print('brackets', stripped.count('['), stripped.count(']'), 'diff', stripped.count('[')-stripped.count(']'))
# show unmatched context: find position of last unmatched '{' or '('

def find_last_unmatched(s, open_ch, close_ch):
    depth=0
    last_unmatched=-1
    for i,ch in enumerate(s):
        if ch==open_ch:
            depth+=1
            last_unmatched=i
        elif ch==close_ch:
            if depth>0:
                depth-=1
            else:
                # extra close
                pass
    return (depth,last_unmatched)

bdepth, bpos = find_last_unmatched(stripped,'{','}')
pdepth, ppos = find_last_unmatched(stripped,'(',')')
print('\nlast unmatched { depth,pos:', bdepth, bpos)
print('last unmatched ( depth,pos:', pdepth, ppos)
if bpos!=-1:
    print('\ncontext around last unmatched {:\n', stripped[max(0,bpos-120):bpos+120])
if ppos!=-1:
    print('\ncontext around last unmatched (:\n', stripped[max(0,ppos-120):ppos+120])
