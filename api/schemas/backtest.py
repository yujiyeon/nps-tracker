from datetime import date

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    """백테스팅 실행 요청 파라미터 (PROJECT_SPEC §4.1 FollowStrategy)"""

    from_date: date
    to_date: date
    min_consecutive_days: int = Field(default=3, ge=1, le=30)
    min_net_buy_amount: int = Field(default=1_000_000_000, ge=0)       # 최소 순매수 10억원
    min_buy_intensity_pct: float = Field(default=0.1, ge=0.0)
    holding_period_days: int = Field(default=20, ge=1, le=250)
    entry_lag_days: int = Field(default=1, ge=1)                       # look-ahead bias 방지
    max_positions: int = Field(default=10, ge=1, le=50)
    initial_capital: int = Field(default=10_000_000, ge=1_000_000)
    transaction_cost_pct: float = Field(default=0.25, ge=0.0, le=2.0)


class EquityPoint(BaseModel):
    trade_date: date
    equity: int


class BacktestResultResponse(BaseModel):
    """백테스팅 결과 (POST 즉시 반환 또는 GET으로 폴링)"""

    job_id: str
    status: str                         # 'pending' | 'running' | 'done' | 'failed'
    request: BacktestRequest | None = None

    # status == 'done'일 때만 채워짐
    total_return_pct: float | None = None
    cagr_pct: float | None = None
    kospi_excess_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    win_rate_pct: float | None = None
    trades_count: int | None = None
    equity_curve: list[EquityPoint] | None = None

    error_message: str | None = None
