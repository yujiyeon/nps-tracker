"""
과거 데이터 백필 스크립트.

실행 방법:
    cd data-collector
    python -m scrapers.backfill --years 5          # 최근 5년치
    python -m scrapers.backfill --from 2020-01-01 --to 2024-12-31  # 특정 기간

특징:
    - collection_logs를 체크해 이미 수집된 날짜는 건너뜀 (중단 후 재개 가능)
    - 영업일이 아닌 날짜 (주말/공휴일)는 빈 데이터 반환으로 자동 감지
    - 부분 실패 허용: 특정 날짜 실패해도 나머지 계속 진행
"""
import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.models import CollectionLog, DailyOhlcv, NpsDailyTrade, Stock
from db.session import get_session
from scrapers.krx_scraper import (
    fetch_daily_ohlcv,
    fetch_nps_daily_trades,
    fetch_stock_master,
)

KST = ZoneInfo("Asia/Seoul")


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────


def _get_weekdays(from_date: date, to_date: date) -> list[date]:
    """주말 제외 영업일 목록 (한국 공휴일은 실제 수집 시 빈 데이터로 감지)"""
    days: list[date] = []
    current = from_date
    while current <= to_date:
        if current.weekday() < 5:  # 월(0) ~ 금(4)
            days.append(current)
        current += timedelta(days=1)
    return days


def _already_collected(session: Session, job_type: str, target_date: date) -> bool:
    """해당 날짜/타입의 수집이 이미 성공적으로 완료됐는지 확인"""
    result = session.execute(
        select(CollectionLog).where(
            CollectionLog.job_type == job_type,
            CollectionLog.target_date == target_date,
            CollectionLog.status == "success",
        )
    ).scalar_one_or_none()
    return result is not None


def _log_collection(
    session: Session,
    job_type: str,
    target_date: date,
    status: str,
    rows_inserted: int,
    started_at: datetime,
    error_message: str | None = None,
) -> None:
    """수집 작업 결과를 collection_logs에 기록"""
    log = CollectionLog(
        job_type=job_type,
        target_date=target_date,
        status=status,
        rows_inserted=rows_inserted,
        error_message=error_message,
        started_at=started_at,
        completed_at=datetime.now(KST),
    )
    session.add(log)


# ──────────────────────────────────────────────
# 종목 마스터 저장
# ──────────────────────────────────────────────


def sync_stock_master(session: Session) -> int:
    """KRX 현재 상장 종목 마스터를 DB에 upsert"""
    df = fetch_stock_master()
    if df.empty:
        return 0

    records = df.to_dict("records")
    stmt = pg_insert(Stock).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_={
            "name": stmt.excluded.name,
            "market": stmt.excluded.market,
            "is_active": True,
        },
    )
    session.execute(stmt)
    logger.info(f"종목 마스터 업서트 완료: {len(records)}개")
    return len(records)


# ──────────────────────────────────────────────
# OHLCV 저장
# ──────────────────────────────────────────────


def save_daily_ohlcv(session: Session, target_date: date) -> int:
    """
    특정 일자 OHLCV를 DB에 upsert.
    멱등성 보장: 같은 날짜 재실행해도 결과 동일.
    """
    started_at = datetime.now(KST)
    job_type = "ohlcv"

    if _already_collected(session, job_type, target_date):
        logger.debug(f"OHLCV 이미 수집됨, 건너뜀: {target_date}")
        return 0

    df = fetch_daily_ohlcv(target_date)
    if df.empty:
        # 휴장일 → success로 기록해 다음 실행 시 재시도 방지
        _log_collection(session, job_type, target_date, "success", 0, started_at)
        return 0

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "trade_date": target_date,
                "ticker": row["ticker"],
                "open": int(row["open"]),
                "high": int(row["high"]),
                "low": int(row["low"]),
                "close": int(row["close"]),
                "volume": int(row["volume"]),
                "trading_value": int(row["trading_value"]),
                "market_cap": row.get("market_cap"),
                "shares_outstanding": row.get("shares_outstanding"),
            }
        )

    stmt = pg_insert(DailyOhlcv).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["trade_date", "ticker"],
        set_={
            col: stmt.excluded[col]
            for col in ["open", "high", "low", "close", "volume", "trading_value", "market_cap", "shares_outstanding"]
        },
    )
    session.execute(stmt)

    _log_collection(session, job_type, target_date, "success", len(records), started_at)
    return len(records)


# ──────────────────────────────────────────────
# NPS 매매 저장
# ──────────────────────────────────────────────


def save_nps_daily_trades(session: Session, target_date: date) -> int:
    """
    특정 일자 연기금 순매수를 DB에 upsert.
    멱등성 보장: 같은 날짜 재실행해도 결과 동일.
    """
    started_at = datetime.now(KST)
    job_type = "daily_trades"

    if _already_collected(session, job_type, target_date):
        logger.debug(f"연기금 매매 이미 수집됨, 건너뜀: {target_date}")
        return 0

    df = fetch_nps_daily_trades(target_date)
    if df.empty:
        _log_collection(session, job_type, target_date, "success", 0, started_at)
        return 0

    now = datetime.now(KST)
    records = [
        {
            "trade_date": target_date,
            "ticker": row["ticker"],
            "net_buy_volume": int(row["net_buy_volume"]),
            "net_buy_amount": int(row["net_buy_amount"]),
            "consecutive_buy_days": 0,  # recalculate_signals에서 갱신
            "buy_intensity_pct": None,   # recalculate_signals에서 갱신
            "created_at": now,
        }
        for _, row in df.iterrows()
    ]

    stmt = pg_insert(NpsDailyTrade).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["trade_date", "ticker"],
        set_={
            "net_buy_volume": stmt.excluded.net_buy_volume,
            "net_buy_amount": stmt.excluded.net_buy_amount,
        },
    )
    session.execute(stmt)

    _log_collection(session, job_type, target_date, "success", len(records), started_at)
    return len(records)


# ──────────────────────────────────────────────
# 시그널 지표 재계산
# ──────────────────────────────────────────────


def recalculate_signals_bulk(session: Session) -> None:
    """
    전체 기간 consecutive_buy_days, buy_intensity_pct 일괄 재계산.
    백필 완료 후 1회 실행 권장.
    """
    logger.info("시그널 지표 재계산 시작 (전체 기간)")

    # 전체 NPS 매매 + OHLCV를 메모리에 로드해 pandas로 계산
    nps_df = pd.read_sql(
        "SELECT trade_date, ticker, net_buy_volume, net_buy_amount "
        "FROM nps_daily_trades ORDER BY ticker, trade_date",
        session.bind,
        parse_dates=["trade_date"],
    )
    ohlcv_df = pd.read_sql(
        "SELECT trade_date, ticker, market_cap "
        "FROM daily_ohlcv WHERE market_cap IS NOT NULL "
        "ORDER BY ticker, trade_date",
        session.bind,
        parse_dates=["trade_date"],
    )

    # 연속 매수일 계산 (gaps-and-islands)
    def calc_consecutive(group: pd.Series) -> pd.Series:
        """순방향으로 누적 - 순매도(≤0) 시 리셋"""
        result = []
        count = 0
        for val in group:
            count = count + 1 if val > 0 else 0
            result.append(count)
        return pd.Series(result, index=group.index)

    nps_df["consecutive_buy_days"] = (
        nps_df.groupby("ticker")["net_buy_volume"]
        .transform(calc_consecutive)
        .astype(int)
    )

    # 매수 강도 계산: 순매수금액 / 시총 * 100
    merged = nps_df.merge(
        ohlcv_df[["trade_date", "ticker", "market_cap"]],
        on=["trade_date", "ticker"],
        how="left",
    )
    merged["buy_intensity_pct"] = merged.apply(
        lambda r: float(r["net_buy_amount"]) / float(r["market_cap"]) * 100
        if pd.notna(r["market_cap"]) and r["market_cap"] > 0
        else None,
        axis=1,
    )

    # 임시 테이블에 적재 후 UPDATE ... FROM으로 일괄 갱신
    # (TimescaleDB hypertable에서 bulk_update_mappings의 rowcount 불일치 회피)
    update_df = merged[["trade_date", "ticker", "consecutive_buy_days", "buy_intensity_pct"]].copy()
    update_df["trade_date"] = update_df["trade_date"].dt.date
    update_df.to_sql("_signal_temp", session.bind, if_exists="replace", index=False)

    # TimescaleDB 압축 청크 DML 제한 해제 (기본 100,000행, 전체 기간 업데이트 시 초과)
    session.execute(text("SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0"))
    session.execute(text("""
        UPDATE nps_daily_trades t
        SET consecutive_buy_days = s.consecutive_buy_days,
            buy_intensity_pct    = s.buy_intensity_pct
        FROM _signal_temp s
        WHERE t.trade_date = s.trade_date
          AND t.ticker     = s.ticker
    """))
    session.execute(text("DROP TABLE IF EXISTS _signal_temp"))
    session.flush()

    logger.info(f"시그널 지표 재계산 완료: {len(update_df)}행 갱신")


# ──────────────────────────────────────────────
# 메인 백필 루프
# ──────────────────────────────────────────────


def run_backfill(from_date: date, to_date: date, skip_recalculate: bool = False) -> None:
    """
    지정 기간의 OHLCV + NPS 매매 데이터 순차 수집.

    collection_logs 기반으로 이미 수집된 날짜는 건너뛰므로
    중단 후 재시작해도 안전.
    """
    trading_days = _get_weekdays(from_date, to_date)
    total = len(trading_days)
    logger.info(f"백필 시작: {from_date} ~ {to_date}, 영업일 후보 {total}일")

    # 종목 마스터 먼저 동기화
    with get_session() as session:
        sync_stock_master(session)

    ohlcv_count = 0
    nps_count = 0
    failed_dates: list[date] = []

    for idx, target_date in enumerate(trading_days, 1):
        if idx % 20 == 0 or idx == total:
            logger.info(f"진행 중: {idx}/{total} ({target_date})")

        try:
            with get_session() as session:
                rows_ohlcv = save_daily_ohlcv(session, target_date)
                rows_nps = save_nps_daily_trades(session, target_date)
                ohlcv_count += rows_ohlcv
                nps_count += rows_nps

        except Exception as e:
            logger.error(f"백필 실패 ({target_date}): {e}")
            failed_dates.append(target_date)
            # 부분 실패 허용 - 다음 날짜 계속 진행
            continue

    logger.info(
        f"백필 수집 완료: OHLCV {ohlcv_count}행, NPS {nps_count}행, "
        f"실패 {len(failed_dates)}일"
    )

    if failed_dates:
        logger.warning(f"실패한 날짜 목록: {failed_dates}")

    # 연속 매수일 / 매수 강도 일괄 재계산
    if not skip_recalculate:
        logger.info("시그널 지표 재계산 중 (백필 후 1회)...")
        with get_session() as session:
            recalculate_signals_bulk(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="NPS Tracker 과거 데이터 백필")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--years", type=int, help="오늘 기준 N년 전부터 수집 (예: --years 5)")
    group.add_argument("--from", dest="from_date", help="시작 날짜 YYYY-MM-DD")

    parser.add_argument("--to", dest="to_date", help="종료 날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument(
        "--skip-recalculate",
        action="store_true",
        help="시그널 지표 재계산 건너뜀",
    )
    args = parser.parse_args()

    today = date.today()

    if args.years:
        from_date = date(today.year - args.years, today.month, today.day)
    elif args.from_date:
        from_date = date.fromisoformat(args.from_date)
    else:
        # 기본: 5년치
        from_date = date(today.year - 5, today.month, today.day)

    to_date = date.fromisoformat(args.to_date) if args.to_date else today

    run_backfill(from_date, to_date, skip_recalculate=args.skip_recalculate)


if __name__ == "__main__":
    main()
