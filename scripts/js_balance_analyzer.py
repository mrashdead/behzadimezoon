import re
p='templates/reservations/partials/_finalize_delivery_modal.html'
s=open(p,encoding='utf-8').read()
import sys
scripts=re.findall(r'<script[^>]*>(.*?)</script>', s, flags=re.S)
if not scripts:
    print('no scripts'); sys.exit(0)
code=scripts[0]
# state machine to skip strings, comments, template literals
depth_brace=0
depth_paren=0
depth_brack=0
max_depth=0
line_no=1
lines=code.splitlines()
# create char iterator with line numbers
idx=0
state='normal'
stack=[]
line_idx=1
last_positions=[]
for i,ch in enumerate(code):
    # update line count
    if ch=='\n':
        line_idx+=1
    if state=='normal':
        if code.startswith("//",i):
            state='line_comment'
            continue
        if code.startswith('/*',i):
            state='block_comment'
            continue
        if ch=='\"':
            state='double_quote'
            continue
        if ch=="'":
            state='single_quote'
            continue
        if ch=='`':
            state='template'
            continue
        if ch=='{':
            depth_brace+=1
            last_positions.append(('brace',depth_brace,line_idx,i))
        elif ch=='}':
            depth_brace-=1
        elif ch=='(':
            depth_paren+=1
            last_positions.append(('paren',depth_paren,line_idx,i))
        elif ch==')':
            depth_paren-=1
        elif ch=='[':
            depth_brack+=1
            last_positions.append(('brack',depth_brack,line_idx,i))
        elif ch==']':
            depth_brack-=1
    elif state=='line_comment':
        if ch=='\n':
            state='normal'
    elif state=='block_comment':
        if code.startswith('*/',i):
            state='normal'
            # skip next char
    elif state=='double_quote':
        if ch=='\\':
            # skip next
            pass
        elif ch=='\"':
            state='normal'
    elif state=='single_quote':
        if ch=='\\':
            pass
        elif ch=="'":
            state='normal'
    elif state=='template':
        if ch=='\\':
            pass
        elif ch=='$' and i+1<len(code) and code[i+1]=='{':
            # enter expression inside template
            stack.append(state)
            state='normal'
            # will return to template when matching '}' encountered? this is tricky
        elif ch=='`':
            state='normal'

# After scan, report depths
print('final depths: brace', depth_brace, 'paren', depth_paren, 'brack', depth_brack)
# Print last few positions
for item in last_positions[-30:]:
    print(item)
# Show around last unmatched if any
if depth_brace>0 or depth_paren>0 or depth_brack>0:
    print('\nShowing last 400 chars of script:')
    print(code[-400:])

