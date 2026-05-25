"""NPS 매매 관련 비즈니스 로직"""
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from db.models import DailyOhlcv, NpsDailyTrade, NpsHolding, Stock
from schemas.nps_trades import (
    NpsDailySummaryResponse,
    NpsHoldingItem,
    NpsHoldingsResponse,
    NpsTopTradeItem,
    NpsTradeTimeSeriesItem,
    NpsTradeTimeSeriesResponse,
)


def _get_prev_trading_date(session: Session, before: date) -> date | None:
    """직전 영업일 조회 (daily_ohlcv에 데이터가 있는 마지막 날짜)"""
    result = session.execute(
        select(func.max(DailyOhlcv.trade_date)).where(DailyOhlcv.trade_date < before)
    ).scalar_one_or_none()
    return result


def get_latest_trade_date(session: Session) -> date | None:
    """수집된 NPS 매매 데이터 중 가장 최근 날짜"""
    return session.execute(
        select(func.max(NpsDailyTrade.trade_date))
    ).scalar_one_or_none()


def get_latest_ohlcv_date(session: Session) -> date | None:
    """수집된 OHLCV 데이터 중 가장 최근 날짜 (종가 기준일)"""
    return session.execute(
        select(func.max(DailyOhlcv.trade_date))
    ).scalar_one_or_none()


def get_nps_daily_summary(
    session: Session,
    trade_date: date,
    limit: int,
    market: str | None,
) -> NpsDailySummaryResponse | None:
    """
    특정 일자의 연기금 순매수 상위 종목 조회.
    종가는 최신 OHLCV 날짜(D-day) 기준 — NPS 데이터는 T+1 공표되므로
    trade_date보다 최신 OHLCV가 있을 수 있다.
    """
    # 최신 OHLCV 날짜 (종가 기준일 — D-day)
    latest_ohlcv_date: date = session.execute(
        select(func.max(DailyOhlcv.trade_date))
    ).scalar_one() or trade_date

    # 전일 영업일 (등락률 계산용 — latest_ohlcv_date 기준 직전 영업일)
    prev_date = _get_prev_trading_date(session, latest_ohlcv_date)

    # 메인 쿼리: NPS 매매 + 종목 정보 + 최신 OHLCV 종가
    # TimescaleDB 청크 프루닝: WHERE trade_date = :date 조건 필수
    base_query = (
        select(
            NpsDailyTrade.ticker,
            NpsDailyTrade.net_buy_amount,
            NpsDailyTrade.net_buy_volume,
            NpsDailyTrade.consecutive_buy_days,
            NpsDailyTrade.buy_intensity_pct,
            Stock.name,
            Stock.market,
            DailyOhlcv.close,
        )
        .join(Stock, NpsDailyTrade.ticker == Stock.ticker)
        .outerjoin(
            DailyOhlcv,
            (NpsDailyTrade.ticker == DailyOhlcv.ticker)
            & (DailyOhlcv.trade_date == latest_ohlcv_date),
        )
        .where(NpsDailyTrade.trade_date == trade_date)
    )

    if market:
        base_query = base_query.where(Stock.market == market)

    rows = session.execute(
        base_query.order_by(NpsDailyTrade.net_buy_amount.desc()).limit(limit)
    ).all()

    if not rows:
        return None

    # 전일 종가 맵 (등락률 계산)
    prev_close_map: dict[str, int] = {}
    if prev_date:
        tickers = [r.ticker for r in rows]
        prev_ohlcv = session.execute(
            select(DailyOhlcv.ticker, DailyOhlcv.close)
            .where(DailyOhlcv.ticker.in_(tickers))
            .where(DailyOhlcv.trade_date == prev_date)
        ).all()
        prev_close_map = {r.ticker: r.close for r in prev_ohlcv}

    # 요약 통계 (전체 - limit 제한 없이)
    summary = session.execute(
        select(
            func.sum(NpsDailyTrade.net_buy_amount).label("total"),
            func.count(NpsDailyTrade.ticker.distinct()).label("total_count"),
            func.count(
                case((NpsDailyTrade.net_buy_amount > 0, 1), else_=None)
            ).label("buy_count"),
        ).where(NpsDailyTrade.trade_date == trade_date)
    ).one()

    total_amount = int(summary.total or 0)
    total_count = int(summary.total_count or 0)
    buy_count = int(summary.buy_count or 0)

    items = []
    for rank, row in enumerate(rows, 1):
        prev_close = prev_close_map.get(row.ticker)
        change_pct: float | None = None
        if prev_close and prev_close > 0 and row.close:
            change_pct = round((row.close - prev_close) / prev_close * 100, 2)

        items.append(
            NpsTopTradeItem(
                rank=rank,
                ticker=row.ticker,
                name=row.name,
                market=row.market,
                close=row.close,
                change_pct=change_pct,
                net_buy_amount=int(row.net_buy_amount),
                net_buy_volume=int(row.net_buy_volume),
                consecutive_buy_days=row.consecutive_buy_days,
                buy_intensity_pct=row.buy_intensity_pct,
            )
        )

    return NpsDailySummaryResponse(
        trade_date=trade_date,
        close_date=latest_ohlcv_date,
        total_net_buy_amount=total_amount,
        net_buy_count=buy_count,
        net_sell_count=total_count - buy_count,
        items=items,
    )


def get_nps_trade_timeseries(
    session: Session,
    ticker: str,
    from_date: date,
    to_date: date,
) -> NpsTradeTimeSeriesResponse | None:
    """
    특정 종목의 NPS 매매 시계열 조회.
    TimescaleDB 청크 프루닝을 위해 반드시 날짜 범위 조건 포함.
    """
    stock = session.get(Stock, ticker)
    if not stock:
        return None

    rows = session.execute(
        select(
            NpsDailyTrade.trade_date,
            NpsDailyTrade.net_buy_amount,
            NpsDailyTrade.net_buy_volume,
            NpsDailyTrade.consecutive_buy_days,
            NpsDailyTrade.buy_intensity_pct,
            DailyOhlcv.close,
        )
        .outerjoin(
            DailyOhlcv,
            (NpsDailyTrade.ticker == DailyOhlcv.ticker)
            & (NpsDailyTrade.trade_date == DailyOhlcv.trade_date),
        )
        .where(NpsDailyTrade.ticker == ticker)
        .where(NpsDailyTrade.trade_date >= from_date)
        .where(NpsDailyTrade.trade_date <= to_date)
        .order_by(NpsDailyTrade.trade_date.desc())
    ).all()

    # 전일 종가 맵 (등락률 계산)
    ohlcv_all = session.execute(
        select(DailyOhlcv.trade_date, DailyOhlcv.close)
        .where(DailyOhlcv.ticker == ticker)
        .where(DailyOhlcv.trade_date >= from_date - timedelta(days=5))
        .where(DailyOhlcv.trade_date <= to_date)
        .order_by(DailyOhlcv.trade_date)
    ).all()

    close_by_date = {r.trade_date: r.close for r in ohlcv_all}
    sorted_dates = sorted(close_by_date.keys())

    def prev_close(d: date) -> int | None:
        idx = sorted_dates.index(d) if d in sorted_dates else -1
        return close_by_date.get(sorted_dates[idx - 1]) if idx > 0 else None

    items = []
    for row in rows:
        pc = prev_close(row.trade_date)
        change_pct = None
        if pc and pc > 0 and row.close:
            change_pct = round((row.close - pc) / pc * 100, 2)

        items.append(
            NpsTradeTimeSeriesItem(
                trade_date=row.trade_date,
                net_buy_amount=int(row.net_buy_amount),
                net_buy_volume=int(row.net_buy_volume),
                consecutive_buy_days=row.consecutive_buy_days,
                buy_intensity_pct=row.buy_intensity_pct,
                close=row.close,
                change_pct=change_pct,
            )
        )

    return NpsTradeTimeSeriesResponse(ticker=ticker, name=stock.name, items=items)


def get_nps_holdings(session: Session, ticker: str) -> NpsHoldingsResponse | None:
    """특정 종목의 NPS 5% 이상 보유 공시 이력"""
    stock = session.get(Stock, ticker)
    if not stock:
        return None

    holdings = session.execute(
        select(NpsHolding)
        .where(NpsHolding.ticker == ticker)
        .order_by(NpsHolding.report_date.desc())
    ).scalars().all()

    return NpsHoldingsResponse(
        ticker=ticker,
        name=stock.name,
        items=[NpsHoldingItem.model_validate(h) for h in holdings],
    )
