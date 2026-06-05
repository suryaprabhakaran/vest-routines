import urllib.request, json, time, re, xml.etree.ElementTree as ET, os
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Baselines (Apr 1 2025) ──────────────────────────────────────────────────
BASELINE = {
    # India indices
    "^NSEI": 22679.40, "^BSESN": 73134.32,
    # India stocks
    "RELIANCE.NS": 1369.20, "BPCL.NS": 281.25, "IOC.NS": 135.72,
    "HINDPETRO.NS": 335.55, "ONGC.NS": 288.05, "HDFCBANK.NS": 742.25,
    "SBIN.NS": 1017.80, "ICICIBANK.NS": 1212.70, "AXISBANK.NS": 1193.10,
    "KOTAKBANK.NS": 356.05, "TCS.NS": 2408.20, "INFY.NS": 1275.70,
    "WIPRO.NS": 191.18, "TECHM.NS": 1404.50, "HCLTECH.NS": 1354.40,
    "SUNPHARMA.NS": 1728.50, "DRREDDY.NS": 1209.60, "CIPLA.NS": 1195.90,
    "MARUTI.NS": 12509.00, "BHARTIARTL.NS": 1781.90, "IDEA.NS": 8.64,
    "HAL.NS": 3670.80, "BEL.NS": 418.70, "HINDUNILVR.NS": 2064.70,
    "ITC.NS": 291.70, "TITAN.NS": 4065.50, "TATAPOWER.NS": 380.20,
    "PAYTM.NS": 997.10, "MCX.NS": 2469.70, "BANKBARODA.NS": 252.03,
    # US indices
    "^GSPC": 5611.85, "^IXIC": 17449.89, "^DJI": 41989.96,
    # US stocks
    "AAPL": 223.19, "MSFT": 378.80, "NVDA": 110.00, "GOOGL": 165.40,
    "AMZN": 197.12, "META": 558.11, "TSLA": 265.00, "JPM": 238.24,
    "BAC": 43.90, "GS": 538.50, "XOM": 117.50, "CVX": 156.70,
    "JNJ": 158.80, "UNH": 490.50, "PFE": 24.80, "LMT": 478.20,
    "RTX": 125.40, "INTC": 20.50,
    # European indices
    "^STOXX50E": 5162.00, "^FTSE": 8614.00, "^GDAXI": 22035.00, "^FCHI": 7882.00,
    # European stocks (Yahoo tickers)
    "ASML.AS": 720.00, "SAP.DE": 254.00, "SHEL.L": 2580.00,
    "NOVN.SW": 87.50, "ROG.SW": 245.00, "SIE.DE": 215.00,
    "MC.PA": 680.00, "AIR.PA": 158.00, "TTE.PA": 58.50,
    "BARC.L": 278.00, "HSBA.L": 782.00,
}

# ── Sector map: keyword → tickers ─────────────────────────────────────────
# Each entry covers one thematic pattern; tickers span all markets as relevant
SECTOR_MAP = [
    {
        "keywords": ["defense","defence","military","missile","army","navy","war","ceasefire","pakistan","china","nato","ukraine","russia","weapons","hal","bel","drdo","lockheed","raytheon"],
        "name": "Defense / Geopolitics",
        "tickers": {"IN": ["HAL.NS","BEL.NS"], "US": ["LMT","RTX"], "EU": ["AIR.PA"]},
        "signal": "positive",
    },
    {
        "keywords": ["oil","crude","opec","petroleum","bpcl","ioc","hpcl","ongc","exxon","chevron","shell","totalenergies","refinery","petrol","diesel","energy"],
        "name": "Oil & Energy",
        "tickers": {"IN": ["BPCL.NS","IOC.NS","ONGC.NS"], "US": ["XOM","CVX"], "EU": ["SHEL.L","TTE.PA"]},
        "signal": "negative",
    },
    {
        "keywords": ["pharma","drug","fda","usfda","health","medicine","cipla","sunpharma","drreddy","pfizer","johnson","novartis","roche","pandemic","biotech"],
        "name": "Pharma / Healthcare",
        "tickers": {"IN": ["SUNPHARMA.NS","CIPLA.NS","DRREDDY.NS"], "US": ["JNJ","PFE","UNH"], "EU": ["NOVN.SW","ROG.SW"]},
        "signal": "positive",
    },
    {
        "keywords": ["it","software","tech","ai","artificial intelligence","chip","semiconductor","nvidia","microsoft","google","apple","infosys","tcs","wipro","hcltech","automation","cloud","quantum"],
        "name": "Tech / AI / Semis",
        "tickers": {"IN": ["TCS.NS","INFY.NS","HCLTECH.NS"], "US": ["NVDA","MSFT","GOOGL","AAPL","INTC"], "EU": ["ASML.AS","SAP.DE"]},
        "signal": "positive",
    },
    {
        "keywords": ["bank","rate","fed","ecb","rbi","repo","interest","inflation","credit","npa","hdfc","sbi","icici","jpmorgan","goldman","barclays","hsbc","liquidity"],
        "name": "Banking & Rates",
        "tickers": {"IN": ["HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","BANKBARODA.NS"], "US": ["JPM","BAC","GS"], "EU": ["BARC.L","HSBA.L"]},
        "signal": "positive",
    },
    {
        "keywords": ["ev","electric vehicle","tesla","auto","automobile","maruti","car","suv","vehicle","battery","charging"],
        "name": "Auto / EV",
        "tickers": {"IN": ["MARUTI.NS","TATAPOWER.NS"], "US": ["TSLA"], "EU": ["SIE.DE"]},
        "signal": "positive",
    },
    {
        "keywords": ["trade","tariff","export","import","wto","supply chain","manufacturing","dollar","euro","rupee","currency","forex"],
        "name": "Trade / Macro",
        "tickers": {"IN": ["RELIANCE.NS","^NSEI"], "US": ["AMZN","^GSPC"], "EU": ["^STOXX50E"]},
        "signal": "positive",
    },
    {
        "keywords": ["fmcg","consumer","hul","hindustan unilever","itc","meta","amazon","retail","luxury","titan","monsoon","rural","spending"],
        "name": "Consumer / FMCG",
        "tickers": {"IN": ["HINDUNILVR.NS","ITC.NS","TITAN.NS"], "US": ["AMZN","META"], "EU": ["MC.PA"]},
        "signal": "positive",
    },
    {
        "keywords": ["telecom","5g","airtel","jio","vodafone","bharti","spectrum","broadband"],
        "name": "Telecom",
        "tickers": {"IN": ["BHARTIARTL.NS","IDEA.NS"], "US": [], "EU": []},
        "signal": "positive",
    },
    {
        "keywords": ["power","renewable","solar","wind","green energy","tatapower","electricity","grid","climate","cop"],
        "name": "Power / Renewables",
        "tickers": {"IN": ["TATAPOWER.NS","ONGC.NS"], "US": ["XOM"], "EU": ["TTE.PA","SIE.DE"]},
        "signal": "positive",
    },
]

# ── News fetch ──────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "India":  ["https://www.livemint.com/rss/markets",
               "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"],
    "US":     ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
               "https://feeds.marketwatch.com/marketwatch/topstories/"],
    "Europe": ["https://feeds.bbci.co.uk/news/business/rss.xml",
               "https://www.ft.com/rss/home/uk"],
}

def fetch_headlines():
    strip = re.compile(r"<[^>]+>")
    all_text = []
    display = {"India": [], "US": [], "Europe": []}
    for region, feeds in RSS_FEEDS.items():
        for feed_url in feeds:
            try:
                req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
                for item in list(root.iter("item"))[:6]:
                    title = strip.sub("", item.findtext("title", "")).strip()
                    desc = strip.sub("", item.findtext("description", "")).strip()
                    if title:
                        all_text.append((title + " " + desc).lower())
                        if len(display[region]) < 3:
                            display[region].append(f"• {title}")
            except Exception as e:
                print(f"Feed error {feed_url}: {e}")
    return all_text, display

def match_sectors(all_text):
    combined = " ".join(all_text)
    matched = []
    for sector in SECTOR_MAP:
        hits = [kw for kw in sector["keywords"] if kw in combined]
        if hits:
            matched.append({**sector, "hits": hits[:3]})
    return matched[:7] if matched else SECTOR_MAP[:4]

# ── Price fetch ─────────────────────────────────────────────────────────────
def get_price(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        meta = d["chart"]["result"][0]["meta"]
        return meta.get("regularMarketPrice") or meta.get("previousClose")
    except:
        return None

def pct(today, base):
    if today and base:
        return (today - base) / base * 100
    return None

def fmt(v):
    if v is None: return "N/A"
    return f"{'+' if v >= 0 else ''}{v:.1f}%"

def score_status(avg, signal):
    if avg is None: return "⚪"
    if signal == "negative":
        return "🔴" if avg < -3 else ("🟡" if avg < 2 else "🟢")
    else:
        return "🟢" if avg > 5 else ("🟡" if avg > 0 else "🔴")

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Tracker failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ─────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    print("Fetching headlines...")
    all_text, display_headlines = fetch_headlines()
    active_sectors = match_sectors(all_text)
    print(f"Active: {[s['name'] for s in active_sectors]}")

    # Collect all tickers needed
    core_indices = ["^NSEI", "^BSESN", "^GSPC", "^IXIC", "^STOXX50E", "^FTSE", "^GDAXI"]
    needed = set(core_indices)
    for s in active_sectors:
        for tlist in s["tickers"].values():
            needed.update(tlist)
    needed.discard("")

    print(f"Fetching {len(needed)} prices...")
    prices = {}
    for t in needed:
        prices[t] = get_price(t)
        time.sleep(0.25)

    # ── Index summary ──
    def idx_line(ticker, label):
        p = prices.get(ticker)
        r = pct(p, BASELINE.get(ticker))
        return f"*{label}:* {p:,.0f} ({fmt(r)} vs Apr 1)" if p else f"*{label}:* N/A"

    index_block = "\n".join([
        "🇮🇳 " + idx_line("^NSEI",     "Nifty 50"),
        "🇮🇳 " + idx_line("^BSESN",    "Sensex"),
        "🇺🇸 " + idx_line("^GSPC",     "S&P 500"),
        "🇺🇸 " + idx_line("^IXIC",     "Nasdaq"),
        "🇪🇺 " + idx_line("^STOXX50E", "Euro Stoxx 50"),
        "🇬🇧 " + idx_line("^FTSE",     "FTSE 100"),
        "🇩🇪 " + idx_line("^GDAXI",    "DAX"),
    ])

    # ── Pattern block ──
    pattern_lines = []
    for s in active_sectors:
        region_parts = []
        for region, tlist in s["tickers"].items():
            tlist = [t for t in tlist if t]
            if not tlist:
                continue
            rets = [pct(prices.get(t), BASELINE.get(t)) for t in tlist if prices.get(t) and BASELINE.get(t)]
            avg = sum(rets) / len(rets) if rets else None
            lead = tlist[0]
            lp = prices.get(lead)
            status = score_status(avg, s["signal"])
            flag = {"IN": "🇮🇳", "US": "🇺🇸", "EU": "🇪🇺"}.get(region, "")
            name = lead.replace(".NS", "").replace(".AS", "").replace(".DE", "").replace(".PA", "").replace(".L", "").replace(".SW", "")
            price_str = f"₹{lp:.0f}" if region == "IN" and lp else (f"${lp:.1f}" if region == "US" and lp else (f"€{lp:.1f}" if lp else "N/A"))
            region_parts.append(f"{flag}{status} {name} {price_str} ({fmt(avg)})")
        triggers = ", ".join(s.get("hits", []))
        if region_parts:
            pattern_lines.append(f"*{s['name']}* — _{triggers}_\n  " + "  ".join(region_parts))

    # ── Headlines ──
    news_block = ""
    for region, lines in display_headlines.items():
        if lines:
            flag = {"India": "🇮🇳", "US": "🇺🇸", "Europe": "🇪🇺"}.get(region, "")
            news_block += f"\n{flag} *{region}*\n" + "\n".join(lines[:2]) + "\n"

    md_content = f"""# Vest Global Market Tracker — {today_str}

## Indices

| Index | Price | vs Apr 1 |
|---|---|---|
""" + "\n".join(
        f"| {label} | {prices.get(ticker, 'N/A')} | {fmt(pct(prices.get(ticker), BASELINE.get(ticker)))} |"
        for ticker, label in [
            ("^NSEI","🇮🇳 Nifty 50"),("^BSESN","🇮🇳 Sensex"),
            ("^GSPC","🇺🇸 S&P 500"),("^IXIC","🇺🇸 Nasdaq"),
            ("^STOXX50E","🇪🇺 Euro Stoxx 50"),("^FTSE","🇬🇧 FTSE 100"),("^GDAXI","🇩🇪 DAX"),
        ]
    ) + f"""

## News-Driven Patterns ({len(active_sectors)} active)

""" + "\n\n".join(
        f"### {s['name']}\n**News triggers:** {', '.join(s.get('hits', []))}\n\n" +
        "\n".join(
            f"- **{region}** {' · '.join(t.replace('.NS','').replace('.AS','').replace('.DE','').replace('.PA','').replace('.L','').replace('.SW','') for t in tlist if t)}"
            for region, tlist in s["tickers"].items() if tlist
        )
        for s in active_sectors
    ) + f"""

## Headlines

""" + "\n".join(
        f"### {flag} {region}\n" + "\n".join(lines)
        for region, lines in display_headlines.items()
        if lines
        for flag in [{"India":"🇮🇳","US":"🇺🇸","Europe":"🇪🇺"}.get(region,"")]
    ) + """

---
_Vest · Global Tracker · news-adaptive_
"""

    summary = f"📊 Vest Global Tracker {today_str} — {len(active_sectors)} patterns active"
    print(md_content)
    publish(TG_TOKEN, TG_CHAT_ID, md_content, "market-tracker", summary)
    print("Sent successfully.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
