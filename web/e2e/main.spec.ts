/**
 * 메인 페이지 E2E 테스트.
 *
 * 검증 항목:
 *  - 페이지 로드 및 핵심 UI 요소 존재
 *  - 금지 문구 없음 (법적 제약 §1.3.2)
 *  - 면책 고지 노출 (PROJECT_SPEC §7)
 *  - 연기금 매매 테이블 데이터 표시
 */
import { test, expect } from '@playwright/test'

test.describe('메인 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('페이지 제목과 헤더가 표시된다', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('연기금 순매수 상위 종목')
    await expect(page.locator('nav')).toContainText('NPS Tracker')
  })

  test('요약 카드 3개가 표시된다', async ({ page }) => {
    // 연기금 순거래 합계, 순매수 종목 수, 순매도 종목 수
    await expect(page.getByText('연기금 순거래 합계')).toBeVisible()
    await expect(page.getByText('순매수 종목 수')).toBeVisible()
    await expect(page.getByText('순매도 종목 수')).toBeVisible()
  })

  test('순매수 상위 테이블이 표시된다', async ({ page }) => {
    // 테이블 헤더 확인 (th 요소만 명시)
    await expect(page.getByRole('columnheader', { name: '종목명' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '순매수금액' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '연속매수일' })).toBeVisible()

    // 데이터 행이 최소 1개 이상 있어야 함
    const rows = page.locator('tbody tr')
    await expect(rows.first()).toBeVisible()
  })

  test('날짜 선택기와 시장 필터가 있다', async ({ page }) => {
    await expect(page.locator('input[type="date"]')).toBeVisible()
    await expect(page.locator('select').first()).toBeVisible()
  })

  // ── 법적 제약 검증 ──────────────────────────────────────────
  test('금지 문구 "추천 종목"이 없다', async ({ page }) => {
    const content = await page.content()
    expect(content).not.toContain('추천 종목')
    expect(content).not.toContain('매수 추천')
    expect(content).not.toContain('수익 보장')
  })

  test('면책 고지가 푸터에 표시된다', async ({ page }) => {
    const footer = page.locator('footer')
    await expect(footer).toContainText('투자 자문')
    await expect(footer).toContainText('연기금 등')
    await expect(footer).toContainText('T+1')
  })

  test('데이터 출처가 표시된다', async ({ page }) => {
    await expect(page.locator('footer')).toContainText('KRX')
  })

  // ── 네비게이션 ──────────────────────────────────────────────
  test('백테스팅 페이지로 이동할 수 있다', async ({ page }) => {
    await page.click('a[href="/backtest"]')
    await expect(page).toHaveURL('/backtest')
    await expect(page.locator('h1')).toContainText('백테스팅')
  })

  test('종목 행 클릭 시 종목 상세로 이동한다', async ({ page }) => {
    const firstRow = page.locator('tbody tr').first()
    await firstRow.waitFor({ state: 'visible' })
    await firstRow.click()
    await expect(page).toHaveURL(/\/stocks\/\d{6}/)
  })
})
