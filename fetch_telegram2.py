#!/usr/bin/env python3
"""
Nova Brandly — Supplier #2 Fetcher (Telegram channel)
Run by GitHub Actions on a schedule.

Reads new posts from the Telegram channel/discussion group, downloads
one photo per product post, parses the caption, and merges new products
into products.json (merge-never-shrink — never deletes existing items).

Requires GitHub Secrets: TG_API_ID, TG_API_HASH, TG_SESSION
"""

import json, os, re, sys, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID     = int(os.environ['TG_API_ID'])
API_HASH   = os.environ['TG_API_HASH']
SESSION    = os.environ['TG_SESSION']
CHAT_ID    = int(os.environ.get('TG_CHAT_ID', '-1001831609624'))

IMAGES_DIR = 'supplier2_images'
STATE_FILE = 'supplier2_state.json'
MAX_NEW_MESSAGES = 400  # safety cap per run

# ── Brand normalization (reuse the same map as the first supplier) ──
BRANDS = {
    'lv':'Louis Vuitton','louis':'Louis Vuitton','louis vuitton':'Louis Vuitton','gucci':'Gucci',
    'miumiu':'Miu Miu','miu miu':'Miu Miu','miu':'Miu Miu','ggdb':'Golden Goose','golden':'Golden Goose','ysl':'YSL',
    'saint laurent':'YSL','saint':'YSL','chrome hearts':'Chrome Hearts','chrome':'Chrome Hearts','dior':'Dior','fendi':'Fendi','prada':'Prada',
    'hermes':'Hermès','hermès':'Hermès','balenciaga':'Balenciaga','burberry':'Burberry',
    'chanel':'Chanel','celine':'Celine','loewe':'Loewe','bottega veneta':'Bottega Veneta','bottega':'Bottega Veneta',
    'bv':'Bottega Veneta','coach':'Coach','versace':'Versace','valentino':'Valentino',
    'givenchy':'Givenchy','jacquemus':'Jacquemus','amiri':'AMIRI','cartier':'Cartier',
    'bulgari':'Bulgari','bvlgari':'Bulgari','tiffany':'Tiffany & Co','van cleef':'Van Cleef','van':'Van Cleef','longchamp':'Longchamp',
    'goyard':'Goyard','furla':'Furla','tory burch':'Tory Burch','tory':'Tory Burch','michael kors':'Michael Kors','michael':'Michael Kors','mk':'Michael Kors',
    'marc jacobs':'Marc Jacobs','marc':'Marc Jacobs','moncler':'Moncler','ralph lauren':'Ralph Lauren','ralph':'Ralph Lauren','polo':'Ralph Lauren',
    'tom ford':'Tom Ford','tom':'Tom Ford','jimmy choo':'Jimmy Choo','jimmy':'Jimmy Choo','ferragamo':'Ferragamo','ugg':'UGG',
    'chopard':'Chopard','ami paris':'AMI Paris','ami':'AMI Paris','dolce':'Dolce & Gabbana','d&g':'Dolce & Gabbana','dolce & gabbana':'Dolce & Gabbana',
    'armani':'Armani','new balance':'New Balance','new':'New Balance','alo':'Alo Yoga','canada goose':'Canada Goose','canada':'Canada Goose',
    'adidas':'Adidas','lacoste':'Lacoste','lululemon':'Lululemon','off-white':'Off-White','off':'Off-White',
    'rolex':'Rolex','omega':'Omega','swarovski':'Swarovski','alexander mcqueen':'Alexander McQueen','alexander':'Alexander McQueen',
    'skims':'SKIMS','mcm':'MCM','pinko':'Pinko','loro piana':'Loro Piana','loro':'Loro Piana','max mara':'Max Mara','max':'Max Mara',
    'thom browne':'Thom Browne','thom':'Thom Browne','vetements':'Vetements','messika':'Messika',
}

def norm_brand(raw):
    k = raw.strip().lower()
    return BRANDS.get(k, raw.strip().title() if raw.strip() else 'Unknown')

CAT_MAP = {
    'bag': 'Bags', 'bags': 'Bags',
    'shoe': 'Shoes', 'shoes': 'Shoes',
    'clothes': 'Clothing', 'clothing': 'Clothing',
    'wallet': 'Wallets', 'wallets': 'Wallets',
    'belt': 'Belts', 'belts': 'Belts',
    'jewelry': 'Jewelry', 'jewellery': 'Jewelry',
    'scarf': 'Scarves & Hats', 'hat': 'Scarves & Hats',
    'sunglasses': 'Sunglasses', 'glasses': 'Sunglasses',
}

HEADER_RE = re.compile(r'^([A-Za-z&\.\s]+?)/\s*([A-Za-z]+)\s+(\d+)', re.MULTILINE)
PRICE_RE  = re.compile(r'Price\s*:?\s*\$?\s*([\d.]+)', re.IGNORECASE)

def parse_caption(text):
    if not text:
        return None
    text = text.strip()
    m = HEADER_RE.match(text)
    if not m:
        return None
    brand_raw, cat_raw, item_code = m.groups()
    brand = norm_brand(brand_raw)
    category = CAT_MAP.get(cat_raw.lower().strip(), cat_raw.strip().title())

    pm = PRICE_RE.search(text)
    if not pm:
        return None
    original_price = float(pm.group(1))
    display_price = round(original_price * 1.05 * 2.5)

    lines = text.split('\n')
    desc_lines = []
    for l in lines[1:]:
        if PRICE_RE.search(l):
            break
        clean = l.strip()
        if not clean or 'high quality' in clean.lower():
            continue
        desc_lines.append(clean)
    desc = ' · '.join(desc_lines)[:300]

    return {
        'brand': brand, 'category': category, 'item_code': item_code,
        'price': display_price, 'desc': desc,
    }

def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

async def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    state = load_json(STATE_FILE, {'last_id': 0})
    last_id = state.get('last_id', 0)

    existing = load_json('products.json', [])
    catalog = {p['i']: p for p in existing if isinstance(p, dict) and p.get('i')}
    start_count = len(catalog)

    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()

    print(f'Connected. Fetching messages newer than id={last_id}...', flush=True)

    # Collect messages grouped by album (grouped_id), newest first from Telegram,
    # but we want to process oldest-to-newest for cleaner logic
    messages = []
    async for msg in client.iter_messages(CHAT_ID, min_id=last_id, limit=MAX_NEW_MESSAGES):
        messages.append(msg)
    messages.reverse()  # oldest first

    if not messages:
        print('No new messages.', flush=True)
        await client.disconnect()
        return

    max_id_seen = last_id
    groups = {}  # grouped_id or msg.id -> {'caption':..., 'photo_msg':...}

    for msg in messages:
        max_id_seen = max(max_id_seen, msg.id)
        key = msg.grouped_id or msg.id
        if key not in groups:
            groups[key] = {'caption': None, 'photo_msg': None}
        if msg.text:
            groups[key]['caption'] = msg.text
        if msg.photo and groups[key]['photo_msg'] is None:
            groups[key]['photo_msg'] = msg

    new_count = 0
    for key, g in groups.items():
        parsed = parse_caption(g['caption'])
        if not parsed or not g['photo_msg']:
            continue

        item_code = parsed['item_code']
        pid = f"tg2_{item_code}"
        img_path = f"{IMAGES_DIR}/{item_code}.jpg"

        if not os.path.exists(img_path):
            try:
                await client.download_media(g['photo_msg'], file=img_path)
            except Exception as e:
                print(f'  Failed to download image for {item_code}: {e}', flush=True)
                continue

        name = f"{parsed['brand']} {parsed['category']}".strip()
        catalog[pid] = {
            'i': pid,
            'n': name,
            'b': parsed['brand'],
            'c': parsed['category'],
            'p': parsed['price'],
            'q': 'HQ',
            'd': parsed['desc'],
            'img': f"./{img_path}",
            'src': 'tg2',
        }
        new_count += 1
        print(f'  + {item_code}: {name} (${parsed["price"]})', flush=True)

    await client.disconnect()

    print(f'\nNew products this run: {new_count}', flush=True)

    final = list(catalog.values())
    if len(final) < start_count:
        print('Would shrink catalog — aborting save.', flush=True)
        return

    save_json('products.json', final)
    save_json(STATE_FILE, {'last_id': max_id_seen})
    print(f'Catalog: {start_count} -> {len(final)}', flush=True)
    print('Saved products.json and state.', flush=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        print(f'FATAL: {e}', flush=True)
        traceback.print_exc()
        sys.exit(0)
