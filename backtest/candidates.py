# backtest/candidates.py
"""
NPS 매매동향 후보(candidates) 생성 단일 소스(single source of truth).

학습(rl_env.py)과 추론/백테스트(engine.py)가 *반드시 동일한 필터/정렬*로
후보 리스트를 만들도록 강제한다. DQN의 action 은 종목명이 아니라
"후보 리스트의 좌석 번호(index)"이므로, 이 좌석표가 학습/추론에서
조금이라도 달라지면 추천 종목이 매매동향 리스트와 어긋난다.
"""
from dataclasses import dataclass


@dataclass
class CandidateFilter:
    """후보 진입 필터 임계값. 학습과 추론에서 동일 값을 써야 한다."""
    min_consecutive_days: int = 0
    min_net_buy_amount: float = 0.0
    min_buy_intensity_pct: float = 0.0

    @classmethod
    def from_strategy(cls, strategy) -> "CandidateFilter":
        return cls(
            min_consecutive_days=strategy.min_consecutive_days,
            min_net_buy_amount=strategy.min_net_buy_amount,
            min_buy_intensity_pct=strategy.min_buy_intensity_pct,
        )


def passes_filter(
    net_buy_amount,
    consecutive_buy_days,
    buy_intensity_pct,
    f: "CandidateFilter",
) -> bool:
    """후보 단일 종목이 필터를 통과하는지 판정 (학습/추론 공통)."""
    nb = net_buy_amount or 0
    if nb <= 0:                                       # 순매수 종목만
        return False
    if (consecutive_buy_days or 0) < f.min_consecutive_days:
        return False
    if nb < f.min_net_buy_amount:
        return False
    intensity = 0.0 if buy_intensity_pct is None else buy_intensity_pct
    if intensity < f.min_buy_intensity_pct:
        return False
    return True


def build_nps_candidates(
    nps_by_date,
    trade_date,
    f: "CandidateFilter",
    top_n: int = 50,
    ticker_market: dict | None = None,
    allowed_market: str | None = None,
):
    """
    dict 기반 (engine.py 추론/백테스트용).

    매매동향 페이지(get_nps_daily_summary)와 *동일한 순서*로 후보를 만든다.
      1) 시장 필터(allowed_market) 적용
      2) net_buy_amount 내림차순 상위 top_n = 매매동향 페이지 명단
      3) 그 명단 안에서만 사용자 파라미터(f) 필터 적용
    → 결과는 항상 페이지 명단의 부분집합이 된다.

    nps_by_date: {date: {ticker: {net_buy_amount, consecutive_buy_days, buy_intensity_pct}}}
    반환: 필터 통과 ticker 리스트 (페이지와 동일한 순매수금액 내림차순).
    """
    day = nps_by_date.get(trade_date, {})

    # 1) 시장 필터 + 2) 순매수금액 내림차순 상위 top_n (= 페이지 명단)
    rows = []
    for ticker, d in day.items():
        if allowed_market and ticker_market is not None:
            if ticker_market.get(ticker) != allowed_market:
                continue
        rows.append((ticker, d))
    rows.sort(key=lambda x: -(x[1].get("net_buy_amount") or 0))
    page_list = rows[:top_n]

    # 3) 페이지 명단 안에서만 파라미터 필터
    result = []
    for ticker, d in page_list:
        if passes_filter(
            d.get("net_buy_amount"),
            d.get("consecutive_buy_days"),
            d.get("buy_intensity_pct"),
            f,
        ):
            result.append(ticker)
    return result


def filter_candidates_df(day_df, f: "CandidateFilter", top_k: int = 50):
    """
    DataFrame 기반 (rl_env.py 학습용).
    build_nps_candidates 와 *동일한* 필터/정렬을 DataFrame 에 적용.
    반환: 필터 통과 후 net_buy_amount 내림차순 top_k 행 (index 리셋).
    """
    df = day_df.copy()
    mask = df.apply(
        lambda r: passes_filter(
            r.get("net_buy_amount"),
            r.get("consecutive_buy_days"),
            r.get("buy_intensity_pct"),
            f,
        ),
        axis=1,
    )
    df = df[mask].sort_values("net_buy_amount", ascending=False).head(top_k)
    return df.reset_index(drop=True)