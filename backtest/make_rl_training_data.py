import os
from sqlalchemy import create_engine, text
import pandas as pd

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://nps_user:localdevpassword@127.0.0.1:5432/nps_tracker"
)

OUTPUT_FILE = "nps_rl_training_data.csv"


def make_training_data():
    engine = create_engine(DATABASE_URL)

    sql = text("""
    WITH future_price AS (
        SELECT
            ticker,
            trade_date,
            close,

            LEAD(close, 20)
                OVER (
                    PARTITION BY ticker
                    ORDER BY trade_date
                ) AS future_close_20d

        FROM daily_ohlcv
    )

    SELECT
        n.trade_date,
        n.ticker,

        n.net_buy_amount,
        n.consecutive_buy_days,
        n.buy_intensity_pct,

        o.open,
        o.close,

        CASE
            WHEN f.future_close_20d IS NULL THEN NULL
            ELSE
                (f.future_close_20d - o.close) / o.close
        END AS future_return_20d

    FROM nps_daily_trades n

    JOIN daily_ohlcv o
      ON n.trade_date = o.trade_date
     AND n.ticker = o.ticker

    JOIN future_price f
      ON n.trade_date = f.trade_date
     AND n.ticker = f.ticker

    WHERE o.open > 0
      AND o.close > 0
      AND f.future_close_20d IS NOT NULL

    ORDER BY n.trade_date, n.ticker
    """)

    df = pd.read_sql(sql, engine)

    print("row count =", len(df))

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"생성 완료 : {OUTPUT_FILE}")


if __name__ == "__main__":
    make_training_data()