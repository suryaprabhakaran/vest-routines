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

# ── Global sector map — drives both NSE patterns and global stocks ───────────
# signal: how news about this sector typically moves NSE stocks
#   positive   = good news → stocks go up (buy signal)
#   negative   = bad news  → stocks fall  (sell/avoid)
#   speculative = high volatility, could go either way
GLOBAL_SECTORS = [
    {"name": "Defense / Geopolitics",
     "keywords": ["defense","defence","military","war","nato","missile","army","ceasefire","pakistan","china","border","conflict"],
     "nse": ["HAL.NS","BEL.NS"], "global": ["LMT","RTX","AIR.PA"],
     "signal": "positive"},
    {"name": "Oil & Energy",
     "keywords": ["oil","crude","opec","petroleum","bpcl","ongc","exxon","shell","energy","refinery","petrol","diesel"],
     "nse": ["BPCL.NS","IOC.NS","HINDPETRO.NS","ONGC.NS"], "global": ["XOM","CVX","SHEL.L","TTE.PA"],
     "signal": "negative"},
    {"name": "Pharma / Healthcare",
     "keywords": ["pharma","drug","fda","health","medicine","cipla","pfizer","novartis","pandemic","biotech","hospital"],
     "nse": ["SUNPHARMA.NS","CIPLA.NS","DRREDDY.NS"], "global": ["PFE","JNJ","NOVN.SW","ROG.SW"],
     "signal": "positive"},
    {"name": "Tech / AI",
     "keywords": ["ai","artificial intelligence","chip","semiconductor","nvidia","microsoft","cloud","llm","automation","software","it sector"],
     "nse": ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"], "global": ["NVDA","MSFT","GOOGL","ASML.AS","SAP.DE"],
     "signal": "positive"},
    {"name": "Banking & Rates",
     "keywords": ["bank","rate","fed","ecb","rbi","repo","inflation","credit","interest","npa","liquidity","monetary"],
     "nse": ["HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","BANKBARODA.NS"], "global": ["JPM","BAC","GS","BARC.L","HSBA.L"],
     "signal": "positive"},
    {"name": "Auto / EV",
     "keywords": ["ev","electric vehicle","tesla","auto","automobile","maruti","car","suv","battery","vehicle sales"],
     "nse": ["MARUTI.NS","TATAPOWER.NS"], "global": ["TSLA","SIE.DE"],
     "signal": "positive"},
    {"name": "Safe Haven / Gold",
     "keywords": ["gold","silver","safe haven","risk off","vix","dollar","yen","swiss franc","recession","fear"],
     "nse": ["MCX.NS","TITAN.NS"], "global": ["GC=F"],
     "signal": "positive"},
    {"name": "Trade / Macro",
     "keywords": ["trade","tariff","export","import","supply chain","wto","dollar","forex","rupee","euro","gdp","growth"],
     "nse": ["RELIANCE.NS","MARUTI.NS"], "global": ["AMZN","MSFT"],
     "signal": "positive"},
    {"name": "Telecom",
     "keywords": ["telecom","5g","airtel","jio","vodafone","spectrum","bharti","broadband","vi"],
     "nse": ["BHARTIARTL.NS","IDEA.NS"], "global": [],
     "signal": "speculative"},
    {"name": "Power / Renewables",
     "keywords": ["power","renewable","solar","wind","green energy","tatapower","climate","cop","electricity","grid"],
     "nse": ["TATAPOWER.NS","ONGC.NS"], "global": ["XOM","TTE.PA"],
     "signal": "positive"},
    {"name": "Consumer / FMCG",
     "keywords": ["fmcg","consumer","hul","hindustan unilever","itc","rural","monsoon","retail","spending","kirana"],
     "nse": ["HINDUNILVR.NS","ITC.NS","TITAN.NS"], "global": ["AMZN","META","MC.PA"],
     "signal": "positive"},
    {"name": "PSU / Government Spend",
     "keywords": ["psu","government","public sector","budget","capex","infra","infrastructure","railway","defence spend"],
     "nse": ["HAL.NS","BEL.NS","SBIN.NS","BANKBARODA.NS","ONGC.NS"], "global": [],
     "signal": "positive"},
]

# WATCH_RULES replaced by dynamic build_watch_signals() below

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
    # always return at least 4 sectors even on quiet news days
    return matched[:8] if matched else GLOBAL_SECTORS[:4]

def build_nse_patterns(active_sectors):
    """Build dynamic NSE patterns from today's active sectors."""
    patterns = []
    seen = set()
    for s in active_sectors:
        nse_tickers = [t for t in s["nse"] if t not in seen]
        if not nse_tickers:
            continue
        seen.update(nse_tickers)
        patterns.append({
            "name": s["name"],
            "tickers": nse_tickers,
            "signal": s["signal"],
            "triggers": s.get("hits", []),
        })
    return patterns

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

def build_watch_signals(prices, active_sectors, themes, nse_patterns):
    """
    Build tomorrow's watch signals fully from today's live data:
    - Actual price moves (what moved the most today)
    - Active news themes (what's dominating headlines)
    - Pattern health (what's breaking out or breaking down)
    - Cross-market spillover logic (US close → India open)
    """
    signals = []

    # ── 1. Biggest movers today (top 3 by absolute % vs baseline) ──────────
    movers = []
    for ticker, p_val in prices.items():
        r = pct(p_val, BASELINE.get(ticker))
        if r is not None and ticker not in ("GC=F","CL=F"):
            name = ticker.replace(".NS","").replace(".AS","").replace(".DE","").replace(".PA","").replace(".L","").replace(".SW","")
            movers.append((abs(r), r, name, ticker))
    movers.sort(reverse=True)
    for _, r, name, ticker in movers[:3]:
        direction = f"up {r:+.1f}%" if r > 0 else f"down {r:.1f}%"
        if ticker.endswith(".NS"):
            signals.append(f"- 📈 **{name}** is {direction} vs Apr 1 baseline — watch for continuation or mean-reversion at open")
        elif ticker in ("^GSPC","^IXIC","^DJI"):
            nifty_r = pct(prices.get("^NSEI"), BASELINE.get("^NSEI"))
            lag = "lagging" if nifty_r and abs(nifty_r) < abs(r)/2 else "tracking"
            signals.append(f"- 🌐 **{name}** {direction} — Nifty is {lag}; watch for catch-up at tomorrow's open")
        elif ticker in ("^FTSE","^GDAXI","^STOXX50E"):
            signals.append(f"- 🇪🇺 **{name}** {direction} — European sentiment may carry into Asian open")

    # ── 2. Macro cross-signals (Gold, Crude — with actual values) ──────────
    gold_r  = pct(prices.get("GC=F"),  BASELINE.get("GC=F"))
    crude_r = pct(prices.get("CL=F"),  BASELINE.get("CL=F"))
    sp_r    = pct(prices.get("^GSPC"), BASELINE.get("^GSPC"))
    nsei_r  = pct(prices.get("^NSEI"), BASELINE.get("^NSEI"))

    if gold_r is not None:
        gold_p = prices.get("GC=F")
        if gold_r > 8:
            signals.append(f"- 🥇 Gold at ${gold_p:,.0f} ({gold_r:+.1f}% vs baseline) — strong risk-off signal; expect pressure on HDFC Bank, IT exports")
        elif gold_r > 3:
            signals.append(f"- 🥇 Gold at ${gold_p:,.0f} ({gold_r:+.1f}%) — mild risk-off; monitor FII flows into India")
        elif gold_r < -5:
            signals.append(f"- 🥇 Gold at ${gold_p:,.0f} ({gold_r:.1f}%) — risk-on; equities may see follow-through buying")

    if crude_r is not None:
        crude_p = prices.get("CL=F")
        if crude_r > 10:
            signals.append(f"- 🛢️ WTI at ${crude_p:.1f} ({crude_r:+.1f}%) — elevated crude; OMC margins under pressure (BPCL, IOC, HINDPETRO)")
        elif crude_r < -10:
            signals.append(f"- 🛢️ WTI at ${crude_p:.1f} ({crude_r:.1f}%) — crude falling; OMC input cost relief; watch BPCL, IOC for rally")
        elif -5 < crude_r < 5:
            signals.append(f"- 🛢️ WTI at ${crude_p:.1f} ({crude_r:+.1f}%) — crude stable; no OMC disruption expected")

    if sp_r is not None and nsei_r is not None:
        spread = nsei_r - sp_r
        if spread < -5:
            signals.append(f"- ⚡ Nifty ({nsei_r:+.1f}%) is underperforming S&P 500 ({sp_r:+.1f}%) by {abs(spread):.1f}% — watch for FII-driven catch-up or continued divergence")
        elif spread > 5:
            signals.append(f"- ⚡ Nifty ({nsei_r:+.1f}%) is outperforming S&P 500 ({sp_r:+.1f}%) by {spread:.1f}% — domestic-led rally; watch sustainability")

    # ── 3. News theme spillovers (what today's headlines mean for tomorrow) ─
    theme_watchlist = {
        "Defense / Geopolitics": "Watch HAL, BEL at open — geopolitical news typically has 1-2 day lag on NSE",
        "Oil & Energy":          "OMC stocks (BPCL, IOC) sensitive to overnight crude moves — check WTI at US close",
        "Tech / AI":             "TCS, Infosys follow NASDAQ sentiment — US tech close sets tomorrow's NSE IT direction",
        "Banking & Rates":       "Monitor RBI commentary and bond yields — HDFC Bank, ICICI key bellwethers",
        "Pharma / Healthcare":   "FDA decisions and US pharma moves overnight affect Sunpharma, Cipla at open",
        "Safe Haven / Gold":     "Gold and MCX move inversely to risk appetite — elevated gold = defensive posture",
        "Consumer / FMCG":       "Monsoon and rural data are key catalysts for HUL, ITC this season",
        "Auto / EV":             "Maruti tracks vehicle sales data closely — monthly SIAM numbers are the trigger",
        "Trade / Macro":         "Dollar-Rupee move overnight directly impacts IT exporters and import-heavy sectors",
        "Telecom":               "Spectrum policy and ARPU data drive Airtel — watch for regulatory updates",
        "Power / Renewables":    "Tata Power tracks coal prices and renewable policy — Budget allocations key",
        "PSU / Government Spend":"HAL, BEL, PSU banks linked to defence budget and capex announcements",
    }
    for s in active_sectors[:3]:
        watch_txt = theme_watchlist.get(s["name"])
        if watch_txt:
            triggers = ", ".join(s.get("hits", []))
            signals.append(f"- 👁 **{s['name']}** in focus _(news: {triggers})_ — {watch_txt}")

    # ── 4. Pattern health alerts (what's about to break) ───────────────────
    for p in nse_patterns:
        rets = [pct(prices.get(t), BASELINE.get(t)) for t in p["tickers"] if prices.get(t) and BASELINE.get(t)]
        avg = sum(rets)/len(rets) if rets else None
        if avg is None:
            continue
        lead = p["tickers"][0]
        name = lead.replace(".NS","")
        lp   = prices.get(lead)
        price_disp = f"₹{lp:.0f}" if lp else ""
        if p["signal"] == "positive" and -1 < avg < 2:
            signals.append(f"- ⚠️ **{p['name']}** ({name} {price_disp}, {avg:+.1f}%) is at breakout-or-fade zone — decisive move expected")
        elif p["signal"] == "negative" and -2 < avg < 1:
            signals.append(f"- ⚠️ **{p['name']}** ({name} {price_disp}, {avg:+.1f}%) stabilising — watch if reversal confirms")

    if not signals:
        signals = ["- No strong directional signals today — range-bound open expected"]

    return signals[:8]  # cap at 8 to keep report readable

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Tracker failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    run_ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # 1. News → active sectors → dynamic NSE patterns
    print("Fetching news...")
    all_text, headlines_by_region = fetch_news()
    themes = extract_themes(all_text)
    active_sectors = active_global_sectors(all_text)
    nse_patterns = build_nse_patterns(active_sectors)
    print(f"Active sectors: {[s['name'] for s in active_sectors]}")
    print(f"NSE patterns: {[p['name'] for p in nse_patterns]}")

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
    macro_tickers    = ["^NSEI","^BSESN","^GSPC","^IXIC","^DJI","^FTSE","^GDAXI","^FCHI","^STOXX50E","GC=F","CL=F"]
    nse_tickers      = list({t for p in nse_patterns for t in p["tickers"]})
    adaptive_tickers = list({t for s in active_sectors for t in s.get("global", [])})
    fixed_global     = [t for t, _ in US_STOCKS + EU_STOCKS]
    all_tickers      = list(set(macro_tickers + nse_tickers + adaptive_tickers + fixed_global))

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

    # ── Section 3: NSE Pattern Health (dynamic) ────────────────────────────
    pattern_rows = []
    for p in nse_patterns:
        rets = [pct(prices.get(t), BASELINE.get(t)) for t in p["tickers"] if prices.get(t) and BASELINE.get(t)]
        avg  = sum(rets)/len(rets) if rets else None
        icon, label = pattern_status(avg, p["signal"])
        lead = p["tickers"][0]
        lp   = prices.get(lead)
        lead_name = lead.replace(".NS","")
        p_str = f"₹{lp:.0f}" if lp else "N/A"
        triggers = ", ".join(p.get("triggers", []))
        pattern_rows.append(f"| {icon} {p['name']} | {lead_name} {p_str} | {fmt(pct(lp, BASELINE.get(lead)))} | {label} | _{triggers}_ |")

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

    # Adaptive: news-driven global highlights
    adaptive_rows = []
    seen_adaptive = set()
    for s in active_sectors:
        for ticker in s.get("global", []):
            if ticker in seen_adaptive:
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

    # ── Section 5: What to Watch Tomorrow (fully dynamic) ──────────────────
    watch_signals = build_watch_signals(prices, active_sectors, themes, nse_patterns)

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
        f"## 🟢 NSE Pattern Health — {len(nse_patterns)} patterns today\n\n"
        f"| Pattern | Lead Stock | vs Apr 1 | Status | News Trigger |\n"
        f"|---|---|---|---|---|\n"
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
