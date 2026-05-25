"""로컬 개발용 데모 데이터 (KRX 수집 없이 UI 확인용)."""
from datetime import date, datetime, timezone

from db.models import DailyOhlcv, NpsDailyTrade, Stock
from db.session import get_session

TRADE_DATE = date(2026, 5, 22)
PREV_DATE = date(2026, 5, 21)
NOW = datetime.now(timezone.utc)

STOCKS = [
    ("005930", "삼성전자", "KOSPI"),
    ("000660", "SK하이닉스", "KOSPI"),
    ("035420", "NAVER", "KOSPI"),
    ("051910", "LG화학", "KOSPI"),
    ("006400", "삼성SDI", "KOSPI"),
]

OHLCV = {
    "005930": (72000, 73500, 71500, 72800),
    "000660": (198000, 205000, 195000, 201000),
    "035420": (185000, 190000, 182000, 188000),
    "051910": (410000, 420000, 405000, 415000),
    "006400": (380000, 395000, 375000, 390000),
}

NPS_TRADES = [
    ("005930", 12_500_000_000, 170_000, 3, 0.12),
    ("000660", 8_200_000_000, 40_000, 5, 0.18),
    ("035420", 3_100_000_000, 16_000, 2, 0.09),
    ("051910", 1_800_000_000, 4_300, 1, 0.05),
    ("006400", -900_000_000, -2_300, 0, None),
]


def main() -> None:
    with get_session() as session:
        for ticker, name, market in STOCKS:
            session.merge(
                Stock(
                    ticker=ticker,
                    name=name,
                    market=market,
                    is_active=True,
                )
            )

        for ticker, (o, h, l, c) in OHLCV.items():
            for d, close in [(PREV_DATE, o), (TRADE_DATE, c)]:
                session.merge(
                    DailyOhlcv(
                        trade_date=d,
                        ticker=ticker,
                        open=o,
                        high=h,
                        low=l,
                        close=close,
                        volume=1_000_000,
                        trading_value=close * 1_000_000,
                        market_cap=close * 1_000_000_000,
                        shares_outstanding=1_000_000_000,
                    )
                )

        for ticker, amount, volume, consec, intensity in NPS_TRADES:
            session.merge(
                NpsDailyTrade(
                    trade_date=TRADE_DATE,
                    ticker=ticker,
                    net_buy_amount=amount,
                    net_buy_volume=volume,
                    consecutive_buy_days=consec,
                    buy_intensity_pct=intensity,
                    created_at=NOW,
                )
            )

        session.commit()
    print(f"seed ok: trade_date={TRADE_DATE}")


if __name__ == "__main__":
    main()
