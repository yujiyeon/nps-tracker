import hashlib
import json
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from loguru import logger
from sqlalchemy.orm import Session

from db.session import get_session
from schemas.nps_trades import NpsDailySummaryResponse, NpsHoldingsResponse, NpsTradeTimeSeriesResponse
from services import cache_service
from services.nps_service import (
    get_latest_trade_date,
    get_nps_daily_summary,
    get_nps_holdings,
    get_nps_trade_timeseries,
)

router = APIRouter(prefix="/api/nps", tags=["nps"])


@router.get("/daily", response_model=NpsDailySummaryResponse)
def nps_daily(
    session: Annotated[Session, Depends(get_session)],
    trade_date: Annotated[date | None, Query(description="조회 날짜 (기본: 가장 최근 수집일)")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    market: Annotated[str | None, Query(description="KOSPI / KOSDAQ")] = None,
) -> NpsDailySummaryResponse:
    """
    일별 연기금 순매수 상위 종목.

    메인 화면 핵심 API. Redis TTL 1시간 캐싱.
    trade_date 미지정 시 가장 최근 수집일 자동 선택.
    """
    if trade_date is None:
        trade_date = get_latest_trade_date(session)
        if not trade_date:
            raise HTTPException(status_code=404, detail="수집된 NPS 매매 데이터가 없습니다.")

    # close_date(최신 OHLCV 날짜)가 바뀌면 캐시 무효화되도록 키에 포함
    from services.nps_service import get_latest_ohlcv_date
    latest_ohlcv = get_latest_ohlcv_date(session) or trade_date
    cache_key = f"nps:daily:{trade_date}:{limit}:{market or 'ALL'}:{latest_ohlcv}"
    cached = cache_service.get_cached(cache_key)
    if cached:
        return NpsDailySummaryResponse(**cached)

    result = get_nps_daily_summary(session, trade_date, limit, market)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"{trade_date} 날짜의 NPS 매매 데이터가 없습니다. 휴장일이거나 미수집 날짜입니다.",
        )

    cache_service.set_cached(cache_key, result.model_dump(), ttl=3600)
    return result


@router.get("/stocks/{ticker}/trades", response_model=NpsTradeTimeSeriesResponse)
def nps_trade_timeseries(
    ticker: str,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    from_date: Annotated[date | None, Query()] = None,
    to_date: Annotated[date | None, Query()] = None,
) -> NpsTradeTimeSeriesResponse:
    """
    특정 종목의 NPS 매매 시계열.

    ETag 기반 304 응답으로 대역폭 절약.
    기본 조회 범위: 최근 1년.
    """
    today = date.today()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = today - timedelta(days=365)

    result = get_nps_trade_timeseries(session, ticker, from_date, to_date)
    if not result:
        raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {ticker}")

    # ETag: 데이터의 해시값 (내용이 같으면 304 반환)
    etag = hashlib.md5(
        json.dumps(result.model_dump(), default=str).encode()
    ).hexdigest()
    response.headers["ETag"] = f'"{etag}"'

    if request.headers.get("If-None-Match") == f'"{etag}"':
        return Response(status_code=304)  # type: ignore[return-value]

    return result


@router.get("/stocks/{ticker}/holdings", response_model=NpsHoldingsResponse)
def nps_holdings(
    ticker: str,
    session: Annotated[Session, Depends(get_session)],
) -> NpsHoldingsResponse:
    """특정 종목의 NPS 5% 이상 보유 공시 이력 (DART)"""
    result = get_nps_holdings(session, ticker)
    if not result:
        raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {ticker}")
    return result
