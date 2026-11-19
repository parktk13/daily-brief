
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

# ==================================================
# 기본 설정
# ==================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

NEWS_FILE = DATA_DIR / "latest.json"
OUTPUT_FILE = DATA_DIR / "analysis.json"

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc

# Yahoo Finance 지수 코드
MARKET_INDICES = {
    "us": {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Dow Jones": "^DJI",
    },
    "kr": {
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",
    }
}

# 산업별 분석 대상
INDUSTRY_TOPICS = [
    "반도체·전자",
    "인공지능",
    "로봇·자율주행",
    "통신·RF",
    "배터리·에너지",
    "방산·항공우주",
]

MAX_INDUSTRY_NEWS = 5
MAX_MARKET_NEWS = 5


# ==================================================
# JSON 파일 읽기
# ==================================================

def load_json(path):
    if not path.exists():
        print(f"[경고] 파일이 없습니다: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[오류] JSON 읽기 실패: {e}")
        return {}


# ==================================================
# Yahoo Finance 지수 데이터 수집
# ==================================================

def fetch_index(symbol):
    encoded_symbol = urllib.parse.quote(symbol, safe="")

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + encoded_symbol
        + "?range=10d&interval=1d"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        result = data["chart"]["result"][0]

        timestamps = result.get("timestamp", [])
        quotes = result["indicators"]["quote"][0]
        closes = quotes.get("close", [])

        records = []

        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue

            records.append({
                "date": datetime.fromtimestamp(
                    timestamp, UTC
                ).strftime("%Y-%m-%d"),
                "close": float(close)
            })

        records.sort(key=lambda x: x["date"])

        if len(records) < 2:
            raise ValueError("충분한 거래 데이터가 없습니다.")

        return records

    except Exception as e:
        print(f"[경고] {symbol} 데이터 수집 실패: {e}")
        return []


# ==================================================
# 등락률 계산
# ==================================================

def calculate_change(previous, current):
    if previous == 0:
        return None

    return (current / previous - 1) * 100


def format_number(value):
    return f"{value:,.2f}"


def format_change(value):
    if value is None:
        return "계산 불가"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.2f}%"


# ==================================================
# 시장 지표 생성
# ==================================================

def build_market_stats(country, period):
    stats = []
    dates = []

    for name, symbol in MARKET_INDICES[country].items():
        records = fetch_index(symbol)

        if len(records) < 2:
            continue

        latest = records[-1]
        dates.append(latest["date"])

        if period == "daily":
            previous = records[-2]

        elif period == "weekly":
            if len(records) < 6:
                print(f"[경고] {name}: 주간 데이터 부족")
                continue

            # 최근 종가와 5거래일 전 종가 비교
            previous = records[-6]

        else:
            continue

        change = calculate_change(
            previous["close"],
            latest["close"]
        )

        stats.append({
            "label": name,
            "value": (
                format_number(latest["close"])
                + " ("
                + format_change(change)
                + ")"
            )
        })

    as_of = max(dates) if dates else None

    return stats, as_of


# ==================================================
# 시장 관련 뉴스 정리
# ==================================================

def get_market_news(items, category):
    selected = [
        item for item in items
        if item.get("category") == category
    ]

    selected.sort(
        key=lambda x: x.get("published", ""),
        reverse=True
    )

    return selected[:MAX_MARKET_NEWS]


def build_market_analysis(items, country, period):
    stats, as_of = build_market_stats(country, period)

    news = get_market_news(items, country)

    if stats:
        if period == "daily":
            summary = (
                f"{as_of} 기준 최근 거래일 지수 데이터입니다. "
                "괄호 안은 직전 거래일 대비 등락률입니다."
            )
        else:
            summary = (
                f"{as_of} 기준 최근 5거래일의 지수 변화입니다. "
                "괄호 안은 5거래일 전 종가 대비 등락률입니다."
            )
    else:
        summary = (
            "현재 지수 데이터를 가져오지 못했습니다. "
            "수치를 표시하지 않으며, 아래 뉴스는 참고 자료입니다."
        )

    key_points = []

    for item in news:
        title = item.get("title", "").strip()

        if title:
            key_points.append(title)

    if not key_points:
        key_points.append(
            "해당 기간에 수집된 관련 뉴스가 없습니다."
        )

    return {
        "summary": summary,
        "stats": stats,
        "key_points": key_points,
        "as_of": as_of or "시세 기준일 확인 불가"
    }


# ==================================================
# 산업별 뉴스 분석
# ==================================================

def build_industry_analysis(items):
    grouped = defaultdict(list)

    for item in items:
        if item.get("category") != "tech":
            continue

        topic = item.get("topic")

        if topic not in INDUSTRY_TOPICS:
            continue

        grouped[topic].append(item)

    results = []

    for topic in INDUSTRY_TOPICS:
        articles = grouped.get(topic, [])

        if not articles:
            continue

        articles.sort(
            key=lambda x: x.get("published", ""),
            reverse=True
        )

        articles = articles[:MAX_INDUSTRY_NEWS]

        titles = [
            item.get("title", "").strip()
            for item in articles
            if item.get("title")
        ]

        if not titles:
            continue

        results.append({
            "topic": topic,
            "title": topic + " 산업 동향",
            "summary": (
                f"최근 수집된 {topic} 관련 뉴스 "
                f"{len(articles)}건입니다. "
                "아래 제목을 바탕으로 주요 보도 주제를 확인할 수 있습니다. "
                "기사 제목만으로 산업 전망이나 시장 규모를 단정하지 않습니다."
            ),
            "key_points": titles,
            "as_of": datetime.now(KST).strftime("%Y-%m-%d")
        })

    return results


# ==================================================
# 전체 분석 데이터 생성
# ==================================================

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    news_data = load_json(NEWS_FILE)
    items = news_data.get("items", [])

    if not isinstance(items, list):
        items = []

    print(f"[정보] 뉴스 {len(items)}건 불러오기")

    result = {
        "updated_at": datetime.now(KST).strftime(
            "%Y-%m-%d %H:%M KST"
        ),

        "daily": {
            "us": build_market_analysis(
                items, "us", "daily"
            ),
            "kr": build_market_analysis(
                items, "kr", "daily"
            )
        },

        "weekly": {
            "us": build_market_analysis(
                items, "us", "weekly"
            ),
            "kr": build_market_analysis(
                items, "kr", "weekly"
            )
        },

        "industry": build_industry_analysis(items)
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("[완료] 분석 데이터 생성")
    print(f"[저장 위치] {OUTPUT_FILE}")
    print(f"[산업 분석] {len(result['industry'])}개 분야")


if __name__ == "__main__":
    main()
