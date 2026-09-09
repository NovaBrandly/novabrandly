#!/usr/bin/env python3
"""
ONE-TIME CORRECTION (run this exactly once, then delete/ignore it).

A previous backfill accidentally stamped ALL products (not just genuinely
new ones) with the current time. This undoes that: any product that did
NOT come from the Telegram supplier ('tg2') gets pushed back to an old
timestamp, so only the real new arrivals keep showing the NEW badge.
"""
import json, time

with open('products.json', encoding='utf-8') as f:
    products = json.load(f)

OLD_TS = int(time.time()) - 30 * 24 * 3600  # 30 days ago
fixed = 0

for p in products:
    if p.get('src') != 'tg2':
        p['ts'] = OLD_TS
        fixed += 1

products.sort(key=lambda p: p.get('ts', 0), reverse=True)

with open('products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, separators=(',', ':'))

print(f'Corrected {fixed} products back to an old timestamp.')
print('Only genuine Telegram-supplier new arrivals should show as NEW now.')
