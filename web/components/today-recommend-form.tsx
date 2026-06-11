'use client'

import { useState } from 'react'

type RecommendResult = {
  request_date?: string
  trade_date?: string
  recommended_ticker?: string | null
  recommended_name?: string | null
  action?: number
  entry_price?: number | null
  holding_period_days?: number
  message: string
}

export function TodayRecommendForm() {
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
      const API_BASE_URL =process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
      
      const res = await fetch(`${API_BASE_URL}/api/backtest/recommend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            min_consecutive_days: minConsecutiveDays,
            min_net_buy_amount: minNetBuyAmount,
            min_buy_intensity_pct: minBuyIntensityPct,
            holding_period_days: holdingPeriodDays,
            entry_lag_days: 1,
            max_positions: 10,
            initial_capital: 10000000,
            transaction_cost_pct: 0.25,
        }),
      })
      console.log('추천요청 payload: ',res.body)
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
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
        국민연금 매수 후보 중 DQN이 오늘 기준으로 1개 종목을 선택합니다.
        미래 수익률을 보장하는 기능은 아니며, 학습된 정책 기반 추천 결과입니다.
      </div>
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <div className="mb-3 text-base font-semibold">
            🤖 DQN 기반 오늘의 추천종목
        </div>

        <p className="mb-4">
            국민연금 매수 후보 종목 중에서 AI(DQN 강화학습)가
            가장 유망하다고 판단한 종목 1개를 추천합니다.
            <br />
            <span className="font-medium text-red-600">
            ※ 미래 수익률을 보장하지 않으며 투자 판단의 참고용입니다.
            </span>
        </p>

        <div className="space-y-2">

            <div>
            📅 <span className="font-semibold">최소 연속 매수일</span>
            <br />
            → 국민연금이 며칠 연속으로 매수한 종목만 후보로 선정합니다.
            </div>

            <div>
            💰 <span className="font-semibold">최소 순매수금액</span>
            <br />
            → 국민연금이 일정 금액 이상 순매수한 종목만 후보로 선정합니다.
            </div>

            <div>
            📈 <span className="font-semibold">최소 매수강도</span>
            <br />
            → 국민연금의 매수세가 강한 종목만 후보로 선정합니다.
            <br />
            <span className="text-xs text-gray-500">
                매수강도(%) = 국민연금 순매수금액 ÷ 해당 종목 시가총액 × 100
            </span>
            </div>

            <div>
            ⏳ <span className="font-semibold">보유기간</span>
            <br />
            → 추천 종목을 몇 영업일 동안 보유할지 설정합니다.
            <br />
            <span className="text-gray-500 text-xs">
                • 5일 : 단기 투자
                <br />
                • 20일 : 한 달 투자
                <br />
                • 60일 : 중기 투자
            </span>
            </div>

        </div>
        </div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div>
        <label>최소 연속 매수일</label>
        <input
            type="number"
            value={minConsecutiveDays}
            onChange={(e) =>
            setMinConsecutiveDays(Number(e.target.value))
            }
            className="w-full border rounded px-2 py-1"
        />
        </div>

        <div>
        <label>최소 순매수금액</label>
        <input
            type="number"
            value={minNetBuyAmount}
            onChange={(e) =>
            setMinNetBuyAmount(Number(e.target.value))
            }
            className="w-full border rounded px-2 py-1"
        />
        </div>

        <div>
        <label>최소 매수강도(%)</label>
        <input
            type="number"
            step="0.1"
            value={minBuyIntensityPct}
            onChange={(e) =>
            setMinBuyIntensityPct(Number(e.target.value))
            }
            className="w-full border rounded px-2 py-1"
        />
        </div>

        <div>
        <label>보유기간(영업일)</label>
        <input
            type="number"
            value={holdingPeriodDays}
            onChange={(e) =>
            setHoldingPeriodDays(Number(e.target.value))
            }
            className="w-full border rounded px-2 py-1"
        />
        </div>

        </div>
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <button
          onClick={handleRecommend}
          disabled={isLoading}
          className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? '추천 조회 중...' : '오늘의 추천종목 조회'}
        </button>

        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}

        {result && (
          <div className="mt-6 rounded border border-gray-100 p-4">
            <h2 className="mb-3 font-semibold text-gray-900">DQN 추천 결과</h2>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400">요청일</p>
                <p className="font-medium">{result.request_date ?? '-'}</p>
              </div>
              <div>
                <p className="text-gray-400">추천 기준일</p>
                <p className="font-medium">{result.trade_date ?? '-'}</p>
              </div>
              <div>
                <p className="text-gray-400">추천 종목코드</p>
                <p className="font-bold text-blue-600">
                  {result.recommended_ticker ?? '추천 없음'}
                </p>
              </div>
              <div>
                <p className="text-gray-400">추천 종목명</p>
                <p className="font-bold text-blue-600">
                    {result.recommended_name ?? '-'}
                </p>
              </div>
              <div>
                <p className="text-gray-400">선택 Action</p>
                <p className="font-medium">{result.action ?? '-'}</p>
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
                <p className="font-medium">
                  {result.holding_period_days ?? '-'}영업일
                </p>
              </div>
            </div>

            <p className="mt-4 text-sm text-gray-500">{result.message}</p>
          </div>
        )}
      </div>
    </div>
  )
}