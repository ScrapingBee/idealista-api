"""Idealista search results and listing pages as typed records.

Verified live on 2026-10-29 against idealista.com (Spain), rentals in
Valencia: search page 2 and listing 107904735.

Idealista sits behind DataDome. Every lower tier failed in testing and
Auto-Mode climbed to stealth each time, so this sets stealth_proxy directly:
75 credits per page, and failed calls are not billed.
Set SCRAPINGBEE_API_KEY in your environment before running.
"""

import json
import os
import re
import sys

import requests

API = "https://app.scrapingbee.com/api/v1/"
HEADERS = {"Authorization": f"Bearer {os.environ['SCRAPINGBEE_API_KEY']}"}
SITE = "https://www.idealista.com"

SEARCH_RULES = {
    "heading": "#h1-container__text",
    "listings": {
        "selector": "article.item[data-element-id]",
        "type": "list",
        "output": {
            "id": {"selector": "article", "output": "@data-element-id"},
            "professional": {"selector": "article", "output": "@data-is-professional-ad"},
            "title": "a.item-link",
            "href": {"selector": "a.item-link", "output": "@href"},
            "price": "span.item-price",
            # Unlabelled chips in no fixed order: "3 bed.", "122 m²",
            # "6th floor exterior with lift", "Parking included", "5 hours".
            "chips": {"selector": "span.item-detail", "type": "list"},
            "description": "div.item-description",
            "tags": {"selector": "span.listing-tags", "type": "list"},
        },
    },
}

DETAIL_RULES = {
    "title": ".main-info__title-main",
    "area": ".main-info__title-minor",
    "price": ".info-data-price",
    "features": {"selector": ".details-property_features li", "type": "list"},
    "location": {"selector": ".header-map-list", "type": "list"},
    "advertiser": ".advertiser-name",
    "updated": ".stats-text",
    "description": ".comment",
}


def _get(url, rules):
    params = {"url": url, "stealth_proxy": "true", "extract_rules": json.dumps(rules)}
    # A 500 from ScrapingBee means Idealista timed out or refused (408 and
    # 520 in testing). It is not billed, so it is worth two more tries.
    for _ in range(3):
        r = requests.get(API, headers=HEADERS, params=params, timeout=200)
        if r.status_code != 500:
            break
    r.raise_for_status()
    return r.json(), r.headers.get("spb-cost")


def _int(text):
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _classify(chips):
    """Sort the unlabelled chips into fields by their wording."""
    out = {"bedrooms": None, "size_m2": None, "floor": None, "parking": False, "extra": []}
    for chip in chips or []:
        low = chip.lower()
        if low.endswith("bed.") or low == "studio":
            out["bedrooms"] = 0 if low == "studio" else _int(chip)
        elif "m²" in chip:
            out["size_m2"] = _int(chip)
        elif "floor" in low or "ground" in low:
            out["floor"] = chip
        elif "parking" in low:
            out["parking"] = True
        else:
            out["extra"].append(chip)
    return out


def search_page(path, page=1):
    """One results page, 30 listings, 75 credits.

    path looks like /en/alquiler-viviendas/valencia-valencia/ (rent) or
    /en/venta-viviendas/valencia-valencia/ (sale). Page 2 onwards appends
    pagina-N.htm, which is the link Idealista's own pager uses.
    """
    url = SITE + path + (f"pagina-{page}.htm" if page > 1 else "")
    data, cost = _get(url, SEARCH_RULES)
    rows = []
    for item in data.get("listings", []):
        chips = _classify(item.get("chips"))
        price = _int(item.get("price"))
        rows.append(
            {
                "id": item.get("id"),
                "url": SITE + item["href"] if item.get("href") else None,
                "title": item.get("title"),
                "price_eur": price,
                "per_month": "/month" in (item.get("price") or ""),
                "bedrooms": chips["bedrooms"],
                "size_m2": chips["size_m2"],
                "eur_per_m2": round(price / chips["size_m2"], 2) if price and chips["size_m2"] else None,
                "floor": chips["floor"],
                "parking": chips["parking"],
                "extra": chips["extra"],
                "professional": item.get("professional") == "true",
                "tags": item.get("tags") or [],
            }
        )
    return {"heading": data.get("heading"), "credits": cost, "rows": rows}


def listing(listing_id):
    """One listing page, 75 credits. Features arrive as a flat list of strings."""
    data, cost = _get(f"{SITE}/en/inmueble/{listing_id}/", DETAIL_RULES)
    features = data.get("features") or []

    def pick(pattern):
        for f in features:
            m = re.search(pattern, f, re.I)
            if m:
                return m.group(1)
        return None

    return {
        "credits": cost,
        "title": data.get("title"),
        "area": data.get("area"),
        "price_eur": _int(data.get("price")),
        "built_m2": _int(pick(r"([\d.,]+) m² built")),
        "bedrooms": _int(pick(r"(\d+) bedrooms?")),
        "bathrooms": _int(pick(r"(\d+) bathrooms?")),
        "energy_kwh_m2_year": pick(r"Consumption: ([\d.,]+) kWh"),
        "emissions_kg_co2_m2_year": pick(r"Emissions: ([\d.,]+) kg"),
        "location_path": data.get("location") or [],
        "advertiser": data.get("advertiser"),
        "updated": data.get("updated"),
        "features": features,
        "description": (data.get("description") or "").strip(),
    }


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/en/alquiler-viviendas/valencia-valencia/"

    page = search_page(path, page=2)
    print(f"{page['heading']}: {len(page['rows'])} listings on this page, {page['credits']} credits")
    for r in page["rows"][:5]:
        print(f"  {r['id']}  {r['price_eur']} EUR  {r['bedrooms']} bed  {r['size_m2']} m2  "
              f"{r['eur_per_m2']} EUR/m2  {r['floor']}")

    first = page["rows"][0]["id"]
    d = listing(first)
    print(f"\n{d['title']} ({d['area']}), {d['credits']} credits")
    print(f"  {d['price_eur']} EUR, {d['built_m2']} m2 built, {d['bedrooms']} bed, {d['bathrooms']} bath")
    print(f"  energy {d['energy_kwh_m2_year']} kWh/m2/yr, emissions {d['emissions_kg_co2_m2_year']} kg/m2/yr")
    print(f"  {' > '.join(d['location_path'])}")
    print(f"  {d['advertiser']}, {d['updated']}")
