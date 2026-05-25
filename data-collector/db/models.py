"""SQLAlchemy 2.0 ORM 모델 정의"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Stock(Base):
    """종목 마스터 테이블 - 생존편향 방지를 위해 폐지 종목도 보관"""

    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)  # KOSPI / KOSDAQ
    sector: Mapped[str | None] = mapped_column(String(100))
    listing_date: Mapped[date | None] = mapped_column(Date)
    # 폐지일: 백테스팅에서 생존편향 방지에 필수 (폐지 시 -100% 손실 처리)
    delisting_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DailyOhlcv(Base):
    """일별 OHLCV 시세 - TimescaleDB hypertable (partition by trade_date, 1 month)"""

    __tablename__ = "daily_ohlcv"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    open: Mapped[int] = mapped_column(Integer, nullable=False)
    high: Mapped[int] = mapped_column(Integer, nullable=False)
    low: Mapped[int] = mapped_column(Integer, nullable=False)
    close: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trading_value: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 거래대금 (원, 최대 수조 단위)
    # 시총/상장주식수는 market_cap API에서 별도 수집
    market_cap: Mapped[int | None] = mapped_column(BigInteger)             # 시가총액 (원, 수백조 단위)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)


class NpsDailyTrade(Base):
    """연기금 일별 순매수 매매 - 핵심 테이블, TimescaleDB hypertable"""

    __tablename__ = "nps_daily_trades"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    # 음수 = 순매도
    net_buy_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_buy_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 원 단위 (수천억 가능)
    # 사후 계산 지표 (recalculate_signals에서 갱신)
    consecutive_buy_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 시총 대비 순매수 금액 비중 (%)
    buy_intensity_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NpsHolding(Base):
    """국민연금 5% 이상 보유 공시 (DART 주식등의대량보유상황보고서)"""

    __tablename__ = "nps_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(6), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)  # 보고 기준일
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)  # 공시일
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    holding_ratio: Mapped[float] = mapped_column(Float, nullable=False)  # 보유 비율 %
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)  # 단순투자/경영참여 등
    # DART 접수번호 (중복 수집 방지용 UNIQUE 제약)
    rcept_no: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (UniqueConstraint("rcept_no", name="uq_nps_holdings_rcept_no"),)


class CollectionLog(Base):
    """수집 작업 로그 - 멱등성 보장 및 중단 후 재개를 위한 진행 상황 추적"""

    __tablename__ = "collection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 'daily_trades' | 'ohlcv' | 'holdings'
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 'success' | 'failed' | 'partial'
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
