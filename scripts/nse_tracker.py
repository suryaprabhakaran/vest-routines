"""
Vest Intelligence Brief — combined market tracker + signal log.
Produces one daily document: vest-brief-YYYY-MM-DD.md
Sections: Top 3 Picks (NSE/US/EU) → What to Watch → Top 15 Health → Macro → Key Themes → Follow-Through → News
"""
import urllib.request, json, time, re, xml.etree.ElementTree as ET, os, csv
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN   = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

SCRIPTS_DIR = os.path.dirname(__file__)
LOG_PATH    = os.path.join(SCRIPTS_DIR, "..", "output", "signal_log.csv")
LOG_FIELDS  = ["date", "instrument", "price_at_emission", "signal_type",
               "reason", "follow_through_pct", "scored_date"]


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
     "nse": ["HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","BANKBARODA.NS"],
     "global": ["JPM","BAC","GS","BARC.L","HSBA.L"],
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

# ── Stock universes ───────────────────────────────────────────────────────────
NSE_UNIVERSE = [
    ("HDFCBANK.NS", "HDFC Bank"), ("ICICIBANK.NS", "ICICI Bank"),
    ("SBIN.NS", "SBI"), ("AXISBANK.NS", "Axis Bank"), ("KOTAKBANK.NS", "Kotak"),
    ("BANKBARODA.NS", "Bank of Baroda"), ("TCS.NS", "TCS"), ("INFY.NS", "Infosys"),
    ("WIPRO.NS", "Wipro"), ("HCLTECH.NS", "HCL Tech"), ("TECHM.NS", "Tech M"),
    ("SUNPHARMA.NS", "Sun Pharma"), ("CIPLA.NS", "Cipla"), ("DRREDDY.NS", "Dr Reddy"),
    ("MARUTI.NS", "Maruti"), ("BHARTIARTL.NS", "Airtel"),
    ("HAL.NS", "HAL"), ("BEL.NS", "BEL"),
    ("HINDUNILVR.NS", "HUL"), ("ITC.NS", "ITC"), ("TITAN.NS", "Titan"),
    ("MCX.NS", "MCX"), ("TATAPOWER.NS", "Tata Power"),
    ("BPCL.NS", "BPCL"), ("ONGC.NS", "ONGC"), ("RELIANCE.NS", "Reliance"),
]

US_UNIVERSE = [
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"),
    ("GOOGL", "Alphabet"), ("AMZN", "Amazon"), ("META", "Meta"),
    ("TSLA", "Tesla"), ("JPM", "JPMorgan"), ("BAC", "BofA"),
    ("GS", "Goldman Sachs"), ("XOM", "ExxonMobil"), ("CVX", "Chevron"),
    ("LMT", "Lockheed"), ("PFE", "Pfizer"), ("JNJ", "J&J"),
]

EU_UNIVERSE = [
    ("ASML.AS", "ASML"), ("SAP.DE", "SAP"), ("SIE.DE", "Siemens"),
    ("AIR.PA", "Airbus"), ("MC.PA", "LVMH"), ("SHEL.L", "Shell"),
    ("NOVN.SW", "Novartis"), ("ROG.SW", "Roche"),
    ("BARC.L", "Barclays"), ("HSBA.L", "HSBC"), ("TTE.PA", "TotalEnergies"),
]

STRIP = re.compile(r"<[^>]+>")

# ── Signal log ────────────────────────────────────────────────────────────────
def load_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def save_log(rows):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        w.writerows(rows)

def score_old_signals(rows, prices):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for row in rows:
        if row["date"] == today:
            continue
        p_emit = float(row["price_at_emission"]) if row["price_at_emission"] else None
        ticker = row["instrument"]
        p_now  = prices.get(ticker)
        if p_emit and p_now:
            row["follow_through_pct"] = str(round((p_now - p_emit) / p_emit * 100, 2))
            row["scored_date"] = today

def append_picks_to_log(rows, picks, today):
    existing = {(r["date"], r["instrument"]) for r in rows}
    for pick in picks:
        ticker, name, r_val, signal_type, reason, price_val = pick
        if (today, ticker) not in existing and price_val:
            rows.append({
                "date": today, "instrument": ticker,
                "price_at_emission": str(round(price_val, 2)),
                "signal_type": signal_type, "reason": reason,
                "follow_through_pct": "", "scored_date": "",
            })

# ── News ──────────────────────────────────────────────────────────────────────
# Only economictimes.indiatimes.com and livemint.com are accessible through
# the proxy. FT and all other international domains return 403.
# ET International Markets is the closest equivalent to FT global coverage.
RSS_FEEDS = {
    "IN": [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",     # ET Markets
        "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", # ET Stocks
        "https://economictimes.indiatimes.com/economy/rssfeeds/1373380680.cms",     # ET Economy/Macro
        "https://www.livemint.com/rss/markets",
        "https://www.livemint.com/rss/companies",
    ],
    "GLOBAL": [
        "https://economictimes.indiatimes.com/rssfeedsdefault.cms",  # ET general — includes US/global market news
        "https://www.livemint.com/rss/economy",                      # Livemint Economy — US CPI, Fed, macro
    ],
}

def fetch_news():
    all_text = []
    by_region = {"IN": [], "GLOBAL": []}
    for region, feeds in RSS_FEEDS.items():
        for url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
                for item in list(root.iter("item"))[:10]:
                    title = STRIP.sub("", item.findtext("title", "")).strip()
                    desc  = STRIP.sub("", item.findtext("description", "")).strip()
                    if title:
                        all_text.append((title + " " + desc).lower())
                        if len(by_region[region]) < 8:
                            by_region[region].append(title)
            except Exception as e:
                print(f"Feed error {url}: {e}")
    return all_text, by_region

def extract_themes(all_text):
    combined = " ".join(all_text)
    hits = []
    for s in GLOBAL_SECTORS:
        kw_hits = [kw for kw in s["keywords"] if kw in combined]
        if kw_hits:
            hits.append((len(kw_hits), s["name"], kw_hits[:2]))
    hits.sort(reverse=True)
    return hits[:5]

def active_global_sectors(all_text):
    combined = " ".join(all_text)
    matched = []
    for s in GLOBAL_SECTORS:
        kw_hits = [kw for kw in s["keywords"] if kw in combined]
        if kw_hits:
            matched.append({**s, "hits": kw_hits[:3]})
    return matched[:8] if matched else GLOBAL_SECTORS[:4]

def build_nse_patterns(active_sectors):
    patterns = []
    seen = set()
    for s in active_sectors:
        tickers = [t for t in s["nse"] if t not in seen]
        if not tickers:
            continue
        seen.update(tickers)
        patterns.append({"name": s["name"], "tickers": tickers,
                         "signal": s["signal"], "triggers": s.get("hits", [])})
    return patterns

# ── Calendar ──────────────────────────────────────────────────────────────────
CALENDAR_FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
    "https://www.investing.com/rss/economic_calendar.rss",
]
CALENDAR_KEYWORDS = {
    "fed":          ("🇺🇸 Fed", "interest rate / monetary policy"),
    "fomc":         ("🇺🇸 FOMC", "US rate decision"),
    "ecb":          ("🇪🇺 ECB", "European rate decision"),
    "rbi":          ("🇮🇳 RBI", "India rate decision"),
    "cpi":          ("📊 CPI", "inflation data"),
    "gdp":          ("📊 GDP", "growth data"),
    "nfp":          ("🇺🇸 NFP", "US jobs report"),
    "payroll":      ("🇺🇸 Payrolls", "US jobs data"),
    "pmi":          ("📊 PMI", "manufacturing/services activity"),
    "earnings":     ("💰 Earnings", "corporate results"),
    "inflation":    ("📊 Inflation", "price data"),
    "unemployment": ("📊 Unemployment", "jobs data"),
    "trade":        ("📊 Trade Balance", "trade data"),
    "expiry":       ("⏰ Expiry", "F&O / options expiry"),
    "opec":         ("🛢️ OPEC", "oil supply decision"),
    "budget":       ("🇮🇳 Budget", "fiscal policy"),
    "powell":       ("🇺🇸 Powell", "Fed chair speech"),
    "lagarde":      ("🇪🇺 Lagarde", "ECB president speech"),
}

def fetch_calendar_events():
    events = []
    for feed_url in CALENDAR_FEEDS:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
            for item in list(root.iter("item"))[:30]:
                title = STRIP.sub("", item.findtext("title", "")).strip()
                desc  = STRIP.sub("", item.findtext("description", "")).strip()
                date  = item.findtext("pubDate", "") or item.findtext("date", "")
                if title:
                    events.append((title, desc[:100], date))
        except Exception as e:
            print(f"Calendar feed error {feed_url}: {e}")
    return events

def build_calendar_watchlist(events, all_text):
    watchlist = []
    for title, desc, date in events[:15]:
        text = (title + " " + desc).lower()
        for kw, (label, meaning) in CALENDAR_KEYWORDS.items():
            if kw in text:
                watchlist.append(f"- {label} **{title.strip()}** — {meaning}")
                break
    combined = " ".join(all_text)
    news_calendar = {
        "tomorrow":       "Event flagged in today's news as happening tomorrow",
        "next week":      "Event expected next week — start positioning",
        "wednesday":      "Mid-week event — check economic calendar",
        "thursday":       "Thursday event — check economic calendar",
        "friday":         "End-of-week event — watch for volatility",
        "quarterly":      "Quarterly results season — earnings risk elevated",
        "results":        "Earnings results expected — watch for surprise moves",
        "press conference": "Central bank press conference — volatile session expected",
        "policy meeting": "Policy meeting — rate decision risk",
        "f&o expiry":     "⏰ F&O expiry — expect elevated volatility on NSE",
        "monthly expiry": "⏰ Monthly expiry — NSE positions being squared",
    }
    for kw, note in news_calendar.items():
        if kw in combined and not any(kw in w.lower() for w in watchlist):
            watchlist.append(f"- 📅 _{note}_")
    weekday = datetime.utcnow().weekday()
    standing = {
        3: "- ⏰ **Weekly F&O Expiry tomorrow (Thursday)** — NSE volatility typically elevated; watch Nifty options",
        4: "- 📊 **US markets close early Friday** — liquidity thinner; gap-risk into Monday",
        6: "- 🌏 **Asian markets open Monday** — set the tone for NSE opening; watch SGX Nifty overnight",
        0: "- 🌏 **Monday open** — check weekend news for geopolitical or macro surprises",
    }
    if weekday in standing:
        watchlist.append(standing[weekday])
    seen = set()
    unique = []
    for w in watchlist:
        key = w[:40]
        if key not in seen:
            seen.add(key)
            unique.append(w)
    return unique[:8] if unique else ["- No major scheduled events identified for tomorrow"]

# ── Prices ────────────────────────────────────────────────────────────────────
def get_price(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                    "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        meta = d["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("previousClose") or meta.get("chartPreviousClose")
        return price, prev
    except:
        return None, None

def pct(today, base):
    if today and base:
        return (today - base) / base * 100
    return None

def daily_pct(ticker, prices, prev_closes):
    return pct(prices.get(ticker), prev_closes.get(ticker))

def fmt(v, decimals=1):
    if v is None: return "N/A"
    return f"{'+' if v >= 0 else ''}{v:.{decimals}f}%"

def trend(v):
    if v is None: return "—"
    return "▲" if v > 0 else "▼"

# ── Scoring ───────────────────────────────────────────────────────────────────
def region_flag(ticker):
    if ticker.endswith(".NS"):                          return "🇮🇳"
    if ticker.endswith((".AS",".DE",".PA",".L",".SW")): return "🇪🇺"
    return "🇺🇸"

def price_str(ticker, p):
    if p is None: return "N/A"
    if ticker.endswith(".NS"): return f"₹{p:,.0f}"
    if ticker.endswith(".L"):  return f"p{p:,.0f}"
    return f"${p:,.2f}"

def stock_status(r):
    if r is None: return "⚪ N/A"
    if r > 3:   return "🟢 STRONG"
    if r > 1:   return "🟢 RISING"
    if r > -1:  return "🟡 RANGE"
    if r > -3:  return "🔴 FALLING"
    return "🔴 WEAK"

def news_hits_for(ticker, active_sectors, combined_news):
    best_hits, best_sector = 0, ""
    for s in active_sectors:
        if ticker in s.get("nse", []) + s.get("global", []):
            h = sum(1 for kw in s["keywords"] if kw in combined_news)
            if h > best_hits:
                best_hits, best_sector = h, s["name"]
    return best_hits, best_sector

def pick_top3(universe, prices, prev_closes, active_sectors, combined_news, region_label):
    """Return up to 3 stocks from universe that have news hits today, ranked by hits + daily move."""
    scored = []
    for ticker, name in universe:
        nhits, sector = news_hits_for(ticker, active_sectors, combined_news)
        if nhits == 0:
            continue
        p = prices.get(ticker)
        if p is None:
            continue
        r = daily_pct(ticker, prices, prev_closes) or 0.0
        score = (nhits * 5.0) + min(max(r, -5.0), 5.0)
        scored.append((score, ticker, name, p, r, nhits, sector))
    scored.sort(reverse=True)

    result = []
    for score, ticker, name, p, r, nhits, sector in scored[:3]:
        signal_type = f"PICK ({region_label})"
        reason = f"{sector} · {nhits} news hit{'s' if nhits > 1 else ''} · {r:+.1f}% today"
        result.append((ticker, name, r, signal_type, reason, p, nhits))
    return result

def build_top15_health(prices, prev_closes, active_sectors, combined_news):
    """Pool all universe stocks, score by news×3 + abs daily move (cap 5%), return top 15."""
    all_stocks = NSE_UNIVERSE + US_UNIVERSE + EU_UNIVERSE
    scored = []
    seen = set()
    for ticker, name in all_stocks:
        if ticker in seen:
            continue
        seen.add(ticker)
        p = prices.get(ticker)
        r = daily_pct(ticker, prices, prev_closes)
        if r is None:
            continue
        nhits, sector = news_hits_for(ticker, active_sectors, combined_news)
        score = (nhits * 3) + min(abs(r), 5)
        scored.append((score, ticker, name, p, r, nhits, sector))
    scored.sort(reverse=True)
    return scored[:15]

# ── Watch signals ─────────────────────────────────────────────────────────────
def build_watch_signals(prices, prev_closes, active_sectors, themes, nse_patterns):
    signals = []

    movers = []
    for ticker in prices:
        if ticker in ("GC=F","CL=F") or ticker.startswith("^"):
            continue
        r = daily_pct(ticker, prices, prev_closes)
        if r is not None:
            name = re.sub(r"\.(NS|AS|DE|PA|L|SW)$", "", ticker).replace("=F","")
            movers.append((abs(r), r, name, ticker))
    movers.sort(reverse=True)
    for _, r, name, ticker in movers[:2]:
        direction = f"up {r:+.1f}%" if r > 0 else f"down {r:.1f}%"
        flag = region_flag(ticker)
        signals.append(f"- {flag} **{name}** moved {direction} today — watch for continuation")

    gold_r  = daily_pct("GC=F",  prices, prev_closes)
    crude_r = daily_pct("CL=F",  prices, prev_closes)
    sp_r    = daily_pct("^GSPC", prices, prev_closes)
    nsei_r  = daily_pct("^NSEI", prices, prev_closes)

    if gold_r is not None:
        gp = prices.get("GC=F")
        if gold_r > 1.0:
            signals.append(f"- 🥇 Gold +{gold_r:.1f}% today (${gp:,.0f}) — risk-off move; watch HDFC Bank, IT exporters")
        elif gold_r > 0.3:
            signals.append(f"- 🥇 Gold +{gold_r:.1f}% today (${gp:,.0f}) — mild risk-off; monitor FII flows")
        elif gold_r < -0.5:
            signals.append(f"- 🥇 Gold {gold_r:.1f}% today (${gp:,.0f}) — risk-on; equities may see follow-through")

    if crude_r is not None:
        cp = prices.get("CL=F")
        if crude_r > 1.5:
            signals.append(f"- 🛢️ WTI +{crude_r:.1f}% today (${cp:.1f}) — crude rising; OMC margins under pressure (BPCL, IOC)")
        elif crude_r < -1.5:
            signals.append(f"- 🛢️ WTI {crude_r:.1f}% today (${cp:.1f}) — crude falling; OMC cost relief; watch BPCL, IOC for rally")

    if sp_r is not None and nsei_r is not None:
        spread = nsei_r - sp_r
        if spread < -1.5:
            signals.append(f"- ⚡ Nifty ({nsei_r:+.1f}%) underperforming S&P 500 ({sp_r:+.1f}%) by {abs(spread):.1f}% — watch for catch-up")
        elif spread > 1.5:
            signals.append(f"- ⚡ Nifty ({nsei_r:+.1f}%) outperforming S&P 500 ({sp_r:+.1f}%) by {spread:.1f}% — domestic rally; watch sustainability")

    theme_watchlist = {
        "Defense / Geopolitics": "Watch HAL, BEL at open — geopolitical news typically has 1–2 day lag on NSE",
        "Oil & Energy":          "OMC stocks (BPCL, IOC) sensitive to overnight crude — check WTI at US close",
        "Tech / AI":             "TCS, Infosys follow NASDAQ — US tech close sets tomorrow's NSE IT direction",
        "Banking & Rates":       "Monitor RBI commentary and bond yields — HDFC Bank, ICICI key bellwethers",
        "Pharma / Healthcare":   "FDA decisions and US pharma moves affect Sun Pharma, Cipla at open",
        "Safe Haven / Gold":     "Gold and MCX move inversely to risk appetite — elevated gold = defensive posture",
        "Consumer / FMCG":       "Monsoon and rural data are key catalysts for HUL, ITC this season",
        "Auto / EV":             "Maruti tracks vehicle sales data — monthly SIAM numbers are the trigger",
        "Trade / Macro":         "Dollar-Rupee move overnight directly impacts IT exporters and import-heavy sectors",
        "Telecom":               "Spectrum policy and ARPU data drive Airtel — watch for regulatory updates",
        "Power / Renewables":    "Tata Power tracks coal prices and renewable policy — Budget allocations key",
        "PSU / Government Spend":"HAL, BEL, PSU banks linked to defence budget and capex announcements",
    }
    for s in active_sectors[:3]:
        txt = theme_watchlist.get(s["name"])
        if txt:
            triggers = ", ".join(s.get("hits", []))
            signals.append(f"- 👁 **{s['name']}** in focus _(news: {triggers})_ — {txt}")

    for p in nse_patterns:
        rets = [daily_pct(t, prices, prev_closes) for t in p["tickers"]
                if prices.get(t) and prev_closes.get(t)]
        rets = [r for r in rets if r is not None]
        avg = sum(rets)/len(rets) if rets else None
        if avg is None:
            continue
        lead = p["tickers"][0]
        name = lead.replace(".NS","")
        lp   = prices.get(lead)
        p_s  = f"₹{lp:.0f}" if lp else ""
        if p["signal"] == "positive" and -0.3 < avg < 0.5:
            signals.append(f"- ⚠️ **{p['name']}** ({name} {p_s}, {avg:+.1f}% today) at breakout-or-fade zone — decisive move expected")

    return signals[:8] if signals else ["- No strong directional signals today — range-bound open expected"]


def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID,
                           f"⚠️ *Vest Tracker failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    run_ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    NL        = "\n"

    # Load signal log and score any prior picks
    log_rows = load_log()

    # News + calendar
    print("Fetching news...")
    all_text, headlines_by_region = fetch_news()
    combined_news = " ".join(all_text)
    themes         = extract_themes(all_text)
    active_sectors = active_global_sectors(all_text)
    nse_patterns   = build_nse_patterns(active_sectors)
    print(f"Active sectors: {[s['name'] for s in active_sectors]}")

    print("Fetching calendar...")
    calendar_events   = fetch_calendar_events()
    calendar_watchlist = build_calendar_watchlist(calendar_events, all_text)

    # Prices — all universes + macro indices
    all_tickers = list(set(
        [t for t, _ in NSE_UNIVERSE + US_UNIVERSE + EU_UNIVERSE] +
        ["^NSEI","^GSPC","^FTSE","^GDAXI","GC=F","CL=F"]
    ))
    print(f"Fetching {len(all_tickers)} prices...")
    prices, prev_closes = {}, {}
    for t in all_tickers:
        p, pc = get_price(t)
        prices[t] = p
        prev_closes[t] = pc
        time.sleep(0.15)

    # Score prior signal log entries with today's prices
    score_old_signals(log_rows, prices)

    # Pick top 3 per region — news-driven only
    print("Picking stocks...")
    nse_picks = pick_top3(NSE_UNIVERSE, prices, prev_closes, active_sectors, combined_news, "NSE")
    us_picks  = pick_top3(US_UNIVERSE,  prices, prev_closes, active_sectors, combined_news, "US")
    eu_picks  = pick_top3(EU_UNIVERSE,  prices, prev_closes, active_sectors, combined_news, "EU")

    # Append all 9 picks to signal log
    all_picks_flat = [
        (ticker, name, r, sig_type, reason, p)
        for ticker, name, r, sig_type, reason, p, _ in nse_picks + us_picks + eu_picks
    ]
    append_picks_to_log(log_rows, all_picks_flat, today_str)
    save_log(log_rows)

    # Combined pattern health top 15
    health15 = build_top15_health(prices, prev_closes, active_sectors, combined_news)

    # Watch signals
    watch_signals = build_watch_signals(prices, prev_closes, active_sectors, themes, nse_patterns)

    # Recent follow-through (last 5 scored, excluding today)
    scored_rows = sorted(
        [r for r in log_rows if r["follow_through_pct"] and r["date"] != today_str],
        key=lambda r: r["date"], reverse=True
    )[:5]

    # ── Build sections ────────────────────────────────────────────────────────

    # Key themes
    theme_lines = [f"- **{name}** _(triggers: {', '.join(hits)})_" for _, name, hits in themes]
    if not theme_lines:
        theme_lines = ["- No dominant theme detected today"]

    # Macro snapshot
    def macro_row(ticker, label, currency="", decimals=0):
        p = prices.get(ticker)
        r = daily_pct(ticker, prices, prev_closes)
        p_s = f"{currency}{p:,.{decimals}f}" if p else "N/A"
        return f"| {label} | {p_s} | {fmt(r)} | {trend(r)} |"

    macro_rows = NL.join([
        macro_row("^NSEI",  "🇮🇳 Nifty 50"),
        macro_row("^GSPC",  "🇺🇸 S&P 500"),
        macro_row("^FTSE",  "🇬🇧 FTSE 100"),
        macro_row("^GDAXI", "🇩🇪 DAX"),
        macro_row("GC=F",   "🥇 Gold", "$", 0),
        macro_row("CL=F",   "🛢️ WTI Crude", "$", 1),
    ])

    # Top picks tables
    def pick_rows(picks):
        if not picks:
            return ["| — | _No news-driven signals today_ | — | — | — |"]
        rows = []
        for i, (ticker, name, r, _, reason, p, nhits) in enumerate(picks, 1):
            p_s   = price_str(ticker, p)
            r_s   = fmt(r)
            signal = f"⚡ {nhits} news hit{'s' if nhits > 1 else ''}"
            rows.append(f"| {i} | **{name}** | {p_s} | {r_s} | {signal} |")
        return rows

    # Health top 15
    health_rows = []
    for rank, (score, ticker, name, p, r, nhits, sector) in enumerate(health15, 1):
        flag  = region_flag(ticker)
        p_s   = price_str(ticker, p)
        r_s   = fmt(r)
        news_tag = " ⚡" if nhits > 0 else ""
        health_rows.append(f"| {rank} | {flag} | **{name}** | {p_s} | {r_s} | {stock_status(r)}{news_tag} |")

    # Follow-through
    ft_rows = []
    for row in scored_rows:
        ft   = float(row["follow_through_pct"])
        icon = "✅" if ft > 0 else "❌"
        ft_rows.append(
            f"| {icon} | {row['date']} | {row['instrument']} | "
            f"{row['price_at_emission']} | {ft:+.1f}% | {row['signal_type']} |"
        )

    # News digest
    flag_map = {"IN": "🇮🇳 India", "GLOBAL": "🌍 Global Markets (via ET / Livemint)"}
    news_sections = []
    for region, items in headlines_by_region.items():
        if items:
            bullets = NL.join(f"- {h}" for h in items[:8])
            news_sections.append(f"### {flag_map.get(region, region)}\n{bullets}")

    # ── Assemble markdown ─────────────────────────────────────────────────────
    ft_block = (
        f"---\n\n"
        f"## 📊 Signal Follow-Through\n\n"
        f"_Prior picks scored at today's price_\n\n"
        f"| | Date | Stock | Emitted | Move | Type |\n"
        f"|---|---|---|---|---|---|\n"
        f"{NL.join(ft_rows)}\n\n"
    ) if ft_rows else ""

    md = (
        f"# 📊 Vest Intelligence Brief — {today_str}\n"
        f"_Run: {run_ts}_\n\n"
        f"---\n\n"
        f"## 🎯 Today's Top Picks\n\n"
        f"_Only stocks with today's news signals are shown. Day % = vs yesterday's close._\n\n"
        f"### 🇮🇳 India (NSE)\n\n"
        f"| # | Stock | Price | Day % | Signal |\n"
        f"|---|---|---|---|---|\n"
        f"{NL.join(pick_rows(nse_picks))}\n\n"
        f"### 🇺🇸 United States\n\n"
        f"| # | Stock | Price | Day % | Signal |\n"
        f"|---|---|---|---|---|\n"
        f"{NL.join(pick_rows(us_picks))}\n\n"
        f"### 🇪🇺 Europe\n\n"
        f"| # | Stock | Price | Day % | Signal |\n"
        f"|---|---|---|---|---|\n"
        f"{NL.join(pick_rows(eu_picks))}\n\n"
        f"---\n\n"
        f"## 📅 What to Watch Tomorrow\n\n"
        f"### 🗓 Scheduled Events\n\n"
        f"{NL.join(calendar_watchlist)}\n\n"
        f"### 📡 Price & News Signals\n\n"
        f"{NL.join(watch_signals)}\n\n"
        f"---\n\n"
        f"## 🟢 Market Pattern Health — Top 15\n\n"
        f"_Combined NSE · US · EU — ranked by news momentum + price trend. ⚡ = news-backed today._\n\n"
        f"| # | 🌍 | Stock | Price | Day % | Status |\n"
        f"|---|---|---|---|---|---|\n"
        f"{NL.join(health_rows)}\n\n"
        f"---\n\n"
        f"## 📊 Macro Snapshot\n\n"
        f"| Index / Asset | Price | Day % | |\n"
        f"|---|---|---|---|\n"
        f"{macro_rows}\n\n"
        f"---\n\n"
        f"## 🔴 Today's Key Themes\n\n"
        f"{NL.join(theme_lines)}\n\n"
        f"{ft_block}"
        f"---\n\n"
        f"## 📰 News Digest\n\n"
        f"{NL.join(news_sections)}\n\n"
        f"---\n"
        f"_Vest · Intelligence Brief · {run_ts}_\n"
    )

    nse_names = ", ".join(name for _, name, *_ in nse_picks[:2])
    summary = f"📊 Vest Brief {today_str} — Top NSE picks: {nse_names}"
    publish(TG_TOKEN, TG_CHAT_ID, md, "vest-brief", summary)
    print("Done.")

except Exception as e:
    import traceback
    traceback.print_exc()
    send_error(e)
    raise
