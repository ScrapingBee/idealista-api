// Median asking rent per square metre by neighbourhood, from Idealista
// search result pages.
//
// Verified live on 2026-10-29: Valencia rentals, pages 1 and 2.
// Node 18+ (global fetch). Set SCRAPINGBEE_API_KEY before running.
// Cost: 75 credits per page (stealth proxy; lower tiers are blocked).

const API = "https://app.scrapingbee.com/api/v1/";
const SITE = "https://www.idealista.com";

const RULES = {
  rows: {
    selector: "article.item[data-element-id]",
    type: "list",
    output: {
      title: "a.item-link",
      price: "span.item-price",
      chips: { selector: "span.item-detail", type: "list" },
    },
  },
};

const num = (s) => Number(String(s || "").replace(/[^\d]/g, "")) || null;

// "Flat / apartment in Calle del Hospital, Sant Francesc, València"
// The neighbourhood is the second to last comma separated part.
function neighbourhood(title) {
  const parts = String(title || "").split(",").map((p) => p.trim());
  return parts.length >= 2 ? parts[parts.length - 2] : "unknown";
}

async function page(path, n) {
  const target = SITE + path + (n > 1 ? `pagina-${n}.htm` : "");
  const params = new URLSearchParams({
    url: target,
    stealth_proxy: "true",
    extract_rules: JSON.stringify(RULES),
  });
  // ScrapingBee answers 500 when Idealista times out or refuses (408 and 520
  // in testing). Those are not billed, so try up to three times.
  let res;
  for (let attempt = 1; attempt <= 3; attempt++) {
    res = await fetch(`${API}?${params}`, {
      headers: { Authorization: `Bearer ${process.env.SCRAPINGBEE_API_KEY}` },
    });
    if (res.status !== 500) break;
  }
  if (!res.ok) throw new Error(`page ${n}: ${res.status} ${await res.text()}`);
  const { rows = [] } = await res.json();
  return { rows, credits: Number(res.headers.get("spb-cost")) };
}

function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

async function main() {
  const path = process.argv[2] || "/en/alquiler-viviendas/valencia-valencia/";
  const pages = Number(process.argv[3] || 2);

  const groups = new Map();
  let credits = 0;
  let used = 0;
  let skipped = 0;

  for (let n = 1; n <= pages; n++) {
    const { rows, credits: c } = await page(path, n);
    credits += c;
    for (const r of rows) {
      const m2 = num((r.chips || []).find((x) => x.includes("m²")));
      const price = num(r.price);
      if (!m2 || !price) {
        skipped++;
        continue;
      }
      const key = neighbourhood(r.title);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(price / m2);
      used++;
    }
  }

  const table = [...groups.entries()]
    .map(([name, v]) => ({ name, n: v.length, median: median(v) }))
    .sort((a, b) => b.n - a.n || b.median - a.median);

  console.log(`${used} listings used, ${skipped} skipped, ${credits} credits`);
  for (const row of table.slice(0, 12)) {
    console.log(`  ${row.name.padEnd(36)} ${String(row.n).padStart(3)}  ${row.median.toFixed(2)} EUR/m2`);
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
