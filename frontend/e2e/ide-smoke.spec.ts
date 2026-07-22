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

// Phase 2: confirms the data-connections UI actually renders and round-trips
// through the real backend -- create a connection, run a query against it,
// see real rows back. Needs a SQLite file the backend process can read;
// PLAYWRIGHT_SQLITE_FIXTURE points at one seeded with a `widgets` table.
test('create a SQLite connection and run a query against it end to end', async ({ page }) => {
  const sqlitePath = process.env.PLAYWRIGHT_SQLITE_FIXTURE
  test.skip(!sqlitePath, 'PLAYWRIGHT_SQLITE_FIXTURE not set')

  const email = `smoke-conn-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'

  await page.goto('/')
  await page.getByText("Don't have an account? Create one").click()
  await page.getByLabel('Name').fill('Smoke Test')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /New workspace/ }).click()
  await page.getByPlaceholder('Workspace name').fill('Connections Workspace')
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('No files yet')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Connections' }).click()
  await page.getByTitle('New connection').click()
  await page.getByPlaceholder('Connection name').fill('widgets-db')
  await page.locator('select').selectOption('sqlite')
  await page.getByPlaceholder('File path (on the server)').fill(sqlitePath!)
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('widgets-db')).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/screenshots/03-connection-created.png', fullPage: true })

  page.once('dialog', (dialog) => dialog.accept('query.sql'))
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByTitle('New file').first().click()
  await expect(page.locator('.monaco-editor').first()).toBeVisible({ timeout: 10_000 })
  await page.locator('.monaco-editor').first().click()
  await page.keyboard.type('select * from widgets order by id')

  // The query runner panel only appears for .sql files -- confirms that
  // wiring, not just that the button exists somewhere on the page.
  await page.getByRole('button', { name: 'Run' }).click()
  await expect(page.getByText('alpha')).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('beta')).toBeVisible()
  await expect(page.getByText(/2 rows/)).toBeVisible()
  await page.screenshot({ path: 'e2e/screenshots/04-query-results.png', fullPage: true })
})

// Phase 3b/3c: confirms the investigate agent's job-queue round trip
// actually renders -- submit a question against a real connection (Phase
// 3c made AI connection-aware; the panel now requires picking one rather
// than silently falling back to the bundled demo data), poll to completion
// (needs the AI worker running alongside the backend, see the "Start AI
// worker for e2e smoke test" CI step), then open the report it wrote as a
// real file in the tree.
test('investigate a question against a real connection and open the generated report end to end', async ({ page }) => {
  const sqlitePath = process.env.PLAYWRIGHT_SQLITE_FIXTURE
  test.skip(!sqlitePath, 'PLAYWRIGHT_SQLITE_FIXTURE not set')

  const email = `smoke-investigate-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'

  await page.goto('/')
  await page.getByText("Don't have an account? Create one").click()
  await page.getByLabel('Name').fill('Smoke Test')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /New workspace/ }).click()
  await page.getByPlaceholder('Workspace name').fill('Investigate Workspace')
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('No files yet')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Connections' }).click()
  await page.getByTitle('New connection').click()
  await page.getByPlaceholder('Connection name').fill('widgets-db')
  await page.locator('select').selectOption('sqlite')
  await page.getByPlaceholder('File path (on the server)').fill(sqlitePath!)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('widgets-db')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Investigate' }).click()
  await expect(page.locator('select')).toContainText('widgets-db')
  await page.getByPlaceholder(/why did signups drop/).fill('how many widgets are there')
  await page.getByRole('button', { name: 'Run Investigation' }).click()

  await expect(page.getByText('done', { exact: true })).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: 'e2e/screenshots/05-investigate-done.png', fullPage: true })

  await page.getByRole('button', { name: 'Open Report' }).click()
  await expect(page.locator('.monaco-editor').first()).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.monaco-editor').first()).toContainText('Investigation:')
  await expect(page.locator('.monaco-editor').first()).toContainText('widgets')
  await page.screenshot({ path: 'e2e/screenshots/06-investigate-report-open.png', fullPage: true })
})

// Phase 4a: the literal acceptance bar for this phase is "a dashboard with
// 3+ pinned charts persists and reloads correctly" -- pins 3 tiles from
// real query results (not by calling the API directly) via the "Pin to
// dashboard" flow, then does a full page.reload() and confirms all 3 still
// render with real data, not just that the dashboard row exists.
test('pin 3 charts to a dashboard from real query results and confirm they persist across a reload', async ({ page }) => {
  const sqlitePath = process.env.PLAYWRIGHT_SQLITE_FIXTURE
  test.skip(!sqlitePath, 'PLAYWRIGHT_SQLITE_FIXTURE not set')

  const email = `smoke-dashboard-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'
  const dashboardName = `Widgets Dashboard ${Date.now()}`

  await page.goto('/')
  await page.getByText("Don't have an account? Create one").click()
  await page.getByLabel('Name').fill('Smoke Test')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /New workspace/ }).click()
  await page.getByPlaceholder('Workspace name').fill('Dashboard Workspace')
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('No files yet')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Connections' }).click()
  await page.getByTitle('New connection').click()
  await page.getByPlaceholder('Connection name').fill('widgets-db')
  await page.locator('select').selectOption('sqlite')
  await page.getByPlaceholder('File path (on the server)').fill(sqlitePath!)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('widgets-db')).toBeVisible({ timeout: 10_000 })

  page.once('dialog', (dialog) => dialog.accept('query.sql'))
  await page.getByRole('button', { name: 'Files' }).click()
  await page.getByTitle('New file').first().click()
  await expect(page.locator('.monaco-editor').first()).toBeVisible({ timeout: 10_000 })
  await page.locator('.monaco-editor').first().click()
  await page.keyboard.type('select * from widgets order by id')
  await page.getByRole('button', { name: 'Run' }).click()
  // Shares the same PLAYWRIGHT_SQLITE_FIXTURE as every other test in this
  // file -- CI's own seeding step (and this one) inserts exactly 2 rows.
  await expect(page.getByText(/2 rows/)).toBeVisible({ timeout: 10_000 })

  const pinTile = async (title: string, createNewDashboard: boolean) => {
    await page.getByTitle('Pin to dashboard').click()
    await page.getByPlaceholder('Tile title').fill(title)
    if (createNewDashboard) {
      await page.getByLabel('New dashboard').check()
      await page.getByPlaceholder('Dashboard name').fill(dashboardName)
    } else {
      await page.getByLabel('Existing dashboard').check()
      await page.locator('select').last().selectOption({ label: dashboardName })
    }
    await page.getByRole('button', { name: 'Pin to dashboard' }).click()
    // Not a button-text check: the submit button's own accessible name
    // changes to "Pinning…" the instant the click fires, well before the
    // create-dashboard + add-item round trip actually finishes, so
    // asserting on that name disappearing passes prematurely -- checking
    // the tile-title input itself is gone is what actually proves the
    // menu (and its state) has closed, not just that its label changed.
    await expect(page.getByPlaceholder('Tile title')).toHaveCount(0, { timeout: 10_000 })
  }

  await pinTile('Widget rows', true)
  await pinTile('Widget rows again', false)
  await pinTile('Widget rows once more', false)

  await page.screenshot({ path: 'e2e/screenshots/07-dashboard-pinned.png', fullPage: true })

  await page.getByRole('button', { name: 'Dashboards' }).click()
  await expect(page.getByText(dashboardName)).toBeVisible({ timeout: 10_000 })
  await page.getByText(dashboardName).click()
  await expect(page.getByText('Widget rows', { exact: true })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('Widget rows again')).toBeVisible()
  await expect(page.getByText('Widget rows once more')).toBeVisible()
  await expect(page.getByText('alpha').first()).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/screenshots/08-dashboard-open.png', fullPage: true })

  // The actual acceptance bar: reload the page entirely and confirm the
  // same 3 tiles come back with real data, not just that the dashboard
  // metadata row survived. The active workspace is remembered across a
  // reload (useAuthStore persists it), so this lands straight back in the
  // IDE shell rather than the workspace picker.
  await page.reload()
  await page.getByRole('button', { name: 'Dashboards' }).click({ timeout: 10_000 })
  await page.getByText(dashboardName).click()
  await expect(page.getByText('Widget rows', { exact: true })).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText('Widget rows again')).toBeVisible()
  await expect(page.getByText('Widget rows once more')).toBeVisible()
  await expect(page.getByText('alpha').first()).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/screenshots/09-dashboard-reloaded.png', fullPage: true })
})

// Phase 4b: the cron-firing correctness itself is proven at the pytest
// level (tick()/webhook tests against real Redis and a real local HTTP
// listener -- see tests/test_scheduled_queries.py), not by waiting on a
// live cron here. This just confirms the panel itself actually renders
// and the "run now" round trip (create -> run -> real row count back)
// works through the real UI, the same "does this actually render" bar
// every other phase's UI has been held to.
test('create a scheduled query and confirm "run now" reports a real result', async ({ page }) => {
  const sqlitePath = process.env.PLAYWRIGHT_SQLITE_FIXTURE
  test.skip(!sqlitePath, 'PLAYWRIGHT_SQLITE_FIXTURE not set')

  const email = `smoke-scheduled-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'

  await page.goto('/')
  await page.getByText("Don't have an account? Create one").click()
  await page.getByLabel('Name').fill('Smoke Test')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /New workspace/ }).click()
  await page.getByPlaceholder('Workspace name').fill('Scheduled Workspace')
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('No files yet')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Connections' }).click()
  await page.getByTitle('New connection').click()
  await page.getByPlaceholder('Connection name').fill('widgets-db')
  await page.locator('select').selectOption('sqlite')
  await page.getByPlaceholder('File path (on the server)').fill(sqlitePath!)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('widgets-db')).toBeVisible({ timeout: 10_000 })

  await page.getByRole('button', { name: 'Scheduled' }).click()
  await page.getByTitle('New scheduled query').click()
  await page.getByPlaceholder('Schedule name').fill('Widget count check')
  // No connection picker interaction needed: the form auto-selects the
  // first available connection once loadConnections() resolves, and this
  // workspace only has the one ("widgets-db") -- confirmed already
  // selected by default in the rendered form.
  await page.getByPlaceholder(/SELECT/).fill('select * from widgets')
  await page.getByPlaceholder(/Cron expression/).fill('0 * * * *')
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText('Widget count check')).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'e2e/screenshots/10-scheduled-created.png', fullPage: true })

  // "Run now" only renders (group-hover:flex on a `hidden` parent, i.e.
  // display:none until then) once the row itself is hovered -- Playwright's
  // click() moves the mouse to the target first, but a display:none
  // element has no box to move to, so the row's own :hover has to be
  // triggered explicitly before the button becomes clickable.
  await page.getByText('Widget count check').hover()
  await page.getByTitle('Run now').click()
  await expect(page.getByText(/no webhook\/email configured/)).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(/\(2 rows\)/)).toBeVisible()
  await page.screenshot({ path: 'e2e/screenshots/11-scheduled-run-now.png', fullPage: true })
})

// Phase 5a: additive external sharing, across two REAL separate browser
// sessions/accounts (not the API-level assertions already covered in
// tests/test_sharing.py) -- this is the "does this actually render for a
// second human" proof, matching every other phase's live-UI discipline.
// Account 2 is never made a member of account 1's workspace; access comes
// only from the share grant, surfaced through the "Shared with me" list on
// the workspace picker screen.
test('share a file with a second account and confirm they can see and edit it, but only after being shared with', async ({ browser }) => {
  const ownerContext = await browser.newContext()
  const recipientContext = await browser.newContext()
  const owner = await ownerContext.newPage()
  const recipient = await recipientContext.newPage()

  const ownerEmail = `smoke-share-owner-${Date.now()}@example.com`
  const recipientEmail = `smoke-share-recipient-${Date.now()}@example.com`
  const password = 'correct-horse-battery-staple'

  try {
    // Register the recipient FIRST -- sharing requires an existing account.
    await recipient.goto('/')
    await recipient.getByText("Don't have an account? Create one").click()
    await recipient.getByLabel('Name').fill('Recipient')
    await recipient.getByLabel('Email').fill(recipientEmail)
    await recipient.getByLabel('Password').fill(password)
    await recipient.getByRole('button', { name: 'Create account' }).click()
    await expect(recipient.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
    // No workspace of their own, and nothing shared yet -- the "Shared
    // with me" section shouldn't even render.
    await expect(recipient.getByText('Shared with me')).not.toBeVisible()

    await owner.goto('/')
    await owner.getByText("Don't have an account? Create one").click()
    await owner.getByLabel('Name').fill('Owner')
    await owner.getByLabel('Email').fill(ownerEmail)
    await owner.getByLabel('Password').fill(password)
    await owner.getByRole('button', { name: 'Create account' }).click()
    await expect(owner.getByText('Workspaces')).toBeVisible({ timeout: 10_000 })
    await owner.getByRole('button', { name: /New workspace/ }).click()
    await owner.getByPlaceholder('Workspace name').fill('Sharing Demo Workspace')
    await owner.getByRole('button', { name: 'Create' }).click()
    await expect(owner.getByText('No files yet')).toBeVisible({ timeout: 10_000 })

    owner.once('dialog', (dialog) => dialog.accept('shared-note.md'))
    await owner.getByTitle('New file').first().click()
    await expect(owner.locator('.monaco-editor').first()).toBeVisible({ timeout: 10_000 })
    await owner.locator('.monaco-editor').first().click()
    await owner.keyboard.type('# Shared from owner')
    await owner.keyboard.press(process.platform === 'darwin' ? 'Meta+S' : 'Control+S')

    await owner.getByText('shared-note.md').first().hover()
    await owner.getByTitle('Share').click()
    await owner.getByPlaceholder('Email address').fill(recipientEmail)
    // exact:true -- "Share" (case-insensitive substring, Playwright's
    // default for getByRole) would otherwise also match the open tab
    // button, whose accessible name is "shared-note.md".
    await owner.getByRole('button', { name: 'Share', exact: true }).click()
    await expect(owner.getByText(recipientEmail)).toBeVisible({ timeout: 10_000 })
    await owner.screenshot({ path: 'e2e/screenshots/12-share-dialog.png', fullPage: true })
    await owner.keyboard.press('Escape')

    // Recipient reloads their (already-open) workspace picker and the
    // shared file now appears -- confirms the share grant, not a stale
    // page, is what's driving this.
    await recipient.reload()
    await expect(recipient.getByText('Shared with me')).toBeVisible({ timeout: 10_000 })
    await expect(recipient.getByText('shared-note.md')).toBeVisible()
    await recipient.getByText('shared-note.md').click()

    await expect(recipient.getByText('view only')).toBeVisible({ timeout: 10_000 })
    await expect(recipient.locator('.monaco-editor').first()).toContainText('Shared from owner')
    await recipient.screenshot({ path: 'e2e/screenshots/13-shared-file-view-only.png', fullPage: true })
    // View-only: no Save button should be present at all.
    await expect(recipient.getByRole('button', { name: 'Save' })).toHaveCount(0)

    // Owner upgrades the share to editor.
    await owner.reload()
    await owner.getByText('shared-note.md').first().hover()
    await owner.getByTitle('Share').click()
    await owner.getByPlaceholder('Email address').fill(recipientEmail)
    await owner.locator('select').selectOption('editor')
    await owner.getByRole('button', { name: 'Share', exact: true }).click()
    // The role label text itself is lowercase ("editor") with CSS
    // uppercase styling applied only visually -- Playwright's getByText
    // matches actual DOM text content, not rendered casing.
    await expect(owner.getByText('editor', { exact: true })).toBeVisible({ timeout: 10_000 })

    await recipient.getByRole('button', { name: 'Back' }).click()
    await recipient.reload()
    await recipient.getByText('shared-note.md').click()
    await expect(recipient.getByText('can edit')).toBeVisible({ timeout: 10_000 })
    await recipient.locator('.monaco-editor').first().click()
    await recipient.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
    await recipient.keyboard.type('# Edited by recipient')
    await recipient.getByRole('button', { name: 'Save' }).click()
    await expect(recipient.getByRole('button', { name: 'Save' })).toBeDisabled({ timeout: 10_000 })
    await recipient.screenshot({ path: 'e2e/screenshots/14-shared-file-edited.png', fullPage: true })

    // The owner's own copy reflects the recipient's edit -- proves the
    // shared PATCH actually wrote through to the real File row, not a
    // recipient-local draft.
    await owner.reload()
    await owner.getByText('shared-note.md').first().click()
    await expect(owner.locator('.monaco-editor').first()).toContainText('Edited by recipient')
  } finally {
    await ownerContext.close()
    await recipientContext.close()
  }
})
