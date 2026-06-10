# backtest/rl_state.py
"""
강화학습 상태(state) 생성 단일 소스(single source of truth).

학습(rl_env.py)과 추론/백테스트(engine.py)가 *동일한* 상태 표현을 쓰도록 강제한다.
상태가 조금이라도 달라지면 학습된 정책이 추론에서 무의미해진다.

설계 (bandit → MDP 전환의 핵심):
    - 시장 정보뿐 아니라 '현재 포트폴리오'를 상태에 포함한다.
      → 내 매수 행동이 cash/보유종목/평가손익을 바꾸므로, 행동이 다음 상태에 영향을 준다.
    - 모든 피처는 스케일에 무관하도록 정규화한다(net_buy_amount 지배 문제 해결).

상태 벡터 구성 (길이 = top_k * 8 + 3):
    후보별(top_k개) 8개 피처:
        [순매수금액, 연속매수일, 매수강도, 당일등락(시가대비종가), 순매수순위,  # 시장 5
         보유여부, 보유일수, 평가손익률]                                       # 포트폴리오 3
    전역 3개 피처:
        [현금비중, 포지션비중, 평균 평가손익률]

행동(action) 공간 (길이 = top_k + 1):
    0 ~ top_k-1 : 해당 후보를 매수
    top_k       : 관망(아무것도 사지 않음)  ← skip
"""
import math

N_MARKET = 5
N_PORT_PER_CAND = 3
N_GLOBAL = 3
PER_CAND = N_MARKET + N_PORT_PER_CAND  # 8


def state_size(top_k: int) -> int:
    return top_k * PER_CAND + N_GLOBAL


def action_size(top_k: int) -> int:
    return top_k + 1  # 마지막 인덱스 = 관망(skip)


def skip_action(top_k: int) -> int:
    return top_k


def _market_features(net_buy_amount, consecutive_buy_days, buy_intensity_pct,
                     open_, close, rank, top_k):
    nb = float(net_buy_amount or 0)
    consec = float(consecutive_buy_days or 0)
    inten = float(buy_intensity_pct or 0)
    o = float(open_ or 0)
    c = float(close or 0)

    f1 = math.tanh(nb / 1e10)                         # 순매수금액(스케일 압축, 100억≈0.46)
    f2 = min(consec, 20.0) / 20.0                     # 연속매수일(0~1)
    f3 = math.tanh(inten / 5.0)                       # 매수강도(%)
    f4 = (c / o - 1.0) if o > 0 else 0.0              # 당일 등락(시가 대비 종가)
    f4 = max(min(f4, 0.3), -0.3)                      # 클리핑
    f5 = (top_k - rank) / top_k                       # 순매수 순위(상위일수록 1에 가까움)
    return [f1, f2, f3, f4, f5]


def build_state(
    candidates,          # list[dict], 길이 top_k (부족분은 ticker="NONE")
    portfolio,           # dict[ticker -> {"entry_price", "holding_days", "cur_close"}]
    cash,
    initial_capital,
    max_positions,
    holding_period,
    top_k,
):
    """
    포트폴리오를 포함한 MDP 상태 벡터를 만든다. (학습/추론 공통)

    candidates 각 원소(dict):
        ticker, net_buy_amount, consecutive_buy_days, buy_intensity_pct, open, close
        ticker == "NONE" 이면 빈 후보 슬롯(0 패딩).
    portfolio 각 원소(dict): entry_price(실효 매수가), holding_days(보유 영업일), cur_close(현재 종가)
    """
    import numpy as np

    feats = []
    for i, cand in enumerate(candidates[:top_k]):
        ticker = cand.get("ticker", "NONE")
        if ticker == "NONE":
            feats.extend([0.0] * PER_CAND)
            continue

        market = _market_features(
            cand.get("net_buy_amount"),
            cand.get("consecutive_buy_days"),
            cand.get("buy_intensity_pct"),
            cand.get("open"),
            cand.get("close"),
            rank=i,
            top_k=top_k,
        )

        pos = portfolio.get(ticker)
        if pos:
            held = 1.0
            hd = min(float(pos.get("holding_days", 0)), float(holding_period)) / max(holding_period, 1)
            entry = float(pos.get("entry_price") or 0)
            cur = float(pos.get("cur_close") or entry)
            pnl = (cur / entry - 1.0) if entry > 0 else 0.0
            pnl = max(min(pnl, 0.5), -0.5)
        else:
            held, hd, pnl = 0.0, 0.0, 0.0

        feats.extend(market + [held, hd, pnl])

    # 후보 슬롯이 top_k보다 적으면 0 패딩
    while len(feats) < top_k * PER_CAND:
        feats.extend([0.0] * PER_CAND)

    # 전역 포트폴리오 피처
    cash_ratio = max(min(float(cash) / max(initial_capital, 1), 1.0), 0.0)
    pos_ratio = len(portfolio) / max(max_positions, 1)
    if portfolio:
        pnls = []
        for pos in portfolio.values():
            entry = float(pos.get("entry_price") or 0)
            cur = float(pos.get("cur_close") or entry)
            pnls.append((cur / entry - 1.0) if entry > 0 else 0.0)
        avg_pnl = max(min(sum(pnls) / len(pnls), 0.5), -0.5)
    else:
        avg_pnl = 0.0

    feats.extend([cash_ratio, pos_ratio, avg_pnl])

    return np.array(feats, dtype=np.float32)