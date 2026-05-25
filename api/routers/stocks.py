from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.session import get_session
from schemas.stocks import StockDetailResponse, StockListResponse
from services.stock_service import get_stock_detail, get_stocks

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
def list_stocks(
    session: Annotated[Session, Depends(get_session)],
    market: Annotated[str | None, Query(description="KOSPI / KOSDAQ")] = None,
    is_active: Annotated[bool | None, Query()] = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StockListResponse:
    """종목 마스터 목록 조회 (페이지네이션)"""
    return get_stocks(session, market, is_active, page, page_size)


@router.get("/{ticker}", response_model=StockDetailResponse)
def stock_detail(
    ticker: str,
    session: Annotated[Session, Depends(get_session)],
) -> StockDetailResponse:
    """종목 상세 정보 + 최근 60 영업일 OHLCV"""
    result = get_stock_detail(session, ticker)
    if not result:
        raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {ticker}")
    return result
