import urllib.request, json, time, re, xml.etree.ElementTree as ET, os
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Baselines (Apr 1 2025) ──────────────────────────────────────────────────
BASELINE = {
    "^NSEI": 22679.40, "^BSESN": 73134.32,
    "^GSPC": 5611.85,  "^IXIC": 17449.89,  "^DJI": 41989.96,
    "^FTSE": 8614.00,  "^GDAXI": 22035.00, "^FCHI": 7882.00,
    "^STOXX50E": 5162.00,
    "GC=F": 2100.00,   # Gold futures (USD/oz)
    "CL=F": 71.50,     # WTI Crude (USD/bbl)
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
    "AAPL": 223.19, "MSFT": 378.80, "NVDA": 110.00, "GOOGL": 165.40,
    "AMZN": 197.12, "META": 558.11, "TSLA": 265.00,
    "JPM": 238.24, "BAC": 43.90, "GS": 538.50,
    "XOM": 117.50, "CVX": 156.70, "JNJ": 158.80,
    "UNH": 490.50, "PFE": 24.80, "LMT": 478.20, "RTX": 125.40,
    "ASML.AS": 720.00, "SAP.DE": 254.00, "SHEL.L": 2580.00,
    "NOVN.SW": 87.50, "ROG.SW": 245.00, "SIE.DE": 215.00,
    "MC.PA": 680.00, "AIR.PA": 158.00, "TTE.PA": 58.50,
    "BARC.L": 278.00, "HSBA.L": 782.00,
}

# ── Fixed NSE Patterns (9) ──────────────────────────────────────────────────
NSE_PATTERNS = [
    {"name": "Defense Rerate",    "tickers": ["HAL.NS","BEL.NS"],                               "signal": "positive"},
    {"name": "Commodity/MCX Vol", "tickers": ["MCX.NS"],                                         "signal": "positive"},
    {"name": "IDEA Turnaround",   "tickers": ["IDEA.NS"],                                        "signal": "speculative"},
    {"name": "Pharma Safe-Haven", "tickers": ["SUNPHARMA.NS","CIPLA.NS","DRREDDY.NS"],          "signal": "positive"},
    {"name": "FMCG Safe-Haven",   "tickers": ["HINDUNILVR.NS","ITC.NS"],                        "signal": "positive"},
    {"name": "Paytm Recovery",    "tickers": ["PAYTM.NS"],                                       "signal": "positive"},
    {"name": "OMC Value Trap",    "tickers": ["BPCL.NS","IOC.NS","HINDPETRO.NS"],               "signal": "negative"},
    {"name": "PSU Bank Reversal", "tickers": ["SBIN.NS","BANKBARODA.NS"],                       "signal": "negative"},
    {"name": "IT Earnings Trap",  "tickers": ["HCLTECH.NS","INFY.NS","TCS.NS","TECHM.NS"],     "signal": "negative"},
]

# ── Global sector map for adaptive stocks ───────────────────────────────────
GLOBAL_SECTORS = [
    {"keywords": ["defense","defence","military","war","nato","missile","army","ceasefire","pakistan","china","border"],
     "name": "Defense", "tickers": ["HAL.NS","BEL.NS","LMT","RTX","AIR.PA"]},
    {"keywords": ["oil","crude","opec","petroleum","bpcl","ongc","exxon","shell","energy","refinery"],
     "name": "Oil & Energy", "tickers": ["BPCL.NS","ONGC.NS","XOM","CVX","SHEL.L","TTE.PA"]},
    {"keywords": ["pharma","drug","fda","health","medicine","cipla","pfizer","novartis","pandemic","biotech"],
     "name": "Pharma", "tickers": ["SUNPHARMA.NS","CIPLA.NS","PFE","JNJ","NOVN.SW","ROG.SW"]},
    {"keywords": ["ai","artificial intelligence","chip","semiconductor","nvidia","microsoft","cloud","llm","automation"],
     "name": "Tech / AI", "tickers": ["TCS.NS","INFY.NS","NVDA","MSFT","GOOGL","ASML.AS","SAP.DE"]},
    {"keywords": ["bank","rate","fed","ecb","rbi","repo","inflation","credit","interest","npa","liquidity"],
     "name": "Banking & Rates", "tickers": ["HDFCBANK.NS","SBIN.NS","JPM","BAC","BARC.L","HSBA.L"]},
    {"keywords": ["ev","electric","tesla","auto","automobile","maruti","car","battery","vehicle"],
     "name": "Auto / EV", "tickers": ["MARUTI.NS","TSLA","SIE.DE"]},
    {"keywords": ["gold","silver","safe haven","risk off","vix","dollar","yen","swiss franc"],
     "name": "Safe Haven / Gold", "tickers": ["GC=F","MCX.NS","TITAN.NS"]},
    {"keywords": ["trade","tariff","export","supply chain","wto","dollar","forex","rupee","euro"],
     "name": "Trade / Macro", "tickers": ["RELIANCE.NS","AMZN","MSFT"]},
    {"keywords": ["telecom","5g","airtel","jio","vodafone","spectrum","bharti","broadband"],
     "name": "Telecom", "tickers": ["BHARTIARTL.NS","IDEA.NS"]},
    {"keywords": ["power","renewable","solar","wind","green energy","tatapower","climate","cop","electricity"],
     "name": "Power / Renewables", "tickers": ["TATAPOWER.NS","XOM","TTE.PA"]},
    {"keywords": ["luxury","consumer","fmcg","retail","amazon","meta","spending","hul","itc"],
     "name": "Consumer / FMCG", "tickers": ["HINDUNILVR.NS","ITC.NS","AMZN","META","MC.PA"]},
]

# ── What to Watch signals ────────────────────────────────────────────────────
WATCH_RULES = [
    {"condition": lambda p, b: pct(p.get("GC=F"), b.get("GC=F")) and pct(p.get("GC=F"), b.get("GC=F")) > 5,
     "signal": "Gold up >5% from baseline — risk-off move; watch HDFC Bank, IT sector for pressure"},
    {"condition": lambda p, b: pct(p.get("CL=F"), b.get("CL=F")) and pct(p.get("CL=F"), b.get("CL=F")) < -10,
     "signal": "Crude down >10% — OMC (BPCL/IOC) may rally; input cost relief for India"},
    {"condition": lambda p, b: pct(p.get("CL=F"), b.get("CL=F")) and pct(p.get("CL=F"), b.get("CL=F")) > 10,
     "signal": "Crude up >10% — OMC earnings pressure; inflation risk; watch RBI response"},
    {"condition": lambda p, b: pct(p.get("^NSEI"), b.get("^NSEI")) and pct(p.get("^NSEI"), b.get("^NSEI")) < -5,
     "signal": "Nifty down >5% from baseline — watch for FII selling; support at 21500"},
    {"condition": lambda p, b: pct(p.get("^GSPC"), b.get("^GSPC")) and pct(p.get("^GSPC"), b.get("^GSPC")) < -5,
     "signal": "S&P 500 down >5% — global risk-off; expect Nifty gap-down tomorrow"},
    {"condition": lambda p, b: pct(p.get("NVDA"), b.get("NVDA")) and pct(p.get("NVDA"), b.get("NVDA")) > 15,
     "signal": "NVDA up >15% — AI trade running; watch TCS, Infosys for sentiment lift"},
    {"condition": lambda p, b: pct(p.get("HAL.NS"), b.get("HAL.NS")) and pct(p.get("HAL.NS"), b.get("HAL.NS")) > 10,
     "signal": "HAL up >10% — defense rerate in play; BEL likely to follow"},
]

# ── News ─────────────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "IN": [
        "https://www.livemint.com/rss/markets",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    ],
    "US": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
    ],
    "EU": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
}

STRIP = re.compile(r"<[^>]+>")

def fetch_news():
    """Returns: all_text (list of lowercase strings), headlines_by_region (dict region→list of titles)"""
    all_text = []
    by_region = {"IN": [], "US": [], "EU": []}
    for region, feeds in RSS_FEEDS.items():
        for url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
                for item in list(root.iter("item"))[:8]:
                    title = STRIP.sub("", item.findtext("title", "")).strip()
                    desc  = STRIP.sub("", item.findtext("description", "")).strip()
                    if title:
                        all_text.append((title + " " + desc).lower())
                        if len(by_region[region]) < 4:
                            by_region[region].append(title)
            except Exception as e:
                print(f"Feed error {url}: {e}")
    return all_text, by_region

def extract_themes(all_text):
    """Pick top 5 themes from headlines."""
    combined = " ".join(all_text)
    theme_hits = []
    for sector in GLOBAL_SECTORS:
        hits = [kw for kw in sector["keywords"] if kw in combined]
        if hits:
            theme_hits.append((len(hits), sector["name"], hits[:2]))
    theme_hits.sort(reverse=True)
    return theme_hits[:5]

def active_global_sectors(all_text):
    combined = " ".join(all_text)
    matched = []
    for sector in GLOBAL_SECTORS:
        hits = [kw for kw in sector["keywords"] if kw in combined]
        if hits:
            matched.append({**sector, "hits": hits[:3]})
    return matched[:6] if matched else GLOBAL_SECTORS[:4]

# ── Price ─────────────────────────────────────────────────────────────────────
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

def fmt(v, decimals=1):
    if v is None: return "N/A"
    return f"{'+' if v >= 0 else ''}{v:.{decimals}f}%"

def trend(v):
    if v is None: return "—"
    return "▲" if v > 0 else "▼"

def pattern_status(avg, signal):
    if avg is None: return ("⚪", "NO DATA")
    if signal == "negative":
        if avg < -3:  return ("🔴", "PLAYING OUT")
        if avg <  2:  return ("🟡", "STABILISING")
        return ("🟢", "REVERSED")
    elif signal == "speculative":
        if avg > 10: return ("🚀", "ACCELERATING")
        if avg >  0: return ("🟡", "HOLDING")
        return ("🔴", "REVERSING")
    else:
        if avg >  5: return ("🟢", "RUNNING")
        if avg >  0: return ("🟡", "FADING")
        return ("🔴", "BROKEN")

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Tracker failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    run_ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # 1. News
    print("Fetching news...")
    all_text, headlines_by_region = fetch_news()
    themes = extract_themes(all_text)
    active_sectors = active_global_sectors(all_text)

    # Fixed global stock lists — always fetched and shown
    US_STOCKS = [
        ("AAPL",  "Apple"),
        ("MSFT",  "Microsoft"),
        ("NVDA",  "Nvidia"),
        ("GOOGL", "Alphabet"),
        ("AMZN",  "Amazon"),
        ("META",  "Meta"),
        ("TSLA",  "Tesla"),
        ("JPM",   "JPMorgan"),
        ("XOM",   "ExxonMobil"),
        ("LMT",   "Lockheed"),
    ]
    EU_STOCKS = [
        ("ASML.AS", "ASML"),
        ("SAP.DE",  "SAP"),
        ("SIE.DE",  "Siemens"),
        ("AIR.PA",  "Airbus"),
        ("MC.PA",   "LVMH"),
        ("SHEL.L",  "Shell"),
        ("NOVN.SW", "Novartis"),
        ("ROG.SW",  "Roche"),
        ("BARC.L",  "Barclays"),
        ("HSBA.L",  "HSBC"),
    ]

    # 2. Prices — collect all tickers we need
    macro_tickers  = ["^NSEI","^BSESN","^GSPC","^IXIC","^DJI","^FTSE","^GDAXI","^FCHI","^STOXX50E","GC=F","CL=F"]
    nse_tickers    = list({t for p in NSE_PATTERNS for t in p["tickers"]})
    adaptive_tickers = list({t for s in active_sectors for t in s["tickers"]})
    fixed_global   = [t for t, _ in US_STOCKS + EU_STOCKS]
    all_tickers    = list(set(macro_tickers + nse_tickers + adaptive_tickers + fixed_global))

    print(f"Fetching {len(all_tickers)} prices...")
    prices = {}
    for t in all_tickers:
        prices[t] = get_price(t)
        time.sleep(0.2)

    # ── Section 1: Today's Key Themes ──────────────────────────────────────
    theme_lines = []
    for _, name, hits in themes:
        theme_lines.append(f"- **{name}** _(triggers: {', '.join(hits)})_")
    if not theme_lines:
        theme_lines = ["- No dominant theme detected today"]

    # ── Section 2: Macro Snapshot ──────────────────────────────────────────
    def macro_row(ticker, label, currency="", decimals=0):
        p = prices.get(ticker)
        r = pct(p, BASELINE.get(ticker))
        price_str = f"{currency}{p:,.{decimals}f}" if p else "N/A"
        return f"| {label} | {price_str} | {fmt(r)} | {trend(r)} |"

    macro_rows = "\n".join([
        macro_row("^NSEI",     "🇮🇳 Nifty 50"),
        macro_row("^GSPC",     "🇺🇸 S&P 500"),
        macro_row("^FTSE",     "🇬🇧 FTSE 100"),
        macro_row("^GDAXI",    "🇩🇪 DAX"),
        macro_row("GC=F",      "🥇 Gold",  "$", 0),
        macro_row("CL=F",      "🛢️ WTI Crude", "$", 1),
    ])

    # ── Section 3: NSE Pattern Health ─────────────────────────────────────
    pattern_rows = []
    for p in NSE_PATTERNS:
        rets = [pct(prices.get(t), BASELINE.get(t)) for t in p["tickers"] if prices.get(t) and BASELINE.get(t)]
        avg  = sum(rets)/len(rets) if rets else None
        icon, label = pattern_status(avg, p["signal"])
        lead = p["tickers"][0]
        lp   = prices.get(lead)
        price_str = f"₹{lp:.0f}" if lp else "N/A"
        pattern_rows.append(f"| {icon} {p['name']} | {price_str} | {fmt(pct(lp, BASELINE.get(lead)))} | {label} |")

    # ── Section 4: Global Stocks in Focus ──────────────────────────────────
    def price_fmt(ticker, p_val):
        if p_val is None: return "N/A"
        if ticker.endswith(".NS"):  return f"₹{p_val:,.0f}"
        if ticker.endswith(".L"):   return f"p{p_val:,.0f}"
        if "=F" in ticker:          return f"${p_val:,.1f}"
        return f"${p_val:,.2f}"

    def stock_signal(r):
        if r is None:   return ("⚪", "NO DATA")
        if r > 10:      return ("🟢", "STRONG BUY")
        if r >  3:      return ("🟢", "BUY")
        if r > -3:      return ("🟡", "HOLD")
        if r > -10:     return ("🔴", "SELL")
        return                 ("🔴", "STRONG SELL")

    def stock_row(ticker, label):
        p_val = prices.get(ticker)
        r     = pct(p_val, BASELINE.get(ticker))
        sig_icon, sig_label = stock_signal(r)
        return f"| {label} | {price_fmt(ticker, p_val)} | {fmt(r)} | {sig_icon} {sig_label} |"

    # Adaptive: news-driven highlights (deduplicated, exclude NSE-only tickers)
    adaptive_rows = []
    seen_adaptive = set()
    for s in active_sectors:
        for ticker in s["tickers"]:
            if ticker in seen_adaptive or ticker.endswith(".NS"):
                continue
            seen_adaptive.add(ticker)
            p_val = prices.get(ticker)
            r     = pct(p_val, BASELINE.get(ticker))
            name  = ticker.replace(".AS","").replace(".DE","").replace(".PA","").replace(".L","").replace(".SW","")
            sig_icon, sig_label = stock_signal(r)
            adaptive_rows.append(
                f"| {name} | {s['name']} | {price_fmt(ticker, p_val)} | {fmt(r)} | {sig_icon} {sig_label} |"
            )

    # Fixed US stocks table
    us_rows   = [stock_row(t, label) for t, label in US_STOCKS]
    # Fixed EU stocks table
    eu_rows   = [stock_row(t, label) for t, label in EU_STOCKS]

    # ── Section 5: What to Watch Tomorrow ──────────────────────────────────
    watch_signals = []
    for rule in WATCH_RULES:
        try:
            if rule["condition"](prices, BASELINE):
                watch_signals.append(f"- ⚠️ {rule['signal']}")
        except:
            pass
    # Always add a news-derived watch signal
    for _, name, hits in themes[:2]:
        watch_signals.append(f"- 👁 **{name}** in focus — monitor related stocks at open")
    if not watch_signals:
        watch_signals = ["- No major alerts — steady market conditions"]

    # ── Section 6: News Digest ─────────────────────────────────────────────
    flag = {"IN": "🇮🇳", "US": "🇺🇸", "EU": "🇪🇺"}
    news_sections = []
    for region, items in headlines_by_region.items():
        if items:
            bullets = "\n".join(f"- {h}" for h in items[:4])
            news_sections.append(f"### {flag[region]} {region}\n{bullets}")

    # ── Assemble .md ────────────────────────────────────────────────────────
    NL = "\n"
    news_block = "\n\n".join(news_sections)

    adaptive_block = (
        f"### 📡 News-Adaptive Highlights\n\n"
        f"| Ticker | Theme | Price | vs Apr 1 | Signal |\n"
        f"|---|---|---|---|---|\n"
        f"{NL.join(adaptive_rows)}\n"
    ) if adaptive_rows else ""

    md = (
        f"# 📊 Vest Market Tracker — {today_str}\n"
        f"_Run: {run_ts}_\n\n"
        f"---\n\n"
        f"## 🔴 Today's Key Themes\n\n"
        f"{NL.join(theme_lines)}\n\n"
        f"---\n\n"
        f"## 📊 Macro Snapshot\n\n"
        f"| Index / Asset | Price | vs Apr 1 | |\n"
        f"|---|---|---|---|\n"
        f"{macro_rows}\n\n"
        f"---\n\n"
        f"## 🟢 NSE Pattern Health\n\n"
        f"| Pattern | Lead Stock | vs Apr 1 | Status |\n"
        f"|---|---|---|---|\n"
        f"{NL.join(pattern_rows)}\n\n"
        f"---\n\n"
        f"## 🌍 Global Stocks in Focus\n\n"
        f"{adaptive_block}\n"
        f"### 🇺🇸 US Stocks\n\n"
        f"| Stock | Price | vs Apr 1 | Signal |\n"
        f"|---|---|---|---|\n"
        f"{NL.join(us_rows)}\n\n"
        f"### 🇪🇺 European Stocks\n\n"
        f"| Stock | Price | vs Apr 1 | Signal |\n"
        f"|---|---|---|---|\n"
        f"{NL.join(eu_rows)}\n\n"
        f"---\n\n"
        f"## 👀 What to Watch Tomorrow\n\n"
        f"{NL.join(watch_signals)}\n\n"
        f"---\n\n"
        f"## 📰 News Digest\n\n"
        f"{news_block}\n\n"
        f"---\n"
        f"_Vest · Global Market Tracker · news-adaptive · {run_ts}_\n"
    )

    print(md)
    summary = f"📊 Vest Market Tracker {today_str} — {len(themes)} themes · {len(active_sectors)} sectors in focus"
    publish(TG_TOKEN, TG_CHAT_ID, md, "market-tracker", summary)
    print("Done.")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    send_error(e)
    raise
