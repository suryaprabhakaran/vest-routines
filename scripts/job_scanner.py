"""
Vest Job Scanner — dual-profile edition
Profiles: Surya (Enterprise Architect) · Ramalakshmi (PMO / Programme)
Rules:  75%+ match threshold · jobs posted within last 30 days only
"""
import urllib.request, urllib.parse, json, os, time, re
from datetime import datetime, timedelta
from output_helper import publish, send_telegram_text

TG_TOKEN   = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Date helpers ──────────────────────────────────────────────────────────────
CUTOFF_DAYS = 30
TODAY       = datetime.utcnow()
CUTOFF_DATE = TODAY - timedelta(days=CUTOFF_DAYS)

def _parse_date(s):
    if not s:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.replace(tzinfo=None)
        except Exception:
            continue
    return None

def is_fresh(date_str):
    """True when posting date is within CUTOFF_DAYS; assume fresh when date is unavailable."""
    dt = _parse_date(date_str)
    return dt is None or dt >= CUTOFF_DATE

# ── Surya — Enterprise Architect ──────────────────────────────────────────────
SURYA_QUERIES = [
    "Chief Architect Belgium",
    "Enterprise Architect Director Belgium",
    "VP Architecture Belgium",
    "Head of Enterprise Architecture Belgium",
    "Principal Architect TOGAF Belgium",
]

def match_surya(title, desc=""):
    text = (title + " " + desc).lower()
    score = 50
    if any(k in text for k in [
        "chief architect", "vp architect", "head of architect", "ea director",
        "lead enterprise architect", "vp of architect",
    ]):
        score += 10
    if any(k in text for k in [
        "belgium", "brussels", "antwerp", "ghent", "liege", "bruges", "leuven", "zaventem",
    ]):
        score += 10
    if any(k in text for k in ["togaf", "cloud", "aws", "azure", "gcp"]):
        score += 10
    if any(k in text for k in ["travel", "international", "european", "pan-european"]):
        score += 10
    if any(k in text for k in ["financial", "insurance", "healthcare", "public sector", "banking"]):
        score += 10
    if any(k in text for k in ["junior", "medior", "graduate", "intern", "entry level"]):
        score -= 20
    if any(k in text for k in ["developer", "devops", "frontend", "backend", "qa", "scrum"]):
        score -= 20
    return min(max(score, 0), 100)

# ── Ramalakshmi — PMO / Programme Management ──────────────────────────────────
# Profile: 13+ yrs, Brussels, ITIL · governance · Agile/Waterfall · vendor mgmt
# Target:  PMO Manager/Lead/Director, Programme Manager, Head of PMO, Portfolio Manager
# Industries: Banking, Financial Services, Telecoms, Technology, Public Sector, Healthcare
RAMA_QUERIES = [
    "PMO Manager Belgium",
    "PMO Lead Belgium",
    "Programme Manager governance Belgium",
    "Head of PMO Belgium",
    "Portfolio Manager delivery Belgium",
    "Delivery Manager ITIL Belgium",
]

def match_rama(title, desc=""):
    text = (title + " " + desc).lower()
    score = 50
    # Title match: senior PMO / programme signals
    if any(k in text for k in [
        "pmo", "programme manager", "program manager", "portfolio manager",
        "delivery manager", "programme director", "program director",
    ]):
        score += 10
    # Belgium location
    if any(k in text for k in [
        "belgium", "brussels", "antwerp", "ghent", "liege", "bruges",
        "leuven", "zaventem", "diegem", "mechelen",
    ]):
        score += 10
    # ITIL / governance / process signals
    if any(k in text for k in [
        "itil", "governance", "sla", "process", "agile", "waterfall",
        "stakeholder", "vendor", "procurement", "compliance",
    ]):
        score += 10
    # Right industry
    if any(k in text for k in [
        "banking", "financial", "insurance", "telecoms", "telecom",
        "technology", "public sector", "healthcare", "pharma",
    ]):
        score += 10
    # International / cross-functional scope
    if any(k in text for k in [
        "international", "global", "cross-functional", "cross functional",
        "european", "europe", "northern europe",
    ]):
        score += 10
    # Junior / non-PMO penalties
    if any(k in text for k in ["junior", "graduate", "intern", "entry level", "level 1"]):
        score -= 20
    if any(k in text for k in ["developer", "devops", "engineer", "qa", "scrum master"]):
        score -= 10
    return min(max(score, 0), 100)

# ── Job board sources ─────────────────────────────────────────────────────────
def search_adzuna(query, max_results=10):
    results = []
    try:
        q   = urllib.parse.quote_plus(query)
        url = f"https://www.adzuna.be/search?q={q}&w=Belgium&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("title", "").strip()
            company = job.get("company", {}).get("display_name", "") or job.get("company", "")
            link    = job.get("redirect_url", "") or job.get("url", "")
            desc    = job.get("description", "")[:200]
            created = job.get("created", "")
            if title and link and is_fresh(created):
                results.append((title, company, link, desc, "Adzuna BE"))
    except Exception as e:
        print(f"Adzuna error [{query}]: {e}")
    return results

def search_indeed_json(query, location="Belgium", max_results=10):
    results = []
    try:
        q   = urllib.parse.quote_plus(query)
        l   = urllib.parse.quote_plus(location)
        # fromage=30 restricts results to last 30 days
        url = f"https://be.indeed.com/jobs?q={q}&l={l}&sort=date&fromage=30&format=json"
        req = urllib.request.Request(url, headers={
            "User-Agent":      "Mozilla/5.0",
            "Accept":          "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("jobtitle", "").strip()
            company = job.get("company", "").strip()
            link    = "https://be.indeed.com" + job.get("url", "")
            desc    = job.get("snippet", "")[:200]
            if title and link:
                results.append((title, company, link, desc, "Indeed BE"))
    except Exception as e:
        print(f"Indeed JSON error [{query}]: {e}")
    return results

def search_eurojobsites(query):
    results = []
    try:
        import xml.etree.ElementTree as ET
        STRIP = re.compile(r"<[^>]+>")
        q   = urllib.parse.quote_plus(query)
        url = f"https://www.eurojobsites.com/jobs/rss/?q={q}&c=Belgium"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
        for item in list(root.iter("item"))[:8]:
            title    = STRIP.sub("", item.findtext("title", "")).strip()
            link     = item.findtext("link", "").strip()
            desc     = STRIP.sub("", item.findtext("description", "")).strip()[:200]
            pub_date = item.findtext("pubDate", "")
            if title and link and is_fresh(pub_date):
                results.append((title, "", link, desc, "EuroJobSites"))
    except Exception as e:
        print(f"EuroJobSites error [{query}]: {e}")
    return results

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Job Scanner failed*\n```\n{str(err)[:300]}\n```")
    except Exception:
        pass

# ── Profile runner ────────────────────────────────────────────────────────────
def run_profile(queries, match_fn, threshold=75, max_results=15):
    seen_urls = set()
    all_jobs  = []
    for query in queries:
        for fn in [search_adzuna, search_indeed_json, search_eurojobsites]:
            try:
                for title, company, url, desc, source in fn(query):
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    pct = match_fn(title, desc)
                    if pct >= threshold:
                        all_jobs.append((pct, title, company, url, source))
            except Exception as e:
                print(f"Error in {fn.__name__} [{query}]: {e}")
            time.sleep(0.4)
    all_jobs.sort(key=lambda x: x[0], reverse=True)
    return all_jobs[:max_results]

def format_md(title_line, today_str, jobs, footer_extra=""):
    if jobs:
        lines = "\n".join(
            f"- [{t}{' — ' + c if c else ''}]({u}) — **{p}% match**"
            for p, t, c, u, _ in jobs
        )
    else:
        lines = "- No 75%+ matches found this week."
    return (
        f"# {title_line} — {today_str}\n\n"
        f"## Matches ({len(jobs)} roles)\n\n"
        f"{lines}\n\n"
        f"---\n"
        f"_Vest · Job Scanner{footer_extra} · {today_str}_\n"
    )

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = TODAY.strftime("%Y-%m-%d")
    print("Scanning job boards (30-day window, 75%+ threshold)...")

    # Surya — Enterprise Architect
    print("\n=== SURYA: Enterprise Architecture ===")
    surya_jobs = run_profile(SURYA_QUERIES, match_surya)
    surya_md   = format_md("💼 Vest Job Scanner", today_str, surya_jobs)
    print(surya_md)
    publish(TG_TOKEN, TG_CHAT_ID, surya_md, "job-scan",
            f"💼 Job Scan (Surya) {today_str} — {len(surya_jobs)} matches")

    # Ramalakshmi — PMO / Programme
    print("\n=== RAMALAKSHMI: PMO / Programme Management ===")
    rama_jobs = run_profile(RAMA_QUERIES, match_rama)
    rama_md   = format_md("💼 Vest Job Scanner (PMO)", today_str, rama_jobs, " · Ramalakshmi")
    print(rama_md)
    publish(TG_TOKEN, TG_CHAT_ID, rama_md, "job-scan-ramalakshmi",
            f"💼 Job Scan (Ramalakshmi) {today_str} — {len(rama_jobs)} matches")

    print("\nDone.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
