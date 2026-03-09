import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const statePath = path.join(repoRoot, 'demo', 'intelligence_cases', '.demo_state.json')
const screenshotDir = process.env.SCREENSHOT_OUTDIR || path.join(repoRoot, 'demo', 'assets', 'screenshots')

function loadState() {
  if (!fs.existsSync(statePath)) {
    throw new Error(`Demo state file not found: ${statePath}`)
  }
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

test.describe('Demo pack screenshot capture', () => {
  test.beforeAll(() => {
    fs.mkdirSync(screenshotDir, { recursive: true })
  })

  test('capture list and detail screenshots for seeded demo cases', async ({ page }) => {
    const state = loadState()
    const entries = Object.entries(state.cases || {})
    expect(entries.length).toBeGreaterThanOrEqual(5)

    await page.goto('/?presentation=1')
    await expect(page.getByText('Five deterministic credit intelligence cases')).toBeVisible()
    await page.screenshot({ path: path.join(screenshotDir, '01_case_list.png'), fullPage: true })

    for (const [label, info] of entries) {
      await page.goto(`/cases/${info.case_id}?presentation=1`)
      await expect(page.locator('text=Executive Readout')).toBeVisible()
      await page.screenshot({ path: path.join(screenshotDir, `${label.toLowerCase()}_detail.png`), fullPage: true })

      const graphCard = page.locator('div').filter({ has: page.getByText('Graph Intelligence') }).first()
      await expect(graphCard).toBeVisible()
      await graphCard.screenshot({ path: path.join(screenshotDir, `${label.toLowerCase()}_graph.png`) })
    }
  })
})
