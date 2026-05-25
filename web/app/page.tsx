import { getNpsDaily } from '@/lib/api'
import { NpsDailyDashboard } from '@/components/nps-daily-dashboard'
import { getPreviousBusinessDay } from '@/lib/utils'

export const revalidate = 3600 // 1시간마다 ISR 재생성

export default async function HomePage() {
  const defaultDate = getPreviousBusinessDay()
  let initialData = null
  let loadError: string | null = null
  try {
    initialData = await getNpsDaily({ date: defaultDate, limit: 50 })
  } catch (e) {
    loadError = e instanceof Error ? e.message : '알 수 없는 오류'
  }

  if (!initialData) {
    const isNoData =
      loadError?.includes('수집된 NPS') || loadError?.includes('없습니다')
    return (
      <div>
        <h1 className="mb-6 text-2xl font-bold text-gray-900">연기금 순매수 상위 종목</h1>
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          {isNoData ? (
            <>
              <p className="font-semibold">표시할 매매 데이터가 아직 없습니다.</p>
              <p className="mt-2">
                API 서버는 연결되었지만 DB에 KRX 수집 데이터가 없습니다. 터미널에서 아래를 실행한 뒤
                페이지를 새로고침하세요.
              </p>
              <pre className="mt-3 overflow-x-auto rounded bg-yellow-100/80 p-2 text-xs">
                cd data-collector{'\n'}
                DATABASE_URL=&quot;postgresql+psycopg2://nps_user:localdevpassword@127.0.0.1:5432/nps_tracker&quot;{' '}
                .venv/bin/python -m scrapers.daily_runner --now
              </pre>
            </>
          ) : (
            <>
              데이터를 불러올 수 없습니다. API 서버({process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}
              ) 연결 상태를 확인해주세요.
              {loadError ? <p className="mt-2 text-xs opacity-80">상세: {loadError}</p> : null}
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-gray-900">연기금 순매수 상위 종목</h1>
      <p className="mb-6 text-sm text-gray-500">
        KRX &quot;연기금 등&quot; 카테고리 기준 | 국민연금 단독 매매가 아님
      </p>
      <NpsDailyDashboard initialData={initialData} defaultDate={defaultDate} />
    </div>
  )
}
