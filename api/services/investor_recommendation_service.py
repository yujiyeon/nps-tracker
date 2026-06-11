from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_latest_recommendation_date(session: Session) -> date | None:
    result = session.execute(
        text(
            """
            SELECT MAX(trade_date)
            FROM daily_top_recommendations
            """
        )
    ).scalar_one_or_none()

    return result


def get_top_recommendations(
    session: Session,
    trade_date: date | None = None,
    limit: int = 50,
) -> dict:
    if trade_date is None:
        trade_date = get_latest_recommendation_date(session)

    if trade_date is None:
        return {
            "trade_date": None,
            "total_count": 0,
            "items": [],
        }

    rows = session.execute(
        text(
            """
            SELECT
                trade_date,
                rank_no,
                ticker,
                stock_name,
                consensus_score,
                foreign_score,
                co_buy_score,
                final_score,
                positive_institution_count,
                pension_score,
                trust_score,
                insurance_score,
                private_equity_score,
                bank_score,
                finance_investment_score
            FROM daily_top_recommendations
            WHERE trade_date = :trade_date
            ORDER BY rank_no
            LIMIT :limit
            """
        ),
        {
            "trade_date": trade_date,
            "limit": limit,
        },
    ).mappings().all()

    items = [dict(row) for row in rows]

    return {
        "trade_date": trade_date,
        "total_count": len(items),
        "items": items,
    }