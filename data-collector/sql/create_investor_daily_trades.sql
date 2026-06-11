CREATE TABLE IF NOT EXISTS investor_daily_trades (
    trade_date DATE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    investor_type VARCHAR(40) NOT NULL,
    investor_name VARCHAR(40) NOT NULL,

    net_buy_volume BIGINT NOT NULL DEFAULT 0,
    net_buy_amount BIGINT NOT NULL DEFAULT 0,

    consecutive_buy_days INTEGER NOT NULL DEFAULT 0,
    buy_intensity_pct DOUBLE PRECISION,
    buy_amount_per_price DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (trade_date, ticker, investor_type)
);

CREATE INDEX IF NOT EXISTS idx_investor_daily_trades_date
ON investor_daily_trades (trade_date);

CREATE INDEX IF NOT EXISTS idx_investor_daily_trades_ticker_date
ON investor_daily_trades (ticker, trade_date);

CREATE INDEX IF NOT EXISTS idx_investor_daily_trades_type_date
ON investor_daily_trades (investor_type, trade_date);

CREATE TABLE IF NOT EXISTS investor_collection_logs (
    job_type VARCHAR(50) NOT NULL,
    target_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (job_type, target_date)
);