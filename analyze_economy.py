
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""DAILY BRIEF - 경제지표 규칙 기반 분석기"""

import json
from pathlib import Path
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
INPUT_FILE = DATA_DIR / "economy.json"
OUTPUT_FILE = DATA_DIR / "economic_analysis.json"

KST = ZoneInfo("Asia/Seoul")


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_date(value):
    if not value:
        return None

    value = str(value)

    try:
        if len(value) == 6 and value.isdigit():
            return datetime.strptime(value, "%Y%m").date()

        if len(value) == 8 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d").date()

        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def get_indicators(payload):
    result = {}

    for item in payload.get("data", []):
        if item.get("status") == "success" and item.get("latest"):
            result[item.get("id")] = item

    return result


def get_value(indicators, key):
    item = indicators.get(key)

    if not item:
        return None

    try:
        return float(item["latest"]["value"])
    except (TypeError, ValueError, KeyError):
        return None


def get_date(indicators, key):
    item = indicators.get(key)

    if not item:
        return None

    return item.get("latest", {}).get("date")


def get_yoy(item):
    """관측일의 전년 같은 달 또는 같은 분기와 직접 비교합니다."""
    if not item:
        return None

    observations = item.get("observations", [])
    latest = item.get("latest")

    if not latest:
        return None

    latest_date = parse_date(latest.get("date"))

    if not latest_date:
        return None

    target_year = latest_date.year - 1
    candidates = []

    for observation in observations:
        obs_date = parse_date(observation.get("date"))

        if not obs_date or obs_date.year != target_year:
            continue

        # 월간·분기 자료는 같은 월 또는 같은 분기 기준으로 비교
        if obs_date.month == latest_date.month:
            candidates.append(observation)

    if not candidates:
        return None

    previous = candidates[-1]

    try:
        old_value = float(previous["value"])
        new_value = float(latest["value"])
    except (TypeError, ValueError, KeyError):
        return None

    if old_value == 0:
        return None

    change = (new_value - old_value) / abs(old_value) * 100

    return {
        "reference_date": previous.get("date"),
        "reference_value": old_value,
        "change_percent": round(change, 2),
    }


def describe_change(item, unit=None):
    if not item:
        return "비교할 과거 관측값이 없습니다."

    change = item.get("change_from_previous")

    if not change:
        return "직전 관측값과 비교할 수 없습니다."

    difference = change.get("difference")

    if difference is None:
        return "변화량을 확인할 수 없습니다."

    try:
        difference = float(difference)
    except (TypeError, ValueError):
        return "변화량을 확인할 수 없습니다."

    label = unit or change.get("difference_label") or ""

    if difference > 0:
        direction = "상승"
    elif difference < 0:
        direction = "하락"
    else:
        direction = "보합"

    return f"직전 관측 대비 {direction} {abs(difference):,.3f}{label}"


def freshness_message(item):
    if not item:
        return "자료 없음"

    if item.get("freshness_status") == "check_update":
        age = item.get("observation_age_days")
        return f"확인 필요: 관측 기준일로부터 {age}일 경과"

    return "참고 갱신 기준 이내"


def indicator_summary(item, yoy=False):
    if not item:
        return None

    latest = item.get("latest", {})
    result = {
        "name": item.get("name"),
        "value": latest.get("value"),
        "unit": latest.get("unit") or item.get("unit", ""),
        "as_of": latest.get("date"),
        "source": item.get("source"),
        "source_url": item.get("source_url"),
        "change": describe_change(item),
        "freshness": freshness_message(item),
    }

    if yoy:
        result["year_over_year"] = get_yoy(item)

    return result


def rate_direction(item):
    if not item:
        return "자료가 없어 금리 방향을 판단하기 어렵습니다."

    change = item.get("change_from_previous")

    if not change:
        return "직전 관측값과 비교할 수 없습니다."

    value = change.get("difference", 0)

    if value > 0.03:
        return "최근 관측에서 금리가 상승했습니다."
    if value < -0.03:
        return "최근 관측에서 금리가 하락했습니다."

    return "최근 관측에서 금리는 대체로 보합입니다."


def inflation_direction(item):
    yoy = get_yoy(item)

    if not yoy:
        return "전년 같은 달 자료가 부족해 물가 흐름을 판단하기 어렵습니다."

    change = yoy["change_percent"]

    if change >= 3:
        return f"소비자물가지수는 전년 같은 달보다 {change:.2f}% 높습니다."
    if change <= 1:
        return f"소비자물가지수는 전년 같은 달보다 {change:.2f}% 높아 상승 폭이 비교적 낮습니다."

    return f"소비자물가지수는 전년 같은 달보다 {change:.2f}% 높습니다."


def labor_direction(item):
    if not item:
        return "고용 자료가 없습니다."

    change = item.get("change_from_previous")

    if not change:
        return "직전 실업률과 비교할 수 없습니다."

    difference = change.get("difference", 0)

    if difference >= 0.2:
        return "실업률이 직전 관측보다 상승해 고용 둔화 여부를 살펴볼 필요가 있습니다."
    if difference <= -0.2:
        return "실업률이 직전 관측보다 하락했습니다."

    return "실업률은 직전 관측과 큰 차이가 없습니다."


def build_country_analysis(country, indicators):
    if country == "US":
        definitions = [
            ("us_fed_rate", False),
            ("us_cpi", True),
            ("us_unemployment", False),
            ("us_treasury_10y", False),
            ("us_real_gdp", True),
        ]
        title = "미국 경제 분석"
        rate_key = "us_fed_rate"
        cpi_key = "us_cpi"
        labor_key = "us_unemployment"
        bond_key = "us_treasury_10y"
        gdp_key = "us_real_gdp"
    else:
        definitions = [
            ("kr_base_rate", False),
            ("kr_usd_exchange", False),
            ("kr_bond_3y", False),
            ("kr_cpi", True),
        ]
        title = "한국 경제 분석"
        rate_key = "kr_base_rate"
        cpi_key = "kr_cpi"
        labor_key = None
        bond_key = "kr_bond_3y"
        gdp_key = None

    rows = []

    for key, yoy in definitions:
        summary = indicator_summary(indicators.get(key), yoy=yoy)
        if summary:
            rows.append(summary)

    points = [
        "금리: " + rate_direction(indicators.get(rate_key)),
        "물가: " + inflation_direction(indicators.get(cpi_key)),
    ]

    if labor_key:
        points.append(
            "고용: " + labor_direction(indicators.get(labor_key))
        )

    if bond_key:
        points.append(
            "시장금리: " + rate_direction(indicators.get(bond_key))
        )

    if gdp_key:
        gdp_yoy = get_yoy(indicators.get(gdp_key))

        if gdp_yoy:
            points.append(
                "실질 GDP: 전년 같은 분기 대비 "
                f"{gdp_yoy['change_percent']:.2f}% 변화했습니다."
            )
        else:
            points.append(
                "실질 GDP: 전년 같은 분기와 비교할 자료가 부족합니다."
            )

    dates = [
        row["as_of"] for row in rows if row.get("as_of")
    ]

    return {
        "title": title,
        "summary": (
            f"{len(rows)}개 지표를 바탕으로 작성한 규칙 기반 분석입니다. "
            "각 지표의 관측 기준일과 갱신 상태를 함께 확인해야 합니다."
        ),
        "indicators": rows,
        "key_points": points,
        "as_of": max(dates) if dates else None,
    }


def build_cross_market(indicators):
    us_rate = get_value(indicators, "us_fed_rate")
    kr_rate = get_value(indicators, "kr_base_rate")

    us_date = parse_date(get_date(indicators, "us_fed_rate"))
    kr_date = parse_date(get_date(indicators, "kr_base_rate"))

    if us_rate is None or kr_rate is None:
        return {
            "title": "한·미 기준금리 비교",
            "summary": "두 나라의 기준금리 자료가 모두 있어야 비교할 수 있습니다.",
        }

    gap = us_rate - kr_rate
    date_gap = None

    if us_date and kr_date:
        date_gap = abs((us_date - kr_date).days)

    warning = ""

    if date_gap is None or date_gap > 45:
        warning = (
            " 두 금리의 관측 기준일 차이가 커서 단순 비교에 주의가 필요합니다."
        )

    return {
        "title": "한·미 기준금리 비교",
        "us_rate": us_rate,
        "kr_rate": kr_rate,
        "gap_percentage_points": round(gap, 2),
        "us_date": get_date(indicators, "us_fed_rate"),
        "kr_date": get_date(indicators, "kr_base_rate"),
        "summary": (
            f"미국 기준금리가 한국 기준금리보다 "
            f"{abs(gap):.2f}%p "
            f"{'높습니다.' if gap > 0 else '낮습니다.' if gap < 0 else '같습니다.'}"
            + warning
        ),
    }


def build_asset_impacts(indicators):
    us_rate = indicators.get("us_fed_rate")
    kr_rate = indicators.get("kr_base_rate")
    us_cpi = indicators.get("us_cpi")
    kr_cpi = indicators.get("kr_cpi")
    exchange = indicators.get("kr_usd_exchange")
    us_bond = indicators.get("us_treasury_10y")

    results = []

    results.append({
        "asset": "주식시장",
        "summary": (
            "금리 상승은 일반적으로 기업의 자금조달 비용과 "
            "주식의 할인율을 높이는 요인이 될 수 있습니다. "
            "다만 기업 실적, 경기 전망, 시장 기대에 따라 실제 반응은 달라집니다."
        ),
        "signals": [
            "미국 기준금리: " + rate_direction(us_rate),
            "미국 10년물 금리: " + rate_direction(us_bond),
            "한국 기준금리: " + rate_direction(kr_rate),
        ],
    })

    results.append({
        "asset": "금",
        "summary": (
            "실질금리와 달러 흐름은 금 가격에 영향을 줄 수 있습니다. "
            "명목금리만으로 금 가격의 방향을 단정할 수는 없습니다."
        ),
        "signals": [
            "미국 기준금리: " + rate_direction(us_rate),
            "미국 물가: " + inflation_direction(us_cpi),
            "원/달러 환율: " + describe_change(exchange, "원"),
        ],
    })

    results.append({
        "asset": "원유",
        "summary": (
            "원유는 세계 경기와 수요, 산유국 공급, 지정학적 상황, "
            "달러 가치의 영향을 함께 받습니다. 현재 지표만으로 "
            "유가 상승·하락을 확정할 수 없습니다."
        ),
        "signals": [
            "미국 실업률: " + labor_direction(indicators.get("us_unemployment")),
            "미국 물가: " + inflation_direction(us_cpi),
            "원/달러 환율: " + describe_change(exchange, "원"),
        ],
    })

    results.append({
        "asset": "부동산",
        "summary": (
            "대출금리와 가계의 자금조달 여건은 부동산 수요에 "
            "영향을 줄 수 있습니다. 실제 가격은 지역별 공급, "
            "거래량, 소득, 정책 등도 함께 살펴봐야 합니다."
        ),
        "signals": [
            "한국 기준금리: " + rate_direction(kr_rate),
            "국고채 3년 금리: " + rate_direction(indicators.get("kr_bond_3y")),
            "한국 물가: " + inflation_direction(kr_cpi),
        ],
    })

    return results


def main():
    print("=" * 55)
    print("DAILY BRIEF 경제 분석 시작")
    print("=" * 55)

    payload = load_json(INPUT_FILE)
    indicators = get_indicators(payload)

    us_analysis = build_country_analysis("US", indicators)
    kr_analysis = build_country_analysis("KR", indicators)
    cross_market = build_cross_market(indicators)
    asset_impacts = build_asset_impacts(indicators)

    now = datetime.now(KST)

    output = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M KST"),
        "source_updated_at": payload.get("updated_at"),
        "success_count": len(indicators),
        "overview": (
            "미국과 한국의 금리·물가·고용·환율 등 "
            "수집된 경제지표를 바탕으로 작성한 자동 분석입니다. "
            "지표의 관측 기준일이 서로 다를 수 있으므로 "
            "각 기준일과 갱신 상태를 함께 확인하세요."
        ),
        "countries": {
            "US": us_analysis,
            "KR": kr_analysis,
        },
        "cross_market": cross_market,
        "asset_impacts": asset_impacts,
        "methodology": [
            "소비자물가지수와 실질 GDP는 전년 같은 기간의 관측값과 비교합니다.",
            "금리·환율의 단기 변화는 직전 관측값과 비교합니다.",
            "관측 기준일은 수집일과 다를 수 있습니다.",
            "자산 영향은 일반적인 경제 경로를 설명하며 가격 예측이 아닙니다.",
            "뉴스, 정책, 수급, 기업 실적 등은 이 분석에 모두 반영되지 않습니다.",
        ],
    }

    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[분석 지표] {len(indicators)}개")
    print(f"[저장 위치] {OUTPUT_FILE}")
    print("[완료] 경제 분석 데이터 생성")


if __name__ == "__main__":
    main()
