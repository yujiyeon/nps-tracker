CREATE TABLE IF NOT EXISTS investor_daily_scores (
    trade_date DATE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    investor_type VARCHAR(40) NOT NULL,
    investor_name VARCHAR(40) NOT NULL,

    net_buy_amount BIGINT NOT NULL DEFAULT 0,
    net_buy_volume BIGINT NOT NULL DEFAULT 0,
    consecutive_buy_days INTEGER NOT NULL DEFAULT 0,
    buy_intensity_pct DOUBLE PRECISION,

    amount_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    consecutive_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    intensity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    investor_score DOUBLE PRECISION NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (trade_date, ticker, investor_type)
);

CREATE TABLE IF NOT EXISTS daily_top_recommendations (
    trade_date DATE NOT NULL,
    rank_no INTEGER NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100),

    consensus_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    foreign_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    co_buy_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    final_score DOUBLE PRECISION NOT NULL DEFAULT 0,

    positive_institution_count INTEGER NOT NULL DEFAULT 0,

    pension_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    trust_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    insurance_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    private_equity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    bank_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    finance_investment_score DOUBLE PRECISION NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (trade_date, rank_no)
);

CREATE INDEX IF NOT EXISTS idx_daily_top_recommendations_date_score
ON daily_top_recommendations (trade_date, final_score DESC);

CREATE INDEX IF NOT EXISTS idx_investor_daily_scores_date_ticker
ON investor_daily_scores (trade_date, ticker);