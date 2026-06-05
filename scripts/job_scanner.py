import urllib.request, json, os

TOKEN = os.environ["TG_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15)

msg = """💼 *Vest Job Scanner — weekly run*

🔍 Search queries dispatched:
- LinkedIn: Chief Architect TOGAF Belgium
- Indeed: Principal Architect Cloud Brussels

📌 Open these links to review fresh listings:
- https://www.linkedin.com/jobs/search/?keywords=chief+architect+TOGAF&location=Belgium
- https://be.indeed.com/jobs?q=principal+architect+cloud&l=Brussels
- https://eu-careers.europa.eu (EU institutions — check manually)

_Vest · Job Scanner · auto-run_"""

send_telegram(msg)
print("Sent.")
