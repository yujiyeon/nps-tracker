"""SQLAlchemy 2.0 ORM 모델 - data-collector/db/models.py와 동일한 스키마"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100))
    listing_date: Mapped[date | None] = mapped_column(Date)
    delisting_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DailyOhlcv(Base):
    __tablename__ = "daily_ohlcv"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    open: Mapped[int] = mapped_column(Integer, nullable=False)
    high: Mapped[int] = mapped_column(Integer, nullable=False)
    low: Mapped[int] = mapped_column(Integer, nullable=False)
    close: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trading_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)


class NpsDailyTrade(Base):
    __tablename__ = "nps_daily_trades"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    net_buy_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_buy_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consecutive_buy_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buy_intensity_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NpsHolding(Base):
    __tablename__ = "nps_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(6), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False)
    holding_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    rcept_no: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (UniqueConstraint("rcept_no", name="uq_nps_holdings_rcept_no"),)


class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
