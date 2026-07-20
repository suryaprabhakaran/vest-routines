"""
Vest Job Scanner
----------------
Scans Belgian job boards for two profiles:
  - Surya Prabhakaran      : Chief Enterprise Architect (senior tech leadership)
  - Ramalakshmi Perianayagam: PMO / Programme Manager (governance, delivery)

Sources (in order of reliability):
1. Adzuna Belgium public API  — free, no key needed for basic search
2. Indeed BE JSON endpoint    — fallback
3. EuroJobSites RSS           — EU-focused

The Claude Code routine also runs Indeed MCP independently for richer results
and writes its own output files with the same prefixes.
"""
import urllib.request, urllib.parse, json, os, time, re
from datetime import datetime, date
from output_helper import publish, send_telegram_text

# ── Job-seen registry (suppress roles after 3 days) ───────────────────────────
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "job-registry.json")
ROLE_TTL_DAYS = 3

def load_registry():
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_registry(registry):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

def is_fresh(registry, url, today):
    """Return True if this URL should be shown today (new or within TTL)."""
    first_seen = registry.get(url)
    if first_seen is None:
        return True
    age = (date.fromisoformat(today) - date.fromisoformat(first_seen)).days
    return age < ROLE_TTL_DAYS

TG_TOKEN  = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Surya: Chief Enterprise Architect ─────────────────────────────────────────
SURYA_QUERIES = [
    "Chief Architect",
    "Enterprise Architect Director",
    "VP Architecture",
    "Head of Enterprise Architecture",
    "Principal Architect TOGAF",
]

def match_pct_surya(title, desc=""):
    text = (title + " " + desc).lower()
    score = 50
    if any(k in text for k in [
        "chief architect","vp architect","head of architect","ea director",
        "vp of architect","lead enterprise architect","enterprise architect",
        "principal architect",
    ]):
        score += 10
    if any(k in text for k in ["belgium","brussels","antwerp","ghent","liege","bruges"]):
        score += 10
    if any(k in text for k in ["togaf","cloud","aws","azure","gcp"]):
        score += 10
    if any(k in text for k in ["travel","international","european","pan-european"]):
        score += 10
    if any(k in text for k in ["financial","insurance","healthcare","public sector","banking"]):
        score += 10
    if any(k in text for k in ["junior","medior","graduate","intern","entry level"]):
        score -= 20
    if any(k in text for k in ["developer","devops","frontend","backend","qa","scrum"]):
        score -= 20
    return min(max(score, 0), 100)

# ── Ramalakshmi: PMO / Programme Manager ──────────────────────────────────────
RAMALAKSHMI_QUERIES = [
    "PMO Manager Belgium",
    "PMO Lead Belgium",
    "Programme Manager Belgium",
    "Head of PMO Belgium",
    "Portfolio Manager Belgium",
    "Governance Manager Belgium",
    "Delivery Manager Belgium",
    "Service Delivery Manager Belgium",
]

def match_pct_ramalakshmi(title, desc=""):
    text = (title + " " + desc).lower()
    score = 50
    if any(k in text for k in [
        "pmo manager","pmo lead","head of pmo","programme manager","program manager",
        "portfolio manager","delivery manager","governance manager",
        "service delivery manager","project management office",
    ]):
        score += 10
    if any(k in text for k in ["belgium","brussels","antwerp","ghent","liege","bruges"]):
        score += 10
    if any(k in text for k in ["itil","agile","waterfall","governance","programme","pmo","jira","confluence","stakeholder"]):
        score += 10
    if any(k in text for k in ["banking","financial","telecoms","telecom","technology","insurance","consulting"]):
        score += 10
    if any(k in text for k in ["senior","lead","head","manager","director"]):
        score += 10
    if any(k in text for k in ["junior","medior","graduate","intern","entry level"]):
        score -= 20
    if any(k in text for k in ["developer","devops","frontend","backend","qa","architect","data scientist","scrum master"]):
        score -= 20
    return min(max(score, 0), 100)

# ── Source 1: Adzuna Belgium public API ───────────────────────────────────────
def search_adzuna(query, max_results=10):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://www.adzuna.be/search?q={q}&w=Belgium&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("title","").strip()
            company = job.get("company",{}).get("display_name","") or job.get("company","")
            link    = job.get("redirect_url","") or job.get("url","")
            desc    = job.get("description","")[:200]
            if title and link:
                results.append((title, company, link, desc, "Adzuna BE"))
    except Exception as e:
        print(f"Adzuna error [{query}]: {e}")
    return results

# ── Source 2: Indeed via public search JSON ────────────────────────────────────
def search_indeed_json(query, location="Belgium", max_results=10):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        l = urllib.parse.quote_plus(location)
        url = f"https://be.indeed.com/jobs?q={q}&l={l}&sort=date&fromage=14&format=json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        for job in data.get("results", [])[:max_results]:
            title   = job.get("jobtitle","").strip()
            company = job.get("company","").strip()
            link    = "https://be.indeed.com" + job.get("url","")
            desc    = job.get("snippet","")[:200]
            if title and link:
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
            title = STRIP.sub("", item.findtext("title","")).strip()
            link  = item.findtext("link","").strip()
            desc  = STRIP.sub("", item.findtext("description","")).strip()[:200]
            if title and link:
                results.append((title, "", link, desc, "EuroJobSites"))
    except Exception as e:
        print(f"EuroJobSites error [{query}]: {e}")
    return results

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Job Scanner failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

def _reg_key(title, company):
    """Canonical registry key: 'company|title' (lowercase, normalised whitespace).

    Using company+title instead of URL because Indeed generates fresh redirect
    URLs every session, which would cause the same job to appear every day.
    """
    import re as _re
    def _n(s): return _re.sub(r'\s+', ' ', s.lower().strip())
    return f"{_n(company)}|{_n(title)}"


def run_scan(queries, scorer_fn, registry, today_str, top_n=12):
    """Run all queries through all sources, deduplicate, score, and return top_n.

    Only includes jobs that are new or were first seen within ROLE_TTL_DAYS.
    Registers newly discovered titles in `registry` (caller must save it).
    """
    seen_keys = set()
    all_jobs  = []
    for query in queries:
        for fn in [search_adzuna, search_indeed_json, search_eurojobsites]:
            try:
                rows = fn(query)
                for title, company, url, desc, source in rows:
                    key = _reg_key(title, company)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    if not is_fresh(registry, key, today_str):
                        continue
                    pct = scorer_fn(title, desc)
                    if pct >= 70:
                        if key not in registry:
                            registry[key] = today_str
                        all_jobs.append((pct, title, company, url, source))
            except Exception as e:
                print(f"Error in {fn.__name__}: {e}")
            time.sleep(0.4)
    all_jobs.sort(key=lambda x: x[0], reverse=True)
    return all_jobs[:top_n]

def build_md(today_str, person_name, jobs):
    if jobs:
        sources = {}
        for _, _, _, _, src in jobs:
            sources[src] = sources.get(src, 0) + 1
        source_summary = " · ".join(f"{s} ({n})" for s, n in sources.items())
        job_lines = "\n".join(
            f"- [{title}{' — ' + company if company else ''}]({url}) — **{pct}% match**"
            for pct, title, company, url, _ in jobs
        )
    else:
        source_summary = "no results"
        job_lines = "- No matches found — boards may be rate-limiting. The Claude Code routine runs Indeed MCP separately."

    return (
        f"# 💼 Vest Job Scanner — {person_name} — {today_str}\n\n"
        f"_Sources checked: {source_summary}_\n\n"
        f"## Matches ({len(jobs)} roles)\n\n"
        f"{job_lines}\n\n"
        f"---\n"
        f"_Vest · Job Scanner · {today_str}_\n"
    )

# ── Main ──────────────────────────────────────────────────────────────────────
try:
    today_str = datetime.now().strftime("%Y-%m-%d")
    registry  = load_registry()
    print(f"Scanning job boards (registry: {len(registry)} known URLs)...")

    # Surya: Chief Enterprise Architect
    print("\n--- Surya (Enterprise Architect) ---")
    surya_jobs = run_scan(SURYA_QUERIES, match_pct_surya, registry, today_str, top_n=12)
    surya_md   = build_md(today_str, "Surya", surya_jobs)
    print(surya_md)
    publish(TG_TOKEN, TG_CHAT_ID, surya_md, "job-scan",
            f"💼 Vest Job Scanner · Surya · {today_str} — {len(surya_jobs)} matches")

    # Ramalakshmi: PMO / Programme Manager
    print("\n--- Ramalakshmi (PMO / Programme Manager) ---")
    rama_jobs = run_scan(RAMALAKSHMI_QUERIES, match_pct_ramalakshmi, registry, today_str, top_n=12)
    rama_md   = build_md(today_str, "Ramalakshmi", rama_jobs)
    print(rama_md)
    publish(TG_TOKEN, TG_CHAT_ID, rama_md, "job-scan-ramalakshmi",
            f"💼 Vest Job Scanner · Ramalakshmi · {today_str} — {len(rama_jobs)} matches")

    save_registry(registry)
    print(f"Done. Registry saved ({len(registry)} URLs total).")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
