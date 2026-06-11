'use client'

import { Fragment, useState } from 'react'

type RecommendationItem = {
  trade_date: string
  rank_no: number
  ticker: string
  stock_name?: string | null

  consensus_score: number
  foreign_score: number
  co_buy_score: number
  final_score: number
  positive_institution_count: number

  pension_score: number
  trust_score: number
  insurance_score: number
  private_equity_score: number
  bank_score: number
  finance_investment_score: number
}

type RecommendationResponse = {
  trade_date?: string | null
  total_count: number
  items: RecommendationItem[]
}

function formatScore(value: number | null | undefined) {
  if (value == null) return '-'
  return value.toFixed(2)
}

function rankLabel(rank: number) {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return rank
}

function finalScoreBadgeClass(score: number) {
  if (score >= 70) return 'border-red-200 bg-red-50 text-red-600'
  if (score >= 60) return 'border-orange-200 bg-orange-50 text-orange-600'
  if (score >= 50) return 'border-yellow-200 bg-yellow-50 text-yellow-700'
  return 'border-gray-200 bg-gray-50 text-gray-500'
}

function coBuyCountBadgeClass(count: number) {
  if (count >= 5) return 'border-red-200 bg-red-50 text-red-600'
  if (count >= 4) return 'border-yellow-200 bg-yellow-50 text-yellow-700'
  if (count >= 2) return 'border-orange-200 bg-orange-50 text-orange-600'
  return 'border-gray-200 bg-gray-50 text-gray-500'
}

function getRecommendReasons(item: RecommendationItem) {
  const reasons: string[] = []

  if (item.positive_institution_count >= 5) {
    reasons.push(`기관 ${item.positive_institution_count}개 동시매수`)
  } else if (item.positive_institution_count >= 3) {
    reasons.push(`기관 ${item.positive_institution_count}개 매수`)
  }

  if (item.foreign_score >= 70) {
    reasons.push('외국인 동행')
  }

  if (item.pension_score >= 70) {
    reasons.push('국민연금 강세')
  }

  if (item.consensus_score >= 70) {
    reasons.push('기관 컨센서스 우수')
  }

  return reasons.slice(0, 3)
}

function ScoreBar({ value }: { value: number }) {
    const width = Math.max(0, Math.min(100, value))
  
    return (
      <div className="flex items-center justify-end gap-2">
        <div className="h-2 w-24 overflow-hidden rounded-full bg-blue-50">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-400 to-indigo-500"
            style={{ width: `${width}%` }}
          />
        </div>
        <span className="w-11 text-right font-semibold text-blue-700">
          {formatScore(value)}
        </span>
      </div>
    )
  }

export function InvestorConsensusRecommendForm() {
  const [tradeDate, setTradeDate] = useState('')
  const [limit, setLimit] = useState(50)
  const [result, setResult] = useState<RecommendationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)
  const items = Array.isArray(result?.items) ? result.items : []
  const top3 = items.slice(0, 3)

  const handleSearch = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      params.set('limit', String(limit))

      if (tradeDate) {
        params.set('trade_date', tradeDate)
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

      const res = await fetch(
        `${API_BASE_URL}/api/investor-recommendations/top?${params.toString()}`
      )

      if (!res.ok) {
        throw new Error('기관 컨센서스 추천 종목 조회에 실패했습니다.')
      }

      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900">
        <div className="mb-2 text-base font-semibold">
          🏦 기관 컨센서스 기반 TOP 50 추천종목
        </div>
        <p>
          국민연금, 투신, 보험, 사모펀드, 은행, 금융투자의 기관별 점수에
          가중치를 적용하고 외국인 점수와 동시매수 기관 수를 함께 반영합니다.
        </p>

        <div className="mt-3 rounded-md bg-white/70 p-3">
          <p className="text-xs font-semibold text-gray-700">점수 산정 기준</p>
          <ul className="mt-2 space-y-1 text-xs text-gray-600">
            <li>
              • 최종점수 = 기관컨센서스(75%) + 외국인점수(15%) +
              동시매수점수(10%)
            </li>
            <li>
              • 기관컨센서스 = 국민연금(30%) + 투신(25%) + 보험(15%) +
              사모펀드(15%) + 은행(5%) + 금융투자(10%)
            </li>
            <li>
              • 기관별점수 = 순매수금액점수(50%) + 연속매수일수점수(30%) +
              매수강도점수(20%)
            </li>
            <li>
              * 순매수금액 = 매수금액 - 매도금액 으로 매도금액이 더 클 시 점수는 0점으로 산정될 수 있습니다.
            </li>
          </ul>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="mb-4 grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              추천 기준일
            </label>
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-gray-400">
              비워두면 가장 최근 추천일 기준으로 조회합니다.
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              조회 건수
            </label>
            <input
                type="number"
                value={limit}
                min={1}
                max={50}
                onChange={(e) => {
                    const value = Number(e.target.value)

                    if (value > 50) {
                    setLimit(50)
                    } else if (value < 1) {
                    setLimit(1)
                    } else {
                    setLimit(value)
                    }
                }}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="flex items-center mt-[4px]">
            <button
              onClick={handleSearch}
              disabled={isLoading}
              className="rounded bg-gray-900 px-6 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
            >
              {isLoading ? '조회 중...' : '추천종목 조회'}
            </button>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-red-500">{error}</p>}

        {result && (
          <>
            <div className="mb-4 text-sm text-gray-600">
              추천 기준일:{' '}
              <span className="font-semibold text-gray-900">
                {result.trade_date ?? '-'}
              </span>
              {' '} / 조회 건수:{' '}
              <span className="font-semibold text-gray-900">
                {result.total_count}
              </span>
            </div>

            {top3.length > 0 && (
              <div className="mb-5 grid grid-cols-3 gap-4">
                {top3.map((item) => {
                  const reasons = getRecommendReasons(item)

                  return (
                    <div
                      key={`top-${item.ticker}`}
                      className="rounded-xl border border-gray-200 bg-gradient-to-br from-white to-gray-50 p-4 shadow-sm"
                    >
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-xl">
                          {rankLabel(item.rank_no)}
                        </span>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs font-bold ${finalScoreBadgeClass(
                            item.final_score
                          )}`}
                        >
                          {formatScore(item.final_score)}
                        </span>
                      </div>

                      <div className="font-bold text-gray-900">
                        {item.stock_name ?? '-'}
                      </div>
                      <div className="mt-0.5 text-xs text-gray-400">
                        {item.ticker}
                      </div>

                      <div className="mt-3 flex flex-wrap gap-1">
                        {reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>

                      <div className="mt-3 text-xs text-gray-500">
                        기관컨센서스 {formatScore(item.consensus_score)} ·
                        동시매수 {item.positive_institution_count}개
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <table className="min-w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 text-xs text-gray-500">
                <tr>
                    <th className="px-4 py-3 text-center">순위</th>
                    <th className="px-4 py-3 text-left">종목</th>
                    <th className="px-4 py-3 text-left">추천사유</th>
                    <th className="px-4 py-3 text-right">최종점수</th>
                    <th className="px-4 py-3 text-right">기관컨센서스</th>
                    <th className="px-4 py-3 text-center">동시매수</th>
                </tr>
              </thead>

                <tbody className="divide-y divide-gray-100">
                {items.map((item) => {
                    const reasons = getRecommendReasons(item)
                    const isExpanded = expandedTicker === item.ticker

                    return (
                        <Fragment key={`${item.trade_date}-${item.rank_no}-${item.ticker}`}>
                        <tr
                            onClick={() =>
                            setExpandedTicker(isExpanded ? null : item.ticker)
                            }
                            className={`cursor-pointer transition-colors ${
                            item.rank_no <= 3
                                ? 'bg-blue-50/50 hover:bg-blue-50'
                                : 'hover:bg-gray-50'
                            }`}
                        >
                            <td className="px-4 py-3 text-center font-medium text-gray-400">
                            {rankLabel(item.rank_no)}
                            </td>

                            <td className="px-4 py-3">
                            <div className="font-semibold text-gray-900">
                                {item.stock_name ?? '-'}
                            </div>
                            <div className="mt-0.5 text-xs text-gray-400">
                                {item.ticker}
                            </div>
                            </td>

                            <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                                {reasons.length > 0 ? (
                                reasons.map((reason) => (
                                    <span
                                    key={reason}
                                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600"
                                    >
                                    {reason}
                                    </span>
                                ))
                                ) : (
                                <span className="text-xs text-gray-300">-</span>
                                )}
                            </div>
                            </td>

                            <td className="px-4 py-3 text-right">
                            <span
                                className={`rounded-full border px-2 py-0.5 text-xs font-bold ${finalScoreBadgeClass(
                                item.final_score
                                )}`}
                            >
                                {formatScore(item.final_score)}
                            </span>
                            </td>

                            <td className="px-4 py-3 text-right">
                            <ScoreBar value={item.consensus_score} />
                            </td>

                            <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-2">
                                {item.positive_institution_count > 0 ? (
                                <span
                                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${coBuyCountBadgeClass(
                                    item.positive_institution_count
                                    )}`}
                                >
                                    {item.positive_institution_count}개
                                </span>
                                ) : (
                                <span className="text-gray-300">-</span>
                                )}

                                <span className="text-xs text-gray-300">
                                {isExpanded ? '▲' : '▼'}
                                </span>
                            </div>
                            </td>
                        </tr>

                        {isExpanded && (
                            <tr key={`${item.trade_date}-${item.ticker}-detail`}>
                            <td colSpan={6} className="bg-gray-50 px-6 py-4">
                                <div className="grid grid-cols-6 gap-3">
                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">국민연금</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.pension_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">외국인</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.foreign_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">투신</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.trust_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">보험</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.insurance_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">사모펀드</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.private_equity_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">은행</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.bank_score)}
                                    </p>
                                </div>

                                <div className="rounded-lg border border-gray-200 bg-white p-3">
                                    <p className="text-xs text-gray-400">금융투자</p>
                                    <p className="mt-1 text-lg font-bold text-gray-900">
                                    {formatScore(item.finance_investment_score)}
                                    </p>
                                </div>
                                </div>
                            </td>
                            </tr>
                        )}
                        </Fragment>
                    )
                    })}

                  {items.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-10 text-center text-sm text-gray-400"
                      >
                        조회된 추천 종목이 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}