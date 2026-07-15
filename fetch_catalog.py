#!/usr/bin/env python3
"""
Nova Brandly — Supplier Catalog Fetcher
Run by GitHub Actions every 6 hours.
Fetches ALL products from supplier and saves products.json
"""

import json, os, re, time, sys
import urllib.request, urllib.parse

TOKEN    = os.environ.get('SUPPLIER_TOKEN', '')
BASE     = 'https://www.5270527.xyz'
ALBUM    = '_ZC8qfT_u4BkOnvDjx3c7FjRykKm4t18k'

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

BRANDS = {
    'lv':'Louis Vuitton','louis':'Louis Vuitton','gucci':'Gucci','gucc':'Gucci',
    'miumiu':'Miu Miu','miu':'Miu Miu','ggdb':'Golden Goose','golden':'Golden Goose',
    'ysl':'YSL','saint':'YSL','chrome':'Chrome Hearts','dior':'Dior','fendi':'Fendi',
    'prada':'Prada','hermes':'Hermès','hermès':'Hermès','balenciaga':'Balenciaga',
    'burberry':'Burberry','chanel':'Chanel','celine':'Celine','loewe':'Loewe',
    'bottega':'Bottega Veneta','bv':'Bottega Veneta','coach':'Coach','versace':'Versace',
    'valentino':'Valentino','givenchy':'Givenchy','jacquemus':'Jacquemus','amiri':'AMIRI',
    'cartier':'Cartier','bulgari':'Bulgari','tiffany':'Tiffany & Co','van':'Van Cleef',
    'longchamp':'Longchamp','goyard':'Goyard','furla':'Furla','tory':'Tory Burch',
    'michael':'Michael Kors','marc':'Marc Jacobs','moncler':'Moncler','ralph':'Ralph Lauren',
    'polo':'Ralph Lauren','tom':'Tom Ford','jimmy':'Jimmy Choo','ferragamo':'Ferragamo',
    'ugg':'UGG','chopard':'Chopard','ami':'AMI Paris','dolce':'Dolce & Gabbana',
    'd&g':'Dolce & Gabbana','armani':'Armani','new':'New Balance','alo':'Alo Yoga',
    'canada':'Canada Goose','adidas':'Adidas','lacoste':'Lacoste','lululemon':'Lululemon',
    'off':'Off-White','rolex':'Rolex','omega':'Omega','swarovski':'Swarovski',
    'alexander':'Alexander McQueen','skims':'SKIMS','messika':'Messika','pinko':'Pinko',
    'schiaparelli':'Schiaparelli','mcm':'MCM','stone':'Stone Island','loro':'Loro Piana',
    'max':'Max Mara','acne':'Acne Studios','maison':'Maison Margiela','thom':'Thom Browne',
    'gianvito':'Gianvito Rossi','manolo':'Manolo Blahnik','roger':'Roger Vivier',
    'patek':'Patek Philippe','zimmermann':'Zimmermann','vetements':'Vetements',
}

def norm_brand(raw):
    k = re.sub(r'[^a-zA-Z&]', '', raw).strip().lower()
    return BRANDS.get(k, raw.strip().capitalize() if raw.strip() else 'Unknown')

def parse_code(line):
    m = re.match(r'^([A-Z0-9]{1,4}?)(\d{2,3})$', line.strip())
    if not m: return None
    pc = int(m.group(2))
    return m.group(1), pc * 2 + 10   # quality, price

def fetch_page(cat_id, ts, headers):
    url = f'{BASE}/album/personal/all?albumId={ALBUM}&tagGroupId={cat_id}&transLang=en&tagUnion=false'
    if ts:
        url += f'&pageTimestamp={ts}'
    data = b'tagList=%5B%5D'
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

MAX_PAGES_PER_CAT = 150     # hard safety cap (150 * 32 = 4800 per category max)
MAX_STUCK_PAGES   = 5       # if 0 new items N times in a row, stop (raised from 3)
CATEGORY_TIME_LIMIT = 130   # seconds max per category (9 cats * 130s = ~20min worst case,
                             # but real runs finish much faster since most cats are smaller)

def fetch_category(cat_id, cat_name, headers, seen, time_limit=CATEGORY_TIME_LIMIT):
    prods, ts, page = [], '', 0
    stuck_count = 0
    last_ts = None
    start_time = time.time()
    print(f'  Fetching {cat_name} ({cat_id})...', flush=True)

    while page < MAX_PAGES_PER_CAT:
        # Hard time limit per category
        if time.time() - start_time > time_limit:
            print(f'    ⏱ Time limit reached for {cat_name}, moving on', flush=True)
            break
        try:
            data = fetch_page(cat_id, ts, headers)
            result = data.get('result', {})
            items = result.get('items', [])
            if not items:
                print(f'    Page {page}: no items, stopping', flush=True)
                break

            new_count = 0
            for item in items:
                gid = item.get('goods_id', '')
                if gid in seen:
                    continue
                seen.add(gid)
                new_count += 1
                lines = [l.strip() for l in item.get('title','').split('\n') if l.strip()]
                if not lines:
                    continue
                parsed = parse_code(lines[0])
                if not parsed:
                    continue
                quality, price = parsed
                name_line = lines[1] if len(lines) > 1 else lines[0]
                brand_raw = name_line.split(' ')[0]
                brand = norm_brand(brand_raw)
                desc = ' · '.join(l for l in lines[2:4] if not l.startswith('#'))
                imgs = [u.split('?')[0] for u in item.get('imgs', []) if u.startswith('http')]
                if not imgs:
                    continue
                prods.append({
                    'i':   f'sup_{gid}',
                    'n':   name_line,
                    'b':   brand,
                    'c':   cat_name,
                    'p':   price,
                    'q':   quality,
                    'd':   desc,
                    'img': imgs[0],
                    'src': 'sup',
                })

            print(f'    Page {page}: {len(items)} items, {new_count} new (total so far: {len(prods)})', flush=True)
            # Note: NOT stopping on 0-new-items streaks — the supplier API legitimately
            # returns long runs of duplicate items between genuinely new ones.
            # We rely on isLoadMore=false / pageTimestamp-stall / hard caps instead.

            pag = result.get('pagination', {})
            if not pag.get('isLoadMore', False):
                print(f'    isLoadMore=false, stopping normally', flush=True)
                break

            new_ts = pag.get('pageTimestamp')
            # Detect stuck: pageTimestamp not advancing
            if new_ts == last_ts:
                print(f'    ⚠ pageTimestamp not advancing, stopping', flush=True)
                break
            last_ts = new_ts
            ts = new_ts
            page += 1
            time.sleep(0.1)
        except Exception as e:
            print(f'    Error on page {page}: {e}', flush=True)
            break

    print(f'    → {cat_name}: {len(prods)} products in {page+1} pages, {time.time()-start_time:.1f}s', flush=True)
    return prods

GLOBAL_TIME_BUDGET = 780  # 13 minutes total (leaves buffer under 15min workflow timeout)

def load_existing():
    '''Load previous products.json to preserve first-seen timestamps'''
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            existing = json.load(f)
        return {p['i']: p.get('ts', 0) for p in existing}
    except Exception:
        return {}

def main():
    if not TOKEN:
        print('ERROR: SUPPLIER_TOKEN not set!')
        sys.exit(1)

    existing_ts = load_existing()
    now = int(time.time())

    def make_headers(cat_id):
        # Fully match a real browser request (including the category-specific Referer)
        return {
            'Content-Type':   'application/x-www-form-urlencoded',
            'Accept':         'application/json, text/plain, */*',
            'Accept-Language':'en,ru-RU;q=0.9,ru;q=0.8,en-US;q=0.7',
            'Connection':     'keep-alive',
            'Cookie':         f'token={TOKEN}',
            'Origin':         BASE,
            'Referer':        f'{BASE}/weshop/goods_list/{ALBUM}?groupId={cat_id}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent':     'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            'sec-ch-ua':          '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile':   '?0',
            'sec-ch-ua-platform': '"Windows"',
            'wego-staging':   '0',
            'x-wg-language':  'en',
            'x-wg-module':    'indsite',
        }

    print('Starting catalog fetch...', flush=True)
    all_products, seen = [], set()
    run_start = time.time()

    for cat_id, cat_name in CATS:
        elapsed = time.time() - run_start
        remaining = GLOBAL_TIME_BUDGET - elapsed
        if remaining < 20:
            print(f'\n⏱ Global time budget nearly exhausted ({elapsed:.0f}s elapsed), skipping remaining categories', flush=True)
            break
        cat_headers = make_headers(cat_id)
        prods = fetch_category(cat_id, cat_name, cat_headers, seen, time_limit=min(CATEGORY_TIME_LIMIT, remaining))
        all_products.extend(prods)

    print(f'\nTotal: {len(all_products)} products in {time.time()-run_start:.1f}s', flush=True)

    # Assign timestamps: keep original first-seen time for existing items,
    # use "now" for genuinely new items
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

    # Sort newest-first so new items appear at the top of the site
    try:
        all_products.sort(key=lambda p: p.get('ts', 0), reverse=True)
    except Exception as e:
        print(f'Warning: sort failed ({e}), keeping unsorted order', flush=True)

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
        # Try to save whatever we have, or keep old file, rather than crash the workflow
        import os
        if not os.path.exists('products.json'):
            print('No products.json exists — writing empty array as fallback', flush=True)
            with open('products.json', 'w', encoding='utf-8') as f:
                json.dump([], f)
        sys.exit(0)  # Exit cleanly so the workflow can still commit/proceed
