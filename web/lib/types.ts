// API 응답 타입 정의 - api/schemas/*.py와 동기화 유지

export interface NpsTopTradeItem {
  rank: number
  ticker: string
  name: string
  market: string
  close: number | null
  change_pct: number | null
  net_buy_amount: number
  net_buy_volume: number
  consecutive_buy_days: number
  buy_intensity_pct: number | null
}

export interface NpsDailySummaryResponse {
  trade_date: string
  close_date: string           // 종가 기준일 (trade_date와 다를 수 있음)
  data_notice: string
  total_net_buy_amount: number
  net_buy_count: number
  net_sell_count: number
  items: NpsTopTradeItem[]
}

export interface NpsTradeTimeSeriesItem {
  trade_date: string
  net_buy_amount: number
  net_buy_volume: number
  consecutive_buy_days: number
  buy_intensity_pct: number | null
  close: number | null
  change_pct: number | null
}

export interface NpsTradeTimeSeriesResponse {
  ticker: string
  name: string
  items: NpsTradeTimeSeriesItem[]
}

export interface NpsHoldingItem {
  report_date: string
  filing_date: string
  shares: number
  holding_ratio: number
  purpose: string
  rcept_no: string
}

export interface NpsHoldingsResponse {
  ticker: string
  name: string
  items: NpsHoldingItem[]
}

export interface StockItem {
  ticker: string
  name: string
  market: string
  sector: string | null
  listing_date: string | null
  delisting_date: string | null
  is_active: boolean
}

export interface OhlcvItem {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  trading_value: number
  market_cap: number | null
  shares_outstanding: number | null
}

export interface StockDetailResponse {
  stock: StockItem
  ohlcv: OhlcvItem[]
}

export interface BacktestRequest {
  from_date: string
  to_date: string
  min_consecutive_days: number
  min_net_buy_amount: number
  min_buy_intensity_pct: number
  holding_period_days: number
  entry_lag_days: number
  max_positions: number
  initial_capital: number
  transaction_cost_pct: number
}

export interface EquityPoint {
  trade_date: string
  equity: number
}

export interface BacktestResultResponse {
  job_id: string
  status: 'pending' | 'running' | 'done' | 'failed'
  request: BacktestRequest | null
  total_return_pct: number | null
  cagr_pct: number | null
  kospi_excess_return_pct: number | null
  max_drawdown_pct: number | null
  sharpe_ratio: number | null
  win_rate_pct: number | null
  trades_count: number | null
  equity_curve: EquityPoint[] | null
  error_message: string | null
}
