"""종목 마스터 및 OHLCV 관련 비즈니스 로직"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import DailyOhlcv, Stock
from schemas.stocks import OhlcvItem, StockDetailResponse, StockItem, StockListResponse


def get_stocks(
    session: Session,
    market: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> StockListResponse:
    query = select(Stock)

    if market:
        query = query.where(Stock.market == market)
    if is_active is not None:
        query = query.where(Stock.is_active == is_active)

    total = session.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar_one()

    stocks = session.execute(
        query.order_by(Stock.market, Stock.ticker)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return StockListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[StockItem.model_validate(s) for s in stocks],
    )


def get_stock_detail(session: Session, ticker: str) -> StockDetailResponse | None:
    stock = session.get(Stock, ticker)
    if not stock:
        return None

    # 최근 60 영업일 OHLCV (TimescaleDB 청크 프루닝을 위해 날짜 범위 조건 필수)
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=90)  # 60 영업일 ≈ 90 달력일

    ohlcv_rows = session.execute(
        select(DailyOhlcv)
        .where(DailyOhlcv.ticker == ticker)
        .where(DailyOhlcv.trade_date >= cutoff)
        .order_by(DailyOhlcv.trade_date.desc())
        .limit(60)
    ).scalars().all()

    return StockDetailResponse(
        stock=StockItem.model_validate(stock),
        ohlcv=[OhlcvItem.model_validate(o) for o in ohlcv_rows],
    )
