"""
API 통합 테스트 픽스처.

nps_tracker_test DB를 사용하며, 각 테스트 세션 후 테이블을 정리합니다.
docker-compose의 db 서비스가 실행 중이어야 합니다.
"""
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 테스트 DB URL (환경변수 우선, 없으면 로컬 기본값)
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://nps_user:localdevpassword@localhost:5432/nps_tracker_test",
)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def setup_schema(test_engine):
    """테스트 세션 시작 시 스키마 생성, 종료 시 정리."""
    with test_engine.connect() as conn:
        # 이전 테스트 실행 잔류 데이터 정리
        for tbl in ["nps_holdings", "nps_daily_trades", "daily_ohlcv", "collection_logs", "stocks"]:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()

        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stocks (
                ticker VARCHAR(6) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                market VARCHAR(10) NOT NULL,
                sector VARCHAR(100),
                listing_date DATE,
                delisting_date DATE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_ohlcv (
                trade_date DATE NOT NULL,
                ticker VARCHAR(6) NOT NULL,
                open INTEGER NOT NULL,
                high INTEGER NOT NULL,
                low INTEGER NOT NULL,
                close INTEGER NOT NULL,
                volume BIGINT NOT NULL,
                trading_value BIGINT NOT NULL,
                market_cap BIGINT,
                shares_outstanding BIGINT,
                PRIMARY KEY (trade_date, ticker)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS nps_daily_trades (
                trade_date DATE NOT NULL,
                ticker VARCHAR(6) NOT NULL,
                net_buy_volume BIGINT NOT NULL,
                net_buy_amount BIGINT NOT NULL,
                consecutive_buy_days INTEGER NOT NULL DEFAULT 0,
                buy_intensity_pct DOUBLE PRECISION,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (trade_date, ticker)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS nps_holdings (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(6) NOT NULL,
                report_date DATE NOT NULL,
                filing_date DATE NOT NULL,
                shares BIGINT NOT NULL,
                holding_ratio DOUBLE PRECISION NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                rcept_no VARCHAR(20) UNIQUE NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS collection_logs (
                id SERIAL PRIMARY KEY,
                job_type VARCHAR(30) NOT NULL,
                target_date DATE NOT NULL,
                status VARCHAR(10) NOT NULL,
                rows_inserted INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ
            )
        """))
        conn.commit()

    yield

    # 세션 종료 시 테스트 데이터 정리
    with test_engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS nps_holdings CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS nps_daily_trades CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS daily_ohlcv CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS collection_logs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS stocks CASCADE"))
        conn.commit()


@pytest.fixture
def db_session(test_engine, setup_schema):
    """각 테스트마다 트랜잭션 롤백으로 격리."""
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient - DB 세션을 테스트용으로 오버라이드.

    시작 시 nps:daily:* 캐시를 비워 이전 프로덕션/테스트 캐시가 간섭하지 않게 한다.
    """
    import sys
    import redis as redis_lib
    sys.path.insert(0, "/Users/jisubhan/nps-tracker/api")

    from main import app
    from db.session import get_session

    # 테스트 전 NPS daily 캐시 초기화
    try:
        r = redis_lib.from_url("redis://localhost:6379/0", decode_responses=True)
        for key in r.keys("nps:daily:*"):
            r.delete(key)
    except Exception:
        pass  # Redis 미가동 시 무시

    def override_get_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db_session):
    """테스트용 최소 데이터 삽입."""
    today = date(2026, 5, 6)
    prev = date(2026, 5, 5)

    db_session.execute(text("""
        INSERT INTO stocks (ticker, name, market, is_active)
        VALUES
            ('005930', '삼성전자', 'KOSPI', TRUE),
            ('000660', 'SK하이닉스', 'KOSPI', TRUE),
            ('005380', '현대차', 'KOSPI', TRUE)
        ON CONFLICT DO NOTHING
    """))

    db_session.execute(text("""
        INSERT INTO daily_ohlcv (trade_date, ticker, open, high, low, close, volume, trading_value, market_cap)
        VALUES
            (:today, '005930', 60000, 62000, 59000, 61000, 10000000, 600000000000, 364000000000000),
            (:today, '000660', 120000, 125000, 119000, 122000, 5000000, 610000000000, 88000000000000),
            (:prev,  '005930', 59000, 61000, 58000, 60000, 9000000, 540000000000, 357000000000000),
            (:prev,  '000660', 118000, 121000, 117000, 120000, 4500000, 540000000000, 87000000000000)
    """), {"today": today, "prev": prev})

    db_session.execute(text("""
        INSERT INTO nps_daily_trades
            (trade_date, ticker, net_buy_volume, net_buy_amount, consecutive_buy_days, buy_intensity_pct)
        VALUES
            (:today, '005930', 500000, 30000000000, 5, 0.082),
            (:today, '000660', 200000, 24000000000, 3, 0.027),
            (:today, '005380', -100000, -5000000000, 0, NULL)
    """), {"today": today})

    db_session.flush()
    return {"today": today, "prev": prev}
