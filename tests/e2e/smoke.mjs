// End-to-end smoke test: drives the real /alphax UI against a bench as each persona.
// Usage: node tests/e2e/smoke.mjs http://hr.test:8000 ./screens
import { createRequire } from 'node:module'
// CommonJS resolution so a globally installed Playwright (NODE_PATH) also works.
const { chromium } = createRequire(import.meta.url)('playwright')
import { mkdirSync } from 'node:fs'

const BASE = process.argv[2] || 'http://hr.test:8000'
const OUT = process.argv[3] || './screens'
const PASSWORD = process.env.AXT_PASSWORD || 'Test@12345!x' // fixture users from tests/integration
mkdirSync(OUT, { recursive: true })

const results = []
const ok = (name) => { results.push([true, name]); console.log('  PASS ', name) }
const fail = (name, e) => { results.push([false, name]); console.log('  FAIL ', name, '-', e?.message ?? e) }

async function session(browser, user, { lang = 'en', mobile = false } = {}) {
  const ctx = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } : { viewport: { width: 1366, height: 860 } })
  await ctx.addInitScript((l) => localStorage.setItem('alphax-lang', l), lang)
  const res = await ctx.request.post(`${BASE}/api/method/login`, { data: { usr: user, pwd: PASSWORD } })
  if (!res.ok()) throw new Error(`login failed for ${user}: ${res.status()}`)
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|manifest|status of 417/.test(m.text())) errors.push(m.text()) }) // 417 = expected validation response
  return { ctx, page, errors }
}

async function step(name, fn) {
  try { await fn(); ok(name) } catch (e) { fail(name, e) }
}

const browser = await chromium.launch()
try {
  console.log('\n== Employee (English, desktop)')
  {
    const { page, errors, ctx } = await session(browser, 'emp@axt.test')
    await step('home shows greeting, check-in and leave balance', async () => {
      await page.goto(`${BASE}/alphax`)
      await page.getByText('Leave balance').waitFor()
      await page.getByRole('button', { name: /Check (in|out)/ }).waitFor()
      if (await page.getByText('People', { exact: true }).count()) throw new Error('HR menu visible to employee')
      await page.screenshot({ path: `${OUT}/01-employee-home.png` })
    })
    await step('apply for leave from the UI', async () => {
      await page.goto(`${BASE}/alphax/me/leave`)
      await page.getByRole('button', { name: 'Apply for leave' }).first().click()
      const dialog = page.getByRole('dialog')
      await dialog.locator('select').selectOption({ label: 'AXT Annual' })
      // Try a few random dates: the server correctly rejects overlaps with earlier runs.
      const year = new Date().getUTCFullYear()
      let submitted = false
      for (let attempt = 0; attempt < 6 && !submitted; attempt++) {
        const d = new Date(Date.now() + (10 + Math.floor(Math.random() * 45)) * 86400000)
        while (d.getUTCDay() === 5) d.setUTCDate(d.getUTCDate() + 1)
        if (d.getUTCFullYear() !== year) continue
        const iso = d.toISOString().slice(0, 10)
        const dates = dialog.locator('input[type=date]')
        await dates.nth(0).fill(iso)
        await dates.nth(1).fill(iso)
        await dialog.locator('textarea').fill('E2E test leave')
        if (attempt === 0) await page.screenshot({ path: `${OUT}/02-apply-leave.png` })
        await dialog.getByRole('button', { name: 'Submit request' }).click()
        const outcome = await Promise.race([
          page.getByText('Request submitted').waitFor({ timeout: 15000 }).then(() => 'ok'),
          dialog.getByRole('alert').waitFor({ timeout: 15000 }).then(() => 'error'),
        ])
        submitted = outcome === 'ok'
      }
      if (!submitted) throw new Error('could not submit a leave request')
      await page.screenshot({ path: `${OUT}/03-my-leave.png` })
    })
    await step('attendance calendar renders', async () => {
      await page.goto(`${BASE}/alphax/me/attendance`)
      await page.getByText('Late entries').waitFor()
      await page.screenshot({ path: `${OUT}/04-attendance.png` })
    })
    await step('statutory leave asks for event date and relation', async () => {
      await page.goto(`${BASE}/alphax/me/leave`)
      await page.getByRole('button', { name: 'Apply for leave' }).first().click()
      const dialog = page.getByRole('dialog')
      await dialog.locator('select').first().selectOption({ label: 'Bereavement Leave (Sibling)' })
      await dialog.getByText('Saudi Labor Law rule').waitFor()
      await dialog.getByText('Date of death').waitFor()
      await dialog.locator('select').nth(1).selectOption('Brother')
      await page.screenshot({ path: `${OUT}/05b-statutory-leave.png` })
      await page.keyboard.press('Escape')
    })

    await step('attendance requests from My Attendance', async () => {
      await page.goto(`${BASE}/alphax/me/attendance`)
      await page.getByRole('button', { name: 'Correct attendance' }).click()
      const dialog = page.getByRole('dialog')
      await dialog.locator('textarea').fill('E2E: forgot to punch out')
      await page.screenshot({ path: `${OUT}/04b-correct-attendance.png` })
      await dialog.getByRole('button', { name: 'Send request' }).click()
      await Promise.race([
        page.getByText('Request sent to your approver.').waitFor({ timeout: 15000 }),
        dialog.getByRole('alert').waitFor({ timeout: 15000 }),  // an overlapping request from an earlier run is a valid refusal
      ])
      if (await dialog.isVisible().catch(() => false)) await page.keyboard.press('Escape')
    })

    await step('employee raises a salary certificate request', async () => {
      await page.goto(`${BASE}/alphax/me/requests`)
      await page.getByRole('button', { name: 'New request' }).first().click()
      const dlg = page.getByRole('dialog')
      await dlg.locator('select').first().selectOption('Salary Certificate')
      await dlg.locator('input[type=text]').first().fill('Al Rajhi Bank')
      await dlg.locator('select').nth(1).selectOption('Bank')
      await page.screenshot({ path: `${OUT}/20-new-request.png` })
      await dlg.getByRole('button', { name: 'Submit request' }).click()
      await dlg.waitFor({ state: 'detached' })
      await page.getByText('Pending HR').first().waitFor()
      await page.screenshot({ path: `${OUT}/20b-my-requests.png`, fullPage: true })
    })
    await step('my warnings page', async () => {
      await page.goto(`${BASE}/alphax/me/warnings`)
      await page.getByRole('heading', { name: 'My warnings' }).waitFor()
    })
    await step('vacation plan: add a period next year and save', async () => {
      await page.goto(`${BASE}/alphax/me/vacation-plan`)
      await page.getByRole('heading', { name: 'Vacation plan' }).waitFor()
      const next = String(new Date().getFullYear() + 1)
      await page.locator('select').first().selectOption(next)
      await page.getByText('Planned periods').waitFor()
      const add = page.getByRole('button', { name: 'Add period' })
      if (await add.isVisible()) {
        await add.click()
        const row = page.locator('li').filter({ has: page.locator('input[type=date]') }).last()
        await row.locator('input[type=date]').nth(0).fill(`${next}-03-01`)
        await row.locator('input[type=date]').nth(1).fill(`${next}-03-10`)
        await page.getByRole('button', { name: 'Save draft' }).click()
        await page.getByText('working days').first().waitFor()
      }
      await page.screenshot({ path: `${OUT}/27-vacation-plan.png`, fullPage: true })
    })
    await step('profile: documents card and change request form', async () => {
      await page.goto(`${BASE}/alphax/me/profile`)
      await page.getByText('Documents & personal details').waitFor()
      const btn = page.getByRole('button', { name: 'Request a change' })
      if (await btn.isVisible()) {
        await btn.click()
        await page.getByRole('dialog').getByText('Copy of the new document').waitFor()
        await page.screenshot({ path: `${OUT}/31-profile-change.png` })
        await page.keyboard.press('Escape')
      }
      await page.goto(`${BASE}/alphax`)
      await page.getByText('Recent activity').waitFor()
      await page.screenshot({ path: `${OUT}/32-home-employee.png`, fullPage: true })
    })
    await step('help centre and notifications card', async () => {
      await page.goto(`${BASE}/alphax/me/help`)
      await page.getByRole('heading', { name: 'Help centre' }).waitFor()
      await page.getByRole('button', { name: 'Ask HR' }).first().click()
      await page.getByRole('dialog').getByText('Your question').waitFor()
      await page.screenshot({ path: `${OUT}/33-help-centre.png` })
      await page.keyboard.press('Escape')
      await page.goto(`${BASE}/alphax/me/profile`)
      await page.getByText('Notifications on this device').waitFor()
    })
    await step('HR pages are not reachable by URL', async () => {
      await page.goto(`${BASE}/alphax/people`)
      await page.waitForURL(/\/alphax\/?$/)
    })
    if (errors.length) fail('employee: no console errors', errors.join(' | ')); else ok('employee: no console errors')
    await ctx.close()
  }

  console.log('\n== Employee (Arabic, phone)')
  {
    const { page, errors, ctx } = await session(browser, 'emp2@axt.test', { lang: 'ar', mobile: true })
    await step('Arabic RTL layout on phone', async () => {
      await page.goto(`${BASE}/alphax`)
      await page.getByText('رصيد الإجازات').waitFor()
      const dir = await page.evaluate(() => document.documentElement.dir)
      if (dir !== 'rtl') throw new Error('dir=' + dir)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
      if (overflow) throw new Error('horizontal overflow on phone')
      await page.screenshot({ path: `${OUT}/05-arabic-phone-home.png`, fullPage: true })
    })
    await step('phone: tab bar, services and a late-arrival permission (Arabic)', async () => {
      await page.goto(`${BASE}/alphax`)
      const tabs = page.getByRole('navigation', { name: 'الرئيسية' })
      await tabs.waitFor()
      await page.getByText('آخر النشاطات').waitFor()
      const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
      if (wide) throw new Error('home is wider than the phone screen')
      await tabs.getByText('الخدمات').click()
      await page.getByRole('heading', { name: 'الخدمات' }).waitFor()
      await page.screenshot({ path: `${OUT}/26-phone-services.png`, fullPage: true })
      await page.getByRole('button', { name: 'استئذان تأخير' }).click()
      const dlg = page.getByRole('dialog')
      const d = new Date(Date.now() + 9 * 86400000).toISOString().slice(0, 10)
      await dlg.locator('input[type=date]').fill(d)
      await dlg.locator('input[type=time]').fill('09:45')
      await dlg.getByRole('button', { name: 'إرسال الطلب' }).click()
      await dlg.waitFor({ state: 'detached' })
      await page.goto(`${BASE}/alphax/me/attendance`)
      await page.getByText('استئذان تأخير').first().waitFor()
      await page.screenshot({ path: `${OUT}/26b-phone-attendance.png`, fullPage: true })
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
      if (overflow) throw new Error('horizontal overflow on phone')
    })
    await step('phone: my documents and expenses', async () => {
      await page.goto(`${BASE}/alphax/me/documents`)
      await page.getByRole('heading', { name: 'مستنداتي' }).waitFor()
      await page.goto(`${BASE}/alphax/me/expenses`)
      await page.getByRole('heading', { name: 'مصروفاتي' }).waitFor()
      await page.screenshot({ path: `${OUT}/26c-phone-expenses.png`, fullPage: true })
    })
    await step('installable: manifest and service worker', async () => {
      const m = await page.request.get(`${BASE}/assets/alphax_hr/frontend/manifest.webmanifest`)
      const j = await m.json()
      if (j.scope !== '/alphax' || !j.icons.some((i) => i.purpose === 'maskable')) throw new Error('manifest')
      const sw = await page.request.get(`${BASE}/api/method/alphax_hr.api.pwa.service_worker`)
      if (!sw.headers()['content-type']?.includes('javascript') || sw.headers()['service-worker-allowed'] !== '/alphax') throw new Error('sw headers ' + JSON.stringify(sw.headers()))
      // Service workers need HTTPS (or localhost); the test host is plain http, so only check where allowed.
      const reg = await page.evaluate(async () => {
        if (!window.isSecureContext || !navigator.serviceWorker) return 'insecure-context'
        await new Promise((r) => setTimeout(r, 1500))
        const r = await navigator.serviceWorker.getRegistration('/alphax'); return r ? r.scope : null
      })
      if (!reg) throw new Error('service worker not registered')
    })
    await step('Arabic leave page on phone', async () => {
      await page.goto(`${BASE}/alphax/me/leave`)
      await page.getByText('طلباتي').waitFor()
      await page.screenshot({ path: `${OUT}/06-arabic-phone-leave.png`, fullPage: true })
    })
    await step('phone: notification list fits the screen', async () => {
      await page.getByTestId('bell').click()
      const box = await page.getByTestId('bell-list').boundingBox()
      const width = page.viewportSize().width
      if (!box || box.x < 0 || box.x + box.width > width + 1) throw new Error(`notification list off screen: ${JSON.stringify(box)} / ${width}`)
      await page.screenshot({ path: `${OUT}/06b-phone-bell.png` })
      await page.getByTestId('bell').click()
    })
    await step('phone: my loans', async () => {
      await page.goto(`${BASE}/alphax/me/loans`)
      await page.getByRole('heading', { name: 'قروضي' }).waitFor()
    })
    if (errors.length) fail('arabic: no console errors', errors.join(' | ')); else ok('arabic: no console errors')
    await ctx.close()
  }

  console.log('\n== Manager')
  {
    const { page, errors, ctx } = await session(browser, 'mgr@axt.test')
    await step('approve the request from the inbox', async () => {
      await page.goto(`${BASE}/alphax/approvals`)
      const row = page.locator('li', { hasText: 'E2E test leave' }).first()
      await row.waitFor()
      await page.screenshot({ path: `${OUT}/07-approvals.png` })
      await row.getByRole('button', { name: 'Approve' }).click()
      await page.getByRole('dialog').locator('textarea').fill('Approved in E2E')
      await page.getByRole('dialog').getByRole('button', { name: 'Approve' }).click()
      await page.getByRole('dialog').waitFor({ state: 'detached', timeout: 15000 })
      await page.locator('li', { hasText: 'E2E test leave' }).waitFor({ state: 'detached', timeout: 15000 })
    })
    await step('team calendar shows the approved leave', async () => {
      await page.goto(`${BASE}/alphax/team`)
      await page.getByText('Eman').first().waitFor()
      await page.screenshot({ path: `${OUT}/08-team-calendar.png` })
    })
    if (errors.length) fail('manager: no console errors', errors.join(' | ')); else ok('manager: no console errors')
    await ctx.close()
  }

  console.log('\n== HR')
  {
    const { page, errors, ctx } = await session(browser, 'hr@axt.test')
    await step('HR home dashboard', async () => {
      await page.goto(`${BASE}/alphax`)
      await page.getByText('Data readiness').waitFor()
      await page.waitForTimeout(800)
      await page.screenshot({ path: `${OUT}/09-hr-home.png`, fullPage: true })
    })
    await step('leave counting rule, notification settings, approval delays, bell', async () => {
      await page.goto(`${BASE}/alphax/leave-setup`)
      const card = page.locator('section', { hasText: 'How leave days are counted' }).first()
      await card.waitFor()
      await card.getByRole('button', { name: 'Add rule' }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: 'Leave counting rule' })
      const types = await dialog.locator('select').first().locator('option').allTextContents()
      if (types.length < 2) throw new Error('no leave types offered')
      await dialog.locator('select').nth(1).selectOption('Working days only')
      await dialog.locator('select').nth(2).selectOption('Inside one request')
      await dialog.getByText('Public holidays between leave days count too').waitFor()
      await page.screenshot({ path: `${OUT}/09b-leave-counting.png` })
      await dialog.getByRole('button', { name: 'Cancel' }).click()
      await page.goto(`${BASE}/alphax/notifications-setup`)
      await page.getByText('Emergency leave', { exact: true }).waitFor()
      await page.getByText('Missing check-in', { exact: true }).waitFor()
      await page.screenshot({ path: `${OUT}/09c-notifications.png`, fullPage: true })
      await page.goto(`${BASE}/alphax/approval-delays`)
      await page.getByText('Waiting for a decision').waitFor()
      await page.screenshot({ path: `${OUT}/09d-approval-delays.png`, fullPage: true })
      await page.getByTestId('bell').click()
      await page.getByText('Notifications', { exact: true }).first().waitFor()
    })
    await step('people search and profile edit', async () => {
      await page.goto(`${BASE}/alphax/people`)
      await page.getByPlaceholder('Search people, ID or Iqama…').fill('Omar')
      await page.getByText('Omar Test').first().click()
      await page.getByRole('dialog', { name: 'Quick view' }).getByText('Open full profile').waitFor()
      await page.screenshot({ path: `${OUT}/10a-quick-view.png` })
      await page.getByRole('button', { name: 'Open full profile' }).click()
      await page.getByText('Saudi compliance').waitFor()
      const popup = page.getByRole('dialog').filter({ hasText: 'Mandatory fields missing' })
      if (await popup.isVisible().catch(() => false)) await page.keyboard.press('Escape')
      await page.screenshot({ path: `${OUT}/10-employee-profile.png`, fullPage: true })
      const card = page.locator('section', { hasText: 'Contact' }).first()
      await card.getByRole('button', { name: 'Edit' }).click()
      const mobile = card.locator('label', { hasText: 'Mobile' }).first().locator('input')
      const phone = '055' + String(Date.now()).slice(-7)
      await mobile.fill(phone)
      await card.getByRole('button', { name: 'Save' }).click()
      await card.getByText(phone).waitFor({ timeout: 15000 })
    })
    await step('people table, org chart and export', async () => {
      await page.goto(`${BASE}/alphax/people?view=table`)
      await page.getByRole('columnheader', { name: 'National ID / Iqama' }).waitFor()
      await page.screenshot({ path: `${OUT}/10b-people-table.png` })
      await page.getByRole('tab', { name: 'Org chart' }).click()
      await page.getByRole('tab', { name: 'Chart', exact: true }).click()
      await page.locator('.oc-tree').first().waitFor()
      await page.screenshot({ path: `${OUT}/10c-org-chart.png`, fullPage: true })
      await page.getByRole('tab', { name: 'By department' }).click()
      await page.locator('span.truncate', { hasText: 'Operations - AXT' }).first().waitFor()  // not the hidden <option>
      await page.screenshot({ path: `${OUT}/10c2-org-departments.png`, fullPage: true })
      await page.getByRole('tab', { name: 'Tree', exact: true }).click()
      await page.getByText('Expand all').waitFor()
      for (const [label, ext] of [['Chart (boxes)', '.pdf'], ['Reporting lines (outline)', '.docx'], ['Excel (.xlsx)', '.xlsx']]) {
        await page.getByRole('button', { name: 'Export' }).last().click()
        const [download] = await Promise.all([page.waitForEvent('download'), page.getByText(label, { exact: true }).click()])
        if (!download.suggestedFilename().endsWith(ext)) throw new Error('unexpected export ' + download.suggestedFilename())
      }
    })
    await step('delete several employees from the people table', async () => {
      const tag = `Del${Date.now().toString(36)}`
      const made = await page.evaluate(async (tag) => {
        const out = []
        for (const last of ['Alpha', 'Beta']) {
          const r = await fetch('/api/method/alphax_hr.api.hr.create_employee', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.ALPHAX_BOOT.csrf_token },
            body: JSON.stringify({ data: { first_name: tag, last_name: last, gender: 'Male', date_of_birth: '1990-01-01', date_of_joining: new Date().toISOString().slice(0, 10),
              company: 'AlphaX Test Co', alphax_is_saudi: 1, alphax_iqama_number: '1' + String(Math.floor(Math.random() * 1e9)).padStart(9, '0') } }) })
          const j = await r.json(); if (!r.ok) throw new Error(JSON.stringify(j).slice(0, 300)); out.push(j.message.name)
        }
        return out
      }, tag)
      await page.goto(`${BASE}/alphax/people?view=table`)
      await page.getByPlaceholder('Search people, ID or Iqama…').fill(tag)
      await page.getByRole('checkbox', { name: `Select ${tag} Alpha` }).check()
      await page.getByRole('checkbox', { name: `Select ${tag} Beta` }).check()
      await page.getByRole('button', { name: 'Delete selected' }).click()
      await page.getByRole('dialog').getByText(`${tag} Beta`).waitFor()
      await page.screenshot({ path: `${OUT}/10f-delete-employees.png` })
      await page.getByRole('button', { name: 'Delete permanently' }).click()
      await page.getByRole('dialog').getByText('2 deleted').waitFor()
      await page.getByRole('dialog').getByRole('button', { name: 'Close' }).last().click()
      const left = await page.evaluate(async ([ids, tag]) => {
        const r = await fetch('/api/method/alphax_hr.api.hr.employees', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.ALPHAX_BOOT.csrf_token }, body: JSON.stringify({ search: tag, status: '' }) })
        return (await r.json()).message.rows.map((x) => x.name).filter((n) => ids.includes(n))
      }, [made, tag])
      if (left.length) throw new Error('employees not deleted: ' + left.join(', '))
    })

    await step('new employee wizard checks each step', async () => {
      await page.goto(`${BASE}/alphax/people/new`)
      await page.getByRole('button', { name: 'Personal & contact' }).waitFor()
      await page.getByRole('button', { name: 'Next' }).click()
      await page.getByRole('dialog').getByText('These fields are mandatory').waitFor()
      await page.screenshot({ path: `${OUT}/10d-new-employee-missing.png` })
      await page.keyboard.press('Escape')
      await page.locator('[data-field="alphax_iqama_number"] input').fill('2123456789')
      await page.getByText('Non-Saudi (Iqama)').waitFor()
      await page.screenshot({ path: `${OUT}/10e-new-employee-identity.png` })
    })

    await step('roster: assign a shift to selected employees', async () => {
      await page.goto(`${BASE}/alphax/roster`)
      await page.getByText('Faded = default shift', { exact: false }).waitFor()
      await page.screenshot({ path: `${OUT}/12-roster.png`, fullPage: true })
      await page.getByRole('row').nth(1).locator('input[type=checkbox]').check()
      await page.getByRole('button', { name: /Assign shift/ }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Assign' }).click()
      await page.getByRole('dialog').getByText(/Assigned|Not assigned/).first().waitFor({ timeout: 20000 })
      await page.screenshot({ path: `${OUT}/12b-roster-assigned.png` })
      await page.getByRole('dialog').getByRole('button', { name: 'Close' }).last().click()
    })

    await step('attendance register and overtime', async () => {
      await page.goto(`${BASE}/alphax/attendance`)
      await page.getByText('Missing punches').waitFor()
      await page.getByRole('button', { name: 'Previous' }).click()
      await page.getByText('Late arrivals').waitFor()
      await page.waitForTimeout(800)
      await page.screenshot({ path: `${OUT}/13-attendance-register.png`, fullPage: true })
      await page.getByRole('tab', { name: 'Overtime' }).click()
      await page.getByText('Overtime (Art. 107)').waitFor()
      await page.screenshot({ path: `${OUT}/13b-overtime.png`, fullPage: true })
    })

    await step('approvals: activity trail of a request', async () => {
      await page.goto(`${BASE}/alphax/approvals`)
      await page.getByRole('tab', { name: 'Decided' }).click()
      await page.getByTitle('Show activity').first().click()
      await page.getByRole('dialog', { name: 'Activity' }).getByText('created the request').waitFor()
      await page.screenshot({ path: `${OUT}/14-activity-trail.png` })
      await page.getByRole('link', { name: 'Open record' }).click()
      await page.getByText('Show empty fields').waitFor()
      if (!page.url().includes('/alphax/r/')) throw new Error('record must open inside AlphaX: ' + page.url())
      await page.screenshot({ path: `${OUT}/14b-record-view.png`, fullPage: true })
    })

    await step('activity log, leave balances, week-off dialog', async () => {
      await page.goto(`${BASE}/alphax/activity`)
      await page.getByText('events', { exact: false }).first().waitFor()
      await page.screenshot({ path: `${OUT}/15-activity-log.png`, fullPage: true })
      await page.goto(`${BASE}/alphax/leave-balances`)
      await page.getByText('Sick left (of 120)').waitFor()
      await page.getByRole('row').nth(1).click()
      await page.getByRole('dialog', { name: 'Leave ledger' }).getByText('Leave ledger').first().waitFor()
      await page.screenshot({ path: `${OUT}/16-leave-ledger.png` })
      await page.keyboard.press('Escape').catch(() => {})
      await page.goto(`${BASE}/alphax/roster`)
      await page.getByRole('row').nth(1).locator('input[type=checkbox]').check()
      await page.getByRole('button', { name: 'Set week-off' }).click()
      await page.getByRole('dialog').getByText('Replace their current week-offs').waitFor()
      await page.screenshot({ path: `${OUT}/17-week-off.png` })
      await page.getByRole('dialog').getByRole('button', { name: 'Close' }).first().click()
    })

    await step('setup & health page', async () => {
      await page.goto(`${BASE}/alphax/setup`)
      await page.getByText('Employees missing mandatory data').waitFor()
      await page.screenshot({ path: `${OUT}/18-setup-health.png`, fullPage: true })
      if (await page.getByRole('tab', { name: /System|Employee fields/ }).count()) throw new Error('System health and field map live in the Desk only')
      await page.locator('li').filter({ hasText: /Leave approvers|Shift approvers|Reporting managers|Employee user accounts|Employees without salary/ })
        .getByRole('button', { name: 'Fix' }).first().click()
      await page.getByText('Department', { exact: true }).first().waitFor()
      await page.screenshot({ path: `${OUT}/18c-fix-panel.png` })
      await page.keyboard.press('Escape').catch(() => {})
      await page.goto(`${BASE}/alphax/setup`)
      await page.getByRole('tab', { name: 'Settings' }).click()
      await page.getByRole('button', { name: 'Payroll, GOSI & loans' }).click()
      await page.getByText('Salary component mapping').waitFor()
      await page.screenshot({ path: `${OUT}/18b-settings.png`, fullPage: true })
      // finding a setting from any section; an edit shows the unsaved-changes bar until discarded
      await page.getByPlaceholder('Find a setting…').fill('grace')
      await page.getByText(/Settings matching/).waitFor()
      await page.getByPlaceholder('Find a setting…').fill('')
      await page.getByRole('button', { name: 'Company & branding' }).click()
      const first = page.locator('main input[type="text"]:not([placeholder])').first()
      if (await first.count()) {
        await first.fill(((await first.inputValue()) || '') + ' x')
        await page.getByText(/unsaved changes/).waitFor()
        await page.screenshot({ path: `${OUT}/18d-settings-unsaved.png` })
        await page.getByRole('button', { name: 'Discard' }).click()
      }
    })

    await step('compliance dashboard', async () => {
      await page.goto(`${BASE}/alphax/compliance`)
      await page.getByText('Saudization (estimate)').waitFor()
      await page.waitForTimeout(500)
      await page.screenshot({ path: `${OUT}/11-compliance.png`, fullPage: true })
    })
    await step('leave setup page', async () => {
      await page.goto(`${BASE}/alphax/leave-setup`)
      await page.getByText('Sick and statutory leave').waitFor()
      await page.getByText('Company policy', { exact: true }).waitFor()
      await page.getByText('Allocation plan').waitFor()
      await page.screenshot({ path: `${OUT}/11b-leave-setup.png`, fullPage: true })
    })

    await step('HR completes the request and the letter is issued', async () => {
      await page.goto(`${BASE}/alphax/requests`)
      await page.locator('select').first().selectOption('Salary Certificate')
      await page.getByRole('button', { name: 'Approve', exact: true }).first().click()
      await page.getByRole('dialog').getByRole('button', { name: 'Approve', exact: true }).click()
      await page.getByRole('dialog').waitFor({ state: 'detached' })
      await page.getByRole('button', { name: 'Completed' }).click()
      await page.getByRole('link', { name: 'Letter' }).first().waitFor()
      await page.screenshot({ path: `${OUT}/21-requests-hr.png`, fullPage: true })
      await page.getByRole('tab', { name: 'Request types' }).click()
      await page.getByText('Exit & Re-entry Visa').waitFor()
    })
    await step('penalties: schedule and new penalty preview', async () => {
      await page.goto(`${BASE}/alphax/penalties`)
      await page.getByRole('tab', { name: 'Violations schedule' }).click()
      await page.getByText('Late arrival up to 15 minutes').waitFor()
      await page.screenshot({ path: `${OUT}/22-violations.png`, fullPage: true })
      await page.getByRole('tab', { name: 'Penalties' }).click()
      await page.screenshot({ path: `${OUT}/22b-penalties.png`, fullPage: true })
    })
    await step('payroll control centre with checklist', async () => {
      await page.goto(`${BASE}/alphax/payroll`)
      await page.getByText('Payroll checklist').waitFor()
      await page.getByText('No salary structure').first().waitFor()
      await page.getByText('GOSI (employee share)').waitFor()
      await page.screenshot({ path: `${OUT}/23-payroll-control.png`, fullPage: true })
      await page.getByRole('button', { name: 'New payroll run' }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: 'Run payroll for' })
      await dialog.locator('select').first().selectOption('Department')
      await dialog.locator('select').nth(1).locator('option').nth(1).waitFor({ state: 'attached', timeout: 10000 })
      await dialog.locator('select').first().selectOption('Employees')
      await dialog.getByText('One employee = single salary processing.').waitFor()
      await page.screenshot({ path: `${OUT}/23b-payroll-new-run.png` })
      await dialog.getByRole('button', { name: 'Cancel' }).click()
    })
    await step('loans, bonuses & deductions', async () => {
      await page.goto(`${BASE}/alphax/payroll/loans`)
      await page.getByText('Being repaid').waitFor()
      await page.getByRole('button', { name: 'New loan or advance' }).click()
      await page.getByRole('dialog').filter({ hasText: 'New loan or salary advance' }).getByRole('button', { name: 'Cancel' }).click()
      await page.screenshot({ path: `${OUT}/23d-loans.png`, fullPage: true })
      await page.goto(`${BASE}/alphax/payroll/adjustments`)
      await page.getByText('Deduction limits for one employee').waitFor()
      await page.getByRole('button', { name: 'Bonus or deduction' }).click()
      const dlg = page.getByRole('dialog').filter({ hasText: 'Category' })
      await dlg.getByRole('button', { name: 'Deduction', exact: true }).click()
      await dlg.locator('select').first().selectOption('Damage or loss (Art. 91)')
      await dlg.getByText('five days', { exact: false }).waitFor()
      await page.screenshot({ path: `${OUT}/23e-adjustment.png` })
      await dlg.getByRole('button', { name: 'Cancel' }).click()
    })
    await step('appraisals: cycles, templates, management approvers', async () => {
      await page.goto(`${BASE}/alphax/appraisals`)
      await page.getByRole('tab', { name: 'Templates' }).click()
      await page.getByText('AXT Standard').waitFor()
      await page.getByRole('tab', { name: 'Management approvers' }).click()
      await page.getByText('This is a role, not the reporting-manager chain.', { exact: false }).waitFor()
      await page.getByRole('tab', { name: 'Cycles' }).click()
      await page.getByText('AXT Cycle', { exact: false }).first().click()
      await page.getByText('Average final score').waitFor()
      await page.screenshot({ path: `${OUT}/23c-appraisal-cycle.png`, fullPage: true })
    })
    await step('final settlements page', async () => {
      await page.goto(`${BASE}/alphax/payroll/settlements`)
      await page.getByRole('heading', { name: 'Final settlements' }).waitFor()
      await page.screenshot({ path: `${OUT}/24-settlements.png`, fullPage: true })
    })
    await step('appraisals and cut-over readiness', async () => {
      await page.goto(`${BASE}/alphax/appraisals`)
      await page.getByRole('heading', { name: 'Appraisals' }).waitFor()
      await page.goto(`${BASE}/alphax/cutover`)
      await page.getByText('Employee requests to import').waitFor()
      await page.screenshot({ path: `${OUT}/25-cutover.png`, fullPage: true })
    })
    await step('attendance exceptions and vacation planner', async () => {
      await page.goto(`${BASE}/alphax/attendance-policies`)
      await page.getByRole('heading', { name: 'Attendance exceptions' }).waitFor()
      await page.getByRole('button', { name: 'New policy' }).click()
      await page.getByRole('dialog').getByText('Exempt from attendance tracking').waitFor()
      await page.screenshot({ path: `${OUT}/28-attendance-policy.png` })
      await page.keyboard.press('Escape')
      await page.goto(`${BASE}/alphax/vacation-planner`)
      await page.getByText('Away per week').or(page.getByText('No plans yet')).first().waitFor()
      await page.screenshot({ path: `${OUT}/29-vacation-planner.png`, fullPage: true })
    })
    await step('contract preview and PDF download over HTTP', async () => {
      const empId = await page.evaluate(async () => {
        const r = await fetch('/api/method/alphax_hr.api.hr.employees', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.ALPHAX_BOOT.csrf_token }, body: JSON.stringify({ search: 'Eman' }) })
        return (await r.json()).message.rows[0].name
      })
      await page.goto(`${BASE}/alphax/people/${empId}/contract`)
      await page.getByRole('button', { name: 'Download PDF' }).waitFor()
      const res = await page.request.get(`${BASE}/api/method/alphax_hr.api.contract.download?employee=${encodeURIComponent(empId)}`)
      const body = await res.body()
      if (!res.ok() || body.subarray(0, 4).toString() !== '%PDF') throw new Error('contract PDF ' + res.status())
    })
    await step('profile change request and announcements', async () => {
      await page.goto(`${BASE}/alphax/announcements`)
      await page.getByRole('heading', { name: 'Announcements' }).waitFor()
      await page.screenshot({ path: `${OUT}/30-announcements.png`, fullPage: true })
    })
    await step('check-ins & movements, work locations, payslip preview', async () => {
      await page.goto(`${BASE}/alphax/checkins`)
      await page.getByText('Outside a work location').first().waitFor()
      await page.screenshot({ path: `${OUT}/34-checkins.png`, fullPage: true })
      await page.goto(`${BASE}/alphax/work-locations`)
      await page.getByRole('heading', { name: 'Work locations' }).waitFor()
      await page.goto(`${BASE}/alphax/setup`)
      await page.getByRole('tab', { name: 'Settings' }).click()
      await page.getByRole('button', { name: 'Payslips & letters' }).click()
      await page.getByRole('button', { name: 'Preview payslip' }).click()
      await page.getByRole('dialog').getByText('Net pay').first().waitFor()
      await page.screenshot({ path: `${OUT}/35-payslip.png`, fullPage: true })
      await page.keyboard.press('Escape')
    })
    await step('accruals preview and page access settings', async () => {
      await page.goto(`${BASE}/alphax/payroll/accruals`)
      await page.getByText('Monthly provisions for end of service and annual leave').waitFor()
      await page.getByText('Posted runs').waitFor()
      await page.screenshot({ path: `${OUT}/35-accruals.png`, fullPage: true })
      await page.goto(`${BASE}/alphax/setup#settings`)
      await page.getByRole('button', { name: 'Portal & pages' }).click()
      await page.getByText('Hide pages for everyone').waitFor()
    })
    await step('GOSI register', async () => {
      await page.goto(`${BASE}/alphax/payroll/gosi`)
      await page.getByText('Employer share').first().waitFor()
      await page.screenshot({ path: `${OUT}/12-gosi.png`, fullPage: true })
    })
    await step('end-of-service calculator', async () => {
      await page.goto(`${BASE}/alphax/payroll/eosb`)
      const inputs = page.locator('form input')
      await inputs.nth(0).fill('')
      const empId = await page.evaluate(async () => {
        const r = await fetch('/api/method/alphax_hr.api.hr.employees', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': window.ALPHAX_BOOT.csrf_token }, body: JSON.stringify({ search: 'Eman' }) })
        return (await r.json()).message.rows[0].name
      })
      await inputs.nth(0).fill(empId)
      await page.locator('form select').selectOption('Resignation')
      await inputs.nth(2).fill('12000')
      await page.getByRole('button', { name: 'Calculate' }).click()
      await page.getByText('Gross award').waitFor()
      await page.screenshot({ path: `${OUT}/13-eosb.png` })
    })
    if (errors.length) fail('hr: no console errors', errors.join(' | ')); else ok('hr: no console errors')
    await ctx.close()
  }
  console.log('\n== Sign-in page (guest)')
  {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 } })
    const page = await ctx.newPage()
    await step('AlphaX sign-in page signs an employee in and lands on /alphax', async () => {
      await page.goto(`${BASE}/alphax`)
      await page.waitForURL(/\/alphax-login/)
      await page.locator('#usr').waitFor()
      await page.screenshot({ path: `${OUT}/36-sign-in.png` })
      await page.locator('#usr').fill('emp@axt.test')
      await page.locator('#pwd').fill(PASSWORD)
      await page.locator('#go').click()
      await page.waitForURL(/\/alphax(\/|$|\?)/)
      await page.getByText(/Leave balance|رصيد الإجازات/).first().waitFor()  // user's own language
    })
    await ctx.close()
    const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
    await phone.addInitScript(() => localStorage.setItem('alphax-lang', 'ar'))
    const p2 = await phone.newPage()
    await step('sign-in page in Arabic on a phone', async () => {
      await p2.goto(`${BASE}/alphax-login`)
      await p2.locator('html[dir="rtl"]').waitFor()
      await p2.screenshot({ path: `${OUT}/36b-sign-in-ar-phone.png` })
    })
    await phone.close()
  }
} finally {
  await browser.close()
}
const failed = results.filter(([p]) => !p)
console.log(`\n${results.length - failed.length} passed, ${failed.length} failed`)
process.exit(failed.length ? 1 : 0)
