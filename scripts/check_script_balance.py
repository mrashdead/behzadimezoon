#!/usr/bin/env python3
import os, re, sys

def remove_strings_and_comments(s):
    # remove single-line comments
    s = re.sub(r'//.*', '', s)
    # remove multi-line comments
    s = re.sub(r'/\*[\s\S]*?\*/', '', s)
    # remove single and double quoted strings
    s = re.sub(r"'(?:\\.|[^'\\])*'", '', s)
    s = re.sub(r'\"(?:\\.|[^\\\"])*\"', '', s)
    # remove template literals (backticks)
    s = re.sub(r'`(?:\\.|[^`\\])*`', '', s)
    return s

root = os.path.join('templates', 'reservations')
problems = []
for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.endswith('.html'): continue
        path = os.path.join(dirpath, fname)
        with open(path, 'r', encoding='utf-8') as fh:
            content = fh.read()
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, flags=re.S)
        for idx, code in enumerate(scripts, 1):
            cleaned = remove_strings_and_comments(code)
            # remove django tags
            cleaned = re.sub(r"\{\%.*?\%\}|\{\{.*?\}\}", '', cleaned, flags=re.S)
            b = cleaned.count('{') - cleaned.count('}')
            p = cleaned.count('(') - cleaned.count(')')
            br = cleaned.count('[') - cleaned.count(']')
            if b != 0 or p != 0 or br != 0:
                problems.append((path, idx, b, p, br, cleaned.strip()[:200].replace('\n',' ')))

if not problems:
    print('OK: no script balance issues found')
    sys.exit(0)

print('Found script balance issues:')
for path, idx, b, p, br, preview in problems:
    print(f"{path} script#{idx} braces={b} paren={p} brackets={br} preview={preview}")
sys.exit(2)
