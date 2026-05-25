from datetime import date

from pydantic import BaseModel, ConfigDict


class NpsTopTradeItem(BaseModel):
    """메인 화면 순매수 상위 종목 1행"""

    rank: int
    ticker: str
    name: str
    market: str
    close: int | None
    change_pct: float | None          # 전일 대비 등락률 (%)
    net_buy_amount: int               # 순매수 금액 (원)
    net_buy_volume: int               # 순매수 수량
    consecutive_buy_days: int         # 연속 매수일
    buy_intensity_pct: float | None   # 시총 대비 순매수 비중 (%)


class NpsDailySummaryResponse(BaseModel):
    """메인 화면 응답 - 특정 일자의 순매수 상위 + 요약 통계"""

    trade_date: date
    close_date: date                   # 종가 기준일 (NPS trade_date와 다를 수 있음 — T+1 공표)
    # 데이터 기준 고지 (PROJECT_SPEC §1.3.1)
    data_notice: str = "본 데이터는 KRX의 '연기금 등' 카테고리 합산치이며, 국민연금 단독 매매가 아닙니다. 장 마감 후(T+1) 기준입니다."
    total_net_buy_amount: int         # 전체 순매수 합계 (원)
    net_buy_count: int                # 순매수 종목 수
    net_sell_count: int               # 순매도 종목 수
    items: list[NpsTopTradeItem]


class NpsTradeTimeSeriesItem(BaseModel):
    """종목 상세 화면 - NPS 매매 시계열 1행"""

    trade_date: date
    net_buy_amount: int
    net_buy_volume: int
    consecutive_buy_days: int
    buy_intensity_pct: float | None
    # OHLCV join 결과
    close: int | None
    change_pct: float | None


class NpsTradeTimeSeriesResponse(BaseModel):
    ticker: str
    name: str
    items: list[NpsTradeTimeSeriesItem]


class NpsHoldingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_date: date
    filing_date: date
    shares: int
    holding_ratio: float
    purpose: str
    rcept_no: str


class NpsHoldingsResponse(BaseModel):
    ticker: str
    name: str
    items: list[NpsHoldingItem]
