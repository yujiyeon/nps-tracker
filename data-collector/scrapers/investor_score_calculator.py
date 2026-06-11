import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger
from sqlalchemy import text

from db.session import get_session

KST = ZoneInfo("Asia/Seoul")


# 기관별 가중치
# 국민연금 30%, 투신 25%, 보험 15%, 사모펀드 15%, 은행 5%, 금융투자 10%
INSTITUTION_WEIGHTS = {
    "PENSION": 0.30,
    "INVESTMENT_TRUST": 0.25,
    "INSURANCE": 0.15,
    "PRIVATE_EQUITY": 0.15,
    "BANK": 0.05,
    "FINANCE_INVESTMENT": 0.10,
}

# 기관 내부 점수 가중치
# 순매수금액 50%, 연속매수일수 30%, 매수강도 20%
SCORE_WEIGHTS = {
    "amount": 0.50,
    "consecutive": 0.30,
    "intensity": 0.20,
}

FOREIGN_TYPE = "FOREIGN"


def _score_positive_rank(
    df: pd.DataFrame,
    value_col: str,
    score_col: str,
) -> pd.DataFrame:
    """
    특정 지표를 0~100점으로 변환한다.

    기준:
    - 순매수금액이 0 이하인 행은 0점
    - value_col 값이 0 이하인 행은 0점
    - 같은 trade_date + investor_type 안에서 상대 순위 percentile로 점수화
    """
    df[score_col] = 0.0

    mask = (
        df[value_col].notna()
        & (df[value_col] > 0)
        & (df["net_buy_amount"] > 0)
    )

    if mask.sum() == 0:
        return df

    df.loc[mask, score_col] = (
        df.loc[mask]
        .groupby(["trade_date", "investor_type"])[value_col]
        .rank(method="average", pct=True)
        * 100
    )

    return df


def _load_trade_data_for_date(target_date: date) -> pd.DataFrame:
    with get_session() as session:
        return pd.read_sql(
            text(
                """
                SELECT
                    trade_date,
                    ticker,
                    investor_type,
                    investor_name,
                    net_buy_amount,
                    net_buy_volume,
                    consecutive_buy_days,
                    buy_intensity_pct
                FROM investor_daily_trades
                WHERE trade_date = :target_date
                """
            ),
            session.bind,
            params={"target_date": target_date},
            parse_dates=["trade_date"],
        )


def _load_stock_master() -> pd.DataFrame:
    with get_session() as session:
        return pd.read_sql(
            text(
                """
                SELECT
                    ticker,
                    name AS stock_name
                FROM stocks
                """
            ),
            session.bind,
        )


def _save_investor_daily_scores(
    target_date: date,
    trade_df: pd.DataFrame,
) -> None:
    now = datetime.now(KST)

    score_records = []

    for _, row in trade_df.iterrows():
        score_records.append(
            {
                "trade_date": target_date,
                "ticker": row["ticker"],
                "investor_type": row["investor_type"],
                "investor_name": row["investor_name"],
                "net_buy_amount": int(row["net_buy_amount"]),
                "net_buy_volume": int(row["net_buy_volume"]),
                "consecutive_buy_days": int(row["consecutive_buy_days"]),
                "buy_intensity_pct": float(row["buy_intensity_pct"] or 0),
                "amount_score": float(row["amount_score"]),
                "consecutive_score": float(row["consecutive_score"]),
                "intensity_score": float(row["intensity_score"]),
                "investor_score": float(row["investor_score"]),
                "now": now,
            }
        )

    if not score_records:
        logger.warning(f"저장할 기관별 점수 없음: {target_date}")
        return

    with get_session() as session:
        session.execute(
            text(
                """
                DELETE FROM investor_daily_scores
                WHERE trade_date = :target_date
                """
            ),
            {"target_date": target_date},
        )

        session.execute(
            text(
                """
                INSERT INTO investor_daily_scores (
                    trade_date,
                    ticker,
                    investor_type,
                    investor_name,
                    net_buy_amount,
                    net_buy_volume,
                    consecutive_buy_days,
                    buy_intensity_pct,
                    amount_score,
                    consecutive_score,
                    intensity_score,
                    investor_score,
                    created_at,
                    updated_at
                )
                VALUES (
                    :trade_date,
                    :ticker,
                    :investor_type,
                    :investor_name,
                    :net_buy_amount,
                    :net_buy_volume,
                    :consecutive_buy_days,
                    :buy_intensity_pct,
                    :amount_score,
                    :consecutive_score,
                    :intensity_score,
                    :investor_score,
                    :now,
                    :now
                )
                """
            ),
            score_records,
        )


def _build_recommendations(
    target_date: date,
    trade_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    """
    일자별 종목 컨센서스 점수, 동시매수 기관수, 외국인 점수, 최종 TOP N 계산.
    """
    pivot = trade_df.pivot_table(
        index="ticker",
        columns="investor_type",
        values="investor_score",
        aggfunc="max",
        fill_value=0,
    ).reset_index()

    required_investors = list(INSTITUTION_WEIGHTS.keys()) + [FOREIGN_TYPE]

    for investor_type in required_investors:
        if investor_type not in pivot.columns:
            pivot[investor_type] = 0.0

    # 기관 컨센서스 점수
    pivot["consensus_score"] = 0.0

    for investor_type, weight in INSTITUTION_WEIGHTS.items():
        pivot["consensus_score"] += pivot[investor_type] * weight

    # 동시매수 기관 수
    positive_df = trade_df[
        trade_df["investor_type"].isin(INSTITUTION_WEIGHTS.keys())
        & (trade_df["net_buy_amount"] > 0)
    ]

    positive_count = (
        positive_df.groupby("ticker")["investor_type"]
        .nunique()
        .reset_index(name="positive_institution_count")
    )

    pivot = pivot.merge(positive_count, on="ticker", how="left")
    pivot["positive_institution_count"] = (
        pivot["positive_institution_count"]
        .fillna(0)
        .astype(int)
    )

    # 동시매수 점수: 6개 기관 중 몇 개 기관이 순매수했는지 0~100점
    pivot["co_buy_score"] = (
        pivot["positive_institution_count"] / len(INSTITUTION_WEIGHTS) * 100
    )

    # 외국인 점수
    pivot["foreign_score"] = pivot[FOREIGN_TYPE]

    # 최종 점수
    # 기관 컨센서스 75%, 외국인 15%, 동시매수 10%
    pivot["final_score"] = (
        pivot["consensus_score"] * 0.75
        + pivot["foreign_score"] * 0.15
        + pivot["co_buy_score"] * 0.10
    )

    pivot = pivot.merge(stock_df, on="ticker", how="left")

    top_df = pivot.sort_values("final_score", ascending=False).head(top_n).copy()
    top_df["trade_date"] = target_date
    top_df["rank_no"] = range(1, len(top_df) + 1)

    return top_df


def _save_daily_top_recommendations(
    target_date: date,
    top_df: pd.DataFrame,
) -> None:
    now = datetime.now(KST)

    recommendation_records = []

    for _, row in top_df.iterrows():
        recommendation_records.append(
            {
                "trade_date": target_date,
                "rank_no": int(row["rank_no"]),
                "ticker": row["ticker"],
                "stock_name": row.get("stock_name"),
                "consensus_score": float(row["consensus_score"]),
                "foreign_score": float(row["foreign_score"]),
                "co_buy_score": float(row["co_buy_score"]),
                "final_score": float(row["final_score"]),
                "positive_institution_count": int(row["positive_institution_count"]),
                "pension_score": float(row["PENSION"]),
                "trust_score": float(row["INVESTMENT_TRUST"]),
                "insurance_score": float(row["INSURANCE"]),
                "private_equity_score": float(row["PRIVATE_EQUITY"]),
                "bank_score": float(row["BANK"]),
                "finance_investment_score": float(row["FINANCE_INVESTMENT"]),
                "now": now,
            }
        )

    if not recommendation_records:
        logger.warning(f"저장할 TOP 추천 없음: {target_date}")
        return

    with get_session() as session:
        session.execute(
            text(
                """
                DELETE FROM daily_top_recommendations
                WHERE trade_date = :target_date
                """
            ),
            {"target_date": target_date},
        )

        session.execute(
            text(
                """
                INSERT INTO daily_top_recommendations (
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
                    finance_investment_score,
                    created_at
                )
                VALUES (
                    :trade_date,
                    :rank_no,
                    :ticker,
                    :stock_name,
                    :consensus_score,
                    :foreign_score,
                    :co_buy_score,
                    :final_score,
                    :positive_institution_count,
                    :pension_score,
                    :trust_score,
                    :insurance_score,
                    :private_equity_score,
                    :bank_score,
                    :finance_investment_score,
                    :now
                )
                """
            ),
            recommendation_records,
        )


def calculate_for_date(target_date: date, top_n: int = 50) -> None:
    """
    특정 일자 기준으로 기관별 점수와 TOP 추천 종목을 계산한다.
    """
    logger.info(f"기관 컨센서스 점수 계산 시작: {target_date}")

    trade_df = _load_trade_data_for_date(target_date)

    if trade_df.empty:
        logger.warning(f"투자자 수급 데이터 없음: {target_date}")
        return

    stock_df = _load_stock_master()

    trade_df["buy_intensity_pct"] = trade_df["buy_intensity_pct"].fillna(0)
    trade_df["consecutive_buy_days"] = trade_df["consecutive_buy_days"].fillna(0)

    # 1. 기관별 개별 점수 계산
    trade_df = _score_positive_rank(
        trade_df,
        value_col="net_buy_amount",
        score_col="amount_score",
    )

    trade_df = _score_positive_rank(
        trade_df,
        value_col="consecutive_buy_days",
        score_col="consecutive_score",
    )

    trade_df = _score_positive_rank(
        trade_df,
        value_col="buy_intensity_pct",
        score_col="intensity_score",
    )

    trade_df["investor_score"] = (
        trade_df["amount_score"] * SCORE_WEIGHTS["amount"]
        + trade_df["consecutive_score"] * SCORE_WEIGHTS["consecutive"]
        + trade_df["intensity_score"] * SCORE_WEIGHTS["intensity"]
    )

    # 순매수가 아닌 경우는 0점 처리
    trade_df.loc[trade_df["net_buy_amount"] <= 0, "investor_score"] = 0.0

    # 2. 기관별 점수 저장
    _save_investor_daily_scores(target_date, trade_df)

    # 3. 종목별 컨센서스/동시매수/외국인 점수/TOP N 계산
    top_df = _build_recommendations(
        target_date=target_date,
        trade_df=trade_df,
        stock_df=stock_df,
        top_n=top_n,
    )

    # 4. TOP 추천 저장
    _save_daily_top_recommendations(target_date, top_df)

    logger.info(f"TOP{top_n} 추천 생성 완료: {target_date}, {len(top_df)}건")


def calculate_all_dates(top_n: int = 50) -> None:
    """
    investor_daily_trades 테이블에 존재하는 모든 trade_date에 대해 점수 계산.
    """
    with get_session() as session:
        dates_df = pd.read_sql(
            text(
                """
                SELECT DISTINCT trade_date
                FROM investor_daily_trades
                ORDER BY trade_date
                """
            ),
            session.bind,
            parse_dates=["trade_date"],
        )

    if dates_df.empty:
        logger.warning("계산할 날짜가 없습니다. investor_daily_trades 데이터를 확인하세요.")
        return

    total = len(dates_df)
    logger.info(f"전체 날짜 계산 시작: {total}일")

    success_count = 0
    failed_dates: list[str] = []

    for idx, row in dates_df.iterrows():
        target_date = row["trade_date"].date()

        logger.info(f"[{idx + 1}/{total}] 계산 중: {target_date}")

        try:
            calculate_for_date(target_date=target_date, top_n=top_n)
            success_count += 1

        except Exception as e:
            logger.error(f"계산 실패: {target_date}, error={e}")
            failed_dates.append(str(target_date))

    logger.info(
        f"전체 날짜 계산 완료: 성공 {success_count}일, 실패 {len(failed_dates)}일"
    )

    if failed_dates:
        logger.warning(f"실패 날짜 목록: {failed_dates}")


def main() -> None:
    parser = argparse.ArgumentParser(description="기관 컨센서스 추천 점수 계산기")

    parser.add_argument(
        "--date",
        help="계산 대상 날짜 YYYY-MM-DD",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="investor_daily_trades에 있는 모든 날짜 계산",
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="추천 종목 수",
    )

    args = parser.parse_args()

    if args.all:
        calculate_all_dates(top_n=args.top_n)
        return

    if args.date:
        target_date = date.fromisoformat(args.date)
        calculate_for_date(target_date=target_date, top_n=args.top_n)
        return

    raise ValueError("--date 또는 --all 옵션이 필요합니다.")


if __name__ == "__main__":
    main()