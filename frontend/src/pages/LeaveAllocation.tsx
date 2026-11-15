import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarPlus, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Stat, Table, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

/** This service year's annual leave: how many employees still need it, and one button to give it. */
function AnnualStrip() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const plan = useQuery<any>({ queryKey: ['annualPlan'], queryFn: () => api.annualAllocation(0) })
  const apply = useMutation({ mutationFn: () => api.annualAllocation(1), onSuccess: (d) => { qc.setQueryData(['annualPlan'], d); qc.invalidateQueries({ queryKey: ['leaveAllocations'] }) } })
  const p = plan.data
  if (!p) return null
  if (!p.configured) return (
    <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('Annual leave is not set up yet.')} <Link className="font-medium underline" to="/leave-setup">{t('Leave setup')}</Link></div>
  )
  const todo = p.counts?.create ?? 0
  return (
    <Card title={`${t('Annual leave')} · ${p.leave_type}`} subtitle={t('Each employee gets annual leave per service year, from their joining anniversary (21 days, 30 after 5 years, or your company policy).')}
      action={<Button size="sm" className="whitespace-nowrap" disabled={!todo} loading={apply.isPending} onClick={() => apply.mutate()}>{t('Give to all who need it')}{todo ? ` (${todo})` : ''}</Button>}>
      <div className="flex flex-wrap gap-4 text-sm">
        <span><b>{todo}</b> {t('still need this year\'s allocation')}</span>
        <span className="text-muted"><b>{p.counts?.exists ?? 0}</b> {t('already have it')}</span>
        {(p.counts?.conflict ?? 0) > 0 && <span className="text-amber-800"><b>{p.counts.conflict}</b> {t('have a different period (left unchanged)')}</span>}
        <Link className="text-brand underline" to="/leave-setup">{t('Policy and automatic allocation')}</Link>
      </div>
      {apply.data?.failed?.length > 0 && (
        <ul className="mt-3 list-disc rounded-xl bg-amber-50 p-3 ps-8 text-sm text-amber-900">
          {apply.data.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error}</li>)}
        </ul>
      )}
      {apply.error && <ErrorBox error={apply.error} />}
    </Card>
  )
}

function GiveLeave({ types, onClose }: { types: any[]; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const y = todayISO().slice(0, 4)
  const [d, setD] = useState<any>({ leave_type: '', from_date: `${y}-01-01`, to_date: `${y}-12-31`, days: '', carry_forward: 0, reason: '', who: 'employees' })
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const [department, setDepartment] = useState('')
  const set = (k: string, v: unknown) => { pv.reset(); setD({ ...d, [k]: v }) }
  const people = pick && !ids.includes(pick) ? [...ids, pick] : ids
  const payload = { ...d, days: Number(d.days), employees: d.who === 'employees' ? people : [], department: d.who === 'department' ? department : undefined, everyone: d.who === 'everyone' ? 1 : 0 }
  const pv = useMutation({ mutationFn: () => api.allocateLeave({ ...payload, dry_run: 1 }) })
  const m = useMutation({ mutationFn: () => api.allocateLeave(payload), onSuccess: () => qc.invalidateQueries({ queryKey: ['leaveAllocations'] }) })
  const ready = d.leave_type && Number(d.days) > 0 && d.from_date && d.to_date && (d.who === 'everyone' || (d.who === 'department' ? department : people.length))
  const res: any = m.data
  return (
    <Modal open onClose={onClose} wide title={t('Give leave')}
      footer={res ? <Button onClick={onClose}>{t('Close')}</Button> : <>
        <Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button variant="secondary" disabled={!ready} loading={pv.isPending} onClick={() => pv.mutate()}>{t('Check')}</Button>
        <Button disabled={!ready || !pv.data?.create} loading={m.isPending} onClick={() => m.mutate()}>{t('Allocate')}{pv.data?.create ? ` (${pv.data.create})` : ''}</Button>
      </>}>
      {res ? (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-emerald-700">{t('Allocated')}: {res.created.length}</p>
          {res.skipped.length > 0 && <p className="text-muted">{t('Skipped')}: {res.skipped.length} — {res.skipped.slice(0, 5).map((s: any) => `${s.employee_name} (${s.why})`).join(', ')}</p>}
          {res.failed.length > 0 && <ul className="list-disc rounded-xl bg-amber-50 p-3 ps-8 text-amber-900">{res.failed.map((f: any) => <li key={f.employee}><b>{f.employee_name}</b>: {f.error}</li>)}</ul>}
        </div>
      ) : (
        <div className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t('Leave type')}>
              <Select value={d.leave_type} onChange={(e) => set('leave_type', e.target.value)}>
                <option value="">—</option>{types.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </Select>
            </Field>
            <Field label={t('Days')}><Input type="number" min={0.5} step="0.5" value={d.days} onChange={(e) => set('days', e.target.value)} /></Field>
            <Field label={t('From')}><Input type="date" value={d.from_date} onChange={(e) => set('from_date', e.target.value)} /></Field>
            <Field label={t('To')}><Input type="date" min={d.from_date} value={d.to_date} onChange={(e) => set('to_date', e.target.value)} /></Field>
          </div>
          <div className="flex flex-wrap gap-2" role="radiogroup">
            {(['employees', 'department', 'everyone'] as const).map((w) => (
              <Button key={w} size="sm" variant={d.who === w ? 'primary' : 'secondary'} onClick={() => set('who', w)}>
                {t(w === 'employees' ? 'Chosen employees' : w === 'department' ? 'A department' : 'Every active employee')}</Button>
            ))}
          </div>
          {d.who === 'employees' && (
            <div>
              <div className="flex items-end gap-2">
                <div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={(v) => { pv.reset(); setPick(v) }} onSelect={(v) => { pv.reset(); if (!ids.includes(v)) setIds([...ids, v]); setPick('') }} placeholder={t('Employee ID or name')} /></div>
                <Button size="sm" variant="secondary" disabled={!pick} onClick={() => { if (!ids.includes(pick)) setIds([...ids, pick]); setPick('') }}><Plus className="size-4" />{t('Add')}</Button>
              </div>
              {ids.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{ids.map((i) => (
                <span key={i} className="inline-flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs">{i}
                  <button type="button" aria-label={t('Remove')} onClick={() => { pv.reset(); setIds(ids.filter((x) => x !== i)) }}><X className="size-3" /></button></span>
              ))}</div>}
            </div>
          )}
          {d.who === 'department' && <Field label={t('Department')}><LinkInput doctype="Department" value={department} onChange={(v) => { pv.reset(); setDepartment(v) }} /></Field>}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4" checked={!!d.carry_forward} onChange={(e) => set('carry_forward', e.target.checked ? 1 : 0)} />{t('Add unused days carried from the previous period (if the leave type allows it)')}</label>
          <Field label={t('Reason')}><Textarea rows={2} value={d.reason} onChange={(e) => set('reason', e.target.value)} /></Field>
          {pv.data && (
            <div className="rounded-xl bg-surface p-3 text-sm">
              <b>{pv.data.create}</b> {t('will get the leave')}
              {pv.data.rows.some((r: any) => r.action === 'skip') && <> · <span className="text-muted">{t('Skipped')}: {pv.data.rows.filter((r: any) => r.action === 'skip').slice(0, 6).map((r: any) => `${r.employee_name} (${r.why})`).join(', ')}</span></>}
            </div>
          )}
          {(pv.error || m.error) && <ErrorBox error={pv.error || m.error} />}
        </div>
      )}
    </Modal>
  )
}

export default function LeaveAllocation() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [year, setYear] = useState(Number(todayISO().slice(0, 4)))
  const [leaveType, setLeaveType] = useState('')
  const [find, setFind] = useState('')
  const [give, setGive] = useState(false)
  const q = useQuery<any>({ queryKey: ['leaveAllocations', year, leaveType], queryFn: () => api.leaveAllocations({ year, leave_type: leaveType }) })
  const cancel = useMutation({ mutationFn: (name: string) => api.cancelLeaveAllocation(name), onSuccess: () => qc.invalidateQueries({ queryKey: ['leaveAllocations'] }) })
  const n = find.trim().toLowerCase()
  const rows = (q.data?.rows ?? []).filter((r: any) => !n || r.employee_name?.toLowerCase().includes(n) || r.employee.toLowerCase().includes(n))
  const people = new Set(rows.map((r: any) => r.employee)).size
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Leave allocation')} subtitle={t('Who has which leave balance for the year, and giving or taking back leave days.')}
        actions={q.data?.can_edit && <Button onClick={() => setGive(true)}><CalendarPlus className="size-4" />{t('Give leave')}</Button>} />
      <AnnualStrip />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Allocations')} value={fmtNumber(rows.length, lang)} />
        <Stat label={t('Employees')} value={fmtNumber(people, lang)} tone="blue" />
        <Stat label={t('Days given')} value={fmtNumber(rows.reduce((a: number, r: any) => a + (r.total_leaves_allocated || 0), 0), lang, 1)} />
        <Stat label={t('Days left')} value={fmtNumber(rows.reduce((a: number, r: any) => a + (r.left || 0), 0), lang, 1)} tone="amber" />
      </div>
      <Card>
        <div className="mb-4 flex flex-wrap gap-2">
          <Input className="!w-64" type="search" placeholder={t('Search name or ID')} value={find} onChange={(e) => setFind(e.target.value)} />
          <Select className="!w-56" value={leaveType} onChange={(e) => setLeaveType(e.target.value)} aria-label={t('Leave type')}>
            <option value="">{t('All leave types')}</option>
            {(q.data?.leave_types ?? []).map((x: any) => <option key={x.name} value={x.name}>{x.name}</option>)}
          </Select>
          <Select className="!w-32" value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label={t('Year')}>
            {[0, 1, 2, -1].map((k) => { const v = Number(todayISO().slice(0, 4)) - k; return <option key={v} value={v}>{v}</option> })}
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !rows.length ? (
          <Empty title={t('No leave allocated')}>{t('Use Give leave, or give this year\'s annual leave above.')}</Empty>
        ) : (
          <Table head={[t('Employee'), t('Leave type'), t('Period'), t('Given'), t('Used'), t('Left'), '']}>
            {rows.map((r: any) => (
              <tr key={r.name}>
                <td className="py-2"><div className="font-medium">{r.employee_name}</div><div className="text-xs text-muted">{r.employee}{r.department ? ` · ${r.department}` : ''}</div></td>
                <td>{r.leave_type}{r.carry_forward ? <Badge tone="blue">{t('carry-forward')}</Badge> : null}</td>
                <td className="text-sm">{fmtDate(r.from_date, lang)} – {fmtDate(r.to_date, lang)}</td>
                <td className="tabular-nums">{fmtNumber(r.total_leaves_allocated, lang, 1)}{r.unused_leaves ? <span className="text-xs text-muted"> ({t('incl.')} {fmtNumber(r.unused_leaves, lang, 1)} {t('carried')})</span> : null}</td>
                <td className="tabular-nums">{fmtNumber(r.used, lang, 1)}</td>
                <td className="tabular-nums font-semibold">{fmtNumber(r.left, lang, 1)}</td>
                <td>{q.data.can_edit && !r.used && (
                  <Button size="sm" variant="ghost" loading={cancel.isPending && cancel.variables === r.name}
                    onClick={() => { if (window.confirm(t('Cancel this allocation? The employee loses these days.'))) cancel.mutate(r.name) }}>{t('Cancel')}</Button>
                )}</td>
              </tr>
            ))}
          </Table>
        )}
        {cancel.error && <ErrorBox error={cancel.error} />}
      </Card>
      {give && <GiveLeave types={q.data?.leave_types ?? []} onClose={() => setGive(false)} />}
    </div>
  )
}
