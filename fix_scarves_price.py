#!/usr/bin/env python3
"""One-time fix: recalculate Scarves & Hats pricing to price_code * 3
(same markup rule as Sunglasses), applied retroactively to all existing
items in that category."""
import json, re

with open('products.json', encoding='utf-8') as f:
    products = json.load(f)

fixed = 0
for p in products:
    if p.get('c') == 'Scarves & Hats':
        ref = p.get('ref', '')
        m = re.search(r'(\d{2,3})$', ref)
        if m:
            price_code = int(m.group(1))
            new_price = round(price_code * 3)
            if p.get('p') != new_price:
                p['p'] = new_price
                fixed += 1

with open('products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, separators=(',', ':'))

print(f'Scarves & Hats prices recalculated: {fixed}')
