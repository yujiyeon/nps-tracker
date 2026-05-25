'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getBacktestResult, runBacktest } from '@/lib/api'
import type { BacktestRequest } from '@/lib/types'

const DEFAULTS: BacktestRequest = {
  from_date: '2021-01-01',
  to_date: new Date().toISOString().slice(0, 10),
  min_consecutive_days: 3,
  min_net_buy_amount: 1_000_000_000,
  min_buy_intensity_pct: 0.1,
  holding_period_days: 20,
  entry_lag_days: 1,
  max_positions: 10,
  initial_capital: 10_000_000,
  transaction_cost_pct: 0.25,
}

export function BacktestForm() {
  const [form, setForm] = useState<BacktestRequest>(DEFAULTS)
  const [jobId, setJobId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: result } = useQuery({
    queryKey: ['backtest', jobId],
    queryFn: () => getBacktestResult(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 2000 : false
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    try {
      const res = await runBacktest(form)
      setJobId(res.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '오류가 발생했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const field = (
    label: string,
    key: keyof BacktestRequest,
    type: 'number' | 'date' = 'number',
    hint?: string,
  ) => (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-600">
        {label}
        {hint && <span className="ml-1 text-gray-400">({hint})</span>}
      </label>
      <input
        type={type}
        value={String(form[key])}
        onChange={(e) =>
          setForm((prev) => ({
            ...prev,
            [key]: type === 'number' ? Number(e.target.value) : e.target.value,
          }))
        }
        className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  )

  return (
    <div className="space-y-6">
      {/* 경고 박스 - 백테스팅 결과 페이지 상단 필수 (PROJECT_SPEC §3.3) */}
      <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-800">
        <p className="font-semibold">⚠️ 백테스팅 결과 주의사항</p>
        <p className="mt-1">
          과거 데이터 기반 시뮬레이션으로, 미래 수익을 보장하지 않습니다.
          실제 시장에서는 유동성, 시장 충격, 세금 등 추가 비용이 발생할 수 있습니다.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 font-semibold text-gray-900">전략 파라미터</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {field('시작일', 'from_date', 'date')}
          {field('종료일', 'to_date', 'date')}
          {field('최소 연속 매수일', 'min_consecutive_days', 'number', '일')}
          {field('최소 순매수금액', 'min_net_buy_amount', 'number', '원')}
          {field('최소 매수강도', 'min_buy_intensity_pct', 'number', '%')}
          {field('보유 기간', 'holding_period_days', 'number', '영업일')}
          {field('진입 지연일', 'entry_lag_days', 'number', 'look-ahead 방지')}
          {field('최대 동시 보유', 'max_positions', 'number', '종목')}
          {field('초기 자본', 'initial_capital', 'number', '원')}
          {field('거래 비용', 'transaction_cost_pct', 'number', '%')}
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-5 rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isSubmitting ? '제출 중...' : '백테스팅 실행'}
        </button>
        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
      </form>

      {/* 결과 */}
      {result && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 font-semibold text-gray-900">
            결과{' '}
            <span
              className={`ml-2 text-sm font-normal ${
                result.status === 'done'
                  ? 'text-green-600'
                  : result.status === 'failed'
                    ? 'text-red-500'
                    : 'text-yellow-500'
              }`}
            >
              {result.status === 'pending'
                ? '대기 중...'
                : result.status === 'running'
                  ? '실행 중...'
                  : result.status === 'done'
                    ? '완료'
                    : '실패'}
            </span>
          </h2>

          {result.status === 'done' && (
            <>
              {/* 통계 카드 */}
              <div className="mb-6 grid grid-cols-4 gap-4">
                {[
                  { label: '총 수익률', value: result.total_return_pct, suffix: '%' },
                  { label: 'CAGR', value: result.cagr_pct, suffix: '%' },
                  { label: '최대낙폭(MDD)', value: result.max_drawdown_pct, suffix: '%' },
                  { label: '샤프지수', value: result.sharpe_ratio, suffix: '' },
                  { label: 'KOSPI 초과수익', value: result.kospi_excess_return_pct, suffix: '%' },
                  { label: '승률', value: result.win_rate_pct, suffix: '%' },
                  { label: '총 거래 수', value: result.trades_count, suffix: '회' },
                ].map(({ label, value, suffix }) => (
                  <div key={label} className="rounded border border-gray-100 p-3">
                    <p className="text-xs text-gray-400">{label}</p>
                    <p className="mt-1 text-lg font-bold text-gray-900">
                      {value != null ? `${typeof value === 'number' && suffix === '%' ? value.toFixed(2) : value}${suffix}` : '-'}
                    </p>
                  </div>
                ))}
              </div>

              {/* 누적 수익률 곡선 */}
              {result.equity_curve && result.equity_curve.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-gray-700">자산 변화 곡선</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart
                      data={result.equity_curve}
                      margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis
                        dataKey="trade_date"
                        tick={{ fontSize: 10 }}
                        interval={Math.floor(result.equity_curve.length / 6)}
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        tickFormatter={(v) =>
                          v >= 100_000_000
                            ? `${(v / 100_000_000).toFixed(1)}억`
                            : `${(v / 10_000).toFixed(0)}만`
                        }
                      />
                      <Tooltip
                        formatter={(v) => {
                          const n = Number(v ?? 0)
                          return [
                            n >= 100_000_000
                              ? `${(n / 100_000_000).toFixed(2)}억원`
                              : `${(n / 10_000).toFixed(0)}만원`,
                            '자산',
                          ]
                        }}
                      />
                      <ReferenceLine
                        y={form.initial_capital}
                        stroke="#9ca3af"
                        strokeDasharray="4 2"
                        label={{ value: '초기자본', fontSize: 10 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="equity"
                        stroke="#ef4444"
                        dot={false}
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}

          {result.status === 'failed' && (
            <p className="text-sm text-red-500">{result.error_message ?? '알 수 없는 오류'}</p>
          )}

          {(result.status === 'pending' || result.status === 'running') && (
            <p className="text-sm text-gray-500">백테스팅 엔진은 Phase 4에서 구현 예정입니다.</p>
          )}
        </div>
      )}
    </div>
  )
}
