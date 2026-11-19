
#!/usr/bin/env python3
"""Collect recent RSS news and publish JSON for DAILY BRIEF."""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from pathlib import Path
from html import unescape
import json
import re

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 기본 설정
KST = ZoneInfo("Asia/Seoul")
MAX_AGE_HOURS = 72
MAX_ITEMS = 60
MAX_PER_CATEGORY = 25

# 분야별 뉴스 검색어
QUERIES = {
    "tech": [
        ("AI 인공지능 기술 산업", "ko", "KR", "KR:ko"),
        ("반도체 HBM GPU 파운드리", "ko", "KR", "KR:ko"),
        ("로봇 휴머노이드 자율주행", "ko", "KR", "KR:ko"),
        ("통신 RF 5G 6G 전자 기술", "ko", "KR", "KR:ko"),
        ("배터리 에너지 전력망 기술", "ko", "KR", "KR:ko"),
        ("방산 우주항공 레이더 기술", "ko", "KR", "KR:ko"),
        ("artificial intelligence semiconductor technology", "en", "US", "US:en"),
        ("robotics autonomous driving technology", "en", "US", "US:en"),
        ("6G wireless communication RF technology", "en", "US", "US:en"),
        ("battery energy storage technology", "en", "US", "US:en"),
    ],

    "us": [
        ("US stock market Wall Street Dow Nasdaq S&P 500", "en", "US", "US:en"),
        ("US stocks company earnings financial results", "en", "US", "US:en"),
        ("Federal Reserve interest rates inflation economy", "en", "US", "US:en"),
        ("US stock market technology semiconductor stocks", "en", "US", "US:en"),
        ("미국 증시 나스닥 뉴욕증시", "ko", "KR", "KR:ko"),
    ],

    "kr": [
        ("한국 증시 코스피 코스닥 주식시장", "ko", "KR", "KR:ko"),
        ("국내 기업 실적 발표 공시", "ko", "KR", "KR:ko"),
        ("한국 증시 반도체 2차전지 자동차", "ko", "KR", "KR:ko"),
        ("외국인 기관 투자자 순매수 증시", "ko", "KR", "KR:ko"),
        ("한국 경제 금리 환율 물가", "ko", "KR", "KR:ko"),
    ],
}


def clean_text(value):
    """Remove HTML tags and unnecessary whitespace."""
    value = unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value):
    """Convert RSS publication date to Korean Standard Time."""
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(KST)

    except Exception:
        return None


def normalize_title(title):
    """Normalize titles for duplicate detection."""
    title = title.casefold()
    return re.sub(r"[\W_]+", "", title)


def google_news_url(query, hl, gl, ceid):
    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=" + hl
        + "&gl=" + gl
        + "&ceid=" + ceid
    )


def fetch_feed(url, category):
    req = Request(
        url,
        headers={
            "User-Agent": "DailyBriefRSS/1.0 (personal research project)"
        }
    )

    with urlopen(req, timeout=25) as response:
        xml = response.read()

    root = ET.fromstring(xml)
    results = []

    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title"))
        link = (node.findtext("link") or "").strip()
        summary = clean_text(node.findtext("description"))

        source_node = node.find("source")
        source = clean_text(
            source_node.text if source_node is not None else ""
        )

        published_dt = parse_date(node.findtext("pubDate"))

        # 날짜가 없거나 오래된 뉴스는 제외
        if not published_dt:
            continue

        if title and link:
            results.append({
                "category": category,
                "title": title,
                "link": link,
                "summary": summary[:420],
                "source": source or "Google News RSS",
                "published": published_dt.strftime("%Y-%m-%d %H:%M"),
                "_published_dt": published_dt
            })

    return results


def main():
    now = datetime.now(KST)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)

    items = []
    seen_links = set()
    seen_titles = set()
    errors = []

    # 분야별 RSS 수집
    for category, query_list in QUERIES.items():

        for query, hl, gl, ceid in query_list:

            try:
                url = google_news_url(query, hl, gl, ceid)
                feed_items = fetch_feed(url, category)

                for item in feed_items:

                    # 최근 72시간 이내 뉴스만 유지
                    if item["_published_dt"] < cutoff:
                        continue

                    title_key = normalize_title(item["title"])
                    link_key = item["link"].split("?")[0]

                    # 제목 또는 링크가 중복되면 제외
                    if not title_key or title_key in seen_titles:
                        continue

                    if link_key in seen_links:
                        continue

                    seen_titles.add(title_key)
                    seen_links.add(link_key)

                    items.append(item)

            except Exception as exc:
                errors.append(
                    f"{category}/{query}: "
                    f"{type(exc).__name__}: {exc}"
                )

    # 최신순 정렬
    items.sort(
        key=lambda x: x["_published_dt"],
        reverse=True
    )

    # 카테고리별 뉴스 수 제한
    category_counts = {"tech": 0, "us": 0, "kr": 0}
    filtered_items = []

    for item in items:
        category = item["category"]

        if category_counts[category] >= MAX_PER_CATEGORY:
            continue

        category_counts[category] += 1
        filtered_items.append(item)

    # 전체 뉴스 수 제한
    filtered_items = filtered_items[:MAX_ITEMS]

    # 내부 정렬용 날짜 데이터 제거
    for item in filtered_items:
        del item["_published_dt"]

    # JSON 생성
    payload = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M %Z"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "items": filtered_items,
        "collection_errors": errors
    }

    output = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )

    (DATA_DIR / "latest.json").write_text(
        output,
        encoding="utf-8"
    )

    (DATA_DIR / f"{now.strftime('%Y-%m-%d')}.json").write_text(
        output,
        encoding="utf-8"
    )

    print(f"Saved {len(filtered_items)} headlines.")
    print(f"Tech: {category_counts['tech']}")
    print(f"US: {category_counts['us']}")
    print(f"KR: {category_counts['kr']}")
    print(f"Feed errors: {len(errors)}")


if __name__ == "__main__":
    main()
