from datetime import date

import pandas as pd
from loguru import logger
from pykrx import stock
from tenacity import retry, stop_after_attempt, wait_exponential


INVESTORS = {
    "PENSION": "연기금",
    "INVESTMENT_TRUST": "투신",
    "INSURANCE": "보험",
    "PRIVATE_EQUITY": "사모",
    "BANK": "은행",
    "FINANCE_INVESTMENT": "금융투자",
    "OTHER_FINANCE": "기타금융",
    "FOREIGN": "외국인",
}


def _date_str(target_date: date) -> str:
    return target_date.strftime("%Y%m%d")


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _fetch_net_purchase_by_investor(
    date_str: str,
    market: str,
    investor_name: str,
) -> pd.DataFrame:
    try:
        df = stock.get_market_net_purchases_of_equities_by_ticker(
            date_str,
            date_str,
            market,
            investor_name,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        return df

    except ValueError as e:
        if "Length mismatch" in str(e):
            logger.debug(
                f"빈 수급 데이터 스킵: date={date_str}, market={market}, investor={investor_name}"
            )
            return pd.DataFrame()

        raise


def fetch_all_investor_daily_trades(target_date: date) -> pd.DataFrame:
    date_str = _date_str(target_date)
    frames: list[pd.DataFrame] = []

    for investor_type, investor_name in INVESTORS.items():
        for market in ("KOSPI", "KOSDAQ"):
            try:
                df = _fetch_net_purchase_by_investor(
                    date_str=date_str,
                    market=market,
                    investor_name=investor_name,
                )

                if df is None or df.empty:
                    continue

                required_columns = ["순매수거래량", "순매수거래대금"]

                if not all(col in df.columns for col in required_columns):
                    logger.debug(
                        f"필수 컬럼 없음 스킵: date={target_date}, market={market}, "
                        f"investor={investor_name}, columns={list(df.columns)}"
                    )
                    continue

                df = df.rename(
                    columns={
                        "순매수거래량": "net_buy_volume",
                        "순매수거래대금": "net_buy_amount",
                    }
                )

                df.index.name = "ticker"

                temp = df.reset_index()[
                    ["ticker", "net_buy_volume", "net_buy_amount"]
                ].copy()

                temp["investor_type"] = investor_type
                temp["investor_name"] = investor_name
                temp["market"] = market

                frames.append(temp)

            except Exception as e:
                logger.warning(
                    f"투자자 수급 수집 스킵: {target_date}, "
                    f"{market}, {investor_name}, error={e}"
                )

    if not frames:
        logger.info(f"투자자 수급 데이터 없음: {target_date}")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    combined = combined[
        (combined["net_buy_volume"] != 0)
        | (combined["net_buy_amount"] != 0)
    ]

    combined["net_buy_volume"] = combined["net_buy_volume"].fillna(0).astype(int)
    combined["net_buy_amount"] = combined["net_buy_amount"].fillna(0).astype(int)

    logger.info(f"투자자 수급 수집 완료: {target_date}, {len(combined)}행")

    return combined[
        [
            "ticker",
            "investor_type",
            "investor_name",
            "net_buy_volume",
            "net_buy_amount",
        ]
    ]