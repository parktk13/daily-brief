#!/usr/bin/env python3
"""Collect public RSS headlines and publish date-stamped JSON for the static site."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

QUERIES = {
    "tech": [
        ("AI 인공지능 반도체 기술", "ko", "KR", "KR:ko"),
        ("artificial intelligence semiconductor technology", "en", "US", "US:en"),
    ],
    "us": [
        ("US stock market Wall Street earnings Federal Reserve", "en", "US", "US:en"),
    ],
    "kr": [
        ("한국 증시 코스피 코스닥 기업 실적", "ko", "KR", "KR:ko"),
    ],
}

def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()

def parse_date(value):
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""

def google_news_url(query, hl, gl, ceid):
    return ("https://news.google.com/rss/search?q=" + quote(query) +
            "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)

def fetch_feed(url, category):
    req = Request(url, headers={"User-Agent": "DailyBriefRSS/1.0 (personal research project)"})
    with urlopen(req, timeout=25) as response:
        xml = response.read()
    root = ET.fromstring(xml)
    results = []
    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title"))
        link = (node.findtext("link") or "").strip()
        summary = clean_text(node.findtext("description"))
        source_node = node.find("source")
        source = clean_text(source_node.text if source_node is not None else "")
        published = parse_date(node.findtext("pubDate"))
        if title and link:
            results.append({
                "category": category, "title": title, "link": link,
                "summary": summary[:420], "source": source or "Google News RSS",
                "published": published
            })
    return results

def main():
    items, seen = [], set()
    errors = []
    for category, query_list in QUERIES.items():
        for query, hl, gl, ceid in query_list:
            try:
                for item in fetch_feed(google_news_url(query, hl, gl, ceid), category):
                    key = item["link"]
                    if key not in seen:
                        seen.add(key)
                        items.append(item)
            except Exception as exc:
                errors.append(f"{category}/{query}: {type(exc).__name__}: {exc}")

    # Keep the feed concise and deterministic.
    items = items[:60]
    now = datetime.now().astimezone()
    payload = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M %Z"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "collection_errors": errors
    }
    (DATA_DIR / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / f"{now.strftime('%Y-%m-%d')}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(items)} headlines; {len(errors)} feed errors.")

if __name__ == "__main__":
    main()
