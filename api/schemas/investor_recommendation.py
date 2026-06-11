from datetime import date
from pydantic import BaseModel


class InvestorRecommendationItem(BaseModel):
    trade_date: date
    rank_no: int
    ticker: str
    stock_name: str | None = None

    consensus_score: float
    foreign_score: float
    co_buy_score: float
    final_score: float
    positive_institution_count: int

    pension_score: float
    trust_score: float
    insurance_score: float
    private_equity_score: float
    bank_score: float
    finance_investment_score: float


class InvestorRecommendationResponse(BaseModel):
    trade_date: date | None
    total_count: int
    items: list[InvestorRecommendationItem]