/**
 * 종목 상세 페이지 E2E 테스트.
 */
import { test, expect } from '@playwright/test'

test.describe('종목 상세 페이지', () => {
  // 삼성전자 (005930) 기준 테스트
  test.beforeEach(async ({ page }) => {
    await page.goto('/stocks/005930')
  })

  test('종목 기본 정보가 표시된다', async ({ page }) => {
    await expect(page.locator('h1, h2').first()).toBeVisible()
    // 티커 코드가 어딘가에 표시돼야 함
    await expect(page.getByText('005930')).toBeVisible()
  })

  test('NPS 매매 차트 영역이 있다', async ({ page }) => {
    // Recharts 컨테이너 확인
    await expect(page.locator('.recharts-wrapper').first()).toBeVisible({
      timeout: 10_000,
    })
  })

  test('NPS 매매 내역 테이블이 있다', async ({ page }) => {
    await expect(page.getByText('순매수금액')).toBeVisible()
  })

  test('면책 고지가 표시된다', async ({ page }) => {
    await expect(page.locator('footer')).toContainText('투자 자문')
  })

  test('금지 문구가 없다', async ({ page }) => {
    const content = await page.content()
    expect(content).not.toContain('추천 종목')
    expect(content).not.toContain('매수 추천')
  })

  test('없는 종목 접근 시 404 처리', async ({ page }) => {
    const res = await page.goto('/stocks/XXXXXX')
    // Next.js notFound() 또는 404 상태코드
    expect(res?.status()).toBe(404)
  })
})
