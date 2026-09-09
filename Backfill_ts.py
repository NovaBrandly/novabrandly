#!/usr/bin/env python3
"""One-time fix: add a 'ts' timestamp to any product missing one (the 47
Supplier 2 items added before the timestamp fix), then re-sort newest-first."""
import json, time

with open('products.json', encoding='utf-8') as f:
    products = json.load(f)

now = int(time.time())
fixed = 0
for p in products:
    if not p.get('ts'):
        p['ts'] = now
        fixed += 1

products.sort(key=lambda p: p.get('ts', 0), reverse=True)

with open('products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, separators=(',', ':'))

print(f'Fixed {fixed} products missing a timestamp.')
