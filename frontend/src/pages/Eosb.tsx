import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, Input, PageHeader, Select } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const REASONS = ['Termination by employer', 'End of fixed-term contract', 'Resignation', 'Resignation – Article 87 exception', 'Dismissal under Article 80']

export default function Eosb() {
  const { t, lang } = useI18n()
  const [f, setF] = useState({ employee: '', exit_date: todayISO(), reason: REASONS[0], monthly_wage: '' })
  const m = useMutation<any>({ mutationFn: () => api.eosb({ ...f, monthly_wage: f.monthly_wage === '' ? undefined : Number(f.monthly_wage) }) })
  const r = m.data
  return (
    <div>
      <PageHeader title={t('End of Service')} subtitle="Saudi Labor Law · Art. 84, 85, 87, 80" />
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
            <Field label={t('Employee')}><LinkInput doctype="Employee" required value={f.employee} onChange={(v) => setF({ ...f, employee: v })} /></Field>
            <Field label={t('Exit date')}><Input type="date" required value={f.exit_date} onChange={(e) => setF({ ...f, exit_date: e.target.value })} /></Field>
            <Field label={t('Reason')}><Select value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })}>{REASONS.map((x) => <option key={x} value={x}>{t(x)}</option>)}</Select></Field>
            <Field label={t('Monthly wage (optional)')} hint="Empty = last salary slip (EOSB Wage components)"><Input type="number" min="0" step="0.01" value={f.monthly_wage} onChange={(e) => setF({ ...f, monthly_wage: e.target.value })} /></Field>
            <Button type="submit" loading={m.isPending}>{t('Calculate')}</Button>
            {m.error && <ErrorBox error={m.error} />}
          </form>
        </Card>
        <Card className="lg:col-span-3" title={r ? r.employee_name : t('Award')}>
          {!r ? <p className="text-sm text-muted">—</p> : (
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl bg-brand p-5 text-white">
                <div className="text-sm text-white/70">{t('Award')}</div>
                <div className="text-4xl font-semibold tabular-nums">{fmtMoney(r.award, lang)}</div>
                <div className="mt-1 text-sm text-white/80">{t(r.reason)} · {t('Entitlement')} {fmtNumber(r.entitlement_factor * 100, lang, 1)}%</div>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-muted">{t('Date of joining')}</dt><dd className="font-medium">{fmtDate(r.date_of_joining, lang)}</dd></div>
                <div><dt className="text-muted">{t('Exit date')}</dt><dd className="font-medium">{fmtDate(r.exit_date, lang)}</dd></div>
                <div><dt className="text-muted">{t('Service')}</dt><dd className="font-medium">{fmtNumber(r.service_years, lang, 2)} {t('years')}</dd></div>
                <div><dt className="text-muted">{t('Monthly wage (optional)').replace(/ \(.*\)/, '')}</dt><dd className="font-medium">{fmtMoney(r.monthly_wage, lang)} <span className="text-xs text-muted">({r.wage_source})</span></dd></div>
              </dl>
              <ul className="divide-y divide-line rounded-xl border border-line text-sm">
                <li className="flex justify-between p-3"><span>{t('First 5 years (½ month/year)')} · {fmtNumber(r.breakdown[0].years, lang, 2)}</span><span className="tabular-nums">{fmtMoney(r.breakdown[0].amount, lang)}</span></li>
                <li className="flex justify-between p-3"><span>{t('After 5 years (1 month/year)')} · {fmtNumber(r.breakdown[1].years, lang, 2)}</span><span className="tabular-nums">{fmtMoney(r.breakdown[1].amount, lang)}</span></li>
                <li className="flex justify-between p-3 font-medium"><span>{t('Gross award')}</span><span className="tabular-nums">{fmtMoney(r.gross_award, lang)}</span></li>
              </ul>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
