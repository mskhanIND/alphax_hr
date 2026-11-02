import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CalendarRange, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Button, Card, ErrorBox, Input, PageHeader, Select, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function VacationPlan() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState<number | undefined>(undefined)
  const q = useQuery({ queryKey: ['vacation-plan', year], queryFn: () => api.myVacationPlan(year) })
  const plan = q.data
  const [rows, setRows] = useState<any[]>([])
  useEffect(() => { if (plan) setRows(plan.periods.map((p: any) => ({ ...p }))) }, [plan])
  const y = plan?.year ?? year ?? thisYear
  const editable = plan && ['Draft', 'Changes requested'].includes(plan.status)
  const refresh = (d: any) => qc.setQueryData(['vacation-plan', year], d)
  const save = useMutation({ mutationFn: () => api.saveVacationPlan(y, rows.filter((r) => r.from_date && r.to_date)), onSuccess: refresh })
  const submit = useMutation({ mutationFn: async () => { await api.saveVacationPlan(y, rows.filter((r) => r.from_date && r.to_date)); return api.submitVacationPlan(y) }, onSuccess: refresh })
  const apply = useMutation({ mutationFn: (idx: number) => api.applyPlannedPeriod(y, idx), onSuccess: () => { qc.invalidateQueries({ queryKey: ['vacation-plan'] }); qc.invalidateQueries({ queryKey: ['myLeaves'] }) } })
  const conflict = (idx: number) => plan?.conflicts?.find((c: any) => c.idx === idx)
  const dirty = plan && JSON.stringify(rows.map((r) => [r.from_date, r.to_date, r.note ?? ''])) !== JSON.stringify(plan.periods.map((r: any) => [r.from_date, r.to_date, r.note ?? '']))
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Vacation plan')} subtitle={t('Plan your annual vacation ahead so your team can cover for you')}
        actions={<Select className="w-28" value={y} onChange={(e) => setYear(Number(e.target.value))}>
          {[thisYear, thisYear + 1].map((x) => <option key={x} value={x}>{x}</option>)}</Select>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : plan && (
        <>
          <Card>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <StatusBadge status={plan.status} />
              <span>{t('Entitlement')}: <b>{fmtNumber(plan.entitlement, lang, 0)}</b> {t('days')}</span>
              <span>{t('Planned')}: <b className={plan.total_days > plan.entitlement ? 'text-red-600' : ''}>{fmtNumber(plan.total_days, lang, 0)}</b> {t('days')}</span>
              {plan.rules.min_block_days > 0 && <span className="text-muted">{t('At least one block of')} {plan.rules.min_block_days} {t('days')}</span>}
              {plan.rules.deadline && <span className="text-muted">{t('Submit by')} {fmtDate(plan.rules.deadline, lang)}</span>}
            </div>
            {plan.manager_note && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('Manager note')}: {plan.manager_note}</p>}
          </Card>
          <Card title={t('Planned periods')} action={editable && <Button size="sm" variant="secondary" onClick={() => setRows([...rows, { from_date: '', to_date: '', note: '' }])}><Plus className="size-4" />{t('Add period')}</Button>}>
            {!rows.length ? <p className="text-sm text-muted">{t('No periods yet. Add the dates you would like to be away.')}</p> : (
              <ul className="flex flex-col gap-3">
                {rows.map((r, i) => {
                  const c = r.idx ? conflict(r.idx) : null
                  return (
                    <li key={i} className="rounded-xl border border-line p-3">
                      <div className="flex flex-wrap items-end gap-2">
                        <label className="text-xs text-muted">{t('From')}<Input type="date" disabled={!editable} value={r.from_date} min={`${y}-01-01`} max={`${y}-12-31`} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, from_date: e.target.value, to_date: x.to_date && x.to_date >= e.target.value ? x.to_date : e.target.value } : x))} /></label>
                        <label className="text-xs text-muted">{t('To')}<Input type="date" disabled={!editable} value={r.to_date} min={r.from_date} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, to_date: e.target.value } : x))} /></label>
                        <label className="min-w-40 flex-1 text-xs text-muted">{t('Note')}<Input disabled={!editable} value={r.note ?? ''} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, note: e.target.value } : x))} /></label>
                        {r.days > 0 && <Badge tone="blue">{fmtNumber(r.days, lang, 0)} {t('working days')}</Badge>}
                        {editable && <button className="rounded-lg p-2 text-muted hover:bg-surface" aria-label={t('Delete')} onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 className="size-4" /></button>}
                        {plan.status === 'Approved' && !r.leave_application && <Button size="sm" loading={apply.isPending && apply.variables === r.idx} onClick={() => apply.mutate(r.idx)}>{t('Apply for this leave')}</Button>}
                        {r.leave_application && <StatusBadge status={r.leave_status} />}
                      </div>
                      {c && c.max_off > 1 && (
                        <p className={`mt-2 flex items-center gap-1.5 text-xs ${c.over_limit ? 'text-red-700' : 'text-muted'}`}>
                          {c.over_limit && <AlertTriangle className="size-3.5" />}
                          {t('Also away then')}: {c.colleagues.join(', ')} · {c.max_off}/{c.headcount} ({c.percent}%)
                        </p>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
            {(save.error || submit.error || apply.error) && <div className="mt-3"><ErrorBox error={save.error || submit.error || apply.error} /></div>}
            {(submit.data as any)?.warnings?.map((w: string) => <p key={w} className="mt-2 text-sm text-amber-800">{w}</p>)}
            {editable && (
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="secondary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>{t('Save draft')}</Button>
                <Button disabled={!rows.length} loading={submit.isPending} onClick={() => submit.mutate()}><CalendarRange className="size-4" />{t('Send to my manager')}</Button>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
