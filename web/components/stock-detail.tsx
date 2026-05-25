'use client'

import { useQuery } from '@tanstack/react-query'
import { getNpsHoldings, getNpsTrades } from '@/lib/api'
import type { StockDetailResponse } from '@/lib/types'
import { formatAmount, formatChangePct, formatDate, formatNumber } from '@/lib/utils'
import { NpsTradesChart } from './nps-trades-chart'

interface Props {
  ticker: string
  initialData: StockDetailResponse
}

export function StockDetail({ ticker, initialData }: Props) {
  const { stock, ohlcv } = initialData
  const latestOhlcv = ohlcv[0]

  const { data: trades } = useQuery({
    queryKey: ['nps-trades', ticker],
    queryFn: () => getNpsTrades(ticker, {}),
    staleTime: 60 * 60 * 1000,
  })

  const { data: holdings } = useQuery({
    queryKey: ['nps-holdings', ticker],
    queryFn: () => getNpsHoldings(ticker),
    staleTime: 60 * 60 * 1000,
  })

  const prevClose = ohlcv[1]?.close
  const changePct =
    latestOhlcv && prevClose
      ? ((latestOhlcv.close - prevClose) / prevClose) * 100
      : null
  const cp = formatChangePct(changePct)

  return (
    <div className="space-y-6">
      {/* 종목 정보 카드 */}
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{stock.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-sm text-gray-500">{ticker}</span>
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                {stock.market}
              </span>
              {stock.sector && (
                <span className="text-xs text-gray-400">{stock.sector}</span>
              )}
            </div>
          </div>
          {latestOhlcv && (
            <div className="text-right">
              <p className="text-2xl font-bold text-gray-900">
                {formatNumber(latestOhlcv.close)}원
              </p>
              <p className={`text-sm ${cp.className}`}>{cp.text}</p>
              <p className="mt-0.5 text-xs text-gray-400">
                {formatDate(latestOhlcv.trade_date)} 기준
              </p>
            </div>
          )}
        </div>
        {latestOhlcv && (
          <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-100 pt-4 text-sm">
            <div>
              <p className="text-xs text-gray-400">시가총액</p>
              <p className="font-medium">
                {latestOhlcv.market_cap ? formatAmount(latestOhlcv.market_cap) : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">거래대금</p>
              <p className="font-medium">{formatAmount(latestOhlcv.trading_value)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">거래량</p>
              <p className="font-medium">{formatNumber(latestOhlcv.volume)}주</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">상장주식수</p>
              <p className="font-medium">
                {latestOhlcv.shares_outstanding
                  ? formatNumber(latestOhlcv.shares_outstanding)
                  : '-'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 차트 */}
      {trades && (
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <NpsTradesChart items={trades.items} holdings={holdings?.items ?? []} />
        </div>
      )}

      {/* NPS 매매 내역 테이블 */}
      {trades && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-5 py-3">
            <h2 className="font-semibold text-gray-900">연기금 매매 내역</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-3 text-left">날짜</th>
                  <th className="px-4 py-3 text-right">종가</th>
                  <th className="px-4 py-3 text-right">등락률</th>
                  <th className="px-4 py-3 text-right">순매수금액</th>
                  <th className="px-4 py-3 text-right">순매수수량</th>
                  <th className="px-4 py-3 text-center">연속매수일</th>
                  <th className="px-4 py-3 text-right">매수강도</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {trades.items.slice(0, 60).map((item) => {
                  const icp = formatChangePct(item.change_pct)
                  return (
                    <tr key={item.trade_date} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 text-gray-600">{item.trade_date}</td>
                      <td className="px-4 py-2.5 text-right">
                        {item.close != null ? `${formatNumber(item.close)}원` : '-'}
                      </td>
                      <td className={`px-4 py-2.5 text-right ${icp.className}`}>{icp.text}</td>
                      <td className="px-4 py-2.5 text-right font-medium">
                        {formatAmount(item.net_buy_amount)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-600">
                        {formatNumber(item.net_buy_volume)}주
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {item.consecutive_buy_days > 0 ? (
                          <span className="text-orange-600 font-medium">
                            {item.consecutive_buy_days}일
                          </span>
                        ) : '-'}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-500">
                        {item.buy_intensity_pct != null
                          ? `${item.buy_intensity_pct.toFixed(3)}%`
                          : '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5% 보유 공시 이력 */}
      {holdings && holdings.items.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-5 py-3">
            <h2 className="font-semibold text-gray-900">5% 이상 보유 공시 이력 (DART)</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">보고 기준일</th>
                <th className="px-4 py-3 text-left">공시일</th>
                <th className="px-4 py-3 text-right">보유주식수</th>
                <th className="px-4 py-3 text-right">보유비율</th>
                <th className="px-4 py-3 text-left">목적</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {holdings.items.map((h) => (
                <tr key={h.rcept_no} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-gray-600">{h.report_date}</td>
                  <td className="px-4 py-2.5 text-gray-600">{h.filing_date}</td>
                  <td className="px-4 py-2.5 text-right">{formatNumber(h.shares)}주</td>
                  <td className="px-4 py-2.5 text-right font-medium">{h.holding_ratio}%</td>
                  <td className="px-4 py-2.5 text-gray-600">{h.purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
