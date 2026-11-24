#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""DAILY BRIEF - 한국은행 ECOS + 미국 FRED 경제지표 수집기"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "economy.json"

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
ECOS_KEY = os.getenv("ECOS_API_KEY", "").strip()
FRED_KEY = os.getenv("FRED_API_KEY", "").strip()
TODAY = datetime.now(KST).date()

# freshness_limit_days는 최신 관측일로부터 며칠까지를 정상으로 볼지 정하는 참고 기준입니다.
# 통계 발표 일정은 지표별로 다르므로 '지연' 표시는 공식 발표 지연을 확정하는 의미가 아닙니다.
ECOS_SERIES = [
    {"id": "kr_base_rate", "name": "한국은행 기준금리", "table": "722Y001", "item": "0101000", "cycle": "D", "frequency_name": "일간", "unit": "연 %", "years": 3, "freshness_limit_days": 14},
    {"id": "kr_usd_exchange", "name": "원/달러 환율", "table": "731Y001", "item": "0000001", "cycle": "D", "frequency_name": "일간", "unit": "원", "years": 3, "freshness_limit_days": 14},
    {"id": "kr_bond_3y", "name": "국고채 3년 금리", "table": "817Y002", "item": "010200000", "cycle": "D", "frequency_name": "일간", "unit": "연 %", "years": 3, "freshness_limit_days": 14},
    {"id": "kr_cpi", "name": "한국 소비자물가지수", "table": "901Y009", "item": "0", "cycle": "M", "frequency_name": "월간", "unit": "지수", "years": 5, "freshness_limit_days": 65},
]

FRED_SERIES = [
    {"id": "us_fed_rate", "series": "FEDFUNDS", "name": "미국 연방기금금리", "unit": "%", "frequency": "monthly", "frequency_name": "월간", "freshness_limit_days": 65, "change_type": "percentage_points"},
    {"id": "us_cpi", "series": "CPIAUCSL", "name": "미국 소비자물가지수", "unit": "지수", "frequency": "monthly", "frequency_name": "월간", "freshness_limit_days": 65, "change_type": "percent"},
    {"id": "us_unemployment", "series": "UNRATE", "name": "미국 실업률", "unit": "%", "frequency": "monthly", "frequency_name": "월간", "freshness_limit_days": 65, "change_type": "percentage_points"},
    {"id": "us_treasury_10y", "series": "DGS10", "name": "미국 10년물 국채금리", "unit": "%", "frequency": "daily", "frequency_name": "일간", "freshness_limit_days": 7, "change_type": "percentage_points"},
    {"id": "us_real_gdp", "series": "GDPC1", "name": "미국 실질 GDP", "unit": "십억 달러", "frequency": "quarterly", "frequency_name": "분기별", "freshness_limit_days": 150, "change_type": "percent"},
]

# 위 설정의 오타 방지: 실업률의 갱신 기준을 월간 65일로 고정
FRED_SERIES[2]["freshness_limit_days"] = 65


def request_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DAILY-BRIEF/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def parse_date(value):
    """ECOS 일간/월간 및 FRED 날짜를 date로 변환합니다."""
    value = str(value or "")
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").date()
    if len(value) == 6 and value.isdigit():
        return datetime.strptime(value, "%Y%m").date()
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def add_analysis_fields(observations, frequency, freshness_limit_days, change_type="percent"):
    """최신값, 직전값 비교, 전년 동기 비교, 관측 경과일을 계산합니다."""
    observations = sorted(observations, key=lambda item: item["date"])
    latest = observations[-1]
    latest_date = parse_date(latest["date"])
    age_days = max(0, (TODAY - latest_date).days)

    def comparison(target_date, tolerance_days):
        candidates = []
        for item in observations[:-1]:
            item_date = parse_date(item["date"])
            if item_date <= target_date:
                distance = (target_date - item_date).days
                if distance <= tolerance_days:
                    candidates.append((distance, item))
        return min(candidates, key=lambda pair: pair[0])[1] if candidates else None

    if frequency == "daily":
        previous = observations[-2] if len(observations) >= 2 else None
        year_ago = comparison(latest_date - timedelta(days=365), 10)
    elif frequency == "quarterly":
        previous = observations[-2] if len(observations) >= 2 else None
        year_ago = comparison(latest_date - timedelta(days=365), 120)
    else:  # monthly 또는 ECOS 월간
        previous = observations[-2] if len(observations) >= 2 else None
        year_ago = comparison(latest_date - timedelta(days=365), 45)

    def make_change(reference):
        if reference is None:
            return None
        difference = latest["value"] - reference["value"]
        percent = None
        if reference["value"] != 0:
            percent = (difference / abs(reference["value"])) * 100
        result = {
            "reference_date": reference["date"],
            "reference_value": reference["value"],
            "difference": round(difference, 6),
            "percent_change": round(percent, 4) if percent is not None else None,
            "unit": latest.get("unit", ""),
        }
        if change_type == "percentage_points":
            result["difference_label"] = "%p"
        else:
            result["difference_label"] = latest.get("unit", "")
        return result

    freshness_status = "normal" if age_days <= freshness_limit_days else "check_update"
    return {
        "latest": latest,
        "previous_observation": previous,
        "change_from_previous": make_change(previous),
        "year_over_year": make_change(year_ago),
        "observation_age_days": age_days,
        "freshness_status": freshness_status,
        "freshness_limit_days": freshness_limit_days,
    }


def fetch_ecos(config):
    if not ECOS_KEY:
        raise ValueError("ECOS_API_KEY 환경변수가 없습니다.")

    years = config["years"]
    start_date = TODAY.replace(year=TODAY.year - years)
    cycle = config["cycle"]
    if cycle == "D":
        start, end = start_date.strftime("%Y%m%d"), TODAY.strftime("%Y%m%d")
    elif cycle == "M":
        start, end = start_date.strftime("%Y%m"), TODAY.strftime("%Y%m")
    else:
        raise ValueError("지원하지 않는 ECOS 주기입니다.")

    key = urllib.parse.quote(ECOS_KEY, safe="")
    url = (
        "https://ecos.bok.or.kr/api/StatisticSearch/"
        f"{key}/json/kr/1/1000/{config['table']}/{cycle}/{start}/{end}/{config['item']}"
    )
    data = request_json(url)
    result = data.get("StatisticSearch", {})
    rows = result.get("row", [])
    if not rows:
        error = data.get("RESULT", {})
        if error:
            raise ValueError(f"ECOS 응답: {error}")
        raise ValueError("ECOS 데이터가 없습니다. 통계표 코드와 주기를 확인하세요.")

    observations = []
    for row in rows:
        value = row.get("DATA_VALUE")
        if value in (None, "", "-"):
            continue
        try:
            numeric_value = float(str(value).replace(",", ""))
        except ValueError:
            continue
        observations.append({
            "date": row.get("TIME"),
            "value": numeric_value,
            "unit": row.get("UNIT_NAME") or config["unit"],
        })

    if not observations:
        raise ValueError("ECOS 유효 관측값이 없습니다.")

    observations.sort(key=lambda item: item["date"])
    analysis = add_analysis_fields(
        observations,
        "monthly" if cycle == "M" else "daily",
        config["freshness_limit_days"],
        "percentage_points" if "금리" in config["name"] else "percent",
    )
    return {
        "id": config["id"], "name": config["name"], "country": "KR",
        "source": "한국은행 ECOS", "source_url": "https://ecos.bok.or.kr/",
        "frequency": cycle, "frequency_name": config["frequency_name"],
        "unit": config["unit"], **analysis,
        "observations": observations, "status": "success",
    }


def fetch_fred(config):
    if not FRED_KEY:
        raise ValueError("FRED_API_KEY 환경변수가 없습니다.")

    start_date = TODAY - timedelta(days=365 * 5)
    params = {
        "series_id": config["series"], "api_key": FRED_KEY,
        "file_type": "json", "observation_start": start_date.isoformat(),
        "observation_end": TODAY.isoformat(), "sort_order": "asc",
    }
    url = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(params)
    data = request_json(url)

    observations = []
    for row in data.get("observations", []):
        value = row.get("value")
        if value in (None, "", "."):
            continue
        try:
            numeric_value = float(value)
        except ValueError:
            continue
        observations.append({"date": row.get("date"), "value": numeric_value, "unit": config["unit"]})

    if not observations:
        raise ValueError("FRED 유효 관측값이 없습니다.")

    analysis = add_analysis_fields(
        observations,
        config["frequency"],
        config["freshness_limit_days"],
        config["change_type"],
    )
    return {
        "id": config["id"], "name": config["name"], "country": "US",
        "source": "FRED",
        "source_url": "https://fred.stlouisfed.org/series/" + config["series"],
        "series_id": config["series"], "frequency": config["frequency"],
        "frequency_name": config["frequency_name"], "unit": config["unit"],
        **analysis, "observations": observations, "status": "success",
    }


def collect_all():
    results, errors = [], []

    print("\n[한국 ECOS 수집]")
    for config in ECOS_SERIES:
        print(f"  수집: {config['name']}")
        try:
            result = fetch_ecos(config)
            results.append(result)
            print(f"    성공: {result['latest']['value']} {result['latest']['unit']} (관측일: {result['latest']['date']})")
        except Exception as error:
            errors.append({"id": config["id"], "source": "ECOS", "error": str(error)})
            print(f"    실패: {error}")

    print("\n[미국 FRED 수집]")
    for config in FRED_SERIES:
        print(f"  수집: {config['name']}")
        try:
            result = fetch_fred(config)
            results.append(result)
            print(f"    성공: {result['latest']['value']} {result['latest']['unit']} (관측일: {result['latest']['date']})")
            print(f"    직전 관측 대비: {result['change_from_previous']}")
            print(f"    전년 동기 대비: {result['year_over_year']}")
            print(f"    갱신 상태: {result['freshness_status']} / 관측 후 {result['observation_age_days']}일")
        except Exception as error:
            errors.append({"id": config["id"], "source": "FRED", "error": str(error)})
            print(f"    실패: {error}")

    return results, errors


def main():
    print("=" * 55)
    print("DAILY BRIEF 경제지표 수집 시작")
    print("=" * 55)
    if not ECOS_KEY:
        print("[주의] ECOS_API_KEY가 설정되지 않았습니다.")
    if not FRED_KEY:
        print("[주의] FRED_API_KEY가 설정되지 않았습니다.")

    results, errors = collect_all()
    collected_at = datetime.now(KST)
    payload = {
        "updated_at": collected_at.strftime("%Y-%m-%d %H:%M KST"),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "collection_date": collected_at.date().isoformat(),
        "source_count": 2,
        "success_count": len(results),
        "error_count": len(errors),
        "data": results,
        "errors": errors,
        "notes": [
            "updated_at는 DAILY BRIEF의 수집 시각이며 latest.date는 통계의 실제 관측 기준일입니다.",
            "freshness_status는 지표별 참고 기준에 따른 표시이며 공식 발표 지연을 확정하지 않습니다.",
            "변화율은 비교 가능한 과거 관측값이 있을 때만 계산됩니다.",
        ],
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 55)
    print("[완료] 경제지표 수집 종료")
    print(f"[성공] {len(results)}개")
    print(f"[실패] {len(errors)}개")
    print(f"[저장] {OUTPUT_FILE}")
    print("=" * 55)


if __name__ == "__main__":
    main()
