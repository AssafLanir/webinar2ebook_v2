/**
 * E2E Test: Project Lifecycle
 *
 * Tests the full lifecycle: create → edit → navigate → refresh → reopen
 *
 * Prerequisites:
 * - Backend running on http://localhost:8000
 * - Frontend running on http://localhost:5173
 * - MongoDB running with empty test database
 *
 * Run with: npx playwright test tests/integration/project-lifecycle.spec.ts
 */

import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const TEST_PROJECT_NAME = `Test Project ${Date.now()}`

test.describe('Project Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto(BASE_URL)
    // Wait for the page to load
    await page.waitForSelector('h1:text("Webinar2Ebook")')
  })

  test('should create a new project', async ({ page }) => {
    // Click create button
    await page.click('button:text("+ Create New Project")')

    // Fill in the form
    await page.fill('input[placeholder="Enter your project name"]', TEST_PROJECT_NAME)

    // Select webinar type
    await page.selectOption('select', 'training_tutorial')

    // Submit
    await page.click('button:text("Create Project")')

    // Should navigate to workspace
    await expect(page.locator('h1')).toContainText(TEST_PROJECT_NAME)
  })

  test('should edit content and auto-save on tab navigation', async ({ page }) => {
    // First create a project
    await page.click('button:text("+ Create New Project")')
    await page.fill('input[placeholder="Enter your project name"]', TEST_PROJECT_NAME)
    await page.click('button:text("Create Project")')

    // Wait for workspace to load
    await expect(page.locator('h1')).toContainText(TEST_PROJECT_NAME)

    // Find the transcript textarea and add content
    const transcriptTextarea = page.locator('textarea').first()
    await transcriptTextarea.fill('This is test transcript content for the E2E test.')

    // Click on Tab 2 (Visuals)
    await page.click('button:text("Visuals")')

    // Should see "Saving..." indicator
    await expect(page.locator('text=Saving...')).toBeVisible({ timeout: 2000 })

    // Wait for save to complete
    await expect(page.locator('text=Saving...')).toBeHidden({ timeout: 5000 })

    // Should now be on Tab 2
    await expect(page.locator('button:text("Visuals")')).toHaveAttribute(
      'aria-current',
      'page'
    )
  })

  test('should persist data after refresh', async ({ page }) => {
    const uniqueName = `Persist Test ${Date.now()}`
    const testContent = 'Persisted transcript content'

    // Create a project
    await page.click('button:text("+ Create New Project")')
    await page.fill('input[placeholder="Enter your project name"]', uniqueName)
    await page.click('button:text("Create Project")')

    // Wait for workspace
    await expect(page.locator('h1')).toContainText(uniqueName)

    // Add content
    const transcriptTextarea = page.locator('textarea').first()
    await transcriptTextarea.fill(testContent)

    // Navigate to trigger save
    await page.click('button:text("Visuals")')
    await expect(page.locator('text=Saving...')).toBeHidden({ timeout: 5000 })

    // Go back to project list
    await page.click('button:text("Back to Projects")')

    // Refresh the page
    await page.reload()

    // Wait for project list to load
    await page.waitForSelector(`text=${uniqueName}`)

    // Open the project
    await page.click(`text=${uniqueName}`)
    await page.click('button:text("Open")')

    // Verify content is preserved
    await expect(page.locator('h1')).toContainText(uniqueName)
    const textarea = page.locator('textarea').first()
    await expect(textarea).toHaveValue(testContent)
  })

  test('should delete a project', async ({ page }) => {
    const uniqueName = `Delete Test ${Date.now()}`

    // Create a project
    await page.click('button:text("+ Create New Project")')
    await page.fill('input[placeholder="Enter your project name"]', uniqueName)
    await page.click('button:text("Create Project")')

    // Go back to list
    await page.click('button:text("Back to Projects")')

    // Wait for project list
    await page.waitForSelector(`text=${uniqueName}`)

    // Find and click delete button for this project
    const projectRow = page.locator(`text=${uniqueName}`).locator('..').locator('..')
    await projectRow.locator('button[title="Delete project"]').click()

    // Confirm deletion
    await page.click('button:text("Delete")')

    // Project should be gone
    await expect(page.locator(`text=${uniqueName}`)).toBeHidden({ timeout: 5000 })
  })
})
