"""Shared helper: save output as .md file and send to Telegram as document + text."""
import urllib.request, urllib.parse, json, os, io
from datetime import datetime

def save_md(content: str, prefix: str) -> str:
    """Write content to output/<prefix>-YYYY-MM-DD.md and return the file path."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{prefix}-{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Saved: {path}")
    return path

def send_telegram_text(token: str, chat_id: str, msg: str):
    """Send a plain Markdown text message."""
    if len(msg) > 4000:
        msg = msg[:3990] + "\n…(truncated)"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram sendMessage error: {resp}")

def send_telegram_document(token: str, chat_id: str, file_path: str, caption: str = ""):
    """Send a file as a Telegram document using multipart/form-data."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    boundary = "VestBoundary1234567890"
    body = b""

    def field(name, value):
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    body += field("chat_id", chat_id)
    if caption:
        body += field("caption", caption[:1024])
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: text/markdown\r\n\r\n"
    ).encode() + file_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read())
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram sendDocument error: {resp}")
    print(f"Sent document: {filename}")

def publish(token: str, chat_id: str, md_content: str, prefix: str, summary: str):
    """Save .md, send as document, and send summary text message."""
    path = save_md(md_content, prefix)
    send_telegram_document(token, chat_id, path, caption=summary)
