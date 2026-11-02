import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CalendarClock, CalendarOff, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { addDaysISO, fmtDate, todayISO, weekStart } from '../lib/format'
import { useI18n } from '../lib/i18n'

// Fallback colours when a Shift Type has none (HRMS colour names map to these too).
const PALETTE = ['#0f766e', '#2563eb', '#7c3aed', '#c2410c', '#be185d', '#4d7c0f', '#0369a1', '#a16207']
const NAMED: Record<string, string> = { Blue: '#2563eb', Cyan: '#0891b2', Fuchsia: '#c026d3', Green: '#16a34a', Lime: '#65a30d',
  Orange: '#ea580c', Pink: '#db2777', Red: '#dc2626', Violet: '#7c3aed', Yellow: '#ca8a04' }

function short(name: string) {
  const words = name.replace(/shift/i, '').trim().split(/\s+/)
  return (words.length > 1 ? words.map((w) => w[0]).join('') : name.slice(0, 3)).toUpperCase().slice(0, 3)
}

export default function Roster() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [start, setStart] = useState(weekStart(todayISO()))
  const [days, setDays] = useState(7)
  const [department, setDepartment] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dialog, setDialog] = useState(false)
  const [offDialog, setOffDialog] = useState(false)
  const toggle1 = useMutation({ mutationFn: ({ employee, date }: { employee: string; date: string }) => api.toggleWeekOff(employee, date),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roster'] }) })
  const q = useQuery<any>({ queryKey: ['roster', start, days, department], queryFn: () => api.roster({ start, days, department }) })
  const deps = useQuery<any>({ queryKey: ['employees', '', 'Active', '', '', 0], queryFn: () => api.employees({ status: 'Active', page_length: 1 }) })
  const colour = (shift?: string) => {
    if (!shift) return undefined
    const types: any[] = q.data?.shift_types ?? []
    const i = types.findIndex((s) => s.name === shift)
    const c = types[i]?.color
    return (c && (NAMED[c] ?? c)) || PALETTE[(i < 0 ? 0 : i) % PALETTE.length]
  }
  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const allIds: string[] = (q.data?.rows ?? []).map((r: any) => r.employee)
  const today = todayISO()

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Roster')} subtitle={t('Who works which shift. Assigned shifts override the default shift.')}
        actions={<div className="flex gap-2">
          <Button variant="secondary" disabled={!selected.size} onClick={() => setOffDialog(true)}><CalendarOff className="size-4" />{t('Set week-off')}</Button>
          <Button disabled={!selected.size} onClick={() => setDialog(true)}><CalendarClock className="size-4" />{t('Assign shift')}{selected.size ? ` (${selected.size})` : ''}</Button>
        </div>} />
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" aria-label={t('Previous')} onClick={() => setStart(addDaysISO(start, -days))}><ChevronLeft className="size-4 flip-rtl" /></Button>
          <span className="min-w-52 text-center text-sm font-medium">{fmtDate(start, lang)} – {fmtDate(addDaysISO(start, days - 1), lang)}</span>
          <Button variant="secondary" size="sm" aria-label={t('Next')} onClick={() => setStart(addDaysISO(start, days))}><ChevronRight className="size-4 flip-rtl" /></Button>
          <Button variant="ghost" size="sm" onClick={() => setStart(weekStart(today))}>{t('This week')}</Button>
          <span className="flex-1" />
          <Select aria-label={t('Days')} className="!w-32" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>{t('1 week')}</option><option value={14}>{t('2 weeks')}</option><option value={28}>{t('4 weeks')}</option>
          </Select>
          <Select aria-label={t('Department')} className="!w-56" value={department} onChange={(e) => { setDepartment(e.target.value); setSelected(new Set()) }}>
            <option value="">{t('All departments')}</option>
            {(deps.data?.departments ?? []).map((d: string) => <option key={d} value={d}>{d}</option>)}
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : (
          <>
            <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted">
              {q.data.shift_types.map((s: any) => (
                <span key={s.name} className="flex items-center gap-1.5">
                  <span className="rounded px-1.5 py-0.5 font-semibold text-white" style={{ background: colour(s.name) }}>{short(s.name)}</span>
                  {s.name} {s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)}
                </span>
              ))}
              <span className="flex items-center gap-1.5"><span className="rounded bg-sky-100 px-1.5 py-0.5 font-semibold text-sky-800">{t('Leave')}</span></span>
              <span className="flex items-center gap-1.5"><span className="rounded bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-600">{t('Off')}</span>{t('Week-off')}</span>
              <span className="flex items-center gap-1.5"><span className="rounded bg-rose-100 px-1.5 py-0.5 font-semibold text-rose-800">{t('Hol')}</span>{t('Public holiday')}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-separate border-spacing-0 text-sm">
                <thead>
                  <tr>
                    <th className="sticky start-0 z-10 bg-white pb-2 pe-3 text-start">
                      <label className="flex items-center gap-2 text-xs font-medium text-muted">
                        <input type="checkbox" className="size-4 accent-[var(--color-brand)]" aria-label={t('Select all')}
                          checked={allIds.length > 0 && selected.size === allIds.length}
                          onChange={(e) => setSelected(e.target.checked ? new Set(allIds) : new Set())} />{t('Employee')}
                      </label>
                    </th>
                    {q.data.dates.map((d: string) => (
                      <th key={d} className={clsx('px-1 pb-2 text-center text-xs font-medium', d === today ? 'text-brand' : 'text-muted')}>
                        {new Intl.DateTimeFormat(lang === 'ar' ? 'ar-SA-u-ca-gregory' : 'en-GB', { weekday: 'short', timeZone: 'UTC' }).format(new Date(d + 'T00:00:00Z'))}
                        <div className="tabular-nums">{d.slice(8)}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {q.data.rows.map((r: any) => (
                    <tr key={r.employee} className={selected.has(r.employee) ? 'bg-brand-50' : undefined}>
                      <td className="sticky start-0 z-10 border-t border-line bg-inherit py-1.5 pe-3" style={{ background: selected.has(r.employee) ? undefined : 'white' }}>
                        <label className="flex items-center gap-2">
                          <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={selected.has(r.employee)} onChange={() => toggle(r.employee)} />
                          <span className="min-w-0"><span className="block truncate font-medium">{r.employee_name}</span>
                            <span className="block truncate text-xs text-muted">{r.designation ?? r.department ?? ''}</span></span>
                        </label>
                      </td>
                      {r.cells.map((c: any) => (
                        <td key={c.date} className="border-t border-line px-0.5 py-1.5 text-center"
                          title={[c.shift, c.leave && `${t('Leave')}: ${c.leave}`, c.holiday && (c.holiday === 'weekly_off' ? t('Weekly off') : c.holiday)].filter(Boolean).join(' · ')}>
                          <button type="button" className="block w-full rounded disabled:cursor-default" disabled={!!c.leave || (c.holiday && c.holiday !== 'weekly_off') || toggle1.isPending}
                            title={t('Click to switch week-off on/off')} onClick={() => toggle1.mutate({ employee: r.employee, date: c.date })}>
                          {c.leave ? <span className="block rounded bg-sky-100 py-1 text-xs font-semibold text-sky-800">{t('Leave')}</span>
                            : c.holiday === 'weekly_off' ? <span className="block rounded bg-slate-100 py-1 text-xs font-semibold text-slate-600">{t('Off')}</span>
                            : c.holiday ? <span className="block rounded bg-rose-100 py-1 text-xs font-semibold text-rose-800">{t('Hol')}</span>
                            : c.shift ? <span className={clsx('block rounded py-1 text-xs font-semibold text-white', !c.assignment && 'opacity-60')} style={{ background: colour(c.shift) }}>{short(c.shift)}</span>
                            : <span className="block py-1 text-xs text-muted">—</span>}
                          </button>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {toggle1.error && <div className="mt-3"><ErrorBox error={toggle1.error} /></div>}
            <p className="mt-3 text-xs text-muted">{t('Faded = default shift from the employee profile; solid = assigned for those dates.')} {t('Click a day to switch the week-off on or off.')}</p>
          </>
        )}
      </Card>
      {offDialog && <WeekOffDialog employees={[...selected]} defaultStart={start}
        onClose={() => setOffDialog(false)} onDone={() => { qc.invalidateQueries({ queryKey: ['roster'] }) }} />}
      {dialog && <AssignDialog employees={[...selected]} names={(q.data?.rows ?? []).filter((r: any) => selected.has(r.employee)).map((r: any) => r.employee_name)}
        shiftTypes={q.data?.shift_types ?? []} defaultStart={start}
        onClose={() => setDialog(false)} onDone={() => { qc.invalidateQueries({ queryKey: ['roster'] }); setSelected(new Set()) }} />}
    </div>
  )
}

function AssignDialog({ employees, names, shiftTypes, defaultStart, onClose, onDone }: {
  employees: string[]; names: string[]; shiftTypes: any[]; defaultStart: string; onClose: () => void; onDone: () => void
}) {
  const { t } = useI18n()
  const [form, setForm] = useState({ shift_type: shiftTypes[0]?.name ?? '', start_date: defaultStart, end_date: addDaysISO(defaultStart, 6) })
  const m = useMutation({ mutationFn: () => api.assignShift({ employees, ...form, end_date: form.end_date || undefined }), onSuccess: () => onDone() })
  const res: any = m.data
  return (
    <Modal open onClose={onClose} title={t('Assign shift')}>
      {res ? (
        <div className="flex flex-col gap-3 text-sm">
          <p className="text-emerald-700">{t('Assigned')}: {res.created.length}</p>
          {res.failed.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
              <p className="mb-1 font-medium">{t('Not assigned')} ({res.failed.length})</p>
              <ul className="list-disc ps-5">{res.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error.replace(/<[^>]+>/g, '')}</li>)}</ul>
            </div>
          )}
          <Button onClick={onClose}>{t('Close')}</Button>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
          <p className="text-sm text-muted">{names.slice(0, 6).join(', ')}{names.length > 6 ? ` +${names.length - 6}` : ''}</p>
          <Field label={t('Shift')}>
            <Select required value={form.shift_type} onChange={(e) => setForm({ ...form, shift_type: e.target.value })}>
              {shiftTypes.map((s) => <option key={s.name} value={s.name}>{s.name} ({s.start_time.slice(0, 5)}–{s.end_time.slice(0, 5)})</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('From')}><Input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
            <Field label={t('To')} hint={t('Blank = until changed')}><Input type="date" min={form.start_date} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></Field>
          </div>
          {m.error && <ErrorBox error={m.error} />}
          <Button type="submit" loading={m.isPending}>{t('Assign')}</Button>
        </form>
      )}
    </Modal>
  )
}

function WeekOffDialog({ employees, defaultStart, onClose, onDone }: { employees: string[]; defaultStart: string; onClose: () => void; onDone: () => void }) {
  const { t, lang } = useI18n()
  const [days, setDays] = useState<Set<number>>(new Set([4]))  // Friday
  const [form, setForm] = useState({ start_date: defaultStart, end_date: addDaysISO(defaultStart, 27), replace: true })
  const m = useMutation({ mutationFn: () => api.setWeekOff({ employees, weekdays: [...days], ...form, replace: form.replace ? 1 : 0 }), onSuccess: onDone })
  // Python weekday numbers: Mon=0 .. Sun=6; shown Sunday-first for the Saudi week.
  const order = [6, 0, 1, 2, 3, 4, 5]
  const name = (py: number) => new Intl.DateTimeFormat(lang === 'ar' ? 'ar-SA-u-ca-gregory' : 'en-GB', { weekday: 'short', timeZone: 'UTC' })
    .format(new Date(Date.UTC(2026, 0, 5 + py)))  // 5 Jan 2026 is a Monday
  const res: any = m.data
  return (
    <Modal open onClose={onClose} title={t('Set week-off')}>
      {res ? (
        <div className="flex flex-col gap-3 text-sm">
          <p className="text-emerald-700">{t('Updated')}: {res.done.length} {t('employees')}</p>
          {res.done.some((d: any) => d.beyond_company_list) && <p className="text-amber-800">{t('Some dates are beyond the company holiday list, so public holidays for them are not known yet. Extend the company holiday list (Setup & health shows which).')}</p>}
          {res.failed.length > 0 && <ul className="list-disc rounded-xl bg-amber-50 p-3 ps-8 text-amber-900">{res.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error.replace(/<[^>]+>/g, '')}</li>)}</ul>}
          <Button onClick={onClose}>{t('Close')}</Button>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
          <p className="text-sm text-muted">{employees.length} {t('employees')}</p>
          <div>
            <div className="mb-2 text-sm font-medium">{t('Week-off days')}</div>
            <div className="flex flex-wrap gap-2">
              {order.map((d) => (
                <button type="button" key={d} aria-pressed={days.has(d)}
                  onClick={() => setDays((s) => { const n = new Set(s); if (n.has(d)) n.delete(d); else n.add(d); return n })}
                  className={clsx('rounded-xl border px-3 py-2 text-sm', days.has(d) ? 'border-brand bg-brand text-white' : 'border-line hover:bg-surface')}>{name(d)}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('From')}><Input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
            <Field label={t('To')}><Input type="date" required min={form.start_date} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></Field>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-brand)]" checked={form.replace} onChange={(e) => setForm({ ...form, replace: e.target.checked })} />
            <span>{t('Replace their current week-offs in this period')}<span className="block text-xs text-muted">{t('Untick to add these days on top. Public holidays are never changed.')}</span></span>
          </label>
          {m.error && <ErrorBox error={m.error} />}
          <Button type="submit" loading={m.isPending} disabled={!days.size}>{t('Save week-off')}</Button>
        </form>
      )}
    </Modal>
  )
}
