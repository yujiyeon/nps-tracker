"""
일별 자동 수집 스케줄러.

매일 18:00 KST에 당일 데이터를 수집한다.
장 마감(15:30) 후 KRX 데이터 확정까지 충분한 여유를 두고 실행.

실행 방법:
    cd data-collector
    python -m scrapers.daily_runner          # 스케줄러 상시 가동
    python -m scrapers.daily_runner --now    # 즉시 1회 실행 (수동 트리거)
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from config import settings
from db.models import DailyOhlcv, NpsDailyTrade
from db.session import get_session
from scrapers.backfill import (
    recalculate_signals_bulk,
    save_daily_ohlcv,
    save_nps_daily_trades,
    sync_stock_master,
)

KST = ZoneInfo("Asia/Seoul")

# KRX는 장 마감(15:30) 후 T+1에 데이터를 확정 공개
# 07:00 KST 실행 → 전 영업일 데이터 수집
COLLECTION_HOUR = 7
COLLECTION_MINUTE = 0


def get_previous_trading_day(base_date: date) -> date:
    """전 영업일 반환. 주말은 금요일로 스킵 (공휴일은 pykrx가 빈 응답으로 처리)."""
    prev = base_date - timedelta(days=1)
    while prev.weekday() >= 5:  # 5=토, 6=일
        prev -= timedelta(days=1)
    return prev


def recalculate_signals_for_date(session: Session, target_date: date) -> None:
    """
    특정 일자의 연속 매수일(consecutive_buy_days)과 매수 강도(buy_intensity_pct) 갱신.
    해당 날짜에 NPS 매매 기록이 있는 종목만 처리.
    """
    # 오늘 NPS 매매가 있는 종목 조회
    today_tickers: list[str] = list(
        session.execute(
            select(NpsDailyTrade.ticker).where(NpsDailyTrade.trade_date == target_date)
        ).scalars()
    )

    if not today_tickers:
        return

    for ticker in today_tickers:
        # 최근 100일 순매수량 조회 (연속 매수일 계산용)
        recent_volumes: list[int] = list(
            session.execute(
                select(NpsDailyTrade.net_buy_volume)
                .where(
                    NpsDailyTrade.ticker == ticker,
                    NpsDailyTrade.trade_date <= target_date,
                )
                .order_by(NpsDailyTrade.trade_date.desc())
                .limit(100)
            ).scalars()
        )

        # 현재 날짜부터 역순으로 연속 매수일 카운트
        consecutive = 0
        for volume in recent_volumes:
            if volume > 0:
                consecutive += 1
            else:
                break

        # 매수 강도: 순매수금액 / 시가총액 * 100
        buy_intensity: float | None = None
        trade = session.execute(
            select(NpsDailyTrade).where(
                NpsDailyTrade.trade_date == target_date,
                NpsDailyTrade.ticker == ticker,
            )
        ).scalar_one_or_none()

        ohlcv = session.get(DailyOhlcv, (target_date, ticker))
        if trade and ohlcv and ohlcv.market_cap and ohlcv.market_cap > 0:
            buy_intensity = trade.net_buy_amount / ohlcv.market_cap * 100

        if trade:
            trade.consecutive_buy_days = consecutive
            trade.buy_intensity_pct = buy_intensity

    session.flush()
    logger.debug(f"시그널 지표 갱신 완료: {target_date}, {len(today_tickers)}개 종목")


def collect_for_date(target_date: date) -> None:
    """
    특정 날짜의 전체 수집 파이프라인 실행.
    순서: 종목 마스터 동기화 → OHLCV → NPS 매매 → 시그널 재계산
    """
    logger.info(f"=== 일별 수집 시작: {target_date} ===")

    # 1. 종목 마스터 갱신 (신규 상장/폐지 추적)
    with get_session() as session:
        sync_stock_master(session)

    # 2. OHLCV 수집
    with get_session() as session:
        ohlcv_rows = save_daily_ohlcv(session, target_date)
        logger.info(f"OHLCV 저장: {ohlcv_rows}행")

    # 3. NPS 매매 수집
    with get_session() as session:
        nps_rows = save_nps_daily_trades(session, target_date)
        logger.info(f"NPS 매매 저장: {nps_rows}행")

    # 4. 시그널 지표 재계산 (연속 매수일, 매수 강도)
    if ohlcv_rows > 0 or nps_rows > 0:
        with get_session() as session:
            recalculate_signals_for_date(session, target_date)

    logger.info(f"=== 일별 수집 완료: {target_date} ===")


def run_scheduled_collection() -> None:
    """
    스케줄러에서 호출되는 진입점.
    07:00 KST 실행 → 전 영업일 데이터 수집 (T+1 기준).
    """
    today = datetime.now(KST).date()
    target = get_previous_trading_day(today)
    logger.info(f"스케줄 수집 대상: {target} (실행일: {today})")
    collect_for_date(target)


def _configure_logging() -> None:
    """loguru 설정: JSON 구조화 로그"""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        serialize=False,  # 콘솔 출력은 사람이 읽기 좋게
    )
    logger.add(
        str(log_dir / "collector_{time:YYYY-MM-DD}.log"),
        level=settings.log_level,
        rotation="00:00",  # 자정에 로그 파일 교체
        retention="30 days",
        serialize=True,  # 파일은 JSON 구조화 로그
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="NPS Tracker 일별 자동 수집")
    parser.add_argument(
        "--now",
        action="store_true",
        help="스케줄러 없이 즉시 1회 실행 (수동 트리거)",
    )
    parser.add_argument(
        "--date",
        help="특정 날짜 수집 YYYY-MM-DD (--now와 함께 사용)",
    )
    args = parser.parse_args()

    _configure_logging()

    if args.now:
        if args.date:
            target = date.fromisoformat(args.date)
        else:
            target = get_previous_trading_day(datetime.now(KST).date())
        logger.info(f"수동 실행: {target}")
        collect_for_date(target)
        return

    # 스케줄러 상시 가동
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_scheduled_collection,
        trigger=CronTrigger(
            hour=COLLECTION_HOUR,
            minute=COLLECTION_MINUTE,
            timezone="Asia/Seoul",
        ),
        id="daily_collection",
        name="일별 NPS 매매 수집",
        misfire_grace_time=3600,  # 1시간 내 지연 실행 허용
        coalesce=True,  # 밀린 실행은 1회만
    )

    logger.info(f"스케줄러 시작: 매일 {COLLECTION_HOUR:02d}:{COLLECTION_MINUTE:02d} KST — 전 영업일 데이터 수집")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


if __name__ == "__main__":
    main()
