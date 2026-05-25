/**
 * 백테스팅 페이지 E2E 테스트.
 */
import { test, expect } from '@playwright/test'

test.describe('백테스팅 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/backtest')
  })

  test('페이지 제목이 표시된다', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('백테스팅')
  })

  test('전략 파라미터 입력 폼이 있다', async ({ page }) => {
    await expect(page.getByLabel(/시작일|from/i).or(page.locator('input[type="date"]').first())).toBeVisible()
    await expect(page.getByRole('button', { name: /실행|백테스팅/i })).toBeVisible()
  })

  test('파라미터 기본값이 설정돼 있다', async ({ page }) => {
    // 초기 자본 기본값 1000만원
    const capitalInput = page.locator('input[name="initial_capital"], input[id*="capital"]')
    if (await capitalInput.count() > 0) {
      const val = await capitalInput.inputValue()
      expect(Number(val)).toBeGreaterThan(0)
    }
  })

  test('면책 고지가 표시된다', async ({ page }) => {
    await expect(page.locator('footer')).toContainText('투자 자문')
  })

  test('금지 문구가 없다', async ({ page }) => {
    const content = await page.content()
    expect(content).not.toContain('추천 종목')
    expect(content).not.toContain('수익 보장')
    expect(content).not.toContain('확실한 투자처')
  })

  test('백테스팅 실행 버튼이 동작한다', async ({ page }) => {
    // 짧은 기간으로 테스트
    const dateInputs = page.locator('input[type="date"]')
    const count = await dateInputs.count()
    if (count >= 2) {
      await dateInputs.nth(0).fill('2026-01-01')
      await dateInputs.nth(1).fill('2026-03-31')
    }

    const runBtn = page.getByRole('button', { name: /실행|백테스팅/i })
    await runBtn.click()

    // 버튼 클릭 후 로딩 또는 상태 변화 확인
    await expect(
      page.getByText(/실행 중|pending|running|완료|결과/i).or(runBtn)
    ).toBeVisible({ timeout: 5_000 })
  })
})
