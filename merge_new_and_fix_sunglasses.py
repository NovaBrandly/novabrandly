#!/usr/bin/env python3
"""
One-time / occasional script:
1. Merges new_items_thismonth.json into products.json (dedup by id,
   never removes existing items, new items get today's timestamp so
   they show the "NEW" badge).
2. Retroactively fixes ALL Sunglasses pricing (old AND new) to use
   price_code * 3 instead of the standard price_code * 2 + 10 formula.
"""
import json, re, time

with open('products.json', encoding='utf-8') as f:
    existing = json.load(f)

with open('new_items_thismonth.json', encoding='utf-8') as f:
    new_items = json.load(f)

catalog = {p['i']: p for p in existing if isinstance(p, dict) and p.get('i')}
start_count = len(catalog)
now = int(time.time())

added = 0
for p in new_items:
    if p['i'] not in catalog:
        p['ts'] = now
        catalog[p['i']] = p
        added += 1

print(f'New items added: {added}')

# Retroactive sunglasses price fix — recompute from the ref code (e.g. "TQ118" -> 118)
fixed_sun = 0
for p in catalog.values():
    if p.get('c') == 'Sunglasses':
        ref = p.get('ref', '')
        m = re.search(r'(\d{2,3})$', ref)
        if m:
            price_code = int(m.group(1))
            new_price = round(price_code * 3)
            if p.get('p') != new_price:
                p['p'] = new_price
                fixed_sun += 1

print(f'Sunglasses prices recalculated: {fixed_sun}')

final = list(catalog.values())
if len(final) < start_count:
    print('Would shrink catalog — aborting save.')
else:
    final.sort(key=lambda p: p.get('ts', 0), reverse=True)
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, separators=(',', ':'))
    print(f'Catalog: {start_count} -> {len(final)}')
    print('Saved products.json')
