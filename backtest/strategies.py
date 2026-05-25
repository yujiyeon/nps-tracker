"""
백테스팅 전략 파라미터 정의.

PROJECT_SPEC §4.1 FollowStrategy 구현.
"""
from dataclasses import dataclass, field


@dataclass
class FollowStrategy:
    """
    연기금 추종 전략.

    핵심 불변식 (engine.py에서 assert로 강제):
        entry_lag_days >= 1  →  look-ahead bias 방지 (PROJECT_SPEC §4.2)
    """

    # ── 진입 조건 ──────────────────────────────────────────────────────────
    min_consecutive_days: int = 3
    """연기금이 연속 순매수한 최소 일수"""

    min_net_buy_amount: int = 1_000_000_000
    """최소 순매수 금액 (원). 기본 10억"""

    min_buy_intensity_pct: float = 0.1
    """최소 매수 강도 (시총 대비 %). None이면 조건 미적용"""

    # ── 포지션 관리 ────────────────────────────────────────────────────────
    holding_period_days: int = 20
    """보유 기간 (영업일). 해당 일 이후 첫 거래일 시초가에 매도"""

    entry_lag_days: int = 1
    """
    시그널 발생 후 N 영업일 뒤에 매수.
    1 이상 강제 → T일 데이터로 T일 매수 금지 (look-ahead bias 방지).
    """

    max_positions: int = 10
    """동시 보유 최대 종목 수. 초과 시 시그널 무시"""

    # ── 자본 / 비용 ────────────────────────────────────────────────────────
    initial_capital: int = 10_000_000
    """초기 자본 (원). 기본 1천만원"""

    transaction_cost_pct: float = 0.25
    """
    왕복 거래 비용 (%).
    수수료 0.015% × 2 + 증권거래세 0.18% + 슬리피지 ≈ 0.25%.
    """

    slippage_pct: float = 0.1
    """
    시초가 대비 슬리피지 (%).
    매수: 시초가 × (1 + slippage_pct / 100)
    매도: 시초가 × (1 - slippage_pct / 100)
    """
