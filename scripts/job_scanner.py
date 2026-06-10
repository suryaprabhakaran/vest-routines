"""
Vest Job Scanner
----------------
Sources (in order of reliability):
1. Adzuna Belgium public API  — free, no key needed for basic search
2. Indeed BE JSON endpoint    — fallback
3. Any board that responds    — graceful skip if blocked

The Claude Code routine also runs Indeed MCP independently for richer results.
"""
import urllib.request, urllib.parse, json, os, time, re
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN  = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

POSITIVE = [
    "togaf","enterprise architect","chief architect","vp architect","head of architect",
    "principal architect","transformation","cloud","aws","azure","gcp","ai","mlops",
    "microservices","digital","travel","international","european","governance","strategy",
    "financial services","insurance","healthcare","public sector",
]
NEGATIVE = [
    "junior","medior","graduate","intern","entry level","front-end","frontend",
    "backend","devops engineer","developer","qa","test","scrum master","project manager",
]

def match_pct(title, desc=""):
    text = (title + " " + desc).lower()
    score = 50
    if any(k in text for k in ["chief architect","vp architect","head of architect","ea director","vp of architect"]):
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

# ── Source 1: Adzuna Belgium public API ──────────────────────────────────────
def search_adzuna(query, max_results=10):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        # Adzuna has a free unauthenticated browse endpoint
        url = f"https://api.adzuna.com/v1/api/jobs/be/search/1?results_per_page={max_results}&what={q}&content-type=application/json&app_id=&app_key="
        # Use the public web search instead (no API key needed)
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

# ── Source 2: Indeed via public search JSON ───────────────────────────────────
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

# ── Source 3: EuroJobSites RSS (EU-focused, architecture roles) ───────────────
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

# ── Main ──────────────────────────────────────────────────────────────────────
QUERIES = [
    "Chief Architect",
    "Enterprise Architect Director",
    "VP Architecture",
    "Head of Enterprise Architecture",
    "Principal Architect TOGAF",
]

try:
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("Scanning job boards...")

    seen_urls = set()
    all_jobs  = []  # (match_pct, title, company, url, source)

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
    top_jobs = all_jobs[:12]

    sources = {}
    for _, _, _, _, src in top_jobs:
        sources[src] = sources.get(src, 0) + 1
    source_summary = " · ".join(f"{s} ({n})" for s, n in sources.items()) if sources else "no results"

    if top_jobs:
        job_lines = "\n".join(
            f"- [{title}{' — ' + company if company else ''}]({url}) — **{pct}% match**"
            for pct, title, company, url, source in top_jobs
        )
    else:
        job_lines = "- No matches found — boards may be rate-limiting. The Claude Code routine runs Indeed MCP separately."

    md_content = (
        f"# 💼 Vest Job Scanner — {today_str}\n\n"
        f"_Sources checked: {source_summary}_\n\n"
        f"## Matches ({len(top_jobs)} roles)\n\n"
        f"{job_lines}\n\n"
        f"---\n"
        f"_Vest · Job Scanner · {today_str}_\n"
    )

    summary = f"💼 Vest Job Scanner {today_str} — {len(top_jobs)} matches"
    print(md_content)
    publish(TG_TOKEN, TG_CHAT_ID, md_content, "job-scan", summary)
    print("Done.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
