# backtest/rl_env.py

import numpy as np
import pandas as pd

from backtest.candidates import CandidateFilter, filter_candidates_df


class NpsStockEnv:
    def __init__(
        self,
        data: pd.DataFrame,
        top_k: int = 10,
        holding_period: int = 20,
        transaction_cost: float = 0.001,
        # ⚠️ 아래 3개 임계값은 추론(get_today_recommendation)에서 쓰는
        #    FollowStrategy 값과 *반드시 동일*해야 한다. 다르면 학습/추론
        #    좌석표가 달라져 추천이 매매동향과 어긋난다.
        min_consecutive_days: int = 0,
        min_net_buy_amount: float = 0.0,
        min_buy_intensity_pct: float = 0.0,
    ):
        """
        data 컬럼 예시:
        - trade_date
        - ticker
        - net_buy_amount
        - net_buy_volume
        - consecutive_buy_days
        - buy_intensity_pct
        - close
        - volume
        - market_cap
        - return_5d
        - return_20d
        - volatility_20d
        - future_return_20d
        """

        self.data = data.copy()
        self.top_k = top_k
        self.holding_period = holding_period
        self.transaction_cost = transaction_cost

        # 추론과 공유하는 후보 필터 (single source of truth)
        self.cand_filter = CandidateFilter(
            min_consecutive_days=min_consecutive_days,
            min_net_buy_amount=min_net_buy_amount,
            min_buy_intensity_pct=min_buy_intensity_pct,
        )

        self.feature_cols = [
            "net_buy_amount",
            "consecutive_buy_days",
            "buy_intensity_pct",
            "open",
            "close",
        ]

        self.dates = sorted(self.data["trade_date"].unique())
        self.current_idx = 0

        self.state_size = self.top_k * len(self.feature_cols)
        self.action_size = self.top_k

    def reset(self):
        self.current_idx = 0
        return self._get_state()

    def step(self, action: int):
        current_date = self.dates[self.current_idx]
        candidates = self._get_candidates(current_date)

        selected = candidates.iloc[action]

        reward = selected["future_return_20d"] - self.transaction_cost

        self.current_idx += 1
        done = self.current_idx >= len(self.dates) - 1

        next_state = self._get_state() if not done else np.zeros(self.state_size)

        info = {
            "date": current_date,
            "ticker": selected["ticker"],
            "reward": reward,
            "future_return_20d": selected["future_return_20d"],
        }

        return next_state, reward, done, info

    def _get_state(self):
        current_date = self.dates[self.current_idx]
        candidates = self._get_candidates(current_date)

        features = candidates[self.feature_cols].values

        return features.flatten().astype(np.float32)

    def _get_candidates(self, trade_date):
        day_data = self.data[self.data["trade_date"] == trade_date].copy()

        # 추론(engine.build_nps_candidates)과 동일한 필터/정렬 적용
        day_data = filter_candidates_df(day_data, self.cand_filter, top_k=self.top_k)

        if len(day_data) < self.top_k:
            padding_count = self.top_k - len(day_data)

            padding = pd.DataFrame(
                np.zeros((padding_count, len(day_data.columns))),
                columns=day_data.columns
            )

            padding["ticker"] = "NONE"
            padding["future_return_20d"] = -1.0

            day_data = pd.concat([day_data, padding], ignore_index=True)

        return day_data.reset_index(drop=True)