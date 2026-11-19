
#!/usr/bin/env python3
"""Collect recent RSS news and publish JSON for DAILY BRIEF."""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from pathlib import Path
from html import unescape
import json
import re
import time

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 기본 설정
KST = ZoneInfo("Asia/Seoul")

MAX_AGE_HOURS = 72
MAX_ITEMS = 60
MAX_PER_CATEGORY = {
    "tech": 30,
    "us": 25,
    "kr": 25
}
MAX_PER_TOPIC = 5

# RSS 요청 설정
REQUEST_INTERVAL = 2.5
MAX_RETRIES = 3
RETRY_DELAYS = [10, 20, 40]
REQUEST_TIMEOUT = 25

last_request_time = 0
feed_cache = {}

# 제외할 출처
BLOCKED_SOURCES = {
    "facebook",
    "facebook.com",
}

# 분야별 뉴스 검색어
QUERIES = {
    "tech": [
        "tech": [
    # 1. 반도체
    ("반도체 HBM GPU 파운드리", "ko", "KR", "KR:ko", "반도체"),
    ("semiconductor HBM GPU foundry", "en", "US", "US:en", "반도체"),

    # 2. 인공지능
    ("AI 인공지능 생성형 AI 머신러닝", "ko", "KR", "KR:ko", "인공지능"),
    ("artificial intelligence generative AI machine learning", "en", "US", "US:en", "인공지능"),

    # 3. 로봇 및 자율주행
    ("로봇 휴머노이드 산업용 로봇 자율주행", "ko", "KR", "KR:ko", "로봇·자율주행"),
    ("robotics humanoid industrial robots autonomous driving", "en", "US", "US:en", "로봇·자율주행"),

    # 4. 통신 및 RF
    ("통신 RF 안테나 5G 6G 전자파", "ko", "KR", "KR:ko", "통신·RF"),
    ("wireless communication RF antenna 5G 6G", "en", "US", "US:en", "통신·RF"),

    # 5. 배터리 및 에너지
    ("배터리 ESS 에너지저장 전력망", "ko", "KR", "KR:ko", "배터리·에너지"),
    ("battery energy storage power grid", "en", "US", "US:en", "배터리·에너지"),

    # 6. 방산 및 항공우주
    ("방산 항공우주 위성 레이더 산업", "ko", "KR", "KR:ko", "방산·항공우주"),
    ("defense aerospace satellite radar industry", "en", "US", "US:en", "방산·항공우주"),
],
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

    value = re.sub(
        r"<(script|style).*?</\1>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL
    )

    value = re.sub(r"<[^>]+>", " ", value)

    return re.sub(r"\s+", " ", value).strip()


def clean_summary(description, title, source):
    """Remove repeated title/source from RSS description."""

    summary = clean_text(description)

    if not summary:
        return ""

    # 제목이 요약 앞부분에 반복되는 경우 제거
    if title and summary.casefold().startswith(title.casefold()):
        summary = summary[len(title):].strip()

    # 제목 뒤에 붙는 구분 기호 제거
    summary = re.sub(r"^[\s|:\-–—]+", "", summary)

    # 출처명이 요약 마지막에 반복되는 경우 제거
    if source and summary.casefold().endswith(source.casefold()):
        summary = summary[:-len(source)].strip()

    summary = re.sub(r"[\s|:\-–—]+$", "", summary)

    # 제목만 남았다면 요약으로 사용하지 않음
    if normalize_title(summary) == normalize_title(title):
        return ""

    return summary[:420]


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

    title = (title or "").casefold()

    return re.sub(r"[\W_]+", "", title)


def normalize_link(link):
    """Normalize URLs for duplicate detection."""

    try:
        parsed = urlsplit(link)

        return (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/")
        )

    except Exception:
        return link.strip()


def is_blocked_source(source, link):
    """Exclude unwanted sources."""

    source_lower = (source or "").casefold().strip()

    if source_lower in BLOCKED_SOURCES:
        return True

    try:
        domain = urlsplit(link).netloc.casefold()

        if domain == "facebook.com" or domain.endswith(".facebook.com"):
            return True

    except Exception:
        pass

    return False


def google_news_url(query, hl, gl, ceid):
    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=" + hl
        + "&gl=" + gl
        + "&ceid=" + ceid
    )


def wait_for_request():
    """Maintain a minimum interval between RSS requests."""

    global last_request_time

    elapsed = time.monotonic() - last_request_time

    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)

    last_request_time = time.monotonic()


def get_retry_after(exc):
    """Read Retry-After header when available."""

    try:
        value = exc.headers.get("Retry-After")

        if value:
            return max(1, min(int(value), 60))

    except (AttributeError, TypeError, ValueError):
        pass

    return None


def download_feed(url):
    """Download RSS XML with rate limiting and retries."""

    for attempt in range(MAX_RETRIES + 1):

        wait_for_request()

        req = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; DailyBriefRSS/1.0)"
                ),
                "Accept": (
                    "application/rss+xml, "
                    "application/xml, text/xml"
                )
            }
        )

        try:
            with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                return response.read()

        except HTTPError as exc:

            retryable = exc.code in {
                429, 500, 502, 503, 504
            }

            if not retryable or attempt >= MAX_RETRIES:
                raise

            delay = (
                get_retry_after(exc)
                or RETRY_DELAYS[attempt]
            )

            print(
                f"HTTP {exc.code}: retry "
                f"{attempt + 1}/{MAX_RETRIES} "
                f"after {delay}s"
            )

            time.sleep(delay)

        except (URLError, TimeoutError) as exc:

            if attempt >= MAX_RETRIES:
                raise

            delay = RETRY_DELAYS[attempt]

            print(
                f"Connection error: retry "
                f"{attempt + 1}/{MAX_RETRIES} "
                f"after {delay}s"
            )

            time.sleep(delay)

    raise RuntimeError("RSS download failed after retries")


def fetch_feed(url, category):
    """Fetch and parse RSS feed with URL caching."""

    if url in feed_cache:
        return feed_cache[url]

    xml = download_feed(url)

    root = ET.fromstring(xml)
    results = []

    for node in root.findall(".//item"):

        title = clean_text(node.findtext("title"))
        link = (node.findtext("link") or "").strip()

        description = node.findtext("description") or ""

        source_node = node.find("source")

        source = clean_text(
            source_node.text if source_node is not None else ""
        )

        published_dt = parse_date(
            node.findtext("pubDate")
        )

        # 필수 정보 확인
        if not title or not link or not published_dt:
            continue

        # Facebook 등 제외
        if is_blocked_source(source, link):
            continue

        summary = clean_summary(
            description,
            title,
            source
        )

        results.append({
            "category": category,
            "title": title,
            "link": link,
            "summary": summary,
            "source": source or "Google News RSS",
            "published": published_dt.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "_published_dt": published_dt
        })

    feed_cache[url] = results

    return results


def main():

    now = datetime.now(KST)

    cutoff = now - timedelta(
        hours=MAX_AGE_HOURS
    )

    future_limit = now + timedelta(hours=24)

    items = []

    seen_links = set()
    seen_titles = set()

    errors = []

    # 분야별 RSS 수집
    for category, query_list in QUERIES.items():

        print(f"\nCollecting category: {category}")

        for entry in query_list:

            if len(entry) == 5:
                query, hl, gl, ceid, topic = entry
            else:
                query, hl, gl, ceid = entry
                topic = ""

            try:

                url = google_news_url(
                    query,
                    hl,
                    gl,
                    ceid
                )

                feed_items = fetch_feed(
                    url,
                    category
                )

                added_count = 0

                for item in feed_items:

                    published_dt = item["_published_dt"]

                    # 최근 72시간 이내 뉴스만 유지
                    if published_dt < cutoff:
                        continue

                    # 비정상적인 미래 날짜 제외
                    if published_dt > future_limit:
                        continue

                    title_key = normalize_title(
                        item["title"]
                    )

                    link_key = normalize_link(
                        item["link"]
                    )

                    # 제목 또는 링크 중복 확인
                    if not title_key or title_key in seen_titles:
                        continue

                    if link_key in seen_links:
                        continue

                    seen_titles.add(title_key)
                    seen_links.add(link_key)

                    item["topic"] = topic
                    items.append(item)
                    added_count += 1

                print(
                    f"  {query}: "
                    f"{added_count} new articles"
                )

            except Exception as exc:

                error_message = (
                    f"{category}/{query}: "
                    f"{type(exc).__name__}: {exc}"
                )

                errors.append(error_message)

                print(f"  ERROR: {error_message}")

    # 최신순 정렬
    items.sort(
        key=lambda x: x["_published_dt"],
        reverse=True
    )

    # 카테고리별 뉴스 수 제한
    category_counts = {
        "tech": 0,
        "us": 0,
        "kr": 0
    }

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
        "updated_at": now.strftime(
            "%Y-%m-%d %H:%M %Z"
        ),

        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "items": filtered_items,

        "collection_errors": errors
    }

    output = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )

    # 최신 뉴스 파일 저장
    (DATA_DIR / "latest.json").write_text(
        output,
        encoding="utf-8"
    )

    # 날짜별 백업 파일 저장
    (DATA_DIR / f"{now.strftime('%Y-%m-%d')}.json").write_text(
        output,
        encoding="utf-8"
    )

    print("\n========== DAILY BRIEF ==========")

    print(f"Saved: {len(filtered_items)} articles")

    print(f"Tech: {category_counts['tech']}")
    print(f"US:   {category_counts['us']}")
    print(f"KR:   {category_counts['kr']}")

    print(f"Feed errors: {len(errors)}")

    print("=================================")


if __name__ == "__main__":
    main()
