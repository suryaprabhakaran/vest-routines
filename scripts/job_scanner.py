import urllib.request, urllib.parse, json, os, time, re, xml.etree.ElementTree as ET
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

STRIP = re.compile(r"<[^>]+>")

POSITIVE_SIGNALS = [
    "togaf", "enterprise architect", "chief architect", "vp architect",
    "head of architect", "principal architect", "transformation", "cloud",
    "aws", "azure", "gcp", "ai", "mlops", "microservices", "digital",
    "travel", "international", "european", "governance", "strategy",
    "financial services", "insurance", "healthcare", "public sector",
]
NEGATIVE_SIGNALS = [
    "junior", "medior", "graduate", "intern", "entry level",
    "front-end", "frontend", "backend", "devops engineer", "developer",
    "qa", "test", "scrum master", "project manager",
]

# ── Board scrapers ────────────────────────────────────────────────────────────

def scrape_rss(url, source_name, max_items=8):
    """Generic RSS scraper — returns list of (title, link, desc)."""
    results = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
        for item in list(root.iter("item"))[:max_items]:
            title = STRIP.sub("", item.findtext("title", "")).strip()
            link  = item.findtext("link", "").strip()
            desc  = STRIP.sub("", item.findtext("description", "")).strip()[:300]
            if title and link:
                results.append((title, link, desc, source_name))
    except Exception as e:
        print(f"RSS error [{source_name}]: {e}")
    return results

def search_indeed_rss(query, location="Belgium"):
    q = urllib.parse.quote_plus(query)
    l = urllib.parse.quote_plus(location)
    url = f"https://be.indeed.com/rss?q={q}&l={l}&sort=date&fromage=14"
    return scrape_rss(url, "Indeed BE")

def search_linkedin_rss(query, location="Belgium"):
    q = urllib.parse.quote_plus(query)
    l = urllib.parse.quote_plus(location)
    url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={l}&f_TPR=r604800&format=rss"
    return scrape_rss(url, "LinkedIn")

def search_stepstone(query):
    q = urllib.parse.quote_plus(query)
    url = f"https://www.stepstone.be/candidate/search-results?query={q}&location=Belgium&radius=30&sort=date&format=rss"
    return scrape_rss(url, "Stepstone BE")

def search_eurojobs(query):
    # EuroBrussels / EU-focused boards
    q = urllib.parse.quote_plus(query)
    url = f"https://www.eurojobs.com/search-results/?q={q}&l=Belgium&format=rss"
    return scrape_rss(url, "EuroJobs")

# ── Scoring ───────────────────────────────────────────────────────────────────

def match_pct(title, desc):
    """Score 0-100 match against Surya's profile."""
    text = (title + " " + desc).lower()
    score = 50
    # positive signals
    if any(k in text for k in ["chief architect","vp architect","head of architect","ea director"]):
        score += 10  # senior title
    if "belgium" in text or "brussels" in text or "antwerp" in text or "ghent" in text:
        score += 10  # location confirmed
    if any(k in text for k in ["togaf","cloud","aws","azure","gcp"]):
        score += 10  # tech fit
    if any(k in text for k in ["travel","international","european","pan-european"]):
        score += 10  # travel
    if any(k in text for k in ["financial","insurance","healthcare","public sector","banking"]):
        score += 10  # industry fit
    # negative signals
    if any(k in text for k in ["junior","medior","graduate","intern","entry level"]):
        score -= 20
    if any(k in text for k in ["developer","devops","frontend","backend","qa","scrum"]):
        score -= 20
    return min(max(score, 0), 100)

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
    all_jobs = []  # (match_pct, title, url, source)

    for query in QUERIES:
        for fn in [search_indeed_rss, search_linkedin_rss, search_stepstone, search_eurojobs]:
            try:
                results = fn(query) if fn != search_indeed_rss else search_indeed_rss(query)
                for title, url, desc, source in results:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    pct = match_pct(title, desc)
                    if pct >= 60:
                        all_jobs.append((pct, title, url, source))
            except Exception as e:
                print(f"Board error: {e}")
            time.sleep(0.3)

    # Sort by match % descending, dedupe by title similarity
    all_jobs.sort(key=lambda x: x[0], reverse=True)
    top_jobs = all_jobs[:12]

    # Build source summary
    sources = {}
    for _, _, _, src in top_jobs:
        sources[src] = sources.get(src, 0) + 1
    source_summary = " · ".join(f"{src} ({n})" for src, n in sources.items())

    job_lines = "\n".join(
        f"- [{title} — {source}]({url}) — **{pct}% match**"
        for pct, title, url, source in top_jobs
    ) or "- No strong matches found this week."

    md_content = (
        f"# 💼 Vest Job Scanner — {today_str}\n\n"
        f"_Sources: {source_summary or 'Indeed · LinkedIn · Stepstone · EuroJobs'}_\n\n"
        f"## Matches ({len(top_jobs)} roles)\n\n"
        f"{job_lines}\n\n"
        f"---\n"
        f"_Vest · Job Scanner · {today_str}_\n"
    )

    summary = f"💼 Vest Job Scanner {today_str} — {len(top_jobs)} matches across {len(sources)} boards"
    print(md_content)
    publish(TG_TOKEN, TG_CHAT_ID, md_content, "job-scan", summary)
    print("Sent successfully.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
