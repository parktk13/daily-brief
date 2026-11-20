#뉴스 분야별 키워드 우선순위, 군사, 정세 기사 필터링 중복기사 제거, 미국 증시 관련성 개선
#!/usr/bin/env python3
"""Collect, classify and publish recent RSS news for DAILY BRIEF."""

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


# =========================================================
# 기본 설정
# =========================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

KST = ZoneInfo("Asia/Seoul")

MAX_AGE_HOURS = 72
MAX_ITEMS = 80

MAX_PER_CATEGORY = {
    "tech": 30,
    "us": 25,
    "kr": 25
}

# 분야별 기사 수 제한
MAX_PER_TOPIC = {
    "tech": 5,
    "us": 10,
    "kr": 10
}


# =========================================================
# RSS 요청 설정
# =========================================================

REQUEST_INTERVAL = 2.5
MAX_RETRIES = 3
RETRY_DELAYS = [10, 20, 40]
REQUEST_TIMEOUT = 25

last_request_time = 0
feed_cache = {}


# =========================================================
# 제외할 출처
# =========================================================

BLOCKED_SOURCES = {
    "facebook",
    "facebook.com",
}


# =========================================================
# 뉴스 검색어
# =========================================================

QUERIES = {

    "tech": [

        # 반도체·전자
        ("반도체 HBM GPU 파운드리", "ko", "KR", "KR:ko"),
        ("semiconductor HBM GPU foundry chip", "en", "US", "US:en"),

        # 인공지능
        ("AI 인공지능 생성형 AI 머신러닝", "ko", "KR", "KR:ko"),
        ("artificial intelligence generative AI machine learning", "en", "US", "US:en"),

        # 로봇·자율주행
        ("로봇 휴머노이드 산업용 로봇 자율주행", "ko", "KR", "KR:ko"),
        ("robotics humanoid industrial robots autonomous driving", "en", "US", "US:en"),

        # 통신·RF
        ("통신 RF 안테나 5G 6G 전자파", "ko", "KR", "KR:ko"),
        ("wireless communication RF antenna 5G 6G", "en", "US", "US:en"),

        # 배터리·에너지
        ("배터리 ESS 에너지저장 전력망", "ko", "KR", "KR:ko"),
        ("battery energy storage power grid", "en", "US", "US:en"),

        # 방산·항공우주
        ("방산 국방 미사일 위성 레이더 항공우주", "ko", "KR", "KR:ko"),
        ("defense military missile satellite radar aerospace", "en", "US", "US:en"),
    ],

    "us": [

        ("US stock market Wall Street Dow Nasdaq S&P 500", "en", "US", "US:en"),
        ("US stocks company earnings financial results", "en", "US", "US:en"),
        ("Federal Reserve interest rates inflation economy", "en", "US", "US:en"),
        ("US technology semiconductor stocks market", "en", "US", "US:en"),
        ("US stock market major companies earnings", "en", "US", "US:en"),

    ],

    "kr": [

        ("한국 증시 코스피 코스닥 주식시장", "ko", "KR", "KR:ko"),
        ("국내 상장기업 실적 발표 공시 주가", "ko", "KR", "KR:ko"),
        ("한국 증시 반도체 배터리 자동차 주식", "ko", "KR", "KR:ko"),
        ("외국인 기관 투자자 순매수 순매도 증시", "ko", "KR", "KR:ko"),
        ("한국 경제 금리 환율 물가 증시", "ko", "KR", "KR:ko"),

    ],
}


# =========================================================
# 기술 뉴스 분류 키워드
# =========================================================

TECH_TOPICS = {

    "반도체·전자": [
        r"반도체", r"semiconductor", r"\bchip(s)?\b",
        r"\bHBM\b", r"\bGPU\b", r"\bCPU\b",
        r"파운드리", r"foundry", r"\bwafer\b",
        r"\bDRAM\b", r"\bNAND\b", r"메모리 반도체",
        r"패키징", r"lithography", r"삼성전자",
        r"sk hynix", r"인텔", r"\bIntel\b",
        r"\bTSMC\b", r"반도체 장비"
    ],

    "인공지능": [
        r"인공지능", r"\bAI\b", r"artificial intelligence",
        r"생성형", r"generative AI", r"\bLLM\b",
        r"machine learning", r"머신러닝",
        r"딥러닝", r"deep learning",
        r"챗봇", r"chatbot", r"대규모 언어 모델",
        r"language model", r"AI 모델"
    ],

    "로봇·자율주행": [
        r"로봇", r"\brobot(s|ics)?\b",
        r"휴머노이드", r"humanoid",
        r"산업용 로봇", r"industrial robot",
        r"자율주행", r"autonomous driving",
        r"self.driving", r"무인차량",
        r"협동로봇", r"robot arm",
        r"robotic system"
    ],

    "통신·RF": [
        r"\bRF\b", r"무선통신", r"wireless communication",
        r"안테나", r"\bantenna(s)?\b",
        r"\b5G\b", r"\b6G\b",
        r"통신망", r"telecommunication",
        r"이동통신", r"기지국",
        r"network infrastructure",
        r"전자파", r"전파", r"위성통신",
        r"satellite communication"
    ],

  
    "배터리·에너지": [
        r"배터리", r"\bbattery\b",
        r"\bESS\b", r"에너지 저장",
        r"energy storage",
        r"battery storage",
        r"grid.scale battery",
        r"전기차 배터리",
        r"2차전지",
        r"리튬이온",
        r"lithium.ion",
        r"배터리 셀",
        r"battery cell",
        r"배터리 소재",
        r"양극재", r"음극재",
        r"전력저장장치",
        r"에너지저장장치"
    ],


    "방산·항공우주": [
        r"방산", r"방위산업", r"국방",
        r"\bdefense\b", r"\bmilitary\b",
        r"미사일", r"\bmissile\b",
        r"레이더", r"\bradar\b",
        r"위성", r"\bsatellite\b",
        r"항공우주", r"\baerospace\b",
        r"우주산업", r"space industry",
        r"전투기", r"fighter jet",
        r"air defense", r"방공 시스템",
        r"군사 기술", r"military technology"
    ],
}


# 기술 뉴스에서 제외할 가능성이 높은 기사
TECH_EXCLUDE = [
	 # 일반적인 항공·여행 기사
       r"항공.*날씨",
       r"항공.*기상",
      r"aviation weather",
      r"weather forecast",
      r"항공편 지연",
      r"flight delay",
      r"airport.*weather",
      r"여행.*항공",
      r"airline.*travel",

    # AI 개발업체 홍보 및 서비스 소개 기사
      r"\bAI POC development services\b",
      r"AI development capabilities",
      r"companies offering AI development",
      r"AI development service providers",
      r"AI consulting services",

    # 일반적인 전력망 보안 기사
      r"cyber.?attack",
      r"cyber.?security",
      r"cyber threats",

    # 산업 기술과 직접 관련이 약한 일반 군사·정세 기사
      r"who holds the military advantage",
      r"military advantage in the",
      r"cadets fire.*missile",
    ]


# =========================================================
# 미국 증시 분류 키워드
# =========================================================

US_TOPICS = {

    "지수·시장동향": [
        r"stock market", r"stocks", r"equities",
        r"wall street", r"\bNASDAQ\b",
        r"\bS&P 500\b", r"\bDow Jones\b",
        r"market rally", r"market selloff",
        r"stock futures", r"market close",
        r"market outlook", r"주식시장",
        r"\bSPY\b", r"\bQQQ\b",
        r"미국 증시", r"뉴욕 증시"
    ],

    "기업실적·기업동향": [
        r"earnings", r"quarterly results",
        r"financial results", r"revenue",
        r"operating profit", r"profit growth",
        r"company outlook", r"earnings report",
        r"기업 실적", r"분기 실적",
        r"영업이익", r"매출 실적",
        r"기업 전망", r"실적 발표"
    ],

    "금리·경제지표": [
        r"Federal Reserve", r"\bFed\b",
        r"interest rates", r"inflation",
        r"\bCPI\b", r"\bPCE\b", r"\bGDP\b",
        r"unemployment", r"jobs report",
        r"treasury yields", r"bond yields",
        r"경제지표", r"금리 인하",
        r"금리 동결", r"미국 물가",
        r"미국 고용", r"연준"
    ],

    "산업·섹터": [
        r"technology stocks", r"semiconductor stocks",
        r"bank stocks", r"energy stocks",
        r"AI stocks", r"tech sector",
        r"financial sector", r"healthcare stocks",
        r"technology sector", r"반도체주",
        r"기술주", r"은행주", r"에너지주"
    ],
}


# =========================================================
# 한국 증시 분류 키워드
# =========================================================

KR_TOPICS = {

    "지수·시장동향": [
        r"코스피", r"코스닥",
        r"한국 증시", r"국내 증시",
        r"주식시장", r"증시 상승",
        r"증시 하락", r"주가 상승",
        r"주가 하락", r"상한가",
        r"하한가", r"증시 마감",
        r"장중", r"시가총액"
    ],

    "기업실적·공시": [
        r"기업 실적", r"실적 발표",
        r"영업이익", r"매출액",
        r"분기 실적", r"연간 실적",
        r"잠정 실적", r"사업보고서",
        r"기업 공시", r"유상증자",
        r"무상증자", r"배당",
        r"상장", r"주주총회",
        r"상장기업", r"실적 전망"
    ],

    "수급·투자자": [
        r"외국인 순매수", r"외국인 순매도",
        r"기관 순매수", r"기관 순매도",
        r"개인 투자자", r"투자자별",
        r"수급", r"순매수",
        r"순매도", r"외국인 투자자",
        r"기관 투자자"
    ],

    "산업·섹터": [
        r"반도체주", r"배터리주",
        r"자동차주", r"바이오주",
        r"조선주", r"방산주",
        r"은행주", r"IT 업종",
        r"반도체 산업", r"2차전지",
        r"자동차 산업", r"산업 동향"
    ],

    "거시경제": [
        r"한국은행", r"기준금리",
        r"금리 인하", r"금리 동결",
        r"환율", r"원달러",
        r"물가", r"소비자물가",
        r"경제성장률", r"GDP",
        r"수출", r"무역수지",
        r"한국 경제", r"경제 전망"
    ],
}


# =========================================================
# 품질 관리용 제외 키워드
# =========================================================

US_EXCLUDE = [
    r"esports", r"video game",
    r"soccer", r"football match",
    r"celebrity", r"movie review",
    r"weather forecast", r"travel guide"
]

KR_EXCLUDE = [
    r"수능일.*거래시간",
    r"거래시간.*변경",
    r"개장시간.*변경",
    r"증시 휴장 안내",
    r"특수관계인.*내부거래",
    r"대규모 내부거래",
    r"계열사 간 내부거래",
    r"사내 행사"
]
# =========================================================
# 국가별 시장 관련성 검증
# =========================================================

US_REGION_PATTERNS = [
    r"\bU\.?S\.?A?\.?\b",
    r"\bAmerican\b",
    r"\bUnited States\b",
    r"\bWall Street\b",
    r"\bNew York Stock Exchange\b",
    r"\bNYSE\b",
    r"\bNASDAQ\b",
    r"\bS&P 500\b",
    r"\bDow Jones\b",
    r"\bFederal Reserve\b",
    r"\bFed\b",
    r"\bU\.?S\.? Treasury\b",
    r"\bU\.?S\.? stocks?\b",

    # 주요 미국 기업
    r"\bApple\b",
    r"\bMicrosoft\b",
    r"\bNvidia\b",
    r"\bAmazon\b",
    r"\bAlphabet\b",
    r"\bGoogle\b",
    r"\bMeta\b",
    r"\bTesla\b",
    r"\bWalmart\b",
    r"\bJPMorgan\b",
    r"\bBerkshire Hathaway\b",
    r"\bBroadcom\b",
    r"\bOracle\b",
    r"\bNetflix\b",
]

KR_REGION_PATTERNS = [
    r"한국",
    r"국내",
    r"코스피",
    r"코스닥",
    r"\bKOSPI\b",
    r"\bKOSDAQ\b",
    r"\bKRX\b",
    r"한국은행",
    r"원달러",
    r"원화",
    r"외국인 투자자",
    r"국내 상장기업",
]

# =========================================================
# 텍스트 정리
# =========================================================

def clean_text(value):

    value = unescape(value or "")

    value = re.sub(
        r"<(script|style).*?</\1>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL
    )

    value = re.sub(r"<[^>]+>", " ", value)

    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title):

    title = (title or "").casefold()

    return re.sub(r"[\W_]+", "", title)


def clean_summary(description, title, source):

    summary = clean_text(description)

    if not summary:
        return ""

    if title and summary.casefold().startswith(title.casefold()):
        summary = summary[len(title):].strip()

    summary = re.sub(r"^[\s|:\-–—]+", "", summary)

    if source and summary.casefold().endswith(source.casefold()):
        summary = summary[:-len(source)].strip()

    summary = re.sub(r"[\s|:\-–—]+$", "", summary)

    if normalize_title(summary) == normalize_title(title):
        return ""

    return summary[:420]


# =========================================================
# 키워드 분석
# =========================================================

def keyword_score(text, patterns):
    """Count how many distinct keyword patterns match."""

    score = 0

    for pattern in patterns:

        if re.search(pattern, text, flags=re.IGNORECASE):
            score += 1

    return score


def has_excluded_keyword(text, patterns):

    for pattern in patterns:

        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False



# =========================================================
# 기술 뉴스 분야 우선 지정
# =========================================================

TECH_TOPIC_OVERRIDES = [

    # 배터리·에너지
    (
        "배터리·에너지",
        [
            r"나트륨 배터리",
            r"sodium battery",
            r"data center power strategy",
            r"AI loads.*power"
        ]
    ),

    # 로봇·자율주행
    (
        "로봇·자율주행",
        [
            r"robot motion control",
            r"humanoid robot",
            r"industrial robot"
        ]
    ),

    # 통신·RF
    (
        "통신·RF",
        [
            r"aperture antennas",
            r"6G sensing",
            r"wireless communication"
        ]
    ),
]


def classify_tech_override(title):

    for topic, patterns in TECH_TOPIC_OVERRIDES:

        for pattern in patterns:

            if re.search(
                pattern,
                title,
                flags=re.IGNORECASE
            ):
                return topic

    return None
def classify_by_topics(title, summary, topic_dictionary):
    """
    제목의 키워드 일치 점수를 우선 비교한다.
    점수가 같으면 제목에서 일치한 키워드의 길이를 비교한다.

    예:
    - robot motion control + Physical AI → 로봇·자율주행
    - energy storage + AI data center → 배터리·에너지
    """

    scores = {}

    for topic, patterns in topic_dictionary.items():

        title_score = keyword_score(title, patterns)
        summary_score = keyword_score(summary, patterns)

        # 제목에서 실제로 일치한 키워드 길이의 합
        title_specificity = sum(
            len(match.group())
            for pattern in patterns
            for match in re.finditer(
                pattern,
                title,
                flags=re.IGNORECASE
            )
        )

        scores[topic] = {
            "title": title_score,
            "summary": summary_score,
            "total": title_score * 5 + summary_score,
            "specificity": title_specificity
        }

    if not scores:
        return None, 0

    # 제목에서 관련 키워드가 발견된 분야만 후보로 사용
    title_matches = {
        topic: score
        for topic, score in scores.items()
        if score["title"] > 0
    }

    if title_matches:
        candidates = title_matches

    else:
        candidates = scores

        # 제목에 관련 키워드가 없으면
        # 요약에서 3개 이상 일치해야 통과
        if max(
            score["summary"]
            for score in scores.values()
        ) < 3:
            return None, 0

    # 점수가 같으면 제목에서 더 구체적인 키워드가
    # 일치한 분야를 우선 선택
    best_topic = max(
        candidates,
        key=lambda topic: (
            candidates[topic]["total"],
            candidates[topic]["specificity"]
        )
    )

    return best_topic, candidates[best_topic]["total"]

# =========================================================
# 뉴스 분류 및 관련성 검증
# =========================================================

def classify_article(category, title, summary):

    title = (title or "").casefold()
    summary = (summary or "").casefold()

    text = f"{title} {summary}"

    # -----------------------------------------------------
    # 기술 뉴스
    # -----------------------------------------------------

    if category == "tech":

        if has_excluded_keyword(text, TECH_EXCLUDE):
            return None, 0

        # 군사 외교 및 국제 정세 기사 제외
        if re.search(
            r"senators.*military.*ties|military.*ties with",
            title,
            flags=re.IGNORECASE
        ):
            return None, 0

        # 명확한 분야가 지정된 기사는 우선 분류
        override_topic = classify_tech_override(title)

        if override_topic:
            return override_topic, 10

        topic, score = classify_by_topics(
            title,
            summary,
            TECH_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    # -----------------------------------------------------
    # 미국 증시
    # -----------------------------------------------------

    if category == "us":

        if has_excluded_keyword(text, US_EXCLUDE):
            return None, 0

        if not has_excluded_keyword(text, US_REGION_PATTERNS):
            return None, 0

        topic, score = classify_by_topics(
            title,
            summary,
            US_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    # -----------------------------------------------------
    # 한국 증시
    # -----------------------------------------------------

    if category == "kr":

        if has_excluded_keyword(text, KR_EXCLUDE):
            return None, 0

        if not has_excluded_keyword(text, KR_REGION_PATTERNS):
            return None, 0

        topic, score = classify_by_topics(
            title,
            summary,
            KR_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    return None, 0

    # 명확한 분야가 지정된 기사는 우선 분류
    override_topic = classify_tech_override(title)

    if override_topic:
        return override_topic, 10

        topic, score = classify_by_topics(
            title,
            summary,
            TECH_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    # -----------------------------------------------------
    # 미국 증시
    # -----------------------------------------------------

    if category == "us":

        if has_excluded_keyword(text, US_EXCLUDE):
            return None, 0

        # 미국 시장과의 관련성 먼저 확인
        if not has_excluded_keyword(text, US_REGION_PATTERNS):
            return None, 0

        topic, score = classify_by_topics(
            title,
            summary,
            US_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    # -----------------------------------------------------
    # 한국 증시
    # -----------------------------------------------------

    if category == "kr":

        if has_excluded_keyword(text, KR_EXCLUDE):
            return None, 0

        # 한국 시장과의 관련성 먼저 확인
        if not has_excluded_keyword(text, KR_REGION_PATTERNS):
            return None, 0

        topic, score = classify_by_topics(
            title,
            summary,
            KR_TOPICS
        )

        if topic is None:
            return None, 0

        return topic, score

    return None, 0

# =========================================================
# 날짜 처리
# =========================================================

def parse_date(value):

    if not value:
        return None

    try:

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(KST)

    except Exception:
        return None


# =========================================================
# 중복 기사 확인
# =========================================================

def normalize_link(link):

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


# =========================================================
# Google News RSS URL
# =========================================================

def google_news_url(query, hl, gl, ceid):

    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=" + hl
        + "&gl=" + gl
        + "&ceid=" + ceid
    )


# =========================================================
# RSS 요청 간격 조절
# =========================================================

def wait_for_request():

    global last_request_time

    elapsed = time.monotonic() - last_request_time

    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)

    last_request_time = time.monotonic()


def get_retry_after(exc):

    try:

        value = exc.headers.get("Retry-After")

        if value:
            return max(1, min(int(value), 60))

    except (AttributeError, TypeError, ValueError):
        pass

    return None


# =========================================================
# RSS 다운로드 및 재시도
# =========================================================

def download_feed(url):

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


# =========================================================
# RSS 기사 수집
# =========================================================

def fetch_feed(url, category):

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

        if not title or not link or not published_dt:
            continue

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


# =========================================================
# 중복 제거
# =========================================================

def is_duplicate(item, seen_links, seen_titles):

    title_key = normalize_title(item["title"])
    link_key = normalize_link(item["link"])

    if not title_key or title_key in seen_titles:
        return True

    if link_key in seen_links:
        return True

    seen_titles.add(title_key)
    seen_links.add(link_key)

    return False


# =========================================================
# 메인 실행
# =========================================================

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

    # -----------------------------------------------------
    # RSS 수집 및 기사 분류
    # -----------------------------------------------------

    for category, query_list in QUERIES.items():

        print(f"\nCollecting category: {category}")

        for query, hl, gl, ceid in query_list:

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
                rejected_count = 0

                for item in feed_items:

                    published_dt = item["_published_dt"]

                    if published_dt < cutoff:
                        continue

                    if published_dt > future_limit:
                        continue

                    # 실제 기사 내용을 바탕으로 분류
                    topic, quality_score = classify_article(
                        category,
                        item["title"],
                        item["summary"]
                    )

                    # 분야와 관련 없는 기사 제외
                    if topic is None:
                        rejected_count += 1
                        continue

                    item["topic"] = topic
                    item["_quality_score"] = quality_score

                    # 중복 기사 제거
                    if is_duplicate(
                        item,
                        seen_links,
                        seen_titles
                    ):
                        continue

                    items.append(item)

                    added_count += 1

                print(
                    f"  {query}: "
                    f"{added_count} added / "
                    f"{rejected_count} rejected"
                )

            except Exception as exc:

                error_message = (
                    f"{category}/{query}: "
                    f"{type(exc).__name__}: {exc}"
                )

                errors.append(error_message)

                print(f"  ERROR: {error_message}")

    # -----------------------------------------------------
    # 최신순 정렬
    # -----------------------------------------------------

    items.sort(
        key=lambda x: x["_published_dt"],
        reverse=True
    )

    # -----------------------------------------------------
    # 카테고리 및 세부 분야별 제한
    # -----------------------------------------------------

    category_counts = {
        "tech": 0,
        "us": 0,
        "kr": 0
    }

    topic_counts = {
        "tech": {},
        "us": {},
        "kr": {}
    }

    filtered_items = []

    for item in items:

        category = item["category"]
        topic = item["topic"]

        if category_counts[category] >= MAX_PER_CATEGORY[category]:
            continue

        topic_counts[category].setdefault(topic, 0)

        if topic_counts[category][topic] >= MAX_PER_TOPIC[category]:
            continue

        category_counts[category] += 1
        topic_counts[category][topic] += 1

        filtered_items.append(item)

        if len(filtered_items) >= MAX_ITEMS:
            break

    # -----------------------------------------------------
    # 내부 처리용 데이터 제거
    # -----------------------------------------------------

    for item in filtered_items:

        del item["_published_dt"]
        del item["_quality_score"]

    # -----------------------------------------------------
    # JSON 생성
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 최신 뉴스 저장
    # -----------------------------------------------------

    (DATA_DIR / "latest.json").write_text(
        output,
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # 날짜별 백업 저장
    # -----------------------------------------------------

    backup_path = DATA_DIR / (
        f"{now.strftime('%Y-%m-%d')}.json"
    )

    backup_path.write_text(
        output,
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # 실행 결과 출력
    # -----------------------------------------------------

    print("\n========== DAILY BRIEF ==========")

    print(f"Saved: {len(filtered_items)} articles")

    print(f"Tech: {category_counts['tech']}")
    print(f"US:   {category_counts['us']}")
    print(f"KR:   {category_counts['kr']}")

    for category in ["tech", "us", "kr"]:

        print(f"\n[{category.upper()} TOPICS]")

        for topic, count in topic_counts[category].items():

            print(f"{topic}: {count}")

    print(f"\nFeed errors: {len(errors)}")

    print("=================================")


if __name__ == "__main__":
    main()
