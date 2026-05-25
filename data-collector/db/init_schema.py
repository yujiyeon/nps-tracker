"""
TimescaleDB 스키마 초기화 스크립트 - 최초 1회 실행.

실행 방법:
    cd data-collector
    python -m db.init_schema
"""
import sys

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from db.models import Base
from db.session import engine


def _enable_timescaledb() -> None:
    """TimescaleDB 확장 활성화 (docker/init-db.sql에서 이미 처리되지만 안전하게 재시도)"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.commit()
    logger.info("TimescaleDB 확장 활성화 완료")


def _create_hypertables() -> None:
    """daily_ohlcv, nps_daily_trades를 TimescaleDB hypertable로 변환"""
    hypertable_cmds = [
        (
            "daily_ohlcv",
            """
            SELECT create_hypertable(
                'daily_ohlcv', 'trade_date',
                chunk_time_interval => INTERVAL '1 month',
                if_not_exists => TRUE
            )
            """,
        ),
        (
            "nps_daily_trades",
            """
            SELECT create_hypertable(
                'nps_daily_trades', 'trade_date',
                chunk_time_interval => INTERVAL '1 month',
                if_not_exists => TRUE
            )
            """,
        ),
    ]

    with engine.connect() as conn:
        for table_name, sql in hypertable_cmds:
            conn.execute(text(sql))
            conn.commit()
            logger.info(f"hypertable 생성 완료: {table_name}")


def _set_compression_policies() -> None:
    """3개월 이상 청크 자동 압축 (디스크 70% 절감 효과, segmentby=ticker로 종목별 조회 가속)"""
    compression_cmds = [
        # daily_ohlcv
        """
        ALTER TABLE daily_ohlcv SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'ticker'
        )
        """,
        "SELECT add_compression_policy('daily_ohlcv', INTERVAL '3 months', if_not_exists => TRUE)",
        # nps_daily_trades
        """
        ALTER TABLE nps_daily_trades SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'ticker'
        )
        """,
        "SELECT add_compression_policy('nps_daily_trades', INTERVAL '3 months', if_not_exists => TRUE)",
    ]

    with engine.connect() as conn:
        for sql in compression_cmds:
            try:
                conn.execute(text(sql))
                conn.commit()
            except (ProgrammingError, OperationalError) as e:
                # 이미 설정된 경우 무시 (재실행 시 정상)
                logger.warning(f"압축 정책 설정 건너뜀 (이미 설정됐을 수 있음): {e}")
                conn.rollback()

    logger.info("TimescaleDB 압축 정책 설정 완료")


def _create_indexes() -> None:
    """쿼리 패턴에 최적화된 인덱스 생성"""
    index_cmds = [
        # 메인 화면: "특정 일자의 순매수 상위 종목"
        """
        CREATE INDEX IF NOT EXISTS idx_nps_date_amount
        ON nps_daily_trades (trade_date, net_buy_amount DESC)
        """,
        # 종목 상세 화면: "특정 종목의 NPS 매매 시계열"
        """
        CREATE INDEX IF NOT EXISTS idx_nps_ticker_date
        ON nps_daily_trades (ticker, trade_date)
        """,
        # 종목 상세 화면: "특정 종목의 OHLCV 시계열"
        """
        CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date
        ON daily_ohlcv (ticker, trade_date)
        """,
        # 수집 로그에서 날짜/타입으로 조회
        """
        CREATE INDEX IF NOT EXISTS idx_collection_logs_date_type
        ON collection_logs (target_date, job_type)
        """,
    ]

    with engine.connect() as conn:
        for sql in index_cmds:
            conn.execute(text(sql))
            conn.commit()

    logger.info("인덱스 생성 완료")


def init_schema() -> None:
    """전체 스키마 초기화 (순서 중요: extensions → tables → hypertables → indexes)"""
    logger.info("스키마 초기화 시작")

    _enable_timescaledb()

    # SQLAlchemy ORM 정의 기반 테이블 생성
    Base.metadata.create_all(engine)
    logger.info("테이블 생성 완료")

    _create_hypertables()
    _set_compression_policies()
    _create_indexes()

    logger.info("스키마 초기화 완료")


if __name__ == "__main__":
    init_schema()
    logger.info("✓ 스키마 초기화 성공")
    sys.exit(0)
