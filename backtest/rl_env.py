# backtest/rl_env.py
"""
국민연금 추종 포트폴리오 강화학습 환경 (MDP).

bandit → MDP 전환:
    - 상태: 후보 시장정보 + '현재 포트폴리오'(보유/손익/현금) → 행동이 다음 상태를 바꿈
    - 행동: top_k개 후보 중 하나 매수, 또는 관망(skip)
    - 보상: 미래수익률(future_return_20d)이 아니라 '당일 포트폴리오 가치 변화율'(일일 실현)
    - 매도: 보유기간(holding_period) 만료 시 자동 청산

step() 한 번 = 하루 진행.
"""
import numpy as np
import pandas as pd

from backtest.candidates import CandidateFilter, filter_candidates_df
from backtest import rl_state


class NpsPortfolioEnv:
    def __init__(
        self,
        data: pd.DataFrame,
        top_k: int = 50,
        holding_period: int = 20,
        transaction_cost: float = 0.001,
        max_positions: int = 10,
        initial_capital: float = 10_000_000,
        min_consecutive_days: int = 0,
        min_net_buy_amount: float = 0.0,
        min_buy_intensity_pct: float = 0.0,
    ):
        self.data = data.copy()
        self.top_k = top_k
        self.holding_period = holding_period
        self.transaction_cost = transaction_cost
        self.max_positions = max_positions
        self.initial_capital = float(initial_capital)
        self.slot_capital = self.initial_capital / max(max_positions, 1)

        self.cand_filter = CandidateFilter(
            min_consecutive_days=min_consecutive_days,
            min_net_buy_amount=min_net_buy_amount,
            min_buy_intensity_pct=min_buy_intensity_pct,
        )

        self.dates = sorted(self.data["trade_date"].unique())

        self.close_lookup: dict = {}
        self.open_lookup: dict = {}
        for r in self.data.itertuples():
            self.close_lookup[(r.trade_date, r.ticker)] = getattr(r, "close", 0.0)
            self.open_lookup[(r.trade_date, r.ticker)] = getattr(r, "open", 0.0)

        self._cand_cache: dict = {}

        self.state_size = rl_state.state_size(top_k)
        self.action_size = rl_state.action_size(top_k)
        self.skip_action = rl_state.skip_action(top_k)

    def reset(self):
        self.current_idx = 0
        self.cash = self.initial_capital
        self.positions: dict = {}
        self.prev_equity = self.initial_capital
        return self._get_state()

    def step(self, action: int):
        date_t = self.dates[self.current_idx]

        cands = self._candidates(date_t)
        bought = None
        if action < self.top_k:
            cand = cands[action]
            tk = cand.get("ticker", "NONE")
            close_t = self.close_lookup.get((date_t, tk))
            if (
                tk != "NONE"
                and tk not in self.positions
                and len(self.positions) < self.max_positions
                and self.cash >= self.slot_capital
                and close_t and close_t > 0
            ):
                entry_price = close_t * (1 + self.transaction_cost)
                self.cash -= self.slot_capital
                self.positions[tk] = {
                    "entry_price": entry_price,
                    "capital": self.slot_capital,
                    "entry_idx": self.current_idx,
                }
                bought = tk

        next_idx = self.current_idx + 1
        done = next_idx >= len(self.dates) - 1
        date_t1 = self.dates[next_idx]

        for tk in list(self.positions.keys()):
            pos = self.positions[tk]
            if next_idx - pos["entry_idx"] >= self.holding_period:
                close_now = self.close_lookup.get((date_t1, tk), pos["entry_price"])
                exit_eff = close_now * (1 - self.transaction_cost)
                proceeds = pos["capital"] * (exit_eff / pos["entry_price"])
                self.cash += proceeds
                del self.positions[tk]

        equity = self._equity(date_t1)
        reward = (equity / self.prev_equity - 1.0) if self.prev_equity > 0 else 0.0
        self.prev_equity = equity
        self.current_idx = next_idx

        next_state = self._get_state()

        info = {
            "date": date_t,
            "bought": bought,
            "equity": equity,
            "cash": self.cash,
            "n_positions": len(self.positions),
            "reward": reward,
        }
        return next_state, reward, done, info

    def _candidates(self, trade_date):
        if trade_date in self._cand_cache:
            return self._cand_cache[trade_date]

        df = filter_candidates_df(
            self.data[self.data["trade_date"] == trade_date],
            self.cand_filter,
            top_k=self.top_k,
        )
        cands = []
        for r in df.itertuples():
            cands.append({
                "ticker": r.ticker,
                "net_buy_amount": getattr(r, "net_buy_amount", 0),
                "consecutive_buy_days": getattr(r, "consecutive_buy_days", 0),
                "buy_intensity_pct": getattr(r, "buy_intensity_pct", None),
                "open": getattr(r, "open", 0.0),
                "close": getattr(r, "close", 0.0),
            })
        while len(cands) < self.top_k:
            cands.append({"ticker": "NONE"})

        self._cand_cache[trade_date] = cands
        return cands

    def _portfolio_view(self, trade_date):
        view = {}
        for tk, pos in self.positions.items():
            cur = self.close_lookup.get((trade_date, tk), pos["entry_price"])
            view[tk] = {
                "entry_price": pos["entry_price"],
                "holding_days": self.current_idx - pos["entry_idx"],
                "cur_close": cur,
            }
        return view

    def _equity(self, trade_date):
        val = self.cash
        for tk, pos in self.positions.items():
            cur = self.close_lookup.get((trade_date, tk), pos["entry_price"])
            val += pos["capital"] * (cur / pos["entry_price"])
        return val

    def _get_state(self):
        date = self.dates[self.current_idx]
        cands = self._candidates(date)
        port = self._portfolio_view(date)
        return rl_state.build_state(
            candidates=cands,
            portfolio=port,
            cash=self.cash,
            initial_capital=self.initial_capital,
            max_positions=self.max_positions,
            holding_period=self.holding_period,
            top_k=self.top_k,
        )