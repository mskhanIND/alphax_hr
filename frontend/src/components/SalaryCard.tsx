import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { SalaryEditor, packageReady, type SalaryPackage } from './SalaryEditor'
import { Button, Card, ErrorBox, Field, Input, Modal, Spinner } from './ui'

/** Profile: current salary structure, history, and "Change salary" from a date. */
export function SalaryCard({ employee, isSaudi, gosiDate, company, canWrite }: { employee: string; isSaudi: boolean; gosiDate?: string; company?: string; canWrite: boolean }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['salary', employee], queryFn: () => api.currentSalary(employee) })
  const [open, setOpen] = useState(false)
  const [pkg, setPkg] = useState<SalaryPackage>({ mode: 'total' })
  const [from, setFrom] = useState(todayISO())
  const m = useMutation({ mutationFn: () => api.setSalary(employee, pkg as any, from), onSuccess: () => { setOpen(false); qc.invalidateQueries({ queryKey: ['salary', employee] }) } })
  const cur = q.data?.current
  return (
    <Card title={t('Salary')} action={canWrite ? <Button size="sm" variant="ghost" className="print:hidden" onClick={() => setOpen(true)}>{cur ? t('Change salary') : t('Set salary')}</Button> : undefined}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !cur ? <p className="text-sm text-muted">{t('No salary assigned yet.')}</p> : (
        <div className="text-sm">
          <div className="mb-2 text-xs text-muted">{cur.salary_structure} · {t('from')} {fmtDate(cur.from_date, lang)}</div>
          <ul className="divide-y divide-line">
            {cur.earnings.map((r: any) => <li key={r.salary_component} className="flex justify-between py-1.5"><span>{r.salary_component}</span><span className="tabular-nums">{r.amount_based_on_formula ? r.formula : fmtMoney(r.amount, lang)}</span></li>)}
            <li className="flex justify-between py-1.5 font-medium"><span>{t('Gross')}</span><span className="tabular-nums">{fmtMoney(cur.gross, lang)}</span></li>
            {cur.deductions.map((r: any) => <li key={r.salary_component} className="flex justify-between py-1.5 text-red-700"><span>{r.salary_component}</span><span className="tabular-nums">−{fmtMoney(r.amount, lang)}</span></li>)}
            <li className="flex justify-between py-1.5 font-semibold"><span>{t('Net monthly')}</span><span className="tabular-nums">{fmtMoney(cur.net, lang)}</span></li>
          </ul>
          <div className="mt-3 text-xs" data-testid="salary-history">
            <div className="mb-1 font-medium text-muted">{t('Salary history')}</div>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {q.data.history.map((h: any) => (
                <li key={h.name} className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5">
                  <span>{t('From')} {fmtDate(h.from_date, lang)}{h.alphax_total_package ? ` · ${fmtMoney(h.alphax_total_package, lang)}` : ''}
                    {h.alphax_package_mode ? <span className="text-muted"> · {t(h.alphax_package_mode)}</span> : null}</span>
                  <span className="flex items-center gap-2 text-muted">{t('Created')} {fmtDate(h.created_on, lang)} · {h.created_by}
                    <span className={h.active ? 'rounded-full bg-emerald-50 px-2 text-emerald-700' : 'rounded-full bg-surface px-2'}>{h.active ? t('In use') : t('Inactive')}</span></span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} wide title={cur ? t('Change salary') : t('Set salary')}>
        <div className="flex flex-col gap-4">
          <Field label={t('Effective from')}><Input type="date" required value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <SalaryEditor value={pkg} onChange={setPkg} isSaudi={isSaudi} gosiDate={gosiDate} startDate={from} company={company} />
          {m.error && <ErrorBox error={m.error} />}
          <Button disabled={!packageReady(pkg) || !from} loading={m.isPending} onClick={() => m.mutate()}>{t('Save salary')}</Button>
        </div>
      </Modal>
    </Card>
  )
}
