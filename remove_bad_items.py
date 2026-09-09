#!/usr/bin/env python3
"""One-time removal: deletes the specific YSL bag entries with the
incorrect/weird $40 price (26*20cm, 3A quality) reported by the user."""
import json

with open('products.json', encoding='utf-8') as f:
    products = json.load(f)

before = len(products)

def is_bad(p):
    return (
        p.get('b') == 'YSL'
        and p.get('c') == 'Bags'
        and p.get('p') == 40
        and p.get('q') == '3A'
        and '26' in (p.get('d') or '') and '20' in (p.get('d') or '')
    )

removed = [p for p in products if is_bad(p)]
kept = [p for p in products if not is_bad(p)]

print(f'Found {len(removed)} matching item(s) to remove:')
for p in removed:
    print(f"  - {p['n']} | price={p['p']} | desc={p['d']} | img={p['img']}")

with open('products.json', 'w', encoding='utf-8') as f:
    json.dump(kept, f, ensure_ascii=False, separators=(',', ':'))

print(f'\nCatalog: {before} -> {len(kept)}')
print('Saved products.json')
