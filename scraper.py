# Project : DealOrDud — Fake Discount Detector
# Author  : Anshika Goyal
# Purpose : Scrape Amazon India prices daily, detect fake
#           discounts, and save everything to a CSV file
# ═════════════════════════════════════════════════════════════

import requests
import re
import json
import time
import random
import os
import csv
from bs4 import BeautifulSoup
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

PRODUCTS_FILE = BASE_DIR / "products.csv"
OUTPUT_FILE = BASE_DIR / "price_history.csv"
SEEN_ASINS_FILE = BASE_DIR / "seen_asins.json"
PRODUCT_HISTORY_FILE = BASE_DIR / "asin_history.json"


TIMEOUT = 20

DELAY_MIN = 4
DELAY_MAX = 9

MAX_PER_CATEGORY = 20
TARGET_PRODUCTS_PER_RUN = 30
REPEAT_PRODUCTS_PER_RUN = 4
RECENT_REPEAT_COOLDOWN_DAYS = 14
GROUPS_PER_DAY = 3
PAGES_PER_CATEGORY = 3

CATEGORY_GROUPS = {
    "electronics": [
        "https://www.amazon.in/gp/bestsellers/electronics",
    ],
    "kitchen": [
        "https://www.amazon.in/gp/bestsellers/kitchen",
    ],
    "computers": [
        "https://www.amazon.in/gp/bestsellers/computers",
    ],
    "home_improvement": [
        "https://www.amazon.in/gp/bestsellers/home-improvement",
    ],
    "beauty": [
        "https://www.amazon.in/gp/bestsellers/beauty",
    ],
    "sports": [
        "https://www.amazon.in/gp/bestsellers/sports",
    ],
    "deals": [
        "https://www.amazon.in/deals",
    ],
}

CSV_COLUMNS = [
    "scraped_at",
    "date",
    "asin",
    "product_name",
    "current_price",
    "mrp",
    "displayed_discount_pct",
    "computed_discount_pct",
    "fake_discount",
    "analysis_note",
    "in_stock",
    "url",
]

PRICE_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .priceToPay span.a-offscreen",
    "#corePrice_feature_div .priceToPay span.a-offscreen",
    "#apex_desktop .priceToPay span.a-offscreen",
    "#corePrice_mobile_feature_div .priceToPay span.a-offscreen",
    "#corePriceDisplay_desktop_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
    "#corePrice_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
    "#apex_desktop span.a-price:not(.a-text-price) span.a-offscreen",
    "#corePrice_mobile_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) span.a-offscreen",
    "#corePrice_feature_div .a-price:not(.a-text-price) span.a-offscreen",
    "#apex_desktop .a-price:not(.a-text-price) span.a-offscreen",
    "#tp_price_block_total_price_ww span.a-offscreen",
    "#price_inside_buybox",
    "#priceblock_dealprice",
    "#priceblock_saleprice",
    "#priceblock_ourprice",
]

MRP_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .basisPrice span.a-offscreen",
    "#corePrice_feature_div .basisPrice span.a-offscreen",
    "#apex_desktop .basisPrice span.a-offscreen",
    "#listPrice span.a-offscreen",
    ".priceBlockStrikePriceString",
    "span.a-price.a-text-price span.a-offscreen",
]

DISCOUNT_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .savingsPercentage",
    "#corePrice_feature_div .savingsPercentage",
    "#apex_desktop .savingsPercentage",
    ".reinventPriceSavingsPercentageMargin",
]

BLOCK_MARKERS = [
    "Robot Check",
    "validateCaptcha",
    "Enter the characters you see below",
    "Sorry, we just need to make sure you're not a robot",
]

def build_session():
    session = requests.Session()

    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )

    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.amazon.in/",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    })

    session.cookies.set("i18n-prefs", "INR", domain=".amazon.in")
    session.cookies.set("lc-main", "en_IN", domain=".amazon.in")

    return session

def fetch_page(session, url):
    try:
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        html = response.text

        for marker in BLOCK_MARKERS:
            if marker in html:
                print("    ✗ Amazon blocked us (CAPTCHA). Wait 30+ mins and retry.")
                return None

        return html

    except requests.exceptions.Timeout:
        print(f"    ✗ Timed out after {TIMEOUT}s")
        return None
    except requests.exceptions.ConnectionError:
        print("    ✗ No internet connection or DNS error")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"    ✗ HTTP error: {e}")
        return None
    except Exception as e:
        print(f"    ✗ Unexpected error: {e}")
        return None

def clean_price(text):
    if not text:
        return None

    cleaned = re.sub(r"[^0-9.]", "", text.strip())
    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def find_price_in_selectors(soup, selectors):
    for selector in selectors:
        elements = soup.select(selector)

        for element in elements:
            text = " ".join(element.get_text(" ", strip=True).split())
            price = clean_price(text)

            if price and 1 < price < 1_000_000:
                return price

    return None


def find_split_price(soup):
    containers = [
        "#corePriceDisplay_desktop_feature_div .priceToPay .a-price",
        "#corePrice_feature_div .priceToPay .a-price",
        "#apex_desktop .priceToPay .a-price",
        "#corePrice_mobile_feature_div .priceToPay .a-price",
    ]

    for selector in containers:
        for node in soup.select(selector):
            whole_tag = node.select_one(".a-price-whole")
            if not whole_tag:
                continue

            whole = whole_tag.get_text("", strip=True).replace(",", "").replace(".", "")
            frac_tag = node.select_one(".a-price-fraction")
            fraction = frac_tag.get_text("", strip=True) if frac_tag else "00"

            if whole.isdigit() and fraction.isdigit():
                try:
                    return float(f"{whole}.{fraction}")
                except ValueError:
                    pass

    return None


def find_price_in_scripts(html, price_type):
    patterns = {
        "current": [
            r'"priceToPay"\s*:\s*\{[^}]*"priceAmount"\s*:\s*"?([0-9,]+\.?[0-9]*)"?',
            r'"ourPrice"\s*:\s*\{[^}]*"priceAmount"\s*:\s*"?([0-9,]+\.?[0-9]*)"?',
            r'"displayPrice"\s*:\s*"?(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.\d{1,2})?)"?',
            r'"price"\s*:\s*"?(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.\d{1,2})?)"?',
        ],
        "mrp": [
            r'"listPrice"\s*:\s*\{[^}]*"(?:amount|priceAmount)"\s*:\s*"?([0-9,]+\.?[0-9]*)"?',
            r'"basisPrice"\s*:\s*\{[^}]*"(?:amount|priceAmount)"\s*:\s*"?([0-9,]+\.?[0-9]*)"?',
            r'"strikeThroughPrice"\s*:\s*\{[^}]*"priceAmount"\s*:\s*"?([0-9,]+\.?[0-9]*)"?',
        ],
    }

    script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE)

    for script in script_blocks:
        if '"@type"' in script and '"Offer"' in script and price_type == "current":
            try:
                data = json.loads(script.strip())
                if isinstance(data, dict):
                    offers = data.get("offers", {})
                    if isinstance(offers, dict) and "price" in offers:
                        price = clean_price(str(offers["price"]))
                        if price and 1 < price < 1_000_000:
                            return price
            except json.JSONDecodeError:
                pass

        for pattern in patterns.get(price_type, []):
            match = re.search(pattern, script, re.IGNORECASE)
            if match:
                price = clean_price(match.group(1))
                if price and 1 < price < 1_000_000:
                    return price

    return None


def find_mrp_fallback(soup, current_price):
    if current_price is None:
        return None

    best_mrp = None

    for element in soup.select("span.a-price.a-text-price span.a-offscreen"):
        text = " ".join(element.get_text(" ", strip=True).split())
        price = clean_price(text)

        if price and price > current_price:
            if best_mrp is None or price > best_mrp:
                best_mrp = price

    return best_mrp

def analyze_discount(current_price, mrp, displayed_pct):
    if current_price is None or mrp is None:
        return None, False, "missing_price_data"

    if mrp <= 0:
        return None, False, "invalid_mrp"

    computed_pct = round(((mrp - current_price) / mrp) * 100, 2)

    if current_price > mrp and displayed_pct and displayed_pct > 0:
        return computed_pct, True, "price_above_mrp_fake"

    if displayed_pct is None:
        return computed_pct, False, "no_displayed_discount"

    gap = abs(displayed_pct - computed_pct)

    if gap >= 2:
        return computed_pct, True, f"gap_of_{gap:.1f}_pct_points"

    return computed_pct, False, "discount_looks_genuine"

def scrape_product(session, product):
    html = fetch_page(session, product["url"])
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("span", {"id": "productTitle"})
    title = title_tag.text.strip() if title_tag else product["name"]

    displayed_pct = None
    for selector in DISCOUNT_SELECTORS:
        badge = soup.select_one(selector)
        if badge:
            badge_text = badge.get_text(strip=True)
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", badge_text)
            if match:
                displayed_pct = abs(float(match.group(1)))
                break

    current_price = find_price_in_selectors(soup, PRICE_SELECTORS)

    if current_price is None:
        current_price = find_split_price(soup)

    if current_price is None:
        current_price = find_price_in_scripts(html, "current")

    mrp = find_price_in_selectors(soup, MRP_SELECTORS)

    if mrp and current_price and mrp <= current_price:
        mrp = None

    if mrp is None:
        mrp = find_price_in_scripts(html, "mrp")
        if mrp and current_price and mrp <= current_price:
            mrp = None

    if mrp is None:
        mrp = find_mrp_fallback(soup, current_price)

    computed_pct, is_fake, note = analyze_discount(current_price, mrp, displayed_pct)

    availability = soup.find("div", {"id": "availability"})
    in_stock = True
    if availability and "currently unavailable" in availability.text.lower():
        in_stock = False

    result = {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "asin": product["asin"],
        "product_name": title[:100],
        "current_price": current_price,
        "mrp": mrp,
        "displayed_discount_pct": displayed_pct,
        "computed_discount_pct": computed_pct,
        "fake_discount": is_fake,
        "analysis_note": note,
        "in_stock": in_stock,
        "url": product["url"],
    }

    if current_price is None:
        fake_label = "✗ MISS"
    elif is_fake:
        fake_label = "⚠ FAKE"
    else:
        fake_label = "✓ OK  "

    price_str = f"₹{current_price:,.0f}" if current_price is not None else "N/A"
    mrp_str = f"₹{mrp:,.0f}" if mrp is not None else "N/A"
    disp_str = f"{displayed_pct:.0f}%" if displayed_pct is not None else "N/A"
    comp_str = f"{computed_pct:.1f}%" if computed_pct is not None else "N/A"

    print(
        f"    {fake_label} | Price: {price_str:>8} | MRP: {mrp_str:>8} "
        f"| Amazon says: {disp_str:>5} | We compute: {comp_str:>6} | {note}"
    )

    return result

def load_seen_asins():
    if not os.path.exists(SEEN_ASINS_FILE):
        return set()

    try:
        with open(SEEN_ASINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def save_seen_asins(seen_asins):
    with open(SEEN_ASINS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen_asins)), f, indent=2)


def load_product_history():
    if os.path.exists(PRODUCT_HISTORY_FILE):
        try:
            with open(PRODUCT_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    legacy_seen = load_seen_asins()
    return {asin: "1970-01-01" for asin in legacy_seen}


def save_product_history(history):
    with open(PRODUCT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, sort_keys=True)


def days_since(date_text):
    try:
        old_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        return (datetime.now().date() - old_date).days
    except Exception:
        return 999999


def get_rotating_category_urls():
    group_names = list(CATEGORY_GROUPS.keys())
    if not group_names:
        return []

    day_index = datetime.now().timetuple().tm_yday - 1
    start = day_index % len(group_names)

    rotated = group_names[start:] + group_names[:start]
    selected_groups = rotated[:min(GROUPS_PER_DAY, len(rotated))]

    urls = []
    for group_name in selected_groups:
        urls.extend(CATEGORY_GROUPS[group_name])

    return urls


def build_paginated_urls(base_url):
    urls = [base_url]

    for page_num in range(2, PAGES_PER_CATEGORY + 1):
        if "/gp/bestsellers/" in base_url:
            urls.append(f"{base_url}?pg={page_num}")
        elif "/deals" in base_url:
            sep = "&" if "?" in base_url else "?"
            urls.append(f"{base_url}{sep}pageNum={page_num}")
        else:
            sep = "&" if "?" in base_url else "?"
            urls.append(f"{base_url}{sep}page={page_num}")

    return urls


def discover_products(session):
    print("\n  Auto-discovering products from rotating Amazon category pages...")

    previous_history = load_product_history()
    previous_seen_asins = set(previous_history.keys())

    active_category_urls = get_rotating_category_urls()

    print("\n  Today's active category groups/pages:")
    for url in active_category_urls:
        print(f"   - {url}")

    fresh_products = []
    cooled_repeat_products = []
    recent_repeat_products = []
    seen_this_run = set()

    for base_cat_url in active_category_urls:
        expanded_urls = build_paginated_urls(base_cat_url)

        for cat_url in expanded_urls:
            print(f"\n  Scanning: {cat_url}")

            html = fetch_page(session, cat_url)
            if html is None:
                print("  Skipping — could not load page")
                continue

            soup = BeautifulSoup(html, "html.parser")
            count_from_this_page = 0

            for link in soup.find_all("a", href=True):
                href = link.get("href", "").strip()
                if not href:
                    continue

                full_url = urljoin(cat_url, href)
                match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", full_url, re.IGNORECASE)
                if not match:
                    continue

                asin = match.group(1).upper()

                if asin in seen_this_run:
                    continue

                name = (
                    link.get("title")
                    or link.get("aria-label")
                    or link.get_text(strip=True)
                )

                if not name or len(name.strip()) < 8:
                    continue

                product = {
                    "asin": asin,
                    "name": name.strip()[:80],
                    "url": f"https://www.amazon.in/dp/{asin}",
                }

                seen_this_run.add(asin)

                if asin not in previous_seen_asins:
                    fresh_products.append(product)
                else:
                    age_days = days_since(previous_history.get(asin, "1970-01-01"))
                    if age_days >= RECENT_REPEAT_COOLDOWN_DAYS:
                        cooled_repeat_products.append(product)
                    else:
                        recent_repeat_products.append(product)

                count_from_this_page += 1
                if count_from_this_page >= MAX_PER_CATEGORY:
                    break

            print(f"  Found {count_from_this_page} candidates on this page")

            wait = random.uniform(2, 5)
            print(f"  Waiting {wait:.1f}s before next page...")
            time.sleep(wait)

    random.shuffle(fresh_products)
    random.shuffle(cooled_repeat_products)
    random.shuffle(recent_repeat_products)

    fresh_quota = max(0, TARGET_PRODUCTS_PER_RUN - REPEAT_PRODUCTS_PER_RUN)
    repeat_quota = min(REPEAT_PRODUCTS_PER_RUN, TARGET_PRODUCTS_PER_RUN)

    selected = []
    selected.extend(fresh_products[:fresh_quota])
    selected.extend(cooled_repeat_products[:repeat_quota])

    if len(selected) < TARGET_PRODUCTS_PER_RUN:
        selected_asins = {p["asin"] for p in selected}
        for product in fresh_products[fresh_quota:]:
            if product["asin"] not in selected_asins:
                selected.append(product)
                selected_asins.add(product["asin"])
            if len(selected) >= TARGET_PRODUCTS_PER_RUN:
                break

    if len(selected) < TARGET_PRODUCTS_PER_RUN:
        selected_asins = {p["asin"] for p in selected}
        for product in cooled_repeat_products[repeat_quota:]:
            if product["asin"] not in selected_asins:
                selected.append(product)
                selected_asins.add(product["asin"])
            if len(selected) >= TARGET_PRODUCTS_PER_RUN:
                break

    if len(selected) < TARGET_PRODUCTS_PER_RUN:
        selected_asins = {p["asin"] for p in selected}
        for product in recent_repeat_products:
            if product["asin"] not in selected_asins:
                selected.append(product)
                selected_asins.add(product["asin"])
            if len(selected) >= TARGET_PRODUCTS_PER_RUN:
                break

    today_str = datetime.now().strftime("%Y-%m-%d")
    updated_history = dict(previous_history)

    for product in selected:
        updated_history[product["asin"]] = today_str

    if selected:
        save_products(selected)
        save_product_history(updated_history)
        save_seen_asins(set(updated_history.keys()))

    new_count = sum(1 for p in selected if p["asin"] not in previous_seen_asins)
    cooled_repeat_count = sum(
        1 for p in selected
        if p["asin"] in previous_seen_asins
        and days_since(previous_history.get(p["asin"], "1970-01-01")) >= RECENT_REPEAT_COOLDOWN_DAYS
    )
    recent_repeat_count = len(selected) - new_count - cooled_repeat_count

    print(f"\n  Final product list for today: {len(selected)}")
    print(f"  New products today:          {new_count}")
    print(f"  Old-but-allowed repeats:     {cooled_repeat_count}")
    print(f"  Recent repeats used:         {recent_repeat_count}")
    print(f"  Saved to {PRODUCTS_FILE}")
    print(f"  History saved to {PRODUCT_HISTORY_FILE}")

    return selected

def save_products(products):
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with PRODUCTS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["asin", "name", "url"])
        writer.writeheader()
        for p in products:
            writer.writerow(p)

    print(f"  Product list saved to: {PRODUCTS_FILE}")


def load_products():
    if not PRODUCTS_FILE.exists():
        return []

    products = []
    with PRODUCTS_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("url") and row.get("asin"):
                products.append({
                    "asin": row["asin"].strip(),
                    "name": row.get("name", "").strip(),
                    "url": row["url"].strip(),
                })

    return products


def save_results(results):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_FILE.exists()

    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)

        if not file_exists:
            writer.writeheader()

        for row in results:
            writer.writerow(row)

    with OUTPUT_FILE.open("r", encoding="utf-8") as f:
        total_rows = max(sum(1 for _ in f) - 1, 0)

    print(f"\n  Saved {len(results)} new rows to {OUTPUT_FILE}")
    print(f"  Total records in dataset: {total_rows}")


def run_scraper():
    print("\n" + "=" * 60)
    print("  DealOrDud — Amazon Fake Discount Detector")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Products file: {PRODUCTS_FILE}")
    print(f"  Output file:   {OUTPUT_FILE}")
    print("=" * 60)

    session = build_session()

    print("\n  Building today's product list...")
    products = discover_products(session)

    if not products:
        print("\n  Discovery failed — falling back to previous products.csv")
        products = load_products()

    if not products:
        print("\n  Could not find any products to scrape. Exiting.")
        return

    print(f"\n  Tracking {len(products)} products\n")

    results = []
    success_count = 0
    fail_count = 0

    for i, product in enumerate(products):
        print(f"  [{i + 1}/{len(products)}] {product['name'][:55]}")

        data = scrape_product(session, product)

        if data:
            results.append(data)
            success_count += 1
        else:
            fail_count += 1

        if i < len(products) - 1:
            wait = random.uniform(DELAY_MIN, DELAY_MAX)
            print(f"    Waiting {wait:.1f}s...")
            time.sleep(wait)

    print("\n" + "-" * 60)
    print(f"  Successful result rows collected: {len(results)}")

    if results:
        save_results(results)
    else:
        print("  No successful rows collected, so nothing was appended to price_history.csv")

    fake_count = sum(1 for r in results if r["fake_discount"])
    print(f"\n{'=' * 60}")
    print(f"  Run complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Scraped:      {success_count} / {len(products)} products")
    print(f"  Fake deals:   {fake_count} flagged")
    print(f"  Errors:       {fail_count}")
    print(f"  Dataset:      {OUTPUT_FILE}")
    print(f"{'=' * 60}\n")

if __name__ == "__main__":
    run_scraper()
