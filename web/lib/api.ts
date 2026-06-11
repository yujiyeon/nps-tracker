import type {
  BacktestRequest,
  BacktestResultResponse,
  NpsDailySummaryResponse,
  NpsHoldingsResponse,
  NpsTradeTimeSeriesResponse,
  StockDetailResponse,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail ?? `API 오류: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function getNpsDaily(params: {
  date?: string
  limit?: number
  market?: string
}): Promise<NpsDailySummaryResponse> {
  const qs = new URLSearchParams()
  if (params.date) qs.set('trade_date', params.date)
  if (params.limit) qs.set('limit', String(params.limit))
  if (params.market) qs.set('market', params.market)
  return apiFetch<NpsDailySummaryResponse>(`/api/nps/daily?${qs}`)
}

export function getNpsTrades(
  ticker: string,
  params: { from_date?: string; to_date?: string },
): Promise<NpsTradeTimeSeriesResponse> {
  const qs = new URLSearchParams()
  if (params.from_date) qs.set('from_date', params.from_date)
  if (params.to_date) qs.set('to_date', params.to_date)
  return apiFetch<NpsTradeTimeSeriesResponse>(`/api/nps/stocks/${ticker}/trades?${qs}`)
}

export function getNpsHoldings(ticker: string): Promise<NpsHoldingsResponse> {
  return apiFetch<NpsHoldingsResponse>(`/api/nps/stocks/${ticker}/holdings`)
}

export function getStockDetail(ticker: string): Promise<StockDetailResponse> {
  return apiFetch<StockDetailResponse>(`/api/stocks/${ticker}`)
}

export function runBacktest(req: BacktestRequest): Promise<BacktestResultResponse> {
  return apiFetch<BacktestResultResponse>('/api/backtest', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export function getBacktestResult(jobId: string): Promise<BacktestResultResponse> {
  return apiFetch<BacktestResultResponse>(`/api/backtest/${jobId}`)
}

export function getInvestorRecommendations(params: {
  trade_date?: string
  limit?: number
}) {
  const qs = new URLSearchParams()

  if (params.trade_date) {
    qs.set('trade_date', params.trade_date)
  }

  if (params.limit) {
    qs.set('limit', String(params.limit))
  }

  // Next.js API route 프록시를 경유 — 브라우저가 백엔드를 직접 호출하지 않아 CORS/내부URL 문제 회피
  const path = `/api/investor-recommendations/top?${qs.toString()}`

  if (typeof window === 'undefined') {
    // 서버 사이드: 백엔드 직접 호출
    return apiFetch(path)
  }

  // 클라이언트 사이드: Next.js 프록시 경유 (same-origin)
  return fetch(path).then(async (res) => {
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(error.detail ?? `API 오류: ${res.status}`)
    }
    return res.json()
  })
}