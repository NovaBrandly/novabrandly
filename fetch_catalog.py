#!/usr/bin/env python3
"""
Nova Brandly — Catalog Fetcher (v3, definitive)

- Calls the Cloudflare Worker's fetchcat endpoint. The Worker internally
  repeat-samples each category and returns an accumulated batch of unique
  products (supplier gives a rotating ~30 sample per call; the Worker loops).
- We call each category a few ROUNDS and MERGE everything into products.json.
- MERGE-NEVER-SHRINK: existing products are always kept; we only add. A bad
  run can never wipe the catalog. Over successive 6-hourly runs it converges
  to the supplier's full inventory and keeps picking up new arrivals.
"""

import json, os, sys, time
import urllib.request, urllib.parse

WORKER_URL = 'https://hidden-smoke-0ae0.natali-korabljov.workers.dev'

CATS = [
    ('84646720', 'Bags'), ('84646717', 'Bags'), ('84646715', 'Bags'),
    ('84678648', 'Wallets'), ('84678702', 'Shoes'), ('84678506', 'Clothing'),
    ('84678726', 'Belts'), ('84678751', 'Jewelry'), ('84678809', 'Scarves & Hats'),
]

ROUNDS_PER_CAT     = 4     # Worker already accumulates internally; a few rounds catch the rest
STOP_AFTER_NO_NEW  = 2     # stop a category early after N rounds with 0 new
GLOBAL_TIME_BUDGET = 1200  # 20 min (workflow allows 25)


def worker_fetchcat(cat_id, cat_name):
    url = f'{WORKER_URL}/?action=fetchcat&catId={cat_id}&catName={urllib.parse.quote(cat_name)}'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='GET'), timeout=120) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict) and data.get('error'):
            print(f'    Worker: {data["error"]}', flush=True)
            return None  # signal error (e.g. token expired)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f'    Call failed: {e}', flush=True)
        return []


def load_existing():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def main():
    existing = load_existing()
    catalog = {p['i']: p for p in existing if isinstance(p, dict) and p.get('i')}
    start_count = len(catalog)
    now = int(time.time())
    print(f'Existing catalog: {start_count} products', flush=True)

    run_start = time.time()
    token_dead = False

    for cat_id, cat_name in CATS:
        if token_dead or time.time() - run_start > GLOBAL_TIME_BUDGET:
            break
        print(f'  {cat_name} ({cat_id})...', flush=True)
        no_new = 0
        for rnd in range(ROUNDS_PER_CAT):
            if time.time() - run_start > GLOBAL_TIME_BUDGET:
                break
            batch = worker_fetchcat(cat_id, cat_name)
            if batch is None:
                token_dead = True
                print('    Token appears expired — stopping fetch, keeping existing catalog', flush=True)
                break
            new = 0
            for p in batch:
                pid = p.get('i')
                if pid and pid not in catalog:
                    p['ts'] = now
                    catalog[pid] = p
                    new += 1
            print(f'    Round {rnd+1}: {len(batch)} returned, {new} new (catalog: {len(catalog)})', flush=True)
            if new == 0:
                if (no_new := no_new + 1) >= STOP_AFTER_NO_NEW:
                    break
            else:
                no_new = 0
            time.sleep(0.5)

    final = list(catalog.values())
    final.sort(key=lambda p: p.get('ts', 0), reverse=True)  # newest first
    print(f'\nCatalog: {start_count} → {len(final)} (+{len(final)-start_count})', flush=True)

    # SAFETY: never write fewer than we started with
    if len(final) < start_count:
        print('⚠ Result smaller than existing — keeping existing file', flush=True)
        return

    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, separators=(',', ':'))
    print('Saved products.json ✅', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f'\n❌ FATAL: {type(e).__name__}: {e}', flush=True)
        traceback.print_exc()
        if not os.path.exists('products.json'):
            with open('products.json', 'w', encoding='utf-8') as f:
                json.dump([], f)
        sys.exit(0)
