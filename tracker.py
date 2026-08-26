import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data.json"
REPORT_FILE = ROOT / "index.html"

TRACKED_CURRENCY = "EUR"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def with_currency(url, currency=TRACKED_CURRENCY):
    # Instant Gaming otherwise prices by the requester's geolocated IP
    # (e.g. GitHub Actions runners are US-based -> USD), so the currency
    # must be pinned explicitly to get consistent, comparable history.
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["currency"] = currency
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def fetch_html(url):
    resp = requests.get(with_currency(url), headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_product(page_html):
    soup = BeautifulSoup(page_html, "html.parser")

    sku_meta = soup.select_one('meta[itemprop="sku"]')
    # meta[itemprop="name"] also matches the site-wide og:site_name tag,
    # which has a "property" attribute the actual product name meta lacks.
    name_meta = next(
        (m for m in soup.select('meta[itemprop="name"]') if not m.has_attr("property")),
        None,
    )
    price_meta = soup.select_one('[itemprop="offers"] meta[itemprop="price"]')
    currency_meta = soup.select_one('[itemprop="offers"] meta[itemprop="priceCurrency"]')

    sku = sku_meta["content"].strip() if sku_meta else None
    name = name_meta["content"].strip() if name_meta else None
    price = float(price_meta["content"]) if price_meta else None
    currency = currency_meta["content"].strip() if currency_meta else "EUR"

    if price is None:
        match = re.search(r'"price"\s*:\s*"([\d.]+)"', page_html)
        if match:
            price = float(match.group(1))

    if name is None:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            name = og_title["content"].strip()

    if not sku or price is None or not name:
        raise ValueError("pagina non riconosciuta (struttura del sito cambiata?)")

    return sku, name, price, currency


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"products": []}


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sparkline_svg(prices, width=300, height=60, padding=4):
    if len(prices) == 1:
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
            f'<circle cx="{width / 2}" cy="{height / 2}" r="3" fill="#888"/></svg>'
        )

    lo, hi = min(prices), max(prices)
    span = hi - lo or 1
    n = len(prices)

    def x(i):
        return padding + i * (width - 2 * padding) / (n - 1)

    def y(p):
        return height - padding - (p - lo) * (height - 2 * padding) / span

    points = " ".join(f"{x(i):.1f},{y(p):.1f}" for i, p in enumerate(prices))
    if prices[-1] < prices[0]:
        color = "#2ecc71"
    elif prices[-1] > prices[0]:
        color = "#e74c3c"
    else:
        color = "#888"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    )


def generate_report(data):
    products = sorted(data.get("products", []), key=lambda p: p["name"].lower())
    sections = []

    for p in products:
        history = p["history"]
        currency = p["currency"]
        current = history[-1]["price"]

        delta_html = ""
        if len(history) >= 2:
            diff = current - history[-2]["price"]
            if diff > 0:
                delta_html = f'<span class="up">&#9650; +{diff:.2f} {currency}</span>'
            elif diff < 0:
                delta_html = f'<span class="down">&#9660; {diff:.2f} {currency}</span>'
            else:
                delta_html = '<span class="flat">=</span>'

        rows = "".join(
            f'<tr><td>{h["timestamp"].replace("T", " ")}</td><td>{h["price"]:.2f} {currency}</td></tr>'
            for h in reversed(history)
        )

        sections.append(f"""
        <section class="product">
          <h2><a href="{html.escape(p['url'])}" target="_blank" rel="noopener">{html.escape(p['name'])}</a></h2>
          <div class="current">{current:.2f} {currency} {delta_html}</div>
          {sparkline_svg([h["price"] for h in history])}
          <table>
            <thead><tr><th>Data</th><th>Prezzo</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        """)

    body = "".join(sections) if sections else "<p>Nessun prodotto tracciato ancora.</p>"
    now = datetime.now().isoformat(timespec="seconds").replace("T", " ")

    page = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Instant Gaming - Tracker prezzi</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background:#fafafa; color:#222; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .updated {{ color:#666; font-size:0.9rem; margin-bottom:2rem; }}
  .product {{ background:#fff; border:1px solid #ddd; border-radius:8px; padding:1rem 1.5rem; margin-bottom:1.5rem; }}
  .product h2 {{ margin:0 0 0.5rem; font-size:1.1rem; }}
  .product h2 a {{ color:#222; text-decoration:none; }}
  .current {{ font-size:1.4rem; font-weight:bold; margin-bottom:0.5rem; }}
  .up {{ color:#e74c3c; font-size:0.9rem; font-weight:normal; }}
  .down {{ color:#2ecc71; font-size:0.9rem; font-weight:normal; }}
  .flat {{ color:#888; font-size:0.9rem; font-weight:normal; }}
  table {{ border-collapse: collapse; width:100%; margin-top:0.5rem; font-size:0.9rem; }}
  th, td {{ text-align:left; padding:0.3rem 0.6rem; border-bottom:1px solid #eee; }}
  svg {{ display:block; margin: 0.5rem 0; }}
</style>
</head>
<body>
<h1>Instant Gaming - Tracker prezzi</h1>
<div class="updated">Ultimo aggiornamento: {now}</div>
{body}
</body>
</html>
"""
    REPORT_FILE.write_text(page, encoding="utf-8")


def cmd_add(url):
    data = load_data()
    try:
        page_html = fetch_html(url)
        sku, name, price, currency = parse_product(page_html)
    except Exception as e:
        print(f"Errore: impossibile aggiungere il prodotto ({e})", file=sys.stderr)
        sys.exit(1)

    existing = next((p for p in data["products"] if p["sku"] == sku), None)
    if existing:
        print(f"Prodotto gia' tracciato: {existing['name']} (sku {sku})")
        return

    now = datetime.now().isoformat(timespec="seconds")
    data["products"].append({
        "sku": sku,
        "url": url,
        "name": name,
        "currency": currency,
        "added_at": now,
        "history": [{"timestamp": now, "price": price}],
    })
    save_data(data)
    generate_report(data)
    print(f"Aggiunto: {name} - {price:.2f} {currency}")


def cmd_update():
    data = load_data()
    if not data["products"]:
        print("Nessun prodotto tracciato.")
        return

    now = datetime.now().isoformat(timespec="seconds")
    for product in data["products"]:
        try:
            page_html = fetch_html(product["url"])
            sku, name, price, currency = parse_product(page_html)
        except Exception as e:
            print(f"Saltato {product['name']}: {e}")
            continue
        product["name"] = name
        product["currency"] = currency
        product["history"].append({"timestamp": now, "price": price})

    save_data(data)
    generate_report(data)
    print("Aggiornamento completato.")


def cmd_report():
    data = load_data()
    generate_report(data)
    print(f"Report rigenerato: {REPORT_FILE}")


def cmd_remove(identifier):
    data = load_data()
    key = identifier.strip()
    key_lower = key.lower()

    matches = [
        p for p in data["products"]
        if p["sku"] == key
        or p["url"].rstrip("/") == key.rstrip("/")
        or key_lower in p["name"].lower()
    ]

    if not matches:
        print(f"Nessun prodotto trovato per: {identifier}", file=sys.stderr)
        sys.exit(1)

    if len(matches) > 1:
        options = ", ".join(f"{p['name']} (sku {p['sku']})" for p in matches)
        print(f"Trovati piu' prodotti, specifica meglio (es. lo sku): {options}", file=sys.stderr)
        sys.exit(1)

    product = matches[0]
    data["products"] = [p for p in data["products"] if p["sku"] != product["sku"]]
    save_data(data)
    generate_report(data)
    print(f"Rimosso: {product['name']} (sku {product['sku']})")


def main():
    parser = argparse.ArgumentParser(description="Instant Gaming price tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Aggiungi un prodotto da tracciare")
    p_add.add_argument("url")

    p_remove = sub.add_parser("remove", help="Rimuovi un prodotto tracciato (sku, URL o nome anche parziale)")
    p_remove.add_argument("identifier")

    sub.add_parser("update", help="Aggiorna il prezzo di tutti i prodotti tracciati")
    sub.add_parser("report", help="Rigenera index.html senza fare richieste di rete")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.url)
    elif args.command == "remove":
        cmd_remove(args.identifier)
    elif args.command == "update":
        cmd_update()
    elif args.command == "report":
        cmd_report()


if __name__ == "__main__":
    main()
