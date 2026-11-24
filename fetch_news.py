
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DAILY BRIEF - Free RSS News Collector
경제 / 주식 / 자산 / 정책 / 기술 뉴스 수집기
"""

import json
import re
import time
import hashlib
import urllib.parse
import urllib.request

from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from html import unescape
from zoneinfo import ZoneInfo


# ==================================================
# 기본 설정
# ==================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DATA_DIR / "latest.json"

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc

MAX_AGE_HOURS = 72
MAX_PER_CATEGORY = 20
MAX_ITEMS = 100

REQUEST_TIMEOUT = 25
REQUEST_INTERVAL = 1.5
MAX_RETRIES = 3


# ==================================================
# 뉴스 카테고리 및 검색어
# ==================================================

CATEGORIES = {
    "economy": {
        "name": "경제",
        "queries": [
            "한국 경제 물가 금리 환율 GDP",
            "미국 경제 인플레이션 금리 고용",
            "global economy inflation interest rates GDP",
            "central bank monetary policy economic outlook",
        ],
    },

    "stock": {
        "name": "주식",
        "queries": [
            "미국 증시 S&P500 나스닥 다우존스",
            "한국 증시 코스피 코스닥 주식시장",
            "미국 기업 실적 주식시장 전망",
            "South Korea stock market earnings",
            "US stock market earnings Nasdaq S&P 500",
        ],
    },

    "assets": {
        "name": "자산",
        "queries": [
            "금 가격 국제 금 시세",
            "국제 유가 WTI 브렌트유",
            "한국 부동산 아파트 주택 가격",
            "미국 주택시장 부동산 가격",
            "gold price oil price housing market",
        ],
    },

    "policy": {
        "name": "정책",
        "queries": [
            "한국 정부 경제 정책 금융 정책",
            "미국 정부 경제 정책 관세 무역",
            "한국은행 기준금리 금융통화위원회",
            "미국 연준 Federal Reserve policy",
            "economic policy government regulation trade",
        ],
    },

    "tech": {
        "name": "기술·산업",
        "queries": [
            "반도체 HBM GPU 파운드리",
            "인공지능 AI 생성형 AI 산업",
            "로봇 휴머노이드 자율주행",
            "배터리 전기차 에너지 산업",
            "방산 항공우주 산업 기술",
            "semiconductor AI robotics battery technology",
            "6G telecommunications aerospace defense technology",
        ],
    },
}


# ==================================================
# 텍스트 정리
# ==================================================

def clean_text(value):
    if not value:
        return ""

    value = unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"[^가-힣a-z0-9]", "", title)

    return title


def make_id(title, link):
    raw = normalize_title(title) + "|" + str(link)

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16]


# ==================================================
# 날짜 처리
# ==================================================

def parse_date(value):
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt.astimezone(UTC)

    except Exception:
        return None


# ==================================================
# RSS 주소 생성
# ==================================================

def make_rss_url(query):
    encoded = urllib.parse.quote(query)

    return (
        "https://news.google.com/rss/search?"
        + encoded
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )


# ==================================================
# RSS 다운로드
# ==================================================

def download_rss(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120.0 Safari/537.36"
        )
    }

    request = urllib.request.Request(
        url,
        headers=headers
    )

    for attempt in range(MAX_RETRIES):

        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT
            ) as response:

                return response.read()

        except Exception as error:

            if attempt == MAX_RETRIES - 1:
                raise error

            wait = 2 ** (attempt + 1)

            print(
                f"    재시도 {attempt + 1}/{MAX_RETRIES} "
                f"({wait}초 대기)"
            )

            time.sleep(wait)


# ==================================================
# RSS 파싱
# ==================================================

def parse_rss(xml_data, category):

    root = ET.fromstring(xml_data)

    channel = root.find("channel")

    if channel is None:
        return []

    results = []

    for item in channel.findall("item"):

        title = clean_text(
            item.findtext("title", "")
        )

        link = clean_text(
            item.findtext("link", "")
        )

        summary = clean_text(
            item.findtext("description", "")
        )

        source_element = item.find("source")

        source = ""

        if source_element is not None:
            source = clean_text(
                source_element.text or ""
            )

        published_raw = item.findtext(
            "pubDate",
            ""
        )

        published = parse_date(published_raw)

        if not title or not link or not published:
            continue

        results.append({
            "id": make_id(title, link),
            "category": category,
            "category_name": CATEGORIES[category]["name"],
            "title": title,
            "summary": summary,
            "link": link,
            "source": source,
            "published": published.isoformat(),
        })

    return results


# ==================================================
# 중복 제거
# ==================================================

def remove_duplicates(items):

    unique = []
    seen = set()

    for item in items:

        key = normalize_title(item["title"])

        if not key or key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ==================================================
# 카테고리별 뉴스 수집
# ==================================================

def collect_category(category):

    print(
        f"\nCollecting category: "
        f"{CATEGORIES[category]['name']}"
    )

    collected = []

    for query in CATEGORIES[category]["queries"]:

        print(f"  검색: {query}")

        try:

            url = make_rss_url(query)

            xml_data = download_rss(url)

            items = parse_rss(
                xml_data,
                category
            )

            collected.extend(items)

            print(
                f"    {len(items)}건 수집"
            )

        except Exception as error:

            print(
                f"    수집 실패: {error}"
            )

        time.sleep(REQUEST_INTERVAL)

    return collected


# ==================================================
# 메인 실행
# ==================================================

def main():

    now = datetime.now(UTC)

    cutoff = now - timedelta(
        hours=MAX_AGE_HOURS
    )

    all_items = []
    collection_errors = []

    print("=" * 55)
    print("DAILY BRIEF 뉴스 수집 시작")
    print("=" * 55)

    for category in CATEGORIES:

        try:

            items = collect_category(category)

            valid_items = []

            for item in items:

                published = datetime.fromisoformat(
                    item["published"]
                )

                if published < cutoff:
                    continue

                if published > now + timedelta(hours=1):
                    continue

                valid_items.append(item)

            valid_items.sort(
                key=lambda x: x["published"],
                reverse=True
            )

            valid_items = remove_duplicates(
                valid_items
            )

            selected = valid_items[
                :MAX_PER_CATEGORY
            ]

            all_items.extend(selected)

            print(
                f"[완료] {CATEGORIES[category]['name']}: "
                f"{len(selected)}건"
            )

        except Exception as error:

            collection_errors.append({
                "category": category,
                "error": str(error),
            })

            print(
                f"[오류] {category}: {error}"
            )

    all_items = remove_duplicates(all_items)

    all_items.sort(
        key=lambda x: x["published"],
        reverse=True
    )

    all_items = all_items[:MAX_ITEMS]

    payload = {
        "updated_at": datetime.now(KST).strftime(
            "%Y-%m-%d %H:%M KST"
        ),

        "generated_at_utc": now.isoformat(),

        "total_items": len(all_items),

        "categories": {
            key: {
                "name": value["name"],
                "count": sum(
                    1 for item in all_items
                    if item["category"] == key
                ),
            }
            for key, value in CATEGORIES.items()
        },

        "items": all_items,

        "collection_errors": collection_errors,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 55)
    print("[완료] 뉴스 수집 종료")
    print(f"[전체 뉴스] {len(all_items)}건")
    print(f"[저장 위치] {OUTPUT_FILE}")
    print("=" * 55)


if __name__ == "__main__":
    main()
