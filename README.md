# Idealista API

<p align="center">
  <a href="https://www.scrapingbee.com/">
    <img src="REPLACE_WITH_SCREENSHOT_URL" alt="idealista-api" />
  </a>
</p>

[![checks](https://github.com/ScrapingBee/idealista-api/workflows/checks/badge.svg)](https://github.com/ScrapingBee/idealista-api/actions)
[![license](https://img.shields.io/github/license/ScrapingBee/idealista-api.svg)](LICENSE)

Field reference first, code second. This is an [Idealista API](https://www.scrapingbee.com/scrapers/idealista-api/) built on [ScrapingBee](https://www.scrapingbee.com/) for Spanish property listings, and the two tables below are what it returns. Every field was read from live idealista.com pages on 2026-10-29 (Valencia rentals), and each one comes with the selector that produced it, so you can check our work against the page yourself.

## Schema: one row per search result

`search_page()` in [`examples/idealista_listings.py`](examples/idealista_listings.py). 30 rows per results page, 75 credits per page.

| Field | Example | Source on the page |
|---|---|---|
| `id` | `112937303` | `article.item[data-element-id]`, attribute `data-element-id` |
| `url` | `https://www.idealista.com/en/inmueble/112937303/` | `a.item-link` `href` |
| `title` | `Flat / apartment in Calle d'Ángel Villena, Ciutat de les Arts i de les Ciencies, València` | `a.item-link` text |
| `price_eur` | `2100` | `span.item-price`, digits only |
| `per_month` | `true` | `€/month` suffix inside the price span (rentals) |
| `bedrooms` | `3` | `span.item-detail` chip ending in `bed.` |
| `size_m2` | `122` | `span.item-detail` chip containing `m²` |
| `eur_per_m2` | `17.21` | computed, `price_eur / size_m2` |
| `floor` | `6th floor exterior with lift` | `span.item-detail` chip containing `floor` |
| `parking` | `true` | `span.item-detail` chip `Parking included` |
| `extra` | `["5 hours"]` | any chip not matched above |
| `professional` | `true` | `article` attribute `data-is-professional-ad` |
| `tags` | `["Luxury"]` | `span.listing-tags`, also seen: `Short-term rental` |

**The detail chips have no labels and no fixed order.** One card returned `["Parking included", "3 bed.", "122 m²", "6th floor exterior with lift", "5 hours"]`, the next `["4 bed.", "180 m²", "6th floor exterior with lift"]`. Position based parsing breaks on the first card with a parking chip. `_classify()` sorts them by wording instead, and anything it does not recognise lands in `extra` rather than being dropped. That is where the listing age (`5 hours`) ends up. When a card has no bedroom chip at all, `bedrooms` is `null`.

## Schema: one record per listing page

`listing(id)` in the same file. 75 credits per listing.

| Field | Example | Source on the page |
|---|---|---|
| `title` | `Flat / apartment for rent in Calle del Hospital` | `.main-info__title-main` |
| `area` | `Sant Francesc, Valencia` | `.main-info__title-minor` |
| `price_eur` | `3250` | `.info-data-price` |
| `built_m2` | `180` | feature `180 m² built` |
| `bedrooms` / `bathrooms` | `4` / `2` | features `4 bedrooms`, `2 bathrooms` |
| `energy_kwh_m2_year` | `91` | feature `Consumption: 91 kWh/m² year` |
| `emissions_kg_co2_m2_year` | `21` | feature `Emissions: 21 kg CO2/m² year` |
| `location_path` | `["Calle del Hospital", "Subdistrict Sant Francesc", "District Ciutat Vella", "Valencia", "Valencia"]` | `.header-map-list` items |
| `advertiser` | `aProperties Real Estate Valencia` | `.advertiser-name` |
| `updated` | `Listing updated on 29 October` | `.stats-text` |
| `features` | the full list, 12 strings for that flat | `.details-property_features li` |
| `description` | the advertiser's text | `.comment` |

The `features` list mixes the basic block and the building block into one sequence: `180 m² built`, `4 bedrooms`, `2 bathrooms`, `Second hand/good condition`, `Fitted wardrobes`, `Furnished and with equipped kitchen`, `Individual heating: Electric`, `6th floor exterior`, `With lift`, `Air conditioning`, then the two energy certificate lines. The numeric fields above are pulled out of it with patterns, and the raw list is kept because the rest varies from listing to listing.

`location_path` is the most useful field for analysis. It gives street, subdistrict and district as separate, consistently ordered strings, which the search card only offers as a comma joined title.

## The request

```python
params = {"url": url, "stealth_proxy": "true", "extract_rules": json.dumps(rules)}
requests.get("https://app.scrapingbee.com/api/v1/", headers={"Authorization": f"Bearer {KEY}"}, params=params)
```

Idealista loads a DataDome script on every page (`window.ddjskey` sits at the top of the HTML). With `mode=auto` ScrapingBee tried the cheaper tiers on both page types and settled on the stealth tier each time, so the scripts ask for `stealth_proxy=true` directly and skip the climb. Stealth runs with JavaScript rendering, at 75 credits per successful request.

Two calls out of about ten failed during testing: ScrapingBee returned `500` with Idealista's `408` once and `520` once. Failed requests are not billed, so both scripts retry a `500` up to three times.

## Pagination

Page 1 is the bare search path. Page N appends `pagina-N.htm`, the same link Idealista's own pager uses:

```
https://www.idealista.com/en/alquiler-viviendas/valencia-valencia/
https://www.idealista.com/en/alquiler-viviendas/valencia-valencia/pagina-2.htm
```

The page heading tells you how far to go. `#h1-container__text` read `2,077 houses and flats for rent in Valencia, Spain`, which at 30 per page is 70 pages, 5,250 credits for a full pass over Valencia rentals. Swap `alquiler-viviendas` for `venta-viviendas` for homes for sale.

## A small analysis

[`examples/rent_per_m2.js`](examples/rent_per_m2.js) reads N result pages and groups asking rent per square metre by neighbourhood, taken from the second to last part of the card title. Two pages, 60 listings, 150 credits:

```
60 listings used, 0 skipped, 150 credits
  Russafa                                5  23.33 EUR/m2
  Gran Vía                               4  18.95 EUR/m2
  Playa de la Malvarrosa                 4  17.65 EUR/m2
  El Carme                               4  17.35 EUR/m2
  Sant Francesc                          3  20.94 EUR/m2
```

Sixty listings out of 2,077 is a demonstration of the pipeline, not a market report. Run it with `70` as the page count for the whole city, and use the `location_path` from listing pages if you need districts rather than neighbourhood names parsed from titles.

## Idealista API access versus scraping

Idealista has an official Search API. Keys are issued on request through its developer site, where you describe your project and wait for a decision. If you qualify and the API covers your use, it is the cleaner route. People reach for an Idealista scraper when they need what the public site shows today, across any search a visitor can run, without that approval step. This repo reads public, logged out pages only.

Tested here: idealista.com, Spain, English pages, rentals. The same markup is likely on the Portuguese and Italian sites, but they were not exercised for this README.

Related ScrapingBee real estate endpoints: [Immobiliare scraper](https://www.scrapingbee.com/scrapers/data-analysis-immobiliare/), [SeLoger scraper](https://www.scrapingbee.com/scrapers/seloger-api/), [ImmoScout24 scraper](https://www.scrapingbee.com/scrapers/immoscout24-api/), [Immoweb scraper](https://www.scrapingbee.com/scrapers/immoweb-api/), [Rightmove scraper](https://www.scrapingbee.com/scrapers/rightmove-api/), [Zoopla scraper](https://www.scrapingbee.com/scrapers/zoopla-api/), [Funda scraper](https://www.scrapingbee.com/scrapers/funda-api/), [real estate data API](https://www.scrapingbee.com/scrapers/real-estate-data-api/).

Documentation: [extraction rules](https://www.scrapingbee.com/documentation/data-extraction/), [HTML API and credit costs](https://www.scrapingbee.com/documentation/), [pricing](https://www.scrapingbee.com/pricing/). New accounts get 1,000 free credits, enough for 13 Idealista pages.

## Scope

Public listing and search pages only. Saved searches, favourites, alerts and messaging to advertisers require an account and are out of scope, and scraping under login credentials is prohibited by ScrapingBee's terms of service. Listings contain advertiser names and sometimes agents' details; if you store them, the GDPR applies to you as the controller. Idealista's own terms govern the site.

## FAQ

**How do I scrape Idealista without getting blocked?**
Use ScrapingBee's stealth proxy tier. Classic and premium tiers did not get through in testing; stealth returned every page at 75 credits, and the occasional failure was unbilled.

**How many listings does one request return?**
30 per search results page.

**Can I get the energy certificate?**
Yes, from the listing page. Consumption and emissions are lines in the features list.

**Does the Idealista scraper work for homes for sale?**
Use `/en/venta-viviendas/<city>/`. The card markup is the same; `per_month` will be `false`.

**Is there an official Idealista API?**
Yes, the Search API, with keys granted on request.

## License

MIT. See [LICENSE](LICENSE).
