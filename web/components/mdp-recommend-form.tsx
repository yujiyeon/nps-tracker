'use client'

import { useState } from 'react'

type RecommendResult = {
  request_date?: string
  trade_date?: string
  close_date?: string
  mode?: string
  recommended_ticker?: string | null
  recommended_name?: string | null
  action?: number
  entry_price?: number | null
  holding_period_days?: number
  candidates?: string[]
  message: string
}

export function MdpRecommendForm() {
  const [result, setResult] = useState<RecommendResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [minConsecutiveDays, setMinConsecutiveDays] = useState(3)
  const [minNetBuyAmount, setMinNetBuyAmount] = useState(1000000000)
  const [minBuyIntensityPct, setMinBuyIntensityPct] = useState(0.1)
  const [holdingPeriodDays, setHoldingPeriodDays] = useState(20)

  const handleRecommend = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      
      const res = await fetch(`${API_BASE_URL}/api/backtest/recommend-mdp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          min_consecutive_days: minConsecutiveDays,
          min_net_buy_amount: minNetBuyAmount,
          min_buy_intensity_pct: minBuyIntensityPct,
          holding_period_days: holdingPeriodDays,
        }),
      })
      if (!res.ok) {
        throw new Error('추천 종목 조회에 실패했습니다.')
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
      <div className="rounded-lg border border-purple-200 bg-purple-50 p-4 text-sm text-purple-900">
        <div className="mb-3 text-base font-semibold">
          🧠 포트폴리오 강화학습(MDP) 추천 — 실험 기능
        </div>
        <p className="mb-2">
          기존 추천이 &lsquo;매 시점 독립적으로 1종목&rsquo;을 고르는 방식이라면,
          이 기능은 <span className="font-semibold">현금·보유종목·평가손익을 상태에 포함</span>하고
          <span className="font-semibold"> 일일 수익률을 보상</span>으로 학습한
          포트폴리오 DQN(MDP)이 종목을 선택합니다.
        </p>
        <p className="text-xs text-gray-600">
          ※ 모델이 &lsquo;관망&rsquo;을 선택하면 오늘은 추천 종목이 없을 수 있습니다.
          미래 수익률을 보장하지 않으며 투자 판단의 참고용입니다.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-2">
        <div>
          <label>최소 연속 매수일</label>
          <input
            type="number"
            value={minConsecutiveDays}
            onChange={(e) => setMinConsecutiveDays(Number(e.target.value))}
            className="w-full border rounded px-2 py-1"
          />
        </div>
        <div>
          <label>최소 순매수금액</label>
          <input
            type="number"
            value={minNetBuyAmount}
            onChange={(e) => setMinNetBuyAmount(Number(e.target.value))}
            className="w-full border rounded px-2 py-1"
          />
        </div>
        <div>
          <label>최소 매수강도(%)</label>
          <input
            type="number"
            step="0.1"
            value={minBuyIntensityPct}
            onChange={(e) => setMinBuyIntensityPct(Number(e.target.value))}
            className="w-full border rounded px-2 py-1"
          />
        </div>
        <div>
          <label>보유기간(영업일)</label>
          <input
            type="number"
            value={holdingPeriodDays}
            onChange={(e) => setHoldingPeriodDays(Number(e.target.value))}
            className="w-full border rounded px-2 py-1"
          />
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <button
          onClick={handleRecommend}
          disabled={isLoading}
          className="rounded bg-purple-600 px-6 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {isLoading ? '추천 조회 중...' : 'MDP 추천종목 조회'}
        </button>

        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}

        {result && (
          <div className="mt-6 rounded border border-gray-100 p-4">
            <h2 className="mb-3 font-semibold text-gray-900">포트폴리오 DQN 추천 결과</h2>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400">추천 기준일</p>
                <p className="font-medium">{result.trade_date ?? '-'}</p>
              </div>
              <div>
                <p className="text-gray-400">선택 Action</p>
                <p className="font-medium">{result.action ?? '-'}</p>
              </div>
              <div>
                <p className="text-gray-400">추천 종목코드</p>
                <p className="font-bold text-purple-700">
                  {result.recommended_ticker ?? '관망(추천 없음)'}
                </p>
              </div>
              <div>
                <p className="text-gray-400">추천 종목명</p>
                <p className="font-bold text-purple-700">
                  {result.recommended_name ?? '-'}
                </p>
              </div>
              <div>
                <p className="text-gray-400">진입 기준가</p>
                <p className="font-medium">
                  {result.entry_price != null
                    ? `${result.entry_price.toLocaleString()}원`
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-gray-400">보유 가정</p>
                <p className="font-medium">{result.holding_period_days ?? '-'}영업일</p>
              </div>
            </div>

            <p className="mt-4 text-sm text-gray-500">{result.message}</p>
          </div>
        )}
      </div>
    </div>
  )
}
