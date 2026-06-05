import urllib.request, urllib.parse, json, os, time, re, xml.etree.ElementTree as ET
from datetime import datetime
from output_helper import publish, send_telegram_text

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ── Profile ─────────────────────────────────────────────────────────────────
# Surya Prabhakaran | Chief Architect / VP Architecture | Belgium | Travel-open
# TOGAF 95% | AWS/Azure/GCP | AI/MLOps | 50+ enterprise transformations

SEARCH_QUERIES = [
    "Chief Architect",
    "Enterprise Architect Director",
    "VP Architecture",
    "Head of Enterprise Architecture",
    "Principal Architect TOGAF",
    "Solution Architect Lead cloud",
]

LOCATION = "Belgium"

# Keywords that signal a good fit (travel, senior scope, relevant tech)
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

# ── Scrapers ────────────────────────────────────────────────────────────────
def search_indeed_rss(query, location="Belgium"):
    """Indeed RSS feed — returns list of (title, company, url, snippet)"""
    q = urllib.parse.quote_plus(query)
    l = urllib.parse.quote_plus(location)
    url = f"https://be.indeed.com/rss?q={q}&l={l}&sort=date&fromage=7"
    results = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
        strip = re.compile(r"<[^>]+>")
        for item in list(root.iter("item"))[:5]:
            title = strip.sub("", item.findtext("title", "")).strip()
            link = item.findtext("link", "").strip()
            desc = strip.sub("", item.findtext("description", "")).strip()[:200]
            results.append((title, link, desc))
    except Exception as e:
        print(f"Indeed RSS error [{query}]: {e}")
    return results

def score_job(title, desc):
    """Return (score, reason) — higher is better fit."""
    text = (title + " " + desc).lower()
    pos = sum(1 for kw in POSITIVE_SIGNALS if kw in text)
    neg = sum(1 for kw in NEGATIVE_SIGNALS if kw in text)
    return pos - (neg * 3)

def send_error(err):
    try:
        send_telegram_text(TG_TOKEN, TG_CHAT_ID, f"⚠️ *Vest Job Scanner failed*\n```\n{str(err)[:300]}\n```")
    except:
        pass

# ── Main ─────────────────────────────────────────────────────────────────────
import urllib.parse

try:
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("Scanning job boards...")

    seen_urls = set()
    all_jobs = []  # (score, title, url, desc, query)

    for query in SEARCH_QUERIES:
        results = search_indeed_rss(query, LOCATION)
        for title, url, desc in results:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            score = score_job(title, desc)
            if score >= 0:  # filter out clear mismatches
                all_jobs.append((score, title, url, desc, query))
        time.sleep(0.5)

    # Sort by score descending
    all_jobs.sort(key=lambda x: x[0], reverse=True)
    top_jobs = all_jobs[:8]

    if top_jobs:
        job_lines = []
        for score, title, url, desc, query in top_jobs:
            fit = "🟢 Strong fit" if score >= 4 else ("🟡 Possible" if score >= 2 else "⚪ Review")
            job_lines.append(
                f"{fit} *{title}*\n"
                f"  _{desc[:120]}_\n"
                f"  [Apply]({url})"
            )
        jobs_block = "\n\n".join(job_lines)
    else:
        jobs_block = "_No new matching roles found this week. Check manually:_\n" \
                     "• [LinkedIn](https://www.linkedin.com/jobs/search/?keywords=chief+architect+TOGAF&location=Belgium)\n" \
                     "• [Indeed BE](https://be.indeed.com/jobs?q=chief+architect&l=Belgium)\n" \
                     "• [EU Careers](https://eu-careers.europa.eu)"

    md_content = f"""# Vest Job Scanner — {today_str}

**Profile:** Chief Architect / VP Architecture | Belgium | Travel OK
**Skills:** TOGAF · AWS · Azure · GCP · AI/MLOps · Enterprise Transformation

## Top Matches ({len(top_jobs)} roles)

""" + "\n\n".join(
        f"### {'🟢' if score >= 4 else ('🟡' if score >= 2 else '⚪')} {title}\n- **Query:** {query}\n- **Snippet:** {desc}\n- **Apply:** {url}"
        for score, title, url, desc, query in top_jobs
    ) + f"""

## Direct Search Links

- [LinkedIn – Chief Architect TOGAF Belgium](https://www.linkedin.com/jobs/search/?keywords=chief+architect+TOGAF&location=Belgium)
- [Indeed BE – Chief Architect](https://be.indeed.com/jobs?q=chief+architect+TOGAF&l=Belgium)
- [EU Careers](https://eu-careers.europa.eu)

---
_Vest · Job Scanner · profile-matched_
"""

    summary = f"💼 Vest Job Scanner {today_str} — {len(top_jobs)} matches found"
    print(md_content)
    publish(TG_TOKEN, TG_CHAT_ID, md_content, "job-scan", summary)
    print("Sent successfully.")

except Exception as e:
    print(f"ERROR: {e}")
    send_error(e)
    raise
