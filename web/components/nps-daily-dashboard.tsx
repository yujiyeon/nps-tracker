'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { getNpsDaily } from '@/lib/api'
import type { NpsDailySummaryResponse } from '@/lib/types'
import {
  consecutiveDaysBadgeClass,
  formatAmount,
  formatChangePct,
  formatDate,
  formatNumber,
  getPreviousBusinessDay,
} from '@/lib/utils'

interface Props {
  initialData: NpsDailySummaryResponse
  defaultDate?: string
}

export function NpsDailyDashboard({ initialData, defaultDate }: Props) {
  const router = useRouter()
  const [selectedDate, setSelectedDate] = useState(defaultDate ?? getPreviousBusinessDay())
  const [market, setMarket] = useState<string>('')
  const [sortKey, setSortKey] = useState<'net_buy_amount' | 'consecutive_buy_days'>('net_buy_amount')

  const { data, isLoading } = useQuery({
    queryKey: ['nps-daily', selectedDate, market],
    queryFn: () => getNpsDaily({ date: selectedDate, limit: 50, market: market || undefined }),
    initialData: selectedDate === (defaultDate ?? initialData.trade_date) && !market ? initialData : undefined,
    staleTime: 60 * 60 * 1000,
  })

  const items = [...(data?.items ?? [])].sort((a, b) =>
    sortKey === 'consecutive_buy_days'
      ? b.consecutive_buy_days - a.consecutive_buy_days
      : b.net_buy_amount - a.net_buy_amount,
  )

  return (
    <div>
      {/* 상단 요약 */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">연기금 순거래 합계</p>
          <p
            className={`mt-1 text-xl font-bold ${
              !data
                ? 'text-gray-900'
                : data.total_net_buy_amount > 0
                  ? 'text-red-500'
                  : data.total_net_buy_amount < 0
                    ? 'text-blue-500'
                    : 'text-gray-500'
            }`}
          >
            {data ? formatAmount(data.total_net_buy_amount) : '-'}
          </p>
          <p className="mt-0.5 text-xs text-gray-400">
            {data && data.total_net_buy_amount < 0 ? '순매도 우위' : data ? '순매수 우위' : ''}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">순매수 종목 수</p>
          <p className="mt-1 text-xl font-bold text-red-500">{data?.net_buy_count ?? '-'}종목</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">순매도 종목 수</p>
          <p className="mt-1 text-xl font-bold text-blue-500">{data?.net_sell_count ?? '-'}종목</p>
        </div>
      </div>

      {/* 필터 바 */}
      <div className="mb-4 flex items-center gap-3">
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={market}
          onChange={(e) => setMarket(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">전체 시장</option>
          <option value="KOSPI">KOSPI</option>
          <option value="KOSDAQ">KOSDAQ</option>
        </select>
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as typeof sortKey)}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="net_buy_amount">순매수금액 순</option>
          <option value="consecutive_buy_days">연속매수일 순</option>
        </select>
        {data && (
          <span className="ml-auto text-xs text-gray-400">
            NPS: {formatDate(data.trade_date)} 기준
            {data.close_date !== data.trade_date && (
              <span className="ml-1">| 종가: {formatDate(data.close_date)}</span>
            )}
          </span>
        )}
      </div>

      {/* 테이블 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        {isLoading && (
          <div className="flex h-32 items-center justify-center text-sm text-gray-400">
            불러오는 중...
          </div>
        )}
        {!isLoading && (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200 bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-4 py-3 text-right">순위</th>
                <th className="px-4 py-3 text-left">종목명</th>
                <th className="px-4 py-3 text-center">시장</th>
                <th className="px-4 py-3 text-right">종가</th>
                <th className="px-4 py-3 text-right">등락률</th>
                <th className="px-4 py-3 text-right">순매수금액</th>
                <th className="px-4 py-3 text-center">연속매수일</th>
                <th className="px-4 py-3 text-right">매수강도</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => {
                const cp = formatChangePct(item.change_pct)
                return (
                  <tr
                    key={item.ticker}
                    onClick={() => router.push(`/stocks/${item.ticker}`)}
                    className="cursor-pointer transition-colors hover:bg-blue-50"
                  >
                    <td className="px-4 py-3 text-right text-gray-400">{item.rank}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-gray-900">{item.name}</span>
                      <span className="ml-1.5 text-xs text-gray-400">{item.ticker}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                        {item.market}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      {item.close != null ? `${formatNumber(item.close)}원` : '-'}
                    </td>
                    <td className={`px-4 py-3 text-right ${cp.className}`}>{cp.text}</td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      {formatAmount(item.net_buy_amount)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {item.consecutive_buy_days > 0 ? (
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${consecutiveDaysBadgeClass(item.consecutive_buy_days)}`}
                        >
                          {item.consecutive_buy_days}일
                        </span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {item.buy_intensity_pct != null
                        ? `${item.buy_intensity_pct.toFixed(3)}%`
                        : '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
