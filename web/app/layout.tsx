import type { Metadata } from 'next'
import { Geist } from 'next/font/google'
import './globals.css'
import { Disclaimer } from '@/components/disclaimer'
import { Providers } from './providers'

const geist = Geist({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'NPS Tracker - 연기금 매매 추적',
  description:
    '한국 주식시장 연기금(국민연금 등) 매매 동향 분석. 순매수 상위 종목 및 시계열 데이터 제공.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className={geist.className}>
        <Providers>
          <nav className="border-b border-gray-200 bg-white">
            <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
              <a href="/" className="text-lg font-bold text-gray-900">
                NPS Tracker
              </a>
              <a href="/" className="text-sm text-gray-600 hover:text-gray-900">
                매매 동향
              </a>
              <a href="/backtest" className="text-sm text-gray-600 hover:text-gray-900">
                백테스팅
              </a>
              <a href="/recommend" className="text-sm text-gray-600 hover:text-gray-900">
                오늘의 추천종목
              </a>
              <a href="/investor-recommendations" className="text-sm text-gray-600 hover:text-gray-900">
                기관별 종합추천
              </a>
              <span className="ml-auto text-xs text-gray-400">
                데이터: KRX &quot;연기금 등&quot; | 장 마감 후(T+1) 기준
              </span>
            </div>
          </nav>
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
          <Disclaimer />
        </Providers>
      </body>
    </html>
  )
}
