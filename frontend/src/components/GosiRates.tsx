import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Badge, Button, ErrorBox, Field, Input, Modal, Select, Spinner } from './ui'

const PCT = ['employee_pension', 'employer_pension', 'employee_saned', 'employer_saned', 'employer_hazard'] as const
const LABEL: Record<string, string> = {
  employee_pension: 'Employee annuity %', employer_pension: 'Employer annuity %', employee_saned: 'Employee SANED %',
  employer_saned: 'Employer SANED %', employer_hazard: 'Occupational hazards %',
}
const SYSTEM_HINT: Record<string, string> = {
  New: 'Saudis first registered from 3 July 2024 (annuity rises 0.5% each July until 2028)',
  Legacy: 'Saudis registered before 3 July 2024',
  'Non-Saudi': 'Non-Saudi employees: occupational hazards only, paid by the employer',
}

/** The contribution percentages AlphaX applies, per GOSI system and start date. */
export function GosiRates() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['gosiRates'], queryFn: api.gosiRates })
  const [edit, setEdit] = useState<any>(null)
  const m = useMutation({ mutationFn: (d: any) => api.saveGosiRate(d), onSuccess: (d) => { qc.setQueryData(['gosiRates'], d); setEdit(null) } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const rows: any[] = q.data.rows
  return (
    <div className="mt-5 border-t border-line pt-4">
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{t('Contribution rates')}</div>
        {q.data.can_edit && <Button size="sm" variant="secondary" onClick={() => setEdit({ system: 'New', effective_from: '', employee_pension: '', employer_pension: '', employee_saned: 0.75, employer_saned: 0.75, employer_hazard: 2 })}><Plus className="size-4" />{t('Add rate')}</Button>}
      </div>
      <p className="mb-3 text-xs text-muted">{t('Percent of the contributory wage (basic + housing, within the cap). The row in force on the payroll date is used. Add a row when GOSI announces a change.')}</p>
      {['New', 'Legacy', 'Non-Saudi'].map((sys) => {
        const list = rows.filter((r) => r.system === sys)
        if (!list.length) return null
        return (
          <div key={sys} className="mb-4">
            <div className="text-sm font-semibold">{t(sys === 'New' ? 'New system' : sys === 'Legacy' ? 'Old system' : 'Non-Saudi')}</div>
            <div className="mb-1 text-xs text-muted">{t(SYSTEM_HINT[sys])}</div>
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-sm">
                <thead className="text-xs text-muted"><tr className="border-b border-line">
                  <th className="py-1.5 pe-3 text-start font-medium">{t('From')}</th>
                  <th className="pe-3 text-end font-medium">{t('Employee')}</th>
                  <th className="pe-3 text-end font-medium">{t('Employer')}</th>
                  <th className="pe-3 text-start font-medium text-muted">{t('Breakdown')}</th><th />
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {list.map((r) => (
                    <tr key={r.name} className={r.current ? 'bg-brand-50' : undefined}>
                      <td className="py-1.5 pe-3">{fmtDate(r.effective_from, lang)} {r.current && <Badge tone="green">{t('In force')}</Badge>}</td>
                      <td className="pe-3 text-end font-semibold tabular-nums">{r.employee_total}%</td>
                      <td className="pe-3 text-end font-semibold tabular-nums">{r.employer_total}%</td>
                      <td className="pe-3 text-xs text-muted">{t('Annuity')} {r.employee_pension}/{r.employer_pension} · SANED {r.employee_saned}/{r.employer_saned} · {t('Hazards')} {r.employer_hazard}</td>
                      <td>{q.data.can_edit && <Button size="sm" variant="ghost" aria-label={t('Edit')} onClick={() => setEdit({ ...r })}><Pencil className="size-4" /></Button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.name ? t('Edit rate') : t('Add rate')}
        footer={<><Button variant="secondary" onClick={() => setEdit(null)}>{t('Cancel')}</Button>
          <Button loading={m.isPending} disabled={!edit?.effective_from} onClick={() => m.mutate(edit)}>{t('Save')}</Button></>}>
        {edit && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t('System')}>
              <Select value={edit.system} onChange={(e) => setEdit({ ...edit, system: e.target.value })}>
                {q.data.systems.map((s: string) => <option key={s} value={s}>{t(s === 'New' ? 'New system' : s === 'Legacy' ? 'Old system' : 'Non-Saudi')}</option>)}
              </Select>
            </Field>
            <Field label={t('Starts on')}><Input type="date" value={edit.effective_from ?? ''} onChange={(e) => setEdit({ ...edit, effective_from: e.target.value })} /></Field>
            {PCT.map((k) => (
              <Field key={k} label={t(LABEL[k])}><Input type="number" min={0} max={30} step="0.05" value={edit[k] ?? ''} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></Field>
            ))}
            {m.error && <div className="sm:col-span-2"><ErrorBox error={m.error} /></div>}
          </div>
        )}
      </Modal>
    </div>
  )
}
