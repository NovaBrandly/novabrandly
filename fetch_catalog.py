#!/usr/bin/env python3
"""
Nova Brandly — Supplier Catalog Fetcher (v2)
Run by GitHub Actions every 6 hours.

Delegates the actual supplier fetching to a Cloudflare Worker (which the
supplier's anti-bot system trusts), and just collects + saves the results.
This avoids GitHub Actions' datacenter IPs being blocked/degraded by the
supplier, while still writing nothing to Cloudflare KV (no write limits).
"""

import json, os, sys, time
import urllib.request, urllib.parse

WORKER_URL = 'https://hidden-smoke-0ae0.natali-korabljov.workers.dev'

CATS = [
    ('84646720', 'Bags'),
    ('84646717', 'Bags'),
    ('84646715', 'Bags'),
    ('84678648', 'Wallets'),
    ('84678702', 'Shoes'),
    ('84678506', 'Clothing'),
    ('84678726', 'Belts'),
    ('84678751', 'Jewelry'),
    ('84678809', 'Scarves & Hats'),
]

def fetch_category_via_worker(cat_id, cat_name, retries=2):
    url = f'{WORKER_URL}/?action=fetchcat&catId={cat_id}&catName={urllib.parse.quote(cat_name)}'
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=180) as resp:  # Worker may take a while
                data = json.loads(resp.read().decode())
            if isinstance(data, dict) and data.get('error'):
                print(f'    Worker error: {data["error"]}', flush=True)
                return []
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f'    Attempt {attempt+1} failed: {e}', flush=True)
            time.sleep(3)
    return []

def load_existing():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            existing = json.load(f)
        return {p['i']: p.get('ts', 0) for p in existing}
    except Exception:
        return {}

def main():
    existing_ts = load_existing()
    now = int(time.time())

    print('Starting catalog fetch via Cloudflare Worker...', flush=True)
    all_products = []
    seen = set()
    run_start = time.time()

    for cat_id, cat_name in CATS:
        print(f'  Fetching {cat_name} ({cat_id})...', flush=True)
        t0 = time.time()
        prods = fetch_category_via_worker(cat_id, cat_name)
        new_prods = []
        for p in prods:
            if p['i'] not in seen:
                seen.add(p['i'])
                new_prods.append(p)
        all_products.extend(new_prods)
        print(f'    → {len(new_prods)} products in {time.time()-t0:.1f}s (total: {len(all_products)})', flush=True)

    print(f'\nTotal: {len(all_products)} products in {time.time()-run_start:.1f}s', flush=True)

    # Assign timestamps: keep original first-seen time for existing items,
    # use "now" for genuinely new items — so new arrivals sort to top
    new_count = 0
    for p in all_products:
        try:
            pid = p.get('i')
            if pid and pid in existing_ts:
                p['ts'] = existing_ts[pid]
            else:
                p['ts'] = now
                new_count += 1
        except Exception:
            p['ts'] = now

    try:
        all_products.sort(key=lambda p: p.get('ts', 0), reverse=True)
    except Exception as e:
        print(f'Warning: sort failed ({e})', flush=True)

    print(f'New items this run: {new_count}', flush=True)

    try:
        with open('products.json', 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, separators=(',',':'))
        print('Saved products.json ✅', flush=True)
    except Exception as e:
        print(f'❌ Failed to save products.json: {e}', flush=True)
        raise

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f'\n❌ FATAL ERROR: {type(e).__name__}: {e}', flush=True)
        traceback.print_exc()
        if not os.path.exists('products.json'):
            with open('products.json', 'w', encoding='utf-8') as f:
                json.dump([], f)
        sys.exit(0)
