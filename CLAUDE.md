# Vest Routines — Project Memory

## What this repo does

Automated weekly intelligence hub for two people. Runs three routines every Sunday 18:00 UTC via GitHub Actions (`vest.yml`), plus on-demand via `/vest` slash command or Claude Code agent.

Routines:
- **job-scanner** (`scripts/job_scanner.py`) — job board scan for Surya + Ramalakshmi
- **market-tracker** (`scripts/nse_tracker.py`) — NSE/global market snapshot
- **signal-logger** (`scripts/signal_logger.py`) — 1-2 high-conviction trade signals

Output files land in `output/` and are committed by `vest-bot`, then sent to Telegram.

---

## Profile 1 — Surya Prabhakaran (job-scan)

**Role:** Chief Enterprise Architect, Brussels, Belgium  
**Targets:** Chief Architect · VP Architecture · Head of EA · EA Director · Principal Architect  
**Location:** Belgium (open to pan-European)  
**Strong fit:** TOGAF · Cloud (AWS/Azure/GCP) · AI/MLOps · Digital Transformation · Travel/International  
**Industries:** Financial Services · Insurance · Healthcare · Public Sector · Technology  
**NOT fit:** Junior · Developer · DevOps · Project Manager  

**Output file prefix:** `job-scan` → `output/job-scan-YYYY-MM-DD.md`  
**Scorer:** `match_pct_surya()` in `scripts/job_scanner.py`

---

## Profile 2 — Ramalakshmi Perianayagam (job-scan-ramalakshmi)

**Role:** PMO Analyst / Independent PMO Consultant, Brussels, Belgium  
**Background:** 13+ years · Banking (HSBC, Lloyds via Virtusa) · Telecoms (Verizon via Infinite) · Technology  
**Targets:** PMO Manager · PMO Lead · Head of PMO · Programme Manager · Portfolio Manager · Governance Manager · Service Delivery Manager · Delivery Manager  
**Location:** Belgium (Brussels preferred)  
**Strong fit:** ITIL · Agile · Waterfall · Governance Frameworks · Vendor Management · Procurement · Stakeholder Management · JIRA · Confluence · Clarity  
**Industries:** Banking/Financial Services · Technology · Telecoms · Consulting  
**NOT fit:** Junior · Intern · Developer · Architect · Data Scientist · Scrum Master (if junior)  
**Resume:** `Ramalakshmi_P_2026.pdf` — uploaded by Surya 2026-07-11  

**Output file prefix:** `job-scan-ramalakshmi` → `output/job-scan-ramalakshmi-YYYY-MM-DD.md`  
**Scorer:** `match_pct_ramalakshmi()` in `scripts/job_scanner.py`  
**Search queries:** PMO Manager · PMO Lead · Programme Manager · Head of PMO · Portfolio Manager · Governance Manager · Delivery Manager · Service Delivery Manager — all Belgium

---

## Job-seen registry (deduplication across days)

**File:** `output/job-registry.json`  
**Format:** `{ "url": "YYYY-MM-DD (first seen)" }`  
**Rule:** A role is only shown for **3 days** after it was first seen. On day 4+ it is suppressed.

`scripts/job_scanner.py` loads and saves this file automatically.  
The Claude Code agent must also enforce this rule — see below.

---

## Claude Code agent job scan (manual / on-demand)

When the Claude Code agent runs the job scan (not the GitHub Actions script), it uses the **Indeed MCP tool** for richer results and scores the same way. It must produce **two output files**:

1. `output/job-scan-YYYY-MM-DD.md` — Surya (architecture roles)
2. `output/job-scan-ramalakshmi-YYYY-MM-DD.md` — Ramalakshmi (PMO roles)

Both files are sent to Telegram as documents and committed to the repo.

### Registry check (required for every agent scan)

Before writing the output files, the agent must:

1. Load `output/job-registry.json` (empty dict `{}` if missing).
2. For each scored role with URL `u`:
   - If `u` is absent from the registry → include it, add `u: today` to the registry.
   - If `u` is present and `(today - first_seen).days < 3` → include it.
   - If `u` is present and `(today - first_seen).days >= 3` → **skip it**.
3. After writing both output files, save the updated registry back to `output/job-registry.json` and include it in the git commit.

```python
import json, os
from datetime import date

REGISTRY = 'output/job-registry.json'
ROLE_TTL  = 3  # days

def load_reg():
    try:
        return json.load(open(REGISTRY))
    except FileNotFoundError:
        return {}

def is_fresh(reg, url, today):
    fs = reg.get(url)
    if fs is None:
        return True
    return (date.fromisoformat(today) - date.fromisoformat(fs)).days < ROLE_TTL

def register(reg, url, today):
    if url not in reg:
        reg[url] = today

def save_reg(reg):
    json.dump(reg, open(REGISTRY, 'w'), indent=2)
```

### Ramalakshmi Indeed MCP searches (5 queries)
- `PMO Manager`
- `Programme Manager`
- `Head of PMO`
- `Portfolio Manager`
- `Delivery Manager`

All with `location='Belgium'`, `country_code='BE'`.

---

## Telegram delivery

Both job scan files are sent to the same Telegram chat (`TG_CHAT_ID` env var / hardcoded chat `8223523460`).  
Bot token env var: `TG_TOKEN`.

---

## Notes / History

- 2026-07-11: Added Ramalakshmi profile. Resume uploaded as `Ramalakshmi_P_2026.pdf`. `job_scanner.py` updated to dual-profile. CLAUDE.md created.
- The Claude Code automated routine (system notification) previously only scanned for Surya. Going forward it scans for both.
- 2026-07-15: Added 3-day role deduplication via `output/job-registry.json`. Both `job_scanner.py` and the Claude Code agent path enforce this.
