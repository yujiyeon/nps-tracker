import { TodayRecommendForm } from '@/components/today-recommend-form'
import { MdpRecommendForm } from '@/components/mdp-recommend-form'

export default function TodayRecommendPage() {
  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-gray-900">오늘의 추천종목</h1>
      <p className="mb-6 text-sm text-gray-500">
        국민연금 매수 데이터를 기반으로 DQN이 오늘 기준 추천 종목을 선택합니다.
      </p>

      {/* 기존 추천 (bandit) */}
      <TodayRecommendForm />

      {/* 구분선 */}
      <div className="my-10 border-t border-gray-200" />

      {/* 방향 A: 포트폴리오 강화학습(MDP) 추천 — 신규 */}
      <h2 className="mb-2 text-xl font-bold text-gray-900">
        포트폴리오 강화학습(MDP) 추천
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        현금·보유·평가손익을 상태에 포함하고 일일 수익률로 학습한 DQN의 추천입니다.
      </p>
      <MdpRecommendForm />
    </div>
  )
}
