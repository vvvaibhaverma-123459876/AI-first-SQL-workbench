import { expect, test } from '@playwright/test'

// This exists to close a gap that had gone unverified for three phases: nothing
// had ever confirmed the IDE actually renders in a browser for a logged-in user,
// only that it builds/typechecks/passes store-level tests. A mount-time throw in
// IdeShell, Monaco, or FileTree would white-screen the whole app and none of those
// checks would catch it.
test('register, sign in, create a workspace, and use the IDE end to end', async ({ page }) => {
  const email = `smoke-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'

  await page.goto('/')
  await expect(page.getByText('AI SQL Studio')).toBeVisible()

  await page.getByText("Don't have an account? Create one").click()
  await page.getByLabel('Name').fill('Smoke Test')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /New workspace/ }).click()
  await page.getByPlaceholder('Workspace name').fill('Smoke Workspace')
  await page.getByRole('button', { name: 'Create' }).click()

  // The IDE shell itself: file tree empty state, since this is a fresh workspace.
  await expect(page.getByText('No files yet')).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/screenshots/01-ide-empty.png', fullPage: true })

  // File creation goes through a native prompt() -- handle the dialog inline.
  page.once('dialog', (dialog) => dialog.accept('query.sql'))
  await page.getByTitle('New file').first().click()

  // Confirm Monaco actually mounts and accepts input, not just that the tab appeared.
  await expect(page.locator('.monaco-editor').first()).toBeVisible({ timeout: 10_000 })
  await page.locator('.monaco-editor').first().click()
  await page.keyboard.type('select 1;')
  await expect(page.locator('.monaco-editor').first()).toContainText('select 1;')
  await expect(page.getByText('query.sql').first()).toBeVisible()
  await page.screenshot({ path: 'e2e/screenshots/02-ide-file-open.png', fullPage: true })
})
