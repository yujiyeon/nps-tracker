"""
백테스팅 엔진 단위 테스트.

실제 DB 없이 인메모리 데이터로 핵심 로직 검증.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backtest.engine import (
    _calc_metrics,
    _entry_price,
    _exit_price,
    _get_signals,
    _pnl_ratio,
    ClosedTrade,
)
from backtest.strategies import FollowStrategy


class TestLookAheadBias:
    def test_entry_lag_days_1_미만_거부(self):
        """entry_lag_days < 1이면 AssertionError (look-ahead bias 방지)"""
        from backtest.engine import run_backtest

        strategy = FollowStrategy(entry_lag_days=0)
        mock_session = MagicMock()

        with pytest.raises(AssertionError, match="look-ahead"):
            run_backtest(strategy, mock_session, date(2023, 1, 1), date(2023, 12, 31))


class TestSignalGeneration:
    def test_조건_모두_충족(self):
        nps_by_date = {
            date(2023, 6, 1): {
                "005930": {
                    "net_buy_amount": 5_000_000_000,
                    "consecutive_buy_days": 5,
                    "buy_intensity_pct": 0.5,
                }
            }
        }
        strategy = FollowStrategy(
            min_consecutive_days=3,
            min_net_buy_amount=1_000_000_000,
            min_buy_intensity_pct=0.1,
        )
        signals = _get_signals(nps_by_date, date(2023, 6, 1), strategy)
        assert "005930" in signals

    def test_연속_매수일_부족_시_제외(self):
        nps_by_date = {
            date(2023, 6, 1): {
                "005930": {
                    "net_buy_amount": 5_000_000_000,
                    "consecutive_buy_days": 2,  # 조건: 3 이상
                    "buy_intensity_pct": 0.5,
                }
            }
        }
        strategy = FollowStrategy(min_consecutive_days=3)
        signals = _get_signals(nps_by_date, date(2023, 6, 1), strategy)
        assert "005930" not in signals

    def test_순매수금액_부족_시_제외(self):
        nps_by_date = {
            date(2023, 6, 1): {
                "005930": {
                    "net_buy_amount": 500_000_000,  # 조건: 10억 이상
                    "consecutive_buy_days": 5,
                    "buy_intensity_pct": 0.5,
                }
            }
        }
        strategy = FollowStrategy(min_net_buy_amount=1_000_000_000)
        signals = _get_signals(nps_by_date, date(2023, 6, 1), strategy)
        assert "005930" not in signals

    def test_순매수금액_내림차순_정렬(self):
        """순매수금액이 큰 종목이 먼저 진입"""
        nps_by_date = {
            date(2023, 6, 1): {
                "000660": {
                    "net_buy_amount": 2_000_000_000,
                    "consecutive_buy_days": 5,
                    "buy_intensity_pct": 0.5,
                },
                "005930": {
                    "net_buy_amount": 8_000_000_000,
                    "consecutive_buy_days": 5,
                    "buy_intensity_pct": 0.5,
                },
            }
        }
        strategy = FollowStrategy()
        signals = _get_signals(nps_by_date, date(2023, 6, 1), strategy)
        assert signals[0] == "005930"  # 더 큰 금액이 우선


class TestTransactionCosts:
    def test_매수가_슬리피지_거래비용_포함(self):
        strategy = FollowStrategy(slippage_pct=0.1, transaction_cost_pct=0.25)
        open_price = 10_000
        effective = _entry_price(open_price, strategy)
        # 시초가 × (1 + 0.1%) × (1 + 0.25%)
        expected = 10_000 * 1.001 * 1.0025
        assert abs(effective - expected) < 0.01

    def test_매도가_슬리피지_거래비용_차감(self):
        strategy = FollowStrategy(slippage_pct=0.1, transaction_cost_pct=0.25)
        open_price = 10_000
        effective = _exit_price(open_price, strategy)
        expected = 10_000 * 0.999 * 0.9975
        assert abs(effective - expected) < 0.01

    def test_수익률_계산(self):
        cost = 10_000.0
        exit_eff = 11_000.0
        ratio = _pnl_ratio(cost, exit_eff)
        assert abs(ratio - 0.1) < 0.0001  # 10% 수익


class TestMetrics:
    def _make_equity_curve(self, values: list[float]) -> list[tuple[date, float]]:
        base = date(2023, 1, 2)
        from datetime import timedelta
        return [(base + timedelta(days=i), v) for i, v in enumerate(values)]

    def test_총수익률_계산(self):
        strategy = FollowStrategy(initial_capital=10_000_000)
        curve = self._make_equity_curve([10_000_000, 11_000_000])
        result = _calc_metrics(curve, [], strategy)
        assert result.total_return_pct == pytest.approx(10.0, abs=0.01)

    def test_mdd_하락_구간(self):
        """10% → 5% → 12% → 8% 시 MDD는 최고점 대비 최대 하락"""
        strategy = FollowStrategy(initial_capital=10_000_000)
        curve = self._make_equity_curve([10_000_000, 12_000_000, 6_000_000, 14_000_000])
        result = _calc_metrics(curve, [], strategy)
        # 12M → 6M: -50% MDD
        assert result.max_drawdown_pct == pytest.approx(-50.0, abs=0.5)

    def test_승률_계산(self):
        strategy = FollowStrategy(initial_capital=10_000_000)
        curve = self._make_equity_curve([10_000_000, 11_000_000])
        trades = [
            ClosedTrade("A", date(2023, 1, 2), date(2023, 1, 3), 0.05, "holding_period"),
            ClosedTrade("B", date(2023, 1, 2), date(2023, 1, 3), -0.03, "holding_period"),
            ClosedTrade("C", date(2023, 1, 2), date(2023, 1, 3), 0.10, "holding_period"),
        ]
        result = _calc_metrics(curve, trades, strategy)
        assert result.win_rate_pct == pytest.approx(66.67, abs=0.1)

    def test_폐지_종목_거래_포함(self):
        """폐지 종목은 -100% 손실로 trades에 포함되어야 함"""
        strategy = FollowStrategy(initial_capital=10_000_000)
        curve = self._make_equity_curve([10_000_000, 5_000_000])
        trades = [
            ClosedTrade("ZZZ", date(2023, 1, 2), date(2023, 1, 3), -1.0, "delisted"),
        ]
        result = _calc_metrics(curve, trades, strategy)
        assert result.win_rate_pct == 0.0
        assert result.trades_count == 1
