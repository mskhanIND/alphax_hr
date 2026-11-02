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
    await step('Arabic leave page on phone', async () => {
      await page.goto(`${BASE}/alphax/me/leave`)
      await page.getByText('طلباتي').waitFor()
      await page.screenshot({ path: `${OUT}/06-arabic-phone-leave.png`, fullPage: true })
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
      await page.getByText('Expand all').waitFor()
      await page.screenshot({ path: `${OUT}/10c-org-chart.png`, fullPage: true })
      await page.getByRole('button', { name: 'Export' }).click()
      const [download] = await Promise.all([page.waitForEvent('download'), page.getByText('Excel (.xlsx)').click()])
      if (!download.suggestedFilename().endsWith('.xlsx')) throw new Error('unexpected export ' + download.suggestedFilename())
    })

    await step('new employee wizard checks each step', async () => {
      await page.goto(`${BASE}/alphax/people/new`)
      await page.getByRole('button', { name: 'Personal & contact' }).waitFor()
      await page.getByRole('button', { name: 'Next' }).click()
      await page.getByRole('dialog').getByText('These fields are mandatory').waitFor()
      await page.screenshot({ path: `${OUT}/10d-new-employee-missing.png` })
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: /Identity/ }).click()
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
} finally {
  await browser.close()
}
const failed = results.filter(([p]) => !p)
console.log(`\n${results.length - failed.length} passed, ${failed.length} failed`)
process.exit(failed.length ? 1 : 0)
