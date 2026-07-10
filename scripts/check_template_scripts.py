#!/usr/bin/env python3
import os, re, sys
root = os.path.join('templates', 'reservations')
issues = []
for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.endswith('.html'): continue
        path = os.path.join(dirpath, fname)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, flags=re.S)
        for idx, code in enumerate(scripts, 1):
            # Remove Django template tags to avoid counting braces in templates
            stripped = re.sub(r"\{\%.*?\%\}|\{\{.*?\}\}", '', code, flags=re.S)
            braces = stripped.count('{') - stripped.count('}')
            paren = stripped.count('(') - stripped.count(')')
            brackets = stripped.count('[') - stripped.count(']')
            semicolons = stripped.strip().endswith(';')
            if braces or paren or brackets:
                preview = ' '.join(stripped.strip().splitlines())[:200]
                issues.append((path, idx, braces, paren, brackets, preview))

if not issues:
    print('OK: no imbalance found in reservation template <script> blocks')
    sys.exit(0)

print('Found potential issues:')
for p in issues:
    print('\nFile:', p[0])
    print(' Script #', p[1], 'braces=', p[2], 'paren=', p[3], 'brackets=', p[4])
    print(' Preview:', p[5])

sys.exit(2)
