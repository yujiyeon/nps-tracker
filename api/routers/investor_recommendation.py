from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from db.session import SessionFactory
from schemas.investor_recommendation import InvestorRecommendationResponse
from services.investor_recommendation_service import get_top_recommendations

router = APIRouter(
    prefix="/api/investor-recommendations",
    tags=["Investor Recommendations"],
)


def get_db():
    session: Session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@router.get(
    "/top",
    response_model=InvestorRecommendationResponse,
)
def read_top_recommendations(
    trade_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    daily_top_recommendations 기준 TOP 추천 종목 조회.

    trade_date가 없으면 가장 최근 추천일 기준으로 조회한다.
    """
    session = SessionFactory()

    try:
        return get_top_recommendations(
            session=session,
            trade_date=trade_date,
            limit=limit,
        )
    finally:
        session.close()