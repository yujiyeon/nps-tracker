'use client'

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { NpsHoldingItem, NpsTradeTimeSeriesItem } from '@/lib/types'
import { formatAmount, formatNumber } from '@/lib/utils'

interface Props {
  items: NpsTradeTimeSeriesItem[]
  holdings: NpsHoldingItem[]
}

export function NpsTradesChart({ items, holdings }: Props) {
  // 차트용 데이터 (시간 순 정렬)
  const chartData = [...items].reverse().map((item) => ({
    date: item.trade_date.slice(5), // MM-DD
    fullDate: item.trade_date,
    close: item.close,
    netBuyAmount: item.net_buy_amount,
    // 억 단위로 변환 (y축 가독성)
    netBuyAmountOk: Math.round(item.net_buy_amount / 100_000_000),
  }))

  // 5% 보유 공시 날짜 집합 (참조선 표시)
  const holdingDates = new Set(holdings.map((h) => h.report_date))

  return (
    <div className="space-y-6">
      {/* 차트 1: 종가 + 연기금 순매수 (이중축) */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-gray-700">종가 & 연기금 순매수 (억원)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              interval={Math.floor(chartData.length / 8)}
            />
            {/* 왼쪽 축: 종가 */}
            <YAxis
              yAxisId="price"
              orientation="left"
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${formatNumber(v)}원`}
              width={80}
            />
            {/* 오른쪽 축: 순매수금액 */}
            <YAxis
              yAxisId="nps"
              orientation="right"
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}억`}
              width={60}
            />
            <Tooltip
              formatter={(value, name) => {
                if (name === '종가') return [`${formatNumber(value as number)}원`, name]
                if (name === '순매수') return [`${formatAmount((value as number) * 100_000_000)}`, name]
                return [value, name]
              }}
              labelFormatter={(label) => `${label}`}
            />
            <Legend />
            {/* 5% 보유 공시 마커 */}
            {chartData
              .filter((d) => holdingDates.has(d.fullDate))
              .map((d) => (
                <ReferenceLine
                  key={d.fullDate}
                  yAxisId="price"
                  x={d.date}
                  stroke="#8b5cf6"
                  strokeDasharray="4 2"
                  label={{ value: '5%', fontSize: 10, fill: '#8b5cf6' }}
                />
              ))}
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              name="종가"
              stroke="#374151"
              dot={false}
              strokeWidth={1.5}
            />
            <Bar
              yAxisId="nps"
              dataKey="netBuyAmountOk"
              name="순매수"
              fill="#3b82f6"
              opacity={0.7}
              // 순매도는 파란색, 순매수는 빨간색 (한국 관습)
              label={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* 차트 2: 누적 순매수 추이 */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-gray-700">누적 순매수 추이 (억원)</h3>
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart
            data={chartData.map((d, i) => ({
              ...d,
              cumulative: Math.round(
                chartData.slice(0, i + 1).reduce((sum, x) => sum + x.netBuyAmountOk, 0),
              ),
            }))}
            margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              interval={Math.floor(chartData.length / 8)}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}억`}
              width={60}
            />
            <Tooltip
              formatter={(value) => [`${value}억원`, '누적 순매수']}
            />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <Line
              type="monotone"
              dataKey="cumulative"
              name="누적 순매수"
              stroke="#ef4444"
              dot={false}
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
