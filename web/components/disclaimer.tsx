// 법적 면책 고지 - 모든 페이지 푸터에 필수 노출 (PROJECT_SPEC §7)
export function Disclaimer() {
  return (
    <footer className="mt-16 border-t border-gray-200 bg-gray-50 py-8 text-xs text-gray-500">
      <div className="mx-auto max-w-7xl px-4">
        <p className="mb-2 font-semibold text-gray-600">⚠️ 면책 고지</p>
        <p className="leading-relaxed">
          본 서비스는 정보 제공 목적이며, 투자 자문이 아닙니다.
          <br />• 표시되는 데이터는 한국거래소(KRX)가 공개하는 &quot;연기금 등&quot; 카테고리의
          합산 매매 정보로, 국민연금공단 단독 매매가 아닙니다.
          <br />• 모든 매매 데이터는 장 마감 후(T+1) 기준이며, 실시간 정보가 아닙니다.
          <br />• 과거 매매 패턴이 미래 수익을 보장하지 않습니다.
          <br />• 투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다.
          <br />
          <span className="mt-1 block text-gray-400">
            데이터 출처: 한국거래소(KRX), 금융감독원 전자공시시스템(DART)
          </span>
        </p>
      </div>
    </footer>
  )
}
