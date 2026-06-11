import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger
from sqlalchemy import MetaData, Table, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.session import get_session
from scrapers.backfill import save_daily_ohlcv, sync_stock_master
from scrapers.investor_krx_scraper import fetch_all_investor_daily_trades

KST = ZoneInfo("Asia/Seoul")


def _get_weekdays(from_date: date, to_date: date) -> list[date]:
    days: list[date] = []
    current = from_date

    while current <= to_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)

    return days


def _load_table(session, table_name: str) -> Table:
    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=session.bind)


def _already_collected(session, job_type: str, target_date: date) -> bool:
    result = session.execute(
        text(
            """
            SELECT 1
            FROM investor_collection_logs
            WHERE job_type = :job_type
              AND target_date = :target_date
              AND status = 'success'
            """
        ),
        {
            "job_type": job_type,
            "target_date": target_date,
        },
    ).first()

    return result is not None


def _log_collection(
    session,
    job_type: str,
    target_date: date,
    status: str,
    rows_inserted: int,
    started_at: datetime,
    error_message: str | None = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO investor_collection_logs
            (
                job_type,
                target_date,
                status,
                rows_inserted,
                error_message,
                started_at,
                completed_at
            )
            VALUES
            (
                :job_type,
                :target_date,
                :status,
                :rows_inserted,
                :error_message,
                :started_at,
                :completed_at
            )
            ON CONFLICT (job_type, target_date)
            DO UPDATE SET
                status = EXCLUDED.status,
                rows_inserted = EXCLUDED.rows_inserted,
                error_message = EXCLUDED.error_message,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at
            """
        ),
        {
            "job_type": job_type,
            "target_date": target_date,
            "status": status,
            "rows_inserted": rows_inserted,
            "error_message": error_message,
            "started_at": started_at,
            "completed_at": datetime.now(KST),
        },
    )


def save_investor_daily_trades(session, target_date: date) -> int:
    """
    투자자별 일별 순매수 데이터를 investor_daily_trades에 저장.
    기존 nps_daily_trades는 건드리지 않음.
    """
    started_at = datetime.now(KST)
    job_type = "investor_daily_trades"

    if _already_collected(session, job_type, target_date):
        logger.info(f"이미 수집 완료된 날짜라 건너뜀: {target_date}")
        return 0

    df = fetch_all_investor_daily_trades(target_date)

    if df.empty:
        _log_collection(
            session=session,
            job_type=job_type,
            target_date=target_date,
            status="success",
            rows_inserted=0,
            started_at=started_at,
        )
        return 0

    now = datetime.now(KST)

    records = [
        {
            "trade_date": target_date,
            "ticker": row["ticker"],
            "investor_type": row["investor_type"],
            "investor_name": row["investor_name"],
            "net_buy_volume": int(row["net_buy_volume"]),
            "net_buy_amount": int(row["net_buy_amount"]),
            "consecutive_buy_days": 0,
            "buy_intensity_pct": None,
            "buy_amount_per_price": None,
            "created_at": now,
            "updated_at": now,
        }
        for _, row in df.iterrows()
    ]

    table = _load_table(session, "investor_daily_trades")

    stmt = pg_insert(table).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["trade_date", "ticker", "investor_type"],
        set_={
            "investor_name": stmt.excluded.investor_name,
            "net_buy_volume": stmt.excluded.net_buy_volume,
            "net_buy_amount": stmt.excluded.net_buy_amount,
            "updated_at": now,
        },
    )

    session.execute(stmt)

    _log_collection(
        session=session,
        job_type=job_type,
        target_date=target_date,
        status="success",
        rows_inserted=len(records),
        started_at=started_at,
    )

    logger.info(f"투자자 수급 저장 완료: {target_date}, {len(records)}행")

    return len(records)


def recalculate_investor_signals_bulk(session) -> None:
    """
    전체 기간 기준으로 투자자별 연속매수일, 매수강도 재계산.

    consecutive_buy_days:
        ticker + investor_type 기준으로 순매수량 > 0이면 누적, 아니면 0

    buy_intensity_pct:
        순매수금액 / 시가총액 * 100

    buy_amount_per_price:
        순매수금액 / 종가
    """
    logger.info("투자자별 시그널 전체 재계산 시작")

    trade_df = pd.read_sql(
        """
        SELECT
            trade_date,
            ticker,
            investor_type,
            net_buy_volume,
            net_buy_amount
        FROM investor_daily_trades
        ORDER BY ticker, investor_type, trade_date
        """,
        session.bind,
        parse_dates=["trade_date"],
    )

    if trade_df.empty:
        logger.info("재계산 대상 데이터 없음")
        return

    ohlcv_df = pd.read_sql(
        """
        SELECT
            trade_date,
            ticker,
            close,
            market_cap
        FROM daily_ohlcv
        ORDER BY ticker, trade_date
        """,
        session.bind,
        parse_dates=["trade_date"],
    )

    def calc_consecutive(series: pd.Series) -> pd.Series:
        count = 0
        result = []

        for value in series:
            if value > 0:
                count += 1
            else:
                count = 0
            result.append(count)

        return pd.Series(result, index=series.index)

    trade_df["consecutive_buy_days"] = (
        trade_df.groupby(["ticker", "investor_type"])["net_buy_volume"]
        .transform(calc_consecutive)
        .astype(int)
    )

    merged = trade_df.merge(
        ohlcv_df,
        on=["trade_date", "ticker"],
        how="left",
    )

    merged["buy_intensity_pct"] = merged.apply(
        lambda r: float(r["net_buy_amount"]) / float(r["market_cap"]) * 100
        if pd.notna(r["market_cap"]) and r["market_cap"] > 0
        else None,
        axis=1,
    )

    merged["buy_amount_per_price"] = merged.apply(
        lambda r: float(r["net_buy_amount"]) / float(r["close"])
        if pd.notna(r["close"]) and r["close"] > 0
        else None,
        axis=1,
    )

    update_rows = merged[
        [
            "trade_date",
            "ticker",
            "investor_type",
            "consecutive_buy_days",
            "buy_intensity_pct",
            "buy_amount_per_price",
        ]
    ].to_dict("records")

    for row in update_rows:
        session.execute(
            text(
                """
                UPDATE investor_daily_trades
                SET
                    consecutive_buy_days = :consecutive_buy_days,
                    buy_intensity_pct = :buy_intensity_pct,
                    buy_amount_per_price = :buy_amount_per_price,
                    updated_at = NOW()
                WHERE trade_date = :trade_date
                  AND ticker = :ticker
                  AND investor_type = :investor_type
                """
            ),
            row,
        )

    logger.info(f"투자자별 시그널 재계산 완료: {len(update_rows)}행")


def collect_for_date(target_date: date, recalculate: bool = True) -> None:
    logger.info(f"투자자별 수급 수집 시작: {target_date}")

    with get_session() as session:
        sync_stock_master(session)

    with get_session() as session:
        save_daily_ohlcv(session, target_date)

    with get_session() as session:
        save_investor_daily_trades(session, target_date)

    if recalculate:
        with get_session() as session:
            recalculate_investor_signals_bulk(session)

    logger.info(f"투자자별 수급 수집 완료: {target_date}")


def run_backfill(
    from_date: date,
    to_date: date,
    skip_recalculate: bool = False,
) -> None:
    trading_days = _get_weekdays(from_date, to_date)
    logger.info(f"투자자별 백필 시작: {from_date} ~ {to_date}, {len(trading_days)}일")

    with get_session() as session:
        sync_stock_master(session)

    success_count = 0
    failed_dates: list[date] = []

    for idx, target_date in enumerate(trading_days, 1):
        logger.info(f"[{idx}/{len(trading_days)}] 수집 중: {target_date}")

        try:
            with get_session() as session:
                save_daily_ohlcv(session, target_date)
                rows = save_investor_daily_trades(session, target_date)
                success_count += rows

        except Exception as e:
            logger.error(f"투자자별 수급 백필 실패: {target_date}, error={e}")
            failed_dates.append(target_date)

    logger.info(f"투자자별 백필 수집 완료: {success_count}행 저장")

    if failed_dates:
        logger.warning(f"실패 날짜: {failed_dates}")

    if not skip_recalculate:
        with get_session() as session:
            recalculate_investor_signals_bulk(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="투자자별 수급 데이터 수집기")

    parser.add_argument("--date", help="특정 날짜 수집 YYYY-MM-DD")
    parser.add_argument("--from", dest="from_date", help="시작 날짜 YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", help="종료 날짜 YYYY-MM-DD")
    parser.add_argument(
        "--skip-recalculate",
        action="store_true",
        help="연속매수일/매수강도 재계산 생략",
    )

    args = parser.parse_args()

    if args.date:
        target_date = date.fromisoformat(args.date)
        collect_for_date(
            target_date=target_date,
            recalculate=not args.skip_recalculate,
        )
        return

    if args.from_date:
        from_date = date.fromisoformat(args.from_date)
        to_date = date.fromisoformat(args.to_date) if args.to_date else date.today()

        run_backfill(
            from_date=from_date,
            to_date=to_date,
            skip_recalculate=args.skip_recalculate,
        )
        return

    raise ValueError("--date 또는 --from 옵션이 필요합니다.")


if __name__ == "__main__":
    main()