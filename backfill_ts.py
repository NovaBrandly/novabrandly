#!/usr/bin/env python3
"""One-time fix: products missing a 'ts' timestamp are treated as PRE-EXISTING
catalog items (from the original harvest, before timestamps existed) — they
get an OLD timestamp so they don't falsely show the "NEW" badge. Genuinely
new items always get their real 'now' timestamp at the moment fetch scripts
first see them, so this backfill never overwrites a real timestamp."""
import json, time

with open('products.json', encoding='utf-8') as f:
    products = json.load(f)

# Treat any pre-existing, un-timestamped item as "30 days old" — old enough
# to never trigger the 24h NEW badge, but still sorts after genuinely new items.
OLD_TS = int(time.time()) - 30 * 24 * 3600

fixed = 0
for p in products:
    if not p.get('ts'):
        p['ts'] = OLD_TS
        fixed += 1

products.sort(key=lambda p: p.get('ts', 0), reverse=True)

with open('products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, separators=(',', ':'))

print(f'Backfilled {fixed} products with an old (non-"new") timestamp.')
