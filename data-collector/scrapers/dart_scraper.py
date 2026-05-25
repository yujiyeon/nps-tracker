"""
DART 데이터 수집 - OpenDartReader 래퍼.

국민연금공단의 '주식등의대량보유상황보고서' (5% 이상 보유 공시) 수집.

주요 함수:
    fetch_nps_holdings_for_ticker  - 특정 종목의 국민연금 보유 공시 조회
    fetch_nps_holdings_bulk        - 종목 목록에 대한 일괄 조회
"""
import re
from datetime import date

import OpenDartReader
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

# 국민연금공단 DART corp_code
NPS_KEYWORDS = ("국민연금", "국민연금공단")

# DART 보고서 유형 F: 주식등의대량보유상황보고서
MAJOR_HOLDING_REPORT_TYPE = "F"


def _get_dart_client() -> OpenDartReader.OpenDartReader:
    if not settings.dart_api_key:
        raise ValueError("DART_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return OpenDartReader.OpenDartReader(settings.dart_api_key)


def _is_nps_report(report_nm: str) -> bool:
    """보고서명에 국민연금 관련 키워드가 포함되는지 확인"""
    return any(kw in report_nm for kw in NPS_KEYWORDS)


def _parse_holding_ratio(text: str) -> float | None:
    """보고서 내 '보유비율' 문자열에서 숫자 추출"""
    match = re.search(r"(\d+\.?\d*)%?", text.replace(",", ""))
    return float(match.group(1)) if match else None


def _parse_shares(text: str) -> int | None:
    """보고서 내 '보유주식수' 문자열에서 숫자 추출"""
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=30),
    reraise=True,
)
def _get_corp_code(dart: OpenDartReader.OpenDartReader, ticker: str) -> str | None:
    """ticker → DART corp_code 변환"""
    try:
        corp_df = dart.corp_codes
        result = corp_df[corp_df["stock_code"] == ticker]
        if result.empty:
            return None
        return str(result.iloc[0]["corp_code"])
    except Exception as e:
        logger.warning(f"corp_code 조회 실패 ({ticker}): {e}")
        return None


def fetch_nps_holdings_for_ticker(
    ticker: str,
    from_date: date,
    to_date: date,
) -> list[dict]:
    """
    특정 종목에 대한 국민연금 5% 이상 보유 공시 조회.

    DART의 '주식등의대량보유상황보고서' 중 보고서명에 '국민연금'이 포함된 건만 반환.
    rcept_no UNIQUE 제약으로 DB 중복 저장을 방지.

    Returns:
        list of dict with keys:
            ticker, rcept_no, report_date, filing_date,
            shares, holding_ratio, purpose
    """
    dart = _get_dart_client()

    corp_code = _get_corp_code(dart, ticker)
    if not corp_code:
        logger.debug(f"DART corp_code 없음 (비상장/ETF 등): {ticker}")
        return []

    try:
        reports = dart.list(
            corp_code,
            bgn_de=from_date.strftime("%Y%m%d"),
            end_de=to_date.strftime("%Y%m%d"),
            pblntf_ty=MAJOR_HOLDING_REPORT_TYPE,
        )
    except Exception as e:
        logger.error(f"DART 보고서 목록 조회 실패 ({ticker}): {e}")
        return []

    if reports is None or (isinstance(reports, pd.DataFrame) and reports.empty):
        return []

    # 국민연금이 보고자인 공시만 필터링
    if isinstance(reports, pd.DataFrame):
        nps_reports = reports[reports["report_nm"].apply(_is_nps_report)]
    else:
        return []

    results: list[dict] = []
    for _, row in nps_reports.iterrows():
        rcept_no = str(row.get("rcept_no", ""))
        if not rcept_no:
            continue

        # 보고서 상세 내용에서 보유주식수, 비율, 목적 파싱 시도
        holding_data = _parse_report_detail(dart, rcept_no)

        filing_date_raw = str(row.get("rcept_dt", ""))
        if len(filing_date_raw) == 8:
            filing_date = date(
                int(filing_date_raw[:4]),
                int(filing_date_raw[4:6]),
                int(filing_date_raw[6:8]),
            )
        else:
            filing_date = to_date  # 파싱 실패 시 조회 종료일로 대체

        results.append(
            {
                "ticker": ticker,
                "rcept_no": rcept_no,
                "report_date": holding_data.get("report_date", filing_date),
                "filing_date": filing_date,
                "shares": holding_data.get("shares", 0),
                "holding_ratio": holding_data.get("holding_ratio", 0.0),
                "purpose": holding_data.get("purpose", "단순투자"),
            }
        )

    if results:
        logger.info(f"국민연금 보유 공시 수집 완료: {ticker}, {len(results)}건")

    return results


def _parse_report_detail(
    dart: OpenDartReader.OpenDartReader,
    rcept_no: str,
) -> dict:
    """
    DART 보고서 상세에서 보유주식수, 비율, 목적 파싱.

    DART HTML 문서 파싱이 필요한 복잡한 작업.
    파싱 실패 시 빈 dict 반환 (부분 실패 허용).
    """
    try:
        sub_docs = dart.sub_docs(rcept_no)
        if sub_docs is None or sub_docs.empty:
            return {}

        # 대량보유상황보고서의 첫 번째 문서가 주요 내용을 담음
        first_doc = sub_docs.iloc[0]
        doc_url = first_doc.get("url", "")
        if not doc_url:
            return {}

        doc = dart.document(rcept_no)
        if doc is None:
            return {}

        # HTML 파싱으로 보유 정보 추출
        result: dict = {}

        # '보유주식등의 수' 패턴 찾기
        shares_match = re.search(r"보유주식등의\s*수[^\d]*?([\d,]+)", doc)
        if shares_match:
            result["shares"] = _parse_shares(shares_match.group(1)) or 0

        # '보유비율' 패턴 찾기
        ratio_match = re.search(r"보유비율[^\d]*?([\d.]+)\s*%", doc)
        if ratio_match:
            result["holding_ratio"] = float(ratio_match.group(1))

        # '보유목적' 패턴 찾기
        purpose_match = re.search(r"보유목적[^가-힣]*([가-힣]+)", doc)
        if purpose_match:
            result["purpose"] = purpose_match.group(1)

        return result

    except Exception as e:
        logger.debug(f"보고서 상세 파싱 실패 (rcept_no={rcept_no}): {e}")
        return {}


def fetch_nps_holdings_bulk(
    tickers: list[str],
    from_date: date,
    to_date: date,
) -> list[dict]:
    """
    종목 목록에 대한 국민연금 보유 공시 일괄 조회.

    DART API 과부하 방지를 위해 종목당 순차 처리.
    이미 수집된 rcept_no는 DB의 UNIQUE 제약으로 중복 저장 방지.

    Returns:
        모든 종목의 보유 공시 통합 리스트
    """
    all_results: list[dict] = []
    total = len(tickers)

    for idx, ticker in enumerate(tickers, 1):
        if idx % 50 == 0:
            logger.info(f"DART 조회 진행 중: {idx}/{total}")

        try:
            results = fetch_nps_holdings_for_ticker(ticker, from_date, to_date)
            all_results.extend(results)
        except Exception as e:
            logger.error(f"DART 보유 공시 조회 실패 ({ticker}): {e}")

    logger.info(f"DART 일괄 조회 완료: {len(tickers)}개 종목, {len(all_results)}건 공시")
    return all_results
