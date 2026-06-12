"""
Vest Signal Logger — runs at 11pm Brussels (21:00 UTC)
-------------------------------------------------------
Council verdict implementation:
  1. Emit 1-2 high-conviction signals (not 8)
  2. Log every signal with price-at-emission to signal_log.csv
  3. Score prior signals (follow-through %) each run
  4. After ~60-90 days: know if there is edge

Signal log columns:
  date, instrument, price_at_emission, signal_type, reason, follow_through_pct, scored_date
"""
import urllib.request, json, time, csv, os, re
from datetime import datetime, timedelta
from output_helper import publish, send_telegram_text

TG_TOKEN  = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

SCRIPTS_DIR = os.path.dirname(__file__)
LOG_PATH    = os.path.join(SCRIPTS_DIR, "..", "output", "signal_log.csv")
LOG_FIELDS  = ["date", "instrument", "price_at_emission", "signal_type", "reason",
               "follow_through_pct", "scored_date"]

BASELINE = {
    "^NSEI": 22679.40, "^BSESN": 73134.32,
    "^GSPC": 5611.85,  "^IXIC": 17449.89, "^DJI": 41989.96,
    "^FTSE": 8614.00,  "^GDAXI": 22035.00,
    "GC=F": 2100.00, "CL=F": 71.50,
    "RELIANCE.NS": 1369.20, "BPCL.NS": 281.25, "IOC.NS": 135.72,
    "HINDPETRO.NS": 335.55, "ONGC.NS": 288.05,
    "HDFCBANK.NS": 742.25, "SBIN.NS": 1017.80, "ICICIBANK.NS": 1212.70,
    "AXISBANK.NS": 1193.10, "KOTAKBANK.NS": 356.05,
    "TCS.NS": 2408.20, "INFY.NS": 1275.70, "WIPRO.NS": 191.18,
    "TECHM.NS": 1404.50, "HCLTECH.NS": 1354.40,
    "SUNPHARMA.NS": 1728.50, "DRREDDY.NS": 1209.60, "CIPLA.NS": 1195.90,
    "MARUTI.NS": 12509.00, "BHARTIARTL.NS": 1781.90,
    "HAL.NS": 3670.80, "BEL.NS": 418.70,
    "HINDUNILVR.NS": 2064.70, "ITC.NS": 291.70, "TITAN.NS": 4065.50,
    "TATAPOWER.NS": 380.20, "MCX.NS": 2469.70, "BANKBARODA.NS": 252.03,
    "AAPL": 223.19, "MSFT": 378.80, "NVDA": 110.00, "GOOGL": 165.40,
    "AMZN": 197.12, "META": 558.11, "TSLA": 265.00,
    "JPM": 238.24, "BAC": 43.90, "GS": 538.50,
    "XOM": 117.50, "CVX": 156.70, "LMT": 478.20, "RTX": 125.40,
    "ASML.AS": 720.00, "SAP.DE": 254.00, "SHEL.L": 2580.00,
}

GLOBAL_SECTORS = [
    {"name": "Defense / Geopolitics",
     "keywords": ["defense","defence","military","war","nato","missile","army","ceasefire",
                  "pakistan","china","border","conflict"],
     "nse": ["HAL.NS","BEL.NS"], "signal": "positive"},
    {"name": "Oil & Energy",
     "keywords": ["oil","crude","opec","petroleum","bpcl","ongc","exxon","shell",
                  "energy","refinery","petrol","diesel"],
     "nse": ["BPCL.NS","IOC.NS","HINDPETRO.NS","ONGC.NS"], "signal": "negative"},
    {"name": "Pharma / Healthcare",
     "keywords": ["pharma","drug","fda","health","medicine","cipla","pfizer",
                  "novartis","pandemic","biotech"],
     "nse": ["SUNPHARMA.NS","CIPLA.NS","DRREDDY.NS"], "signal": "positive"},
    {"name": "Tech / AI",
     "keywords": ["ai","artificial intelligence","chip","semiconductor","nvidia",
                  "microsoft","cloud","llm","automation","software","it sector"],
     "nse": ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"], "signal": "positive"},
    {"name": "Banking & Rates",
     "keywords": ["bank","rate","fed","ecb","rbi","repo","inflation","credit",
                  "interest","npa","liquidity","monetary"],
     "nse": ["HDFCBANK.NS","SBIN.NS","ICICIBANK.NS","AXISBANK.NS"], "signal": "positive"},
    {"name": "Safe Haven / Gold",
     "keywords": ["gold","silver","safe haven","risk off","vix","dollar","yen",
                  "recession","fear"],
     "nse": ["MCX.NS","TITAN.NS"], "signal": "positive"},
    {"name": "Trade / Macro",
     "keywords": ["trade","tariff","export","import","supply chain","dollar",
                  "forex","rupee","euro","gdp","growth"],
     "nse": ["RELIANCE.NS","MARUTI.NS"], "signal": "positive"},
    {"name": "Auto / EV",
     "keywords": ["ev","electric vehicle","tesla","auto","automobile","maruti",
                  "car","suv","battery","vehicle sales"],
     "nse": ["MARUTI.NS","TATAPOWER.NS"], "signal": "positive"},
]

STRIP = re.compile(r"<[^>]+>")

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_price(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                    "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        meta = d["chart"]["result"][0]["meta"]
        return meta.get("regularMarketPrice") or meta.get("previousClose")
    except:
        return None

def pct(today, base):
    if today and base:
        return round((today - base) / base * 100, 2)
    return None

def fetch_news():
    import xml.etree.ElementTree as ET
    RSS = {
        "IN": ["https://www.livemint.com/rss/markets",
               "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"],
        "US": ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"],
        "EU": ["https://feeds.bbci.co.uk/news/business/rss.xml"],
    }
    all_text = []
    for feeds in RSS.values():
        for url in feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
                for item in list(root.iter("item"))[:8]:
                    t = STRIP.sub("", item.findtext("title","")).strip()
                    d = STRIP.sub("", item.findtext("description","")).strip()
                    if t:
                        all_text.append((t + " " + d).lower())
            except:
                pass
    return all_text

# ── Signal log CSV ────────────────────────────────────────────────────────────
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

def append_signals(new_signals):
    rows = load_log()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    existing_today = {r["instrument"] for r in rows if r["date"] == today}
    for sig in new_signals:
        if sig["instrument"] not in existing_today:
            rows.append({**sig, "follow_through_pct": "", "scored_date": ""})
    save_log(rows)
    return rows

def score_old_signals(rows, prices):
    """Score signals older than 1 day that haven't been scored yet."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    scored_count = 0
    for row in rows:
        if row["follow_through_pct"] or row["date"] == today:
            continue
        ticker  = row["instrument"]
        p_emit  = float(row["price_at_emission"]) if row["price_at_emission"] else None
        p_now   = prices.get(ticker) or get_price(ticker)
        if p_emit and p_now:
            row["follow_through_pct"] = str(round((p_now - p_emit) / p_emit * 100, 2))
            row["scored_date"] = today
            scored_count += 1
    return rows, scored_count

# ── Signal selection (1-2 high-conviction picks) ─────────────────────────────
def pick_signals(prices, all_text):
    """
    Select max 2 signals by combining:
    - Biggest mover with strong news backing (not just noise)
    - Strongest news theme with confirmed price action
    Returns list of dicts: {instrument, price_at_emission, signal_type, reason}
    """
    combined = " ".join(all_text)
    signals  = []

    # ── Candidate 1: biggest NSE mover with a news reason ──────────────────
    nse_moves = []
    for sector in GLOBAL_SECTORS:
        hits = [kw for kw in sector["keywords"] if kw in combined]
        if not hits:
            continue
        for ticker in sector["nse"]:
            p = prices.get(ticker)
            r = pct(p, BASELINE.get(ticker))
            if r is not None:
                nse_moves.append((abs(r), r, ticker, sector["name"],
                                  hits[:2], sector["signal"]))

    nse_moves.sort(reverse=True)
    if nse_moves:
        _, r_val, ticker, sector_name, triggers, sig_type = nse_moves[0]
        p_now = prices.get(ticker)
        direction = "▲" if r_val > 0 else "▼"
        signals.append({
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "instrument": ticker,
            "price_at_emission": str(round(p_now, 2)) if p_now else "",
            "signal_type": sig_type.upper(),
            "reason": f"{sector_name} | news: {', '.join(triggers)} | {direction}{abs(r_val):.1f}% vs baseline",
        })

    # ── Candidate 2: macro risk signal (Gold or Crude with threshold) ───────
    gold_r  = pct(prices.get("GC=F"), BASELINE.get("GC=F"))
    crude_r = pct(prices.get("CL=F"), BASELINE.get("CL=F"))
    sp_r    = pct(prices.get("^GSPC"), BASELINE.get("^GSPC"))
    nsei_r  = pct(prices.get("^NSEI"), BASELINE.get("^NSEI"))

    macro_sig = None
    if gold_r is not None and gold_r > 15:
        macro_sig = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "instrument": "GC=F",
            "price_at_emission": str(round(prices["GC=F"], 2)),
            "signal_type": "MACRO",
            "reason": f"Gold {gold_r:+.1f}% vs baseline — extreme risk-off; defensive posture",
        }
    elif crude_r is not None and abs(crude_r) > 20:
        direction = "surge" if crude_r > 0 else "crash"
        macro_sig = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "instrument": "CL=F",
            "price_at_emission": str(round(prices["CL=F"], 2)),
            "signal_type": "MACRO",
            "reason": f"Crude {crude_r:+.1f}% — {direction}; watch BPCL/IOC/ONGC",
        }
    elif sp_r is not None and nsei_r is not None and abs(nsei_r - sp_r) > 15:
        spread = nsei_r - sp_r
        macro_sig = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "instrument": "^NSEI",
            "price_at_emission": str(round(prices["^NSEI"], 2)) if prices.get("^NSEI") else "",
            "signal_type": "DIVERGENCE",
            "reason": f"Nifty ({nsei_r:+.1f}%) vs S&P ({sp_r:+.1f}%) gap={spread:+.1f}% — convergence trade setup",
        }

    if macro_sig and (not signals or signals[0]["instrument"] != macro_sig["instrument"]):
        signals.append(macro_sig)

    return signals[:2]

# ── Score summary for the report ──────────────────────────────────────────────
def score_summary(rows):
    scored = [r for r in rows if r["follow_through_pct"]]
    if len(scored) < 3:
        return f"_{len(scored)} signal(s) scored so far — need ~10 for meaningful edge assessment_"

    total     = len(scored)
    positive  = [r for r in scored if float(r["follow_through_pct"]) > 0]
    by_type   = {}
    for r in scored:
        t = r["signal_type"]
        by_type.setdefault(t, []).append(float(r["follow_through_pct"]))

    win_rate = len(positive) / total * 100
    avg_ft   = sum(float(r["follow_through_pct"]) for r in scored) / total

    lines = [
        f"**Win rate:** {win_rate:.0f}% ({len(positive)}/{total} signals positive follow-through)",
        f"**Avg follow-through:** {avg_ft:+.1f}%",
    ]
    for sig_type, vals in by_type.items():
        avg = sum(vals) / len(vals)
        lines.append(f"**{sig_type}:** {avg:+.1f}% avg over {len(vals)} signals")
    return "\n".join(f"- {l}" for l in lines)

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID,
                           f"⚠️ *Vest Signal Logger failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    run_ts    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    NL        = "\n"

    print("Fetching news...")
    all_text = fetch_news()

    print("Fetching prices...")
    watch_tickers = list(BASELINE.keys())
    prices = {}
    for t in watch_tickers:
        prices[t] = get_price(t)
        time.sleep(0.15)

    print("Picking signals...")
    today_signals = pick_signals(prices, all_text)

    print("Loading + scoring signal log...")
    rows = append_signals(today_signals)
    rows, scored_count = score_old_signals(rows, prices)
    save_log(rows)
    print(f"  Scored {scored_count} prior signal(s)")

    # ── Build report ─────────────────────────────────────────────────────────
    signal_lines = []
    for s in today_signals:
        ticker  = s["instrument"]
        p       = float(s["price_at_emission"]) if s["price_at_emission"] else None
        p_base  = BASELINE.get(ticker)
        r_val   = pct(p, p_base)
        currency = "₹" if ticker.endswith(".NS") else ("$" if not ticker.endswith(".L") else "p")
        p_str   = f"{currency}{p:,.0f}" if p else "N/A"
        r_str   = f"{r_val:+.1f}%" if r_val is not None else ""
        signal_lines.append(
            f"### {ticker.replace('.NS','').replace('=F','')}\n"
            f"**Price:** {p_str}  |  **vs Baseline:** {r_str}  |  **Type:** {s['signal_type']}\n\n"
            f"> {s['reason']}\n\n"
            f"**Log entry:** _{today_str} · price locked at {p_str}_"
        )

    scored_rows = [r for r in rows if r["follow_through_pct"]]
    score_block = score_summary(rows)

    # Recent scored signals (last 5)
    recent = sorted(
        [r for r in rows if r["follow_through_pct"]],
        key=lambda r: r["date"], reverse=True
    )[:5]
    recent_lines = []
    for r in recent:
        ft = float(r["follow_through_pct"])
        icon = "✅" if ft > 0 else "❌"
        recent_lines.append(
            f"| {icon} | {r['date']} | {r['instrument']} | "
            f"₹{r['price_at_emission']} | {ft:+.1f}% | {r['signal_type']} |"
        )

    md = (
        f"# 🎯 Vest Signal Log — {today_str}\n"
        f"_Run: {run_ts} · Total signals logged: {len(rows)} · Scored: {len(scored_rows)}_\n\n"
        f"---\n\n"
        f"## Today's 1–2 High-Conviction Signals\n\n"
        f"_These are the only signals worth tracking today. Less is more._\n\n"
        f"{NL.join(NL.join(['---', s]) for s in signal_lines)}\n\n"
        f"---\n\n"
        f"## 📊 Edge Scorecard\n\n"
        f"{score_block}\n\n"
        + (
            f"### Recent Follow-Through\n\n"
            f"| | Date | Instrument | Emitted | Follow-Through | Type |\n"
            f"|---|---|---|---|---|---|\n"
            f"{NL.join(recent_lines)}\n\n"
            if recent_lines else ""
        ) +
        f"---\n\n"
        f"## 📋 What This Means\n\n"
        f"- Each signal is logged with today's price. Tomorrow's run will score it.\n"
        f"- After 60–90 days, the Edge Scorecard will show whether these signals have real predictive value.\n"
        f"- Only act on signal types that show consistent positive follow-through in the scorecard.\n\n"
        f"---\n"
        f"_Vest · Signal Logger · {run_ts}_\n"
    )

    print(md)
    summary = f"🎯 Vest Signal Log {today_str} — {len(today_signals)} signal(s) · {len(scored_rows)} scored"
    publish(TG_TOKEN, TG_CHAT_ID, md, "signal-log", summary)
    print("Done.")

except Exception as e:
    import traceback
    traceback.print_exc()
    send_error(e)
    raise
