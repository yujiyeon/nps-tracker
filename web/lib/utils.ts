// 한국 시장 표시 규칙 유틸리티

/** 금액을 한국식 단위로 표시 (억/만 단위 자동 선택) */
export function formatAmount(amount: number): string {
  const abs = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''

  if (abs >= 1_000_000_000_000) {
    return `${sign}${(abs / 1_000_000_000_000).toFixed(1)}조원`
  }
  if (abs >= 100_000_000) {
    return `${sign}${(abs / 100_000_000).toFixed(1)}억원`
  }
  if (abs >= 10_000) {
    return `${sign}${(abs / 10_000).toFixed(0)}만원`
  }
  return `${sign}${abs.toLocaleString('ko-KR')}원`
}

/** 등락률 표시 - 한국 관습: 상승=빨강, 하락=파랑 */
export function formatChangePct(pct: number | null): {
  text: string
  className: string
} {
  if (pct === null) return { text: '-', className: 'text-gray-400' }
  const text = `${pct > 0 ? '+' : ''}${pct.toFixed(2)}%`
  const className =
    pct > 0 ? 'text-red-500 font-medium' : pct < 0 ? 'text-blue-500 font-medium' : 'text-gray-500'
  return { text, className }
}

/** 날짜를 YYYY-MM-DD (요일) 형식으로 표시 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const days = ['일', '월', '화', '수', '목', '금', '토']
  const dow = days[date.getDay()]
  return `${dateStr} (${dow})`
}

/** 숫자를 천 단위 콤마 포맷 */
export function formatNumber(n: number): string {
  return n.toLocaleString('ko-KR')
}

/**
 * KST 기준 전 영업일을 YYYY-MM-DD 형식으로 반환.
 * 주말이면 금요일로 스킵 (공휴일은 별도 처리 없음).
 */
export function getPreviousBusinessDay(): string {
  const kstNow = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }),
  )
  const prev = new Date(kstNow)
  prev.setDate(prev.getDate() - 1)
  while (prev.getDay() === 0 || prev.getDay() === 6) {
    prev.setDate(prev.getDate() - 1)
  }
  const y = prev.getFullYear()
  const m = String(prev.getMonth() + 1).padStart(2, '0')
  const d = String(prev.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** 연속 매수일 배지 색상 */
export function consecutiveDaysBadgeClass(days: number): string {
  if (days >= 10) return 'bg-red-100 text-red-700 border-red-200'
  if (days >= 5) return 'bg-orange-100 text-orange-700 border-orange-200'
  if (days >= 3) return 'bg-yellow-100 text-yellow-700 border-yellow-200'
  return 'bg-gray-100 text-gray-600 border-gray-200'
}
