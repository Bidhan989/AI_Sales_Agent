"""REAL company research: fetches the lead's website and extracts readable text.
Works for any real public website. Sample '.example' domains will fail (expected)."""
import re
import urllib.request
from html.parser import HTMLParser

class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.title = ""
        self._in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            a = dict(attrs)
            if (a.get("name") or a.get("property") or "").lower() in ("description", "og:description") and a.get("content"):
                self.parts.append(a["content"])
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip and data.strip():
            self.parts.append(data.strip())

def fetch_website_text(url: str, limit: int = 3000) -> dict:
    """Returns {text, ok, note}."""
    if not url:
        return {"text": "", "ok": False, "note": "No website"}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Sales_AI research bot)"})
        with urllib.request.urlopen(req, timeout=6) as r:
            html = r.read(400_000).decode("utf-8", errors="ignore")
        p = _Text()
        p.feed(html)
        text = re.sub(r"\s+", " ", f"{p.title} " + " ".join(p.parts)).strip()[:limit]
        if len(text) < 80:
            return {"text": "", "ok": False, "note": "Page had too little readable text"}
        return {"text": text, "ok": True, "note": "LIVE website research"}
    except Exception as e:
        return {"text": "", "ok": False, "note": f"Website not reachable ({type(e).__name__})"}
