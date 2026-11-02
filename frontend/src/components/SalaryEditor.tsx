import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { fmtMoney } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { ErrorBox, Field, Input, Spinner } from './ui'

export interface SalaryPackage { mode: 'total' | 'components'; total?: number | string; other?: number | string; basic?: number | string; housing?: number | string; transport?: number | string }

export function packageReady(p: SalaryPackage) {
  return p.mode === 'total' ? Number(p.total) > 0 : Number(p.basic) > 0
}

/** Salary package entry with a live breakdown (earnings, GOSI for Saudis, net) computed by the server. */
export function SalaryEditor({ value, onChange, isSaudi, gosiDate, startDate, company }: {
  value: SalaryPackage; onChange: (p: SalaryPackage) => void; isSaudi: boolean; gosiDate?: string; startDate?: string; company?: string
}) {
  const { t, lang } = useI18n()
  const cfg = useQuery<any>({ queryKey: ['salaryConfig', company ?? ''], queryFn: () => api.salaryConfig(company) })
  const [debounced, setDebounced] = useState(value)
  useEffect(() => { const h = setTimeout(() => setDebounced(value), 350); return () => clearTimeout(h) }, [value])
  const prev = useQuery<any>({
    queryKey: ['salaryPreview', debounced, isSaudi, gosiDate, startDate],
    queryFn: () => api.salaryPreview({ package: debounced, is_saudi: isSaudi ? 1 : 0, gosi_registration_date: gosiDate, start_date: startDate }),
    enabled: packageReady(debounced) && !!cfg.data?.ready,
    retry: false,
  })
  const set = (k: keyof SalaryPackage, v: any) => onChange({ ...value, [k]: v })
  const money = (n: number) => fmtMoney(n, lang, cfg.data?.currency ?? 'SAR')
  if (cfg.isLoading) return <Spinner />
  if (cfg.error) return <ErrorBox error={cfg.error} />
  const c = cfg.data
  if (!c.ready) return <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t('Salary components are not set up yet. Ask an HR Manager to set them in Setup → Settings → Salary Package.')}</p>
  const num = (k: keyof SalaryPackage, label: string, hint?: string) => (
    <Field label={label} hint={hint}>
      <Input type="number" min={0} step="0.01" inputMode="decimal" value={value[k] ?? ''} onChange={(e) => set(k, e.target.value)} />
    </Field>
  )
  return (
    <div className="flex flex-col gap-4">
      <div className="flex rounded-xl border border-line p-0.5 self-start" role="tablist">
        {(['total', 'components'] as const).map((m) => (
          <button key={m} type="button" role="tab" aria-selected={value.mode === m} onClick={() => set('mode', m)}
            className={clsx('rounded-lg px-3 py-1.5 text-sm', value.mode === m ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>
            {t(m === 'total' ? 'Total package' : 'Component amounts')}
          </button>
        ))}
      </div>
      {value.mode === 'total' ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {num('total', t('Total monthly package'), `${t('Split into basic, housing')} ${c.housing_percent}% ${t('and transport')} ${c.transport_percent}% ${t('of basic')}.`)}
          {c.other && num('other', `${c.other} (${t('fixed')})`, t('Optional. Taken out of the total before the split.'))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {num('basic', c.basic)}
          {c.housing && num('housing', c.housing, `${t('Usually')} ${c.housing_percent}% ${t('of basic')}`)}
          {c.transport && num('transport', c.transport, `${t('Usually')} ${c.transport_percent}% ${t('of basic')}`)}
          {c.other && num('other', c.other)}
        </div>
      )}
      {packageReady(value) && (
        <div className="rounded-xl border border-line">
          {prev.isFetching && !prev.data ? <Spinner /> : prev.error ? <div className="p-3"><ErrorBox error={prev.error} /></div> : prev.data && (
            <table className="w-full text-sm">
              <tbody className="divide-y divide-line">
                {prev.data.earnings.map((r: any) => (
                  <tr key={r.salary_component}><td className="px-3 py-2">{r.salary_component}</td><td className="px-3 py-2 text-end tabular-nums">{money(r.amount)}</td></tr>
                ))}
                <tr className="bg-surface font-medium"><td className="px-3 py-2">{t('Gross')}</td><td className="px-3 py-2 text-end tabular-nums">{money(prev.data.gross)}</td></tr>
                {prev.data.deductions.map((r: any) => (
                  <tr key={r.salary_component}><td className="px-3 py-2">{r.salary_component}
                    {prev.data.gosi && <span className="ms-2 text-xs text-muted">{t(prev.data.gosi.system)} · {prev.data.gosi.employee_rate}%</span>}</td>
                    <td className="px-3 py-2 text-end tabular-nums text-red-700">−{money(r.amount)}</td></tr>
                ))}
                <tr className="font-semibold"><td className="px-3 py-2">{t('Net monthly')}</td><td className="px-3 py-2 text-end tabular-nums">{money(prev.data.net)}</td></tr>
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
