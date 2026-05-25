"""
KRX 데이터 수집 - pykrx 래퍼.

주요 함수:
    fetch_daily_ohlcv       - 일별 전종목 OHLCV + 시가총액
    fetch_nps_daily_trades  - 일별 '연기금 등' 종목별 순매수
    fetch_stock_master      - 현재 상장 종목 마스터 (KOSPI + KOSDAQ)
"""
import os
from datetime import date, timedelta

import pandas as pd
from loguru import logger
from pykrx import stock
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

# KRX에서 "연기금 등" 카테고리로 제공하는 투자자 코드
# 국민연금이 절대다수 비중이나 단독 수치는 아님 (PROJECT_SPEC §1.3.1 참고)
NPS_INVESTOR = "연기금"


def _inject_krx_credentials() -> None:
    """
    pykrx 1.1+는 KRX 데이터 포털 로그인이 필요.
    config의 KRX_ID / KRX_PW를 환경변수로 주입.
    미설정 시 경고만 출력 (개발/테스트 환경에서 일부 API는 동작 가능).
    """
    if settings.krx_id:
        os.environ["KRX_ID"] = settings.krx_id
    if settings.krx_pw:
        os.environ["KRX_PW"] = settings.krx_pw
    if not settings.krx_id or not settings.krx_pw:
        logger.warning("KRX_ID / KRX_PW 미설정. data.krx.co.kr 가입 후 .env에 추가 필요.")


# 모듈 임포트 시점에 자격증명 주입
_inject_krx_credentials()


def _most_recent_weekday(ref: date | None = None) -> date:
    """가장 최근 평일 반환 (종목 마스터 조회용 - 오늘이 데이터 미확정일 수 있음)"""
    d = ref or date.today()
    # 월요일(0) ~ 금요일(4); 토=5, 일=6
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d - timedelta(days=2)
    # 평일이라도 오늘 데이터가 아직 없을 수 있으므로 전날 사용
    return d - timedelta(days=1)


def _date_str(d: date) -> str:
    return d.strftime("%Y%m%d")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=60),
    reraise=True,
)
def _fetch_ohlcv_with_cap(date_str: str, market: str) -> pd.DataFrame:
    """OHLCV와 시가총액을 한 마켓에서 수집 후 병합"""
    ohlcv = stock.get_market_ohlcv_by_ticker(date_str, market=market)
    if ohlcv.empty:
        return pd.DataFrame()

    # pykrx 반환 컬럼: 시가, 고가, 저가, 종가, 거래량, 거래대금
    ohlcv = ohlcv.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
            "거래대금": "trading_value",
        }
    )
    # pykrx 인덱스가 ticker 코드
    ohlcv.index.name = "ticker"

    # 시가총액 및 상장주식수 병합
    try:
        cap = stock.get_market_cap_by_ticker(date_str, market=market)
        cap = cap.rename(
            columns={
                "시가총액": "market_cap",
                "상장주식수": "shares_outstanding",
            }
        )
        cap.index.name = "ticker"
        ohlcv = ohlcv.join(cap[["market_cap", "shares_outstanding"]], how="left")
    except Exception as e:
        # 시가총액 수집 실패 시 OHLCV만 반환 (부분 실패 허용)
        logger.warning(f"시가총액 수집 실패 ({market}, {date_str}): {e}")
        ohlcv["market_cap"] = None
        ohlcv["shares_outstanding"] = None

    ohlcv["market"] = market
    return ohlcv.reset_index()


def fetch_daily_ohlcv(target_date: date) -> pd.DataFrame:
    """
    특정 일자의 KOSPI + KOSDAQ 전종목 OHLCV + 시가총액 수집.

    Returns:
        columns: ticker, open, high, low, close, volume, trading_value,
                 market_cap, shares_outstanding, market
        휴장일이면 빈 DataFrame 반환.
    """
    date_str = _date_str(target_date)
    frames: list[pd.DataFrame] = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = _fetch_ohlcv_with_cap(date_str, market)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            logger.error(f"OHLCV 수집 실패 ({market}, {target_date}): {e}")

    if not frames:
        logger.info(f"OHLCV 데이터 없음 (휴장일 가능성): {target_date}")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # 종가 0인 데이터는 거래 없음 → 제외
    combined = combined[combined["close"] > 0]

    # int 타입 보장 (pykrx가 float 반환하는 경우 있음)
    int_cols = ["open", "high", "low", "close", "volume", "trading_value"]
    combined[int_cols] = combined[int_cols].fillna(0).astype(int)
    for col in ("market_cap", "shares_outstanding"):
        if col in combined.columns:
            combined[col] = combined[col].where(combined[col].notna(), None)
            combined[col] = combined[col].apply(
                lambda x: int(x) if x is not None and x > 0 else None
            )

    logger.info(f"OHLCV 수집 완료: {target_date}, {len(combined)}개 종목")
    return combined


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=60),
    reraise=True,
)
def _fetch_net_purchases(date_str: str, market: str) -> pd.DataFrame:
    """단일 마켓 연기금 순매수 수집"""
    df = stock.get_market_net_purchases_of_equities_by_ticker(
        date_str, date_str, market, NPS_INVESTOR
    )
    return df


def fetch_nps_daily_trades(target_date: date) -> pd.DataFrame:
    """
    특정 일자의 '연기금 등' 종목별 순매수 수집.

    KRX는 '연기금 등' 합산 카테고리만 제공 (국민연금 단독 아님).
    장 마감 후(T+1) 기준으로 전일 데이터가 확정됨.

    Returns:
        columns: ticker, net_buy_volume, net_buy_amount
        휴장일이면 빈 DataFrame 반환.
    """
    date_str = _date_str(target_date)
    frames: list[pd.DataFrame] = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = _fetch_net_purchases(date_str, market)
            if df.empty:
                continue

            # pykrx 반환 컬럼: 매수거래량, 매도거래량, 순매수거래량, 매수거래대금, 매도거래대금, 순매수거래대금
            df = df.rename(
                columns={
                    "순매수거래량": "net_buy_volume",
                    "순매수거래대금": "net_buy_amount",
                }
            )
            df.index.name = "ticker"
            frames.append(df.reset_index()[["ticker", "net_buy_volume", "net_buy_amount"]])

        except Exception as e:
            logger.error(f"연기금 순매수 수집 실패 ({market}, {target_date}): {e}")

    if not frames:
        logger.info(f"연기금 매매 데이터 없음 (휴장일 가능성): {target_date}")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # 순매수/순매도 모두 0인 종목은 연기금 거래 없음 → 제외
    combined = combined[
        (combined["net_buy_volume"] != 0) | (combined["net_buy_amount"] != 0)
    ]

    combined["net_buy_volume"] = combined["net_buy_volume"].fillna(0).astype(int)
    combined["net_buy_amount"] = combined["net_buy_amount"].fillna(0).astype(int)

    logger.info(f"연기금 매매 수집 완료: {target_date}, {len(combined)}개 종목")
    return combined


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=60),
    reraise=True,
)
def fetch_stock_master() -> pd.DataFrame:
    """
    현재 상장 종목 마스터 (KOSPI + KOSDAQ).

    Returns:
        columns: ticker, name, market
        주의: pykrx는 get_market_ticker_name을 종목당 1회 호출하므로 수천 건 수집 시 느릴 수 있음.
              최초 설정 또는 주 1회 갱신 용도.
    """
    today_str = _most_recent_weekday().strftime("%Y%m%d")
    records: list[dict[str, str]] = []

    for market in ("KOSPI", "KOSDAQ"):
        tickers = stock.get_market_ticker_list(today_str, market=market)
        logger.info(f"{market} 종목 수: {len(tickers)}")

        for ticker in tickers:
            try:
                name = stock.get_market_ticker_name(ticker)
                records.append({"ticker": ticker, "name": name, "market": market})
            except Exception as e:
                logger.warning(f"종목명 조회 실패 ({ticker}): {e}")

    df = pd.DataFrame(records)
    logger.info(f"종목 마스터 수집 완료: {len(df)}개 종목")
    return df
