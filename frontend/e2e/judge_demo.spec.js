/**
 * Judge Demo E2E Smoke Test
 *
 * Tests the full visible user journey against the running dev stack
 * (frontend on :5173, backend on :8000).
 *
 * Run (with servers up):
 *   cd frontend && npx playwright test e2e/judge_demo.spec.js
 *
 * These tests require both `npm run dev` and the FastAPI server running.
 */
import { test, expect } from '@playwright/test'

const API = 'http://localhost:8000'

/** Create a case via API, return its case_id, delete it after the test. */
async function withCase(request, fn) {
  const res = await request.post(`${API}/api/cases/`, {
    data: {
      company_name: 'E2E Playwright Co',
      loan_amount: 3_000_000,
      loan_purpose: 'E2E Test',
      sector: 'tech',
      location: 'Bangalore',
    },
  })
  expect(res.status()).toBe(201)
  const { case_id } = await res.json()
  try {
    await fn(case_id)
  } finally {
    await request.delete(`${API}/api/cases/${case_id}`)
  }
}

test.describe('Navigation smoke', () => {
  test('homepage loads and shows Cases heading', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('🏦 Intelli-Credit')).toBeVisible()
  })

  test('health badge appears (Healthy or Offline)', async ({ page }) => {
    await page.goto('/')
    // Wait for health check to resolve
    await page.waitForTimeout(1500)
    const badge = page.locator('text=/Healthy|Offline/')
    await expect(badge).toBeVisible()
  })

  test('version string shows v3.0', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=/v3\\.0/')).toBeVisible()
  })
})

test.describe('Case list', () => {
  test('Actions column exists in cases table', async ({ page, request }) => {
    await withCase(request, async (_caseId) => {
      await page.goto('/')
      await expect(page.locator('text=Actions')).toBeVisible()
    })
  })

  test('Delete button per row opens confirm modal', async ({ page, request }) => {
    await withCase(request, async (_caseId) => {
      await page.goto('/')
      await expect(page.locator('text=E2E Playwright Co')).toBeVisible()
      const deleteBtn = page.locator('button:has-text("🗑 Delete")').first()
      await deleteBtn.click()
      await expect(page.locator('text=Delete Case')).toBeVisible()
      // Cancel it so we don't actually delete
      await page.locator('button:has-text("Cancel")').click()
      await expect(page.locator('text=Delete Case')).not.toBeVisible()
    })
  })
})

test.describe('Case detail', () => {
  test('case detail page renders and shows tabs', async ({ page, request }) => {
    await withCase(request, async (caseId) => {
      await page.goto(`/cases/${caseId}`)
      await expect(page.locator('text=Overview')).toBeVisible()
      await expect(page.locator('text=Notes')).toBeVisible()
    })
  })

  test('notes tab: can add a note', async ({ page, request }) => {
    await withCase(request, async (caseId) => {
      await page.goto(`/cases/${caseId}`)
      // Click Notes tab
      await page.locator('button:has-text("Notes")').click()
      // Fill in the note form
      await page.locator('input[placeholder="Your name"]').fill('playwright_user')
      await page.locator('textarea').fill('This is a Playwright smoke test note.')
      await page.locator('button:has-text("Save Note")').click()
      // Note should appear in the list
      await expect(page.locator('text=This is a Playwright smoke test note.')).toBeVisible()
    })
  })

  test('notes tab: can delete a note', async ({ page, request }) => {
    // Pre-create a note via API
    await withCase(request, async (caseId) => {
      const nr = await request.post(`${API}/api/cases/${caseId}/notes`, {
        data: {
          author: 'pw_setup',
          text: 'Note to be deleted by Playwright',
          note_type: 'general',
        },
      })
      expect(nr.status()).toBe(201)

      await page.goto(`/cases/${caseId}`)
      await page.locator('button:has-text("Notes")').click()
      await expect(page.locator('text=Note to be deleted by Playwright')).toBeVisible()

      // Click delete (trash button) for that note
      await page.locator('button[title="Delete note"]').first().click()
      // Confirm modal
      await expect(page.locator('text=Delete Note')).toBeVisible()
      await page.locator('button:has-text("Delete")').last().click()

      await expect(page.locator('text=Note to be deleted by Playwright')).not.toBeVisible()
    })
  })

  test('case detail: Delete Case button opens confirm modal', async ({ page, request }) => {
    await withCase(request, async (caseId) => {
      await page.goto(`/cases/${caseId}`)
      await page.locator('button:has-text("Delete Case")').click()
      await expect(page.locator('text=Delete Case')).toBeVisible()
      // Cancel
      await page.locator('button:has-text("Cancel")').click()
    })
  })
})

test.describe('API client coverage', () => {
  test('GET /api/health returns ok', async ({ request }) => {
    const r = await request.get(`${API}/api/health`)
    expect(r.status()).toBe(200)
    const body = await r.json()
    expect(body.status).toBe('ok')
  })

  test('GET /api/health alias works', async ({ request }) => {
    const r = await request.get(`${API}/health`)
    expect(r.status()).toBe(200)
  })

  test('PATCH note works via API', async ({ request }) => {
    await withCase(request, async (caseId) => {
      const rn = await request.post(`${API}/api/cases/${caseId}/notes`, {
        data: { author: 'pw', text: 'Original', note_type: 'general', tags: ['old'] },
      })
      const { note_id } = await rn.json()

      const rp = await request.patch(`${API}/api/cases/${caseId}/notes/${note_id}`, {
        data: { text: 'Patched by Playwright', tags: ['new'] },
      })
      expect(rp.status()).toBe(200)
      const patched = await rp.json()
      expect(patched.text).toBe('Patched by Playwright')
      expect(patched.tags).toContain('new')
    })
  })
})
