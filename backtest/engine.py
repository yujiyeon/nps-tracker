"""
백테스팅 엔진.

PROJECT_SPEC §4.2 핵심 원칙 준수:
    1. No look-ahead bias  : entry_lag_days >= 1 assert
    2. Survivorship bias 방지 : delisting_date 있는 종목도 포함, 폐지 시 -100% 처리
    3. 거래비용 반영      : 매수/매도마다 transaction_cost_pct 차감
    4. 현실적 슬리피지    : 매수 시초가+slippage, 매도 시초가-slippage
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from backtest.strategies import FollowStrategy


# ──────────────────────────────────────────────
# 내부 데이터 구조
# ──────────────────────────────────────────────


@dataclass
class Position:
    ticker: str
    entry_date: date
    cost_price: float         # 슬리피지 + 거래비용 포함 실효 매수가
    capital: float            # 해당 포지션에 투입된 자본
    target_exit_date: date    # 보유 기간 만료 목표일 (영업일 기준)


@dataclass
class ClosedTrade:
    ticker: str
    entry_date: date
    exit_date: date
    pnl_ratio: float          # 순수익률 (거래비용 포함)
    reason: str               # 'holding_period' | 'delisted' | 'end_of_period'


@dataclass
class BacktestResult:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    trades_count: int
    kospi_excess_return_pct: float | None    # KOSPI 비교 (데이터 있을 때)
    equity_curve: list[dict[str, Any]]       # [{trade_date, equity}]


# ──────────────────────────────────────────────
# 데이터 로딩
# ──────────────────────────────────────────────


def _load_data(
    session: Session,
    from_date: date,
    to_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    NPS 매매, OHLCV, 종목 마스터 로드.
    TimescaleDB 청크 프루닝을 위해 날짜 범위 조건 포함.
    """
    # NPS 매매 (시그널 생성용)
    nps_df = pd.read_sql(
        text("""
            SELECT trade_date, ticker, net_buy_amount, net_buy_volume,
                   consecutive_buy_days, buy_intensity_pct
            FROM nps_daily_trades
            WHERE trade_date BETWEEN :from_date AND :to_date
            ORDER BY trade_date, ticker
        """),
        session.bind,
        params={"from_date": from_date, "to_date": to_date},
        parse_dates=["trade_date"],
    )
    nps_df["trade_date"] = nps_df["trade_date"].dt.date

    # OHLCV (매수/매도 가격, 포지션 평가용)
    # 보유 기간 내 청산 가격이 필요하므로 to_date + 여유 기간 추가 로드
    extended_to = to_date + timedelta(days=60)
    ohlcv_df = pd.read_sql(
        text("""
            SELECT trade_date, ticker, open, close
            FROM daily_ohlcv
            WHERE trade_date BETWEEN :from_date AND :to_date
              AND open > 0
            ORDER BY trade_date, ticker
        """),
        session.bind,
        params={"from_date": from_date, "to_date": extended_to},
        parse_dates=["trade_date"],
    )
    ohlcv_df["trade_date"] = ohlcv_df["trade_date"].dt.date

    # 종목 마스터 (생존편향 방지: delisting_date 포함)
    stocks_df = pd.read_sql(
        text("SELECT ticker, delisting_date FROM stocks"),
        session.bind,
        parse_dates=["delisting_date"],
    )
    stocks_df["delisting_date"] = stocks_df["delisting_date"].where(
        stocks_df["delisting_date"].notna(), None
    )

    logger.info(
        f"데이터 로드 완료: NPS {len(nps_df)}행, OHLCV {len(ohlcv_df)}행, "
        f"종목 {len(stocks_df)}행"
    )
    return nps_df, ohlcv_df, stocks_df


def _build_lookups(
    nps_df: pd.DataFrame,
    ohlcv_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> tuple[dict, dict, dict]:
    """O(1) 조회를 위한 dict 변환"""
    # NPS: {date: {ticker: {fields}}}
    nps_by_date: dict[date, dict[str, dict]] = {}
    for row in nps_df.itertuples():
        d = row.trade_date
        nps_by_date.setdefault(d, {})[row.ticker] = {
            "net_buy_amount": row.net_buy_amount,
            "consecutive_buy_days": row.consecutive_buy_days,
            "buy_intensity_pct": row.buy_intensity_pct,
        }

    # OHLCV: {(date, ticker): {open, close}}
    ohlcv_lookup: dict[tuple[date, str], dict] = {
        (row.trade_date, row.ticker): {"open": row.open, "close": row.close}
        for row in ohlcv_df.itertuples()
    }

    # 종목: {ticker: delisting_date | None}
    delisting: dict[str, date | None] = {}
    for row in stocks_df.itertuples():
        dl = row.delisting_date
        delisting[row.ticker] = dl.date() if pd.notna(dl) and dl is not None else None

    return nps_by_date, ohlcv_lookup, delisting


# ──────────────────────────────────────────────
# 시그널 생성
# ──────────────────────────────────────────────


def _get_signals(
    nps_by_date: dict,
    signal_date: date,
    strategy: FollowStrategy,
) -> list[str]:
    """
    signal_date 기준으로 진입 조건을 만족하는 종목 목록 반환.
    순매수금액 내림차순 정렬 (강도 높은 종목 우선 진입).
    """
    day_data = nps_by_date.get(signal_date, {})
    candidates = []

    for ticker, data in day_data.items():
        # 연속 매수일 조건
        if data["consecutive_buy_days"] < strategy.min_consecutive_days:
            continue
        # 최소 순매수금액 조건
        if data["net_buy_amount"] < strategy.min_net_buy_amount:
            continue
        # 매수 강도 조건 (데이터 없으면 통과)
        intensity = data["buy_intensity_pct"]
        if intensity is not None and intensity < strategy.min_buy_intensity_pct:
            continue

        candidates.append((ticker, data["net_buy_amount"]))

    return [t for t, _ in sorted(candidates, key=lambda x: -x[1])]


# ──────────────────────────────────────────────
# 포지션 관리 헬퍼
# ──────────────────────────────────────────────


def _entry_price(open_price: float, strategy: FollowStrategy) -> float:
    """매수 실효가: 시초가 + 슬리피지 + 거래비용"""
    return open_price * (1 + strategy.slippage_pct / 100) * (1 + strategy.transaction_cost_pct / 100)


def _exit_price(open_price: float, strategy: FollowStrategy) -> float:
    """매도 실효가: 시초가 - 슬리피지 - 거래비용"""
    return open_price * (1 - strategy.slippage_pct / 100) * (1 - strategy.transaction_cost_pct / 100)


def _pnl_ratio(cost_price: float, exit_eff_price: float) -> float:
    return (exit_eff_price - cost_price) / cost_price


# ──────────────────────────────────────────────
# 지표 계산
# ──────────────────────────────────────────────


def _calc_metrics(
    equity_curve: list[tuple[date, float]],
    trades: list[ClosedTrade],
    strategy: FollowStrategy,
) -> BacktestResult:
    if not equity_curve:
        raise ValueError("equity_curve가 비어 있습니다.")

    dates, equities = zip(*equity_curve)
    equities = list(equities)

    final_equity = equities[-1]
    initial = strategy.initial_capital

    # 총 수익률
    total_return_pct = (final_equity - initial) / initial * 100

    # CAGR
    n_years = (dates[-1] - dates[0]).days / 365.25
    cagr_pct = ((final_equity / initial) ** (1 / max(n_years, 0.01)) - 1) * 100 if n_years > 0 else 0.0

    # MDD (최대낙폭)
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    # 샤프 지수 (연율화, 무위험금리 0%)
    eq_series = pd.Series(equities)
    daily_returns = eq_series.pct_change().dropna()
    if daily_returns.std() > 0:
        sharpe = (daily_returns.mean() * 252) / (daily_returns.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    # 승률
    wins = sum(1 for t in trades if t.pnl_ratio > 0)
    win_rate = wins / len(trades) * 100 if trades else 0.0

    equity_list = [
        {"trade_date": str(d), "equity": int(round(e))}
        for d, e in zip(dates, equities)
    ]

    return BacktestResult(
        total_return_pct=round(total_return_pct, 2),
        cagr_pct=round(cagr_pct, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 3),
        win_rate_pct=round(win_rate, 2),
        trades_count=len(trades),
        kospi_excess_return_pct=None,  # TODO: KOSPI 인덱스 데이터 수집 후 구현
        equity_curve=equity_list,
    )


# ──────────────────────────────────────────────
# 메인 엔진
# ──────────────────────────────────────────────


def run_backtest(
    strategy: FollowStrategy,
    session: Session,
    from_date: date,
    to_date: date,
) -> BacktestResult:
    """
    연기금 추종 전략 백테스팅 실행.

    Args:
        strategy: 전략 파라미터
        session: DB 세션
        from_date: 백테스팅 시작일
        to_date: 백테스팅 종료일

    Raises:
        AssertionError: entry_lag_days < 1 (look-ahead bias 방지)
        ValueError: 데이터 부족
    """
    # look-ahead bias 방지 강제 (PROJECT_SPEC §4.2)
    assert strategy.entry_lag_days >= 1, (
        f"entry_lag_days는 1 이상이어야 합니다 (현재: {strategy.entry_lag_days}). "
        "T일 데이터로 T일 매수는 look-ahead bias입니다."
    )

    logger.info(
        f"백테스팅 시작: {from_date} ~ {to_date}, "
        f"전략: 연속{strategy.min_consecutive_days}일, "
        f"최소{strategy.min_net_buy_amount // 100_000_000}억, "
        f"보유{strategy.holding_period_days}일"
    )

    # 1. 데이터 로드
    nps_df, ohlcv_df, stocks_df = _load_data(session, from_date, to_date)

    if nps_df.empty or ohlcv_df.empty:
        raise ValueError(f"백테스팅 기간({from_date}~{to_date})에 데이터가 없습니다. 백필 완료 여부를 확인하세요.")

    nps_by_date, ohlcv_lookup, delisting = _build_lookups(nps_df, ohlcv_df, stocks_df)

    # 2. 영업일 목록 (OHLCV 기준)
    trading_days = sorted(
        ohlcv_df[
            (ohlcv_df["trade_date"] >= from_date) &
            (ohlcv_df["trade_date"] <= to_date)
        ]["trade_date"].unique()
    )

    if len(trading_days) < strategy.entry_lag_days + 1:
        raise ValueError("백테스팅 기간이 너무 짧습니다.")

    # entry_lag_days → signal_date 매핑 (look-ahead bias 방지의 핵심)
    lag_map: dict[date, date] = {
        trading_days[i]: trading_days[i - strategy.entry_lag_days]
        for i in range(strategy.entry_lag_days, len(trading_days))
    }

    # 진입일 → 목표 청산일 매핑
    def get_exit_date(entry: date) -> date | None:
        try:
            idx = trading_days.index(entry)
            target = idx + strategy.holding_period_days
            return trading_days[target] if target < len(trading_days) else None
        except ValueError:
            return None

    # 3. 포트폴리오 초기화
    slot_capital = strategy.initial_capital / strategy.max_positions
    cash = float(strategy.initial_capital)
    positions: dict[str, Position] = {}
    trades: list[ClosedTrade] = []
    equity_curve: list[tuple[date, float]] = []

    # 4. 메인 백테스팅 루프
    for today in trading_days:
        # ── 4a. 만기/폐지 포지션 청산 ─────────────────────────────────────
        for ticker in list(positions.keys()):
            pos = positions[ticker]

            # 생존편향 방지: 폐지일 도달 시 -100% 처리 (PROJECT_SPEC §4.2)
            dl = delisting.get(ticker)
            if dl and today >= dl:
                cash += 0  # 전액 손실
                trades.append(
                    ClosedTrade(ticker, pos.entry_date, today, -1.0, "delisted")
                )
                del positions[ticker]
                logger.debug(f"폐지 처리: {ticker} ({today})")
                continue

            # 보유 기간 만료 청산
            if today >= pos.target_exit_date:
                ohlcv = ohlcv_lookup.get((today, ticker))
                if ohlcv and ohlcv["open"] > 0:
                    eff_exit = _exit_price(ohlcv["open"], strategy)
                    ratio = _pnl_ratio(pos.cost_price, eff_exit)
                    proceeds = pos.capital * (1 + ratio)
                else:
                    # 당일 거래 없음 → 자본만 회수 (손익 0)
                    ratio = 0.0
                    proceeds = pos.capital

                cash += proceeds
                trades.append(
                    ClosedTrade(ticker, pos.entry_date, today, ratio, "holding_period")
                )
                del positions[ticker]

        # ── 4b. 신규 시그널 확인 및 포지션 진입 ───────────────────────────
        signal_date = lag_map.get(today)
        if signal_date:
            signals = _get_signals(nps_by_date, signal_date, strategy)

            for ticker in signals:
                if ticker in positions:
                    continue
                if len(positions) >= strategy.max_positions:
                    break
                if cash < slot_capital:
                    break

                ohlcv = ohlcv_lookup.get((today, ticker))
                if not ohlcv or ohlcv["open"] <= 0:
                    continue

                exit_date = get_exit_date(today)
                if exit_date is None:
                    continue  # 백테스팅 종료일 근처 → 진입 스킵

                cost_price = _entry_price(ohlcv["open"], strategy)
                cash -= slot_capital
                positions[ticker] = Position(
                    ticker=ticker,
                    entry_date=today,
                    cost_price=cost_price,
                    capital=slot_capital,
                    target_exit_date=exit_date,
                )

        # ── 4c. 포트폴리오 평가 ───────────────────────────────────────────
        portfolio_value = cash
        for ticker, pos in positions.items():
            ohlcv = ohlcv_lookup.get((today, ticker))
            if ohlcv and ohlcv["close"] > 0:
                # 미실현 P&L (거래비용 미반영 - 보유 중)
                current_value = pos.capital * (ohlcv["close"] / pos.cost_price)
            else:
                current_value = pos.capital  # 데이터 없으면 원가 유지
            portfolio_value += current_value

        equity_curve.append((today, portfolio_value))

    # 5. 기간 종료 시 미청산 포지션 강제 청산
    if positions and trading_days:
        last_day = trading_days[-1]
        for ticker, pos in list(positions.items()):
            ohlcv = ohlcv_lookup.get((last_day, ticker))
            if ohlcv and ohlcv["open"] > 0:
                eff_exit = _exit_price(ohlcv["open"], strategy)
                ratio = _pnl_ratio(pos.cost_price, eff_exit)
                proceeds = pos.capital * (1 + ratio)
            else:
                ratio = 0.0
                proceeds = pos.capital
            trades.append(
                ClosedTrade(ticker, pos.entry_date, last_day, ratio, "end_of_period")
            )

    logger.info(
        f"백테스팅 완료: {len(trades)}건 거래, "
        f"최종 자산 {equity_curve[-1][1]:,.0f}원"
    )

    return _calc_metrics(equity_curve, trades, strategy)
