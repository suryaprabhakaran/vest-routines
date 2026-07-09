"""
Vest PMO Scanner
----------------
Scans Belgian job boards for PMO, Programme Manager, and Governance roles
tailored to Ramalakshmi Perianayagam's profile:
  - 13+ years PMO experience across banking, telecoms, and technology
  - Skills: ITIL, governance, Agile/Waterfall, JIRA, Confluence, Clarity,
    SLA, vendor management, financial governance, stakeholder comms
  - Target titles: PMO Manager/Lead/Director, Head of PMO, Programme
    Manager, Governance Manager, Delivery Manager — Belgium-based

Sources (in order): Adzuna BE → Indeed BE JSON → EuroJobSites RSS
"""
import urllib.request, urllib.parse, json, os, time, re
from datetime import datetime, timedelta
from output_helper import publish, send_telegram_text

TG_TOKEN   = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

MAX_AGE_DAYS = 30   # drop any listing posted more than this many days ago

def _age_days(date_str):
    """Return days since date_str, or None if unparseable (→ include by default)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return (datetime.now() - datetime.strptime(date_str[:len(fmt)], fmt)).days
        except ValueError:
            pass
    try:
        from email.utils import parsedate
        t = parsedate(date_str)
        if t:
            return (datetime.now() - datetime(*t[:6])).days
    except Exception:
        pass
    return None

def _fresh(date_str):
    age = _age_days(date_str)
    return age is None or age <= MAX_AGE_DAYS

# ── Scoring ───────────────────────────────────────────────────────────────────

def match_pct(title, desc=""):
    """
    Score 0-100 against Ramalakshmi's PMO profile.
      Base 50
      +10  senior PMO/Programme/Governance title
      +10  Belgium location confirmed
      +10  PMO tools/methods/frameworks mentioned (ITIL, governance, Agile…)
      +10  target industry (banking, financial, telecoms, tech, public sector)
      +10  seniority/leadership signals in body
      -20  junior/trainee signal
      -20  developer/engineering/non-PMO signal
    """
    text = (title + " " + desc).lower()
    score = 50

    if any(k in text for k in [
        "pmo manager", "pmo lead", "pmo director", "head of pmo",
        "senior pmo", "programme manager", "program manager",
        "governance manager", "delivery manager", "senior programme",
        "senior program", "portfolio manager", "head of programme",
    ]):
        score += 10

    if any(k in text for k in [
        "belgium", "brussels", "bruxelles", "antwerp", "ghent", "liege",
        "bruges", "leuven", "mechelen", "zaventem", "louvain",
    ]):
        score += 10

    if any(k in text for k in [
        "itil", "governance", "agile", "waterfall", "jira", "confluence",
        "clarity", "sla", "stakeholder", "vendor management", "procurement",
        "financial governance", "kpi", "dashboard", "programme delivery",
        "program management office", "pmo", "risk management", "budget",
        "reporting", "compliance framework",
    ]):
        score += 10

    if any(k in text for k in [
        "banking", "financial", "finance", "insurance", "telecoms", "telecom",
        "technology", "public sector", "government", "eu institution",
        "european commission", "nato", "healthcare", "pharma",
    ]):
        score += 10

    if any(k in text for k in [
        "senior", "lead", "head", "director", "strategic", "enterprise",
        "cross-functional", "c-level", "executive", "transformation",
        "10+ years", "leadership",
    ]):
        score += 10

    if any(k in text for k in ["junior", "graduate", "intern", "entry level", "trainee"]):
        score -= 20
    if any(k in text for k in [
        "developer", "software engineer", "devops", "frontend", "backend",
        "data engineer", "qa engineer", "test engineer", "full stack",
    ]):
        score -= 20

    return min(max(score, 0), 100)


# ── Source 1: Adzuna Belgium public API ──────────────────────────────────────

def search_adzuna(query, max_results=10):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://www.adzuna.be/search?q={q}&w=Belgium&days_since={MAX_AGE_DAYS}&format=json"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("title", "").strip()
            company = job.get("company", {}).get("display_name", "") or job.get("company", "")
            link    = job.get("redirect_url", "") or job.get("url", "")
            desc    = job.get("description", "")[:300]
            created = job.get("created", "")
            if title and link and _fresh(created):
                results.append((title, company, link, desc, "Adzuna BE"))
    except Exception as e:
        print(f"Adzuna error [{query}]: {e}")
    return results


# ── Source 2: Indeed BE JSON endpoint ────────────────────────────────────────

def search_indeed_json(query, location="Belgium", max_results=10):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        l = urllib.parse.quote_plus(location)
        url = f"https://be.indeed.com/jobs?q={q}&l={l}&sort=date&fromage={MAX_AGE_DAYS}&format=json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("jobtitle", "").strip()
            company = job.get("company", "").strip()
            link    = "https://be.indeed.com" + job.get("url", "")
            desc    = job.get("snippet", "")[:300]
            date    = job.get("date", "")
            if title and link and _fresh(date):
                results.append((title, company, link, desc, "Indeed BE"))
    except Exception as e:
        print(f"Indeed JSON error [{query}]: {e}")
    return results


# ── Source 3: EuroJobSites RSS ────────────────────────────────────────────────

def search_eurojobsites(query):
    results = []
    try:
        import xml.etree.ElementTree as ET
        STRIP = re.compile(r"<[^>]+>")
        q = urllib.parse.quote_plus(query)
        url = f"https://www.eurojobsites.com/jobs/rss/?q={q}&c=Belgium"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
        for item in list(root.iter("item"))[:8]:
            title   = STRIP.sub("", item.findtext("title", "")).strip()
            link    = item.findtext("link", "").strip()
            desc    = STRIP.sub("", item.findtext("description", "")).strip()[:300]
            pubdate = item.findtext("pubDate", "").strip()
            if title and link and _fresh(pubdate):
                results.append((title, "", link, desc, "EuroJobSites"))
    except Exception as e:
        print(f"EuroJobSites error [{query}]: {e}")
    return results


def send_error(err):
    try:
        send_telegram_text(
            TG_TOKEN, TG_CHAT_ID,
            f"⚠️ *Vest PMO Scanner failed*\n```\n{str(err)[:300]}\n```"
        )
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

QUERIES = [
    "PMO Manager Belgium",
    "Programme Manager PMO",
    "Head of PMO",
    "Governance Manager Belgium",
    "PMO Lead ITIL",
]

try:
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("Scanning job boards for PMO roles...")

    seen_urls = set()
    all_jobs  = []   # (score, title, company, url, source)

    for query in QUERIES:
        for fn in [search_adzuna, search_indeed_json, search_eurojobsites]:
            try:
                rows = fn(query)
                for title, company, url, desc, source in rows:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    pct = match_pct(title, desc)
                    if pct >= 60:
                        all_jobs.append((pct, title, company, url, source))
            except Exception as e:
                print(f"Error in {fn.__name__}: {e}")
            time.sleep(0.4)

    all_jobs.sort(key=lambda x: x[0], reverse=True)
    top_jobs = all_jobs[:15]

    sources = {}
    for _, _, _, _, src in top_jobs:
        sources[src] = sources.get(src, 0) + 1
    source_summary = (
        " · ".join(f"{s} ({n})" for s, n in sources.items())
        if sources else "no results"
    )

    if top_jobs:
        job_lines = "\n".join(
            f"- [{title}{' — ' + company if company else ''}]({url}) — **{pct}% match**"
            for pct, title, company, url, source in top_jobs
        )
    else:
        job_lines = (
            "- No matches found this run — boards may be rate-limiting. "
            "Re-run manually or check back next cycle."
        )

    md_content = (
        f"# 📋 Vest PMO Scanner — {today_str}\n\n"
        f"_Sources checked: {source_summary}_\n\n"
        f"## Matches ({len(top_jobs)} roles)\n\n"
        f"{job_lines}\n\n"
        f"---\n"
        f"_Vest · PMO Scanner · {today_str}_\n"
    )

    summary = f"📋 Vest PMO Scanner {today_str} — {len(top_jobs)} matches"
    print(md_content)
    publish(TG_TOKEN, TG_CHAT_ID, md_content, "pmo-scan", summary)
    print("Done.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
