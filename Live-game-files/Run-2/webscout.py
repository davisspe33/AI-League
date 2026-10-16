import gzip
import json
import math
import os
import re
import urllib.error
import urllib.request
import zlib
from html.parser import HTMLParser

# WebScout tool for the c4 (Dark Prophet) challenge.
# Single file, standard library only (no new dependencies). Python 3.12 Lambda, handler = index.lambda_handler.
# Fetches exactly the URL it is given (the one the question names) and returns readable page text.
# No answers or sites are stored here.
#
# Env (optional):
#   MAX_CHARS     max characters of text returned (default 4000; less text = fewer tokens)
#   TIMEOUT       fetch timeout (default 10)

MAX_CHARS = int(os.environ.get("MAX_CHARS", "4000") or 4000)
TIMEOUT = float(os.environ.get("TIMEOUT", "10") or 10)
UA = "Mozilla/5.0 (compatible; AILeagueWebScout/1.0)"

SKIP = {"script", "style", "noscript", "svg", "head", "template", "iframe"}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
         "header", "footer", "table", "ul", "ol", "dt", "dd", "blockquote", "pre", "hr", "title"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self.meta = [], 0, "", ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            a = dict(attrs)
            if (a.get("name") or a.get("property") or "").lower() in ("description", "og:description") and not self.meta:
                self.meta = (a.get("content") or "").strip()
        if tag in BLOCK:
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not self.skip:
            self.parts.append(data)

    def text(self):
        t = "".join(self.parts)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r" *\n[ \n]*", "\n", t)
        return t.strip()


def fetch(url):
    url = url.strip().strip("\"'<>")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,text/plain,*/*",
                                               "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read(3_000_000)
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        ctype = r.headers.get("Content-Type") or ""
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        charset = m.group(1) if m else "utf-8"
        return r.geturl(), r.status, ctype, raw.decode(charset, errors="replace")


def to_text(body, ctype):
    if "json" in ctype:
        try:
            return "", "", json.dumps(json.loads(body), indent=0)
        except json.JSONDecodeError:
            pass
    if "html" in ctype or re.search(r"<(html|body|div|p)\b", body[:2000], re.I):
        p = _Text()
        p.feed(body)
        return p.title.strip(), p.meta, p.text()
    return "", "", body.strip()


def focus(text, query, limit):
    """Keep only the lines around the query words (saves tokens). Falls back to the start of the page."""
    words = [w for w in re.findall(r"[\w$%.-]{2,}", (query or "").lower())
             if len(w) >= 3 or re.search(r"\d", w)]
    words = [w for w in words
             if w not in {"the", "and", "what", "which", "who", "how", "many", "much", "does", "for", "from", "with",
                          "this", "that", "page", "website", "site", "according", "when", "was", "were", "are",
                          "did", "has", "have", "had", "its", "their", "there", "into", "about", "tell", "give",
                          "name", "list", "find", "first", "last", "used", "use", "can", "you", "your", "they"}]
    if not words:
        return text[:limit]
    lines = text.split("\n")
    lows = [l.lower() for l in lines]
    # Rare words count more (a word on every menu line tells us nothing); short menu-like lines count less.
    idf = {w: math.log((len(lines) + 1) / (1 + sum(w in l for l in lows))) for w in words}
    scored = []
    for i, low in enumerate(lows):
        s = sum(idf[w] for w in words if w in low) * min(1.0, len(low) / 60)
        if s > 0:
            scored.append((s, i))
    if not scored:
        return text[:limit]
    top = max(s for s, _ in scored)
    keep = set()
    for s, i in sorted(scored, reverse=True):
        if s < 0.35 * top:
            break
        keep.add(i)
        if len(lines[i]) < 80:  # short hit (heading, label, table cell): include its neighbours for context
            keep.update(j for j in (i - 1, i + 1) if 0 <= j < len(lines))
        if sum(min(len(lines[k]), 410) + 1 for k in keep) >= limit:
            break
    out, prev = [], -2
    for k in sorted(keep):
        if k != prev + 1:
            out.append("...")
        out.append(_clip(lines[k], lows[k], words))
        prev = k
    return "\n".join(out)[:limit]


def _clip(line, low, words, width=400):
    """Long paragraphs: keep a window around the best match instead of the whole thing."""
    if len(line) <= width:
        return line
    hits = [low.find(w) for w in words if w in low]
    if not hits:
        return line[:width] + "..."
    a = max(0, min(hits) - width // 3)
    return ("..." if a else "") + line[a:a + width] + "..."


def lambda_handler(event, context):
    """
    Fetch one web page and return its readable text. Handles API Gateway and AgentCore Gateway events.

    ---
    Tool: fetch_page
    Description: Fetches the web page at the given URL (only the site the question names) and returns its title and text. Pass query to get only the parts of the page about it.
    Parameters:
        url          (required) - full URL of the page the question names, e.g. https://example.com/about
        query        (optional) - key words from the question, to return only the matching parts of the page
    ---
    """
    try:
        body = event
        if isinstance(event, dict) and "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        url = str(body.get("url") or body.get("link") or body.get("website") or "").strip()
        if not url:
            return _err(400, "Missing url")
        query = str(body.get("query") or body.get("question") or "")
        final_url, status, ctype, raw = fetch(url)
        title, meta, text = to_text(raw, ctype)
        text = focus(text, query, MAX_CHARS)
        print(f"RESULT: url={final_url} status={status} chars={len(text)} query={query!r}")
        out = {"url": final_url, "title": title, "text": text}
        if meta:
            out["description"] = meta[:300]
        return {"statusCode": 200, "body": json.dumps(out)}
    except urllib.error.HTTPError as e:
        return _err(e.code, f"HTTP {e.code} fetching page")
    except Exception as e:
        print(f"ERROR: {e}")
        return _err(500, str(e))


def _err(code, msg):
    return {"statusCode": code, "body": json.dumps({"error": msg})}
