import { InvestorConsensusRecommendForm } from '@/components/investor-consensus-recommend-form'

export default function InvestorRecommendationsPage() {
  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-gray-900">
        기관 컨센서스 TOP 50 추천종목
      </h1>

      <p className="mb-6 text-sm text-gray-500">
        기관별 점수, 외국인 점수,
        동시매수 기관 수를 반영한 TOP 50개 추천종목을 조회합니다.
      </p>

      <InvestorConsensusRecommendForm />
    </div>
  )
}