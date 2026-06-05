import urllib.request, json, time, re, xml.etree.ElementTree as ET, os
from datetime import datetime

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Baselines (Apr 1 2025) ──────────────────────────────────────────────────
BASELINE = {
    "^NSEI":22679.40,"^BSESN":73134.32,"RELIANCE.NS":1369.20,
    "BPCL.NS":281.25,"IOC.NS":135.72,"HINDPETRO.NS":335.55,
    "ONGC.NS":288.05,"HDFCBANK.NS":742.25,"SBIN.NS":1017.80,
    "ICICIBANK.NS":1212.70,"AXISBANK.NS":1193.10,"KOTAKBANK.NS":356.05,
    "TCS.NS":2408.20,"INFY.NS":1275.70,"WIPRO.NS":191.18,
    "TECHM.NS":1404.50,"HCLTECH.NS":1354.40,"SUNPHARMA.NS":1728.50,
    "DRREDDY.NS":1209.60,"CIPLA.NS":1195.90,"MARUTI.NS":12509.00,
    "BHARTIARTL.NS":1781.90,"IDEA.NS":8.64,"HAL.NS":3670.80,
    "BEL.NS":418.70,"HINDUNILVR.NS":2064.70,"ITC.NS":291.70,
    "TITAN.NS":4065.50,"TATAPOWER.NS":380.20,"PAYTM.NS":997.10,
    "MCX.NS":2469.70,"BANKBARODA.NS":252.03,
}

# ── Sector keyword → (tickers, signal_direction) ───────────────────────────
# signal: "positive" = rising is good, "negative" = falling is the thesis
SECTOR_MAP = [
    {
        "keywords": ["defense","defence","military","hal","bel","drdo","missile","army","navy","airforce","border","war","ceasefire","pakistan","china"],
        "name": "Defense / Geopolitics",
        "tickers": ["HAL.NS","BEL.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["oil","crude","opec","petroleum","fuel","bpcl","ioc","hpcl","hindpetro","ongc","refinery","petrol","diesel"],
        "name": "Oil & OMCs",
        "tickers": ["BPCL.NS","IOC.NS","HINDPETRO.NS","ONGC.NS"],
        "signal": "negative",
    },
    {
        "keywords": ["pharma","drug","fda","usfda","health","medicine","hospital","cipla","sunpharma","drreddy","biocon","pandemic","epidemic"],
        "name": "Pharma / Healthcare",
        "tickers": ["SUNPHARMA.NS","CIPLA.NS","DRREDDY.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["it","software","tech","infosys","tcs","wipro","hcltech","techm","layoff","ai","automation","outsourcing","visa","h1b"],
        "name": "IT / Tech",
        "tickers": ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
        "signal": "negative",
    },
    {
        "keywords": ["bank","rbi","rate","repo","credit","loan","npa","nifty bank","hdfc","sbi","icici","axis","kotak","banking","liquidity","inflation"],
        "name": "Banking & Rates",
        "tickers": ["HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","BANKBARODA.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["telecom","5g","jio","airtel","vi","vodafone","idea","spectrum","bharti"],
        "name": "Telecom",
        "tickers": ["BHARTIARTL.NS","IDEA.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["fmcg","consumer","hul","hindustan unilever","itc","rural","inflation","monsoon","kirana"],
        "name": "FMCG / Consumer",
        "tickers": ["HINDUNILVR.NS","ITC.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["commodity","gold","silver","metal","mcx","futures","derivatives","trading volume"],
        "name": "Commodity / MCX",
        "tickers": ["MCX.NS","RELIANCE.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["auto","automobile","ev","electric vehicle","maruti","tata motors","mahindra","car","suv","vehicle sales"],
        "name": "Auto / EV",
        "tickers": ["MARUTI.NS","TATAPOWER.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["fintech","paytm","payment","upi","digital","wallet","sebi","stock market","nse","bse"],
        "name": "Fintech / Markets",
        "tickers": ["PAYTM.NS","MCX.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["power","renewable","solar","wind","energy","tatapower","green","electricity","grid"],
        "name": "Power / Renewables",
        "tickers": ["TATAPOWER.NS","ONGC.NS"],
        "signal": "positive",
    },
    {
        "keywords": ["luxury","jewellery","jewelry","titan","watches","retail","gold demand"],
        "name": "Luxury / Retail",
        "tickers": ["TITAN.NS"],
        "signal": "positive",
    },
]

# ── News fetch ──────────────────────────────────────────────────────────────
RSS_FEEDS = [
    "https://www.livemint.com/rss/markets",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.business-standard.com/rss/markets-106.rss",
]

def fetch_headlines():
    strip = re.compile(r"<[^>]+>")
    headlines = []
    for feed_url in RSS_FEEDS:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
            for item in list(root.iter("item"))[:8]:
                title = strip.sub("", item.findtext("title", "")).strip()
                desc = strip.sub("", item.findtext("description", "")).strip()
                if title:
                    headlines.append((title + " " + desc).lower())
        except Exception as e:
            print(f"Feed error {feed_url}: {e}")
    return headlines

def match_sectors(headlines):
    matched = []
    combined = " ".join(headlines)
    for sector in SECTOR_MAP:
        hits = [kw for kw in sector["keywords"] if kw in combined]
        if hits:
            matched.append({**sector, "hits": hits[:3]})
    # Always include Nifty context — return at most 6 sectors
    return matched[:6] if matched else SECTOR_MAP[:4]

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
    if avg is None: return "⚪ NO DATA"
    if signal == "negative":
        return "🔴 PLAYING OUT" if avg < -3 else ("🟡 STABILISING" if avg < 2 else "🟢 REVERSED")
    elif signal == "speculative":
        return "🚀 RUNNING" if avg > 10 else ("🟡 HOLDING" if avg > 0 else "🔴 FADING")
    else:
        return "🟢 RUNNING" if avg > 5 else ("🟡 FADING" if avg > 0 else "🔴 BROKEN")

# ── Telegram ────────────────────────────────────────────────────────────────
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    # Telegram has a 4096 char limit; trim if needed
    if len(msg) > 4000:
        msg = msg[:3990] + "\n…(truncated)"
    data = json.dumps({"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram error: {resp}")

def send_error(err):
    try:
        send_telegram(f"⚠️ *Vest NSE Tracker failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ─────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    print("Fetching headlines...")
    headlines = fetch_headlines()
    active_sectors = match_sectors(headlines)
    print(f"Active sectors: {[s['name'] for s in active_sectors]}")

    # Collect unique tickers needed
    needed = {"^NSEI", "^BSESN"}
    for s in active_sectors:
        needed.update(s["tickers"])

    print(f"Fetching {len(needed)} prices...")
    prices = {}
    for t in needed:
        prices[t] = get_price(t)
        time.sleep(0.25)

    nifty = prices.get("^NSEI")
    nifty_ret = pct(nifty, BASELINE.get("^NSEI"))
    sensex = prices.get("^BSESN")
    sensex_ret = pct(sensex, BASELINE.get("^BSESN"))

    pattern_lines = []
    for s in active_sectors:
        rets = [pct(prices.get(t), BASELINE.get(t)) for t in s["tickers"] if prices.get(t) and BASELINE.get(t)]
        avg = sum(rets) / len(rets) if rets else None
        status = score_status(avg, s["signal"])
        lead = s["tickers"][0]
        lp = prices.get(lead)
        la = pct(lp, BASELINE.get(lead))
        price_str = f"₹{lp:.0f}" if lp else "N/A"
        triggers = ", ".join(s["hits"]) if s.get("hits") else "—"
        pattern_lines.append(
            f"{status} *{s['name']}*\n"
            f"  {lead.replace('.NS','')} {price_str} | vs Apr1: {fmt(la)} | avg: {fmt(avg)}\n"
            f"  _news triggers: {triggers}_"
        )

    # Top raw headlines for display
    display_headlines = []
    strip = re.compile(r"<[^>]+>")
    for feed_url in RSS_FEEDS[:2]:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
            for item in list(root.iter("item"))[:3]:
                t = strip.sub("", item.findtext("title", "")).strip()
                if t: display_headlines.append(f"• {t}")
        except:
            pass
    if not display_headlines:
        display_headlines = ["• (news fetch failed)"]

    nifty_str = f"{nifty:.0f} ({fmt(nifty_ret)} vs Apr 1)" if nifty else "N/A"
    sensex_str = f"{sensex:.0f} ({fmt(sensex_ret)} vs Apr 1)" if sensex else "N/A"

    msg = (
        f"📊 *Vest NSE Tracker — {today_str}*\n\n"
        f"*Nifty 50:* {nifty_str}\n"
        f"*Sensex:* {sensex_str}\n\n"
        f"*News-Driven Patterns ({len(active_sectors)} active):*\n"
        + "\n\n".join(pattern_lines)
        + "\n\n*Today's Headlines:*\n"
        + "\n".join(display_headlines[:5])
        + "\n\n_Vest · NSE Tracker · news-adaptive_"
    )

    print(msg)
    send_telegram(msg)
    print("Telegram message sent successfully.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
