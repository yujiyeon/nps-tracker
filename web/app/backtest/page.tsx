import { BacktestForm } from '@/components/backtest-form'

export default function BacktestPage() {
  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-gray-900">백테스팅</h1>
      <p className="mb-6 text-sm text-gray-500">
        &quot;연기금이 N일 연속 매수한 종목을 따라 사면 수익이 났을까?&quot; — 과거 데이터로 검증
      </p>
      <BacktestForm />
    </div>
  )
}
