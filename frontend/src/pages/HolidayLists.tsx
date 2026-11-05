import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CalendarPlus, CalendarRange, Plus, Trash2, Users } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TONE: Record<string, string> = { Current: 'green', 'Ends soon': 'amber', Ended: 'red', Future: 'blue' }
const DEFAULT_OFF = ['Friday', 'Saturday']

/** Public holidays, editable: date + name, add and remove. */
function PublicEditor({ rows, onChange }: { rows: any[]; onChange: (r: any[]) => void }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <div key={i} className="grid grid-cols-[10rem_1fr_auto] items-center gap-2">
          <Input type="date" value={r.date} onChange={(e) => onChange(rows.map((x, j) => j === i ? { ...x, date: e.target.value } : x))} />
          <Input value={r.description} onChange={(e) => onChange(rows.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
          <Button size="sm" variant="ghost" aria-label={t('Remove')} onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 className="size-4" /></Button>
        </div>
      ))}
      <Button size="sm" variant="secondary" className="self-start" onClick={() => onChange([...rows, { date: '', description: '' }])}><Plus className="size-4" />{t('Add holiday')}</Button>
    </div>
  )
}

function Library({ ok }: { ok: boolean }) {
  const { t } = useI18n()
  return ok
    ? <p className="text-xs text-muted">{t('Saudi public holidays are filled in. Eid dates are estimates until the moon sighting — change them here when they are announced.')}</p>
    : <p className="rounded-xl bg-amber-50 p-2 text-xs text-amber-900">{t('Public holidays could not be filled in on this server (the holidays library is missing or replaced). Add them below.')}</p>
}

function NewList({ meta, onClose }: { meta: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const year = new Date().getFullYear() + (new Date().getMonth() >= 9 ? 1 : 0)
  const [v, setV] = useState<any>({ name: `${t('Saudi')} ${year}`, from_date: `${year}-01-01`, to_date: `${year}-12-31`, weekly_off: DEFAULT_OFF,
    companies: [] as string[], without_list: true, from_list: '' })
  const [pub, setPub] = useState<any[] | null>(null)
  const sug = useQuery({ queryKey: ['holiday-suggest', v.from_date, v.to_date], queryFn: () => api.holidaySuggest(v.from_date, v.to_date, v.weekly_off),
    enabled: !!v.from_date && !!v.to_date })
  const rows: any[] = pub ?? sug.data?.public ?? []
  const set = (k: string, x: any) => { setV((s: any) => ({ ...s, [k]: x })); if (k === 'from_date' || k === 'to_date') setPub(null) }
  const save = useMutation({
    mutationFn: () => api.holidayCreate({ name: v.name, from_date: v.from_date, to_date: v.to_date, weekly_off: v.weekly_off, public: rows.filter((r: any) => r.date),
      assign: { companies: v.companies, without_list: v.without_list, from_list: v.from_list || undefined } }),
    onSuccess: (d) => { qc.setQueryData(['holiday-lists'], d); onClose() },
  })
  return (
    <Modal open wide onClose={onClose} title={t('New holiday list')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} disabled={!v.name} onClick={() => save.mutate()}>{t('Create')}</Button></>}>
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t('Name')}><Input value={v.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label={t('From')}><Input type="date" value={v.from_date} onChange={(e) => set('from_date', e.target.value)} /></Field>
          <Field label={t('To')}><Input type="date" value={v.to_date} onChange={(e) => set('to_date', e.target.value)} /></Field>
        </div>
        <Field label={t('Weekly off')}>
          <div className="flex flex-wrap gap-2">
            {meta.weekdays.map((d: string) => (
              <label key={d} className={`cursor-pointer rounded-full px-3 py-1 text-sm ring-1 ${v.weekly_off.includes(d) ? 'bg-brand text-white ring-brand' : 'ring-line'}`}>
                <input type="checkbox" className="sr-only" checked={v.weekly_off.includes(d)}
                  onChange={(e) => set('weekly_off', e.target.checked ? [...v.weekly_off, d] : v.weekly_off.filter((x: string) => x !== d))} />{t(d)}
              </label>
            ))}
          </div>
        </Field>
        <section>
          <h3 className="mb-1 font-semibold">{t('Public holidays')}</h3>
          {sug.data && <Library ok={sug.data.library} />}
          <div className="mt-2">{sug.isLoading ? <Spinner /> : <PublicEditor rows={rows} onChange={setPub} />}</div>
        </section>
        <section className="rounded-xl bg-gray-50 p-3">
          <h3 className="mb-2 font-semibold">{t('Use it for')}</h3>
          <div className="flex flex-col gap-2 text-sm">
            {meta.companies.map((c: string) => (
              <label key={c} className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={v.companies.includes(c)}
                onChange={(e) => set('companies', e.target.checked ? [...v.companies, c] : v.companies.filter((x: string) => x !== c))} />{t('Default for {0}').replace('{0}', c)}</label>
            ))}
            <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={v.without_list} onChange={(e) => set('without_list', e.target.checked)} />{t('Employees without a holiday list')}</label>
            <Field label={t('Move the employees of this list to the new one')}><LinkInput doctype="Holiday List" value={v.from_list} onChange={(x) => set('from_list', x)} placeholder={t('None')} /></Field>
          </div>
        </section>
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

function Extend({ list, onClose }: { list: any; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [to, setTo] = useState(list.next_year_end)
  const from = (() => { const d = new Date(list.to_date); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10) })()
  const [pub, setPub] = useState<any[] | null>(null)
  const sug = useQuery({ queryKey: ['holiday-suggest', from, to], queryFn: () => api.holidaySuggest(from, to, list.weekly_off), enabled: !!to })
  const rows: any[] = pub ?? sug.data?.public ?? []
  const save = useMutation({ mutationFn: () => api.holidayExtend(list.name, to, rows.filter((r: any) => r.date)),
    onSuccess: (d) => { qc.setQueryData(['holiday-lists'], d); onClose() } })
  return (
    <Modal open wide onClose={onClose} title={`${t('Extend')} · ${list.name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Extend')}</Button></>}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">{t('The employees stay on this list. It gets the same weekly off ({0}) from {1}, and the public holidays below. Employees\' own week-off lists (roster) are extended too.')
          .replace('{0}', list.weekly_off.map((d: string) => t(d)).join(', ') || '—').replace('{1}', fmtDate(from, lang))}</p>
        <Field label={t('Until')}><Input type="date" value={to} onChange={(e) => { setTo(e.target.value); setPub(null) }} /></Field>
        <section>
          <h3 className="mb-1 font-semibold">{t('Public holidays')}</h3>
          {sug.data && <Library ok={sug.data.library} />}
          <div className="mt-2">{sug.isLoading ? <Spinner /> : <PublicEditor rows={rows} onChange={setPub} />}</div>
        </section>
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

function Holidays({ list, canEdit, onClose }: { list: any; canEdit: boolean; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['holidays-of', list.name], queryFn: () => api.holidaysOf(list.name) })
  const [rows, setRows] = useState<any[] | null>(null)
  const cur = rows ?? q.data?.holidays ?? []
  const save = useMutation({ mutationFn: () => api.holidaySavePublic(list.name, cur.filter((r: any) => r.date)),
    onSuccess: (d) => { qc.setQueryData(['holidays-of', list.name], d); setRows(null); qc.invalidateQueries({ queryKey: ['holiday-lists'] }) } })
  return (
    <Modal open wide onClose={onClose} title={`${t('Public holidays')} · ${list.name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Close')}</Button>{canEdit && <Button loading={save.isPending} disabled={!rows} onClick={() => save.mutate()}>{t('Save')}</Button>}</>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t('Weekly off')}: {q.data.weekly_off.map((d: string) => t(d)).join(', ') || '—'}</p>
          {canEdit ? <PublicEditor rows={cur} onChange={setRows} /> : (
            <ul className="divide-y divide-line text-sm">{cur.map((r: any) => <li key={r.date} className="flex gap-3 py-1.5"><span className="w-28 text-muted">{r.date}</span>{r.description}</li>)}</ul>
          )}
          {save.error && <ErrorBox error={save.error} />}
        </div>
      )}
    </Modal>
  )
}

function Assign({ list, meta, onClose }: { list: any; meta: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [v, setV] = useState<any>({ companies: [], without_list: false, from_list: '' })
  const save = useMutation({ mutationFn: () => api.holidayAssign(list.name, v), onSuccess: (d) => { qc.setQueryData(['holiday-lists'], d); onClose() } })
  return (
    <Modal open onClose={onClose} title={`${t('Set on employees')} · ${list.name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Apply')}</Button></>}>
      <div className="flex flex-col gap-2 text-sm">
        {meta.companies.map((c: string) => (
          <label key={c} className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={v.companies.includes(c)}
            onChange={(e) => setV({ ...v, companies: e.target.checked ? [...v.companies, c] : v.companies.filter((x: string) => x !== c) })} />{t('Default for {0}').replace('{0}', c)}</label>
        ))}
        <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={v.without_list} onChange={(e) => setV({ ...v, without_list: e.target.checked })} />{t('Employees without a holiday list')}</label>
        <Field label={t('Move the employees of this list to it')}><LinkInput doctype="Holiday List" value={v.from_list} onChange={(x) => setV({ ...v, from_list: x })} placeholder={t('None')} /></Field>
        <p className="text-xs text-muted">{t('Employees with their own week-off list (roster) keep it; it then takes its public holidays from this list.')}</p>
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

export default function HolidayLists() {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['holiday-lists'], queryFn: api.holidayLists })
  const [dlg, setDlg] = useState<{ kind: string; list?: any } | null>(null)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const byName = (n: string) => d.lists.find((l: any) => l.name === n)
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Holiday lists')}
        subtitle={t('Weekly offs and public holidays. Leave day counts, attendance and payroll use each employee\'s list, or the company default.')}
        actions={d.can_edit ? <Button onClick={() => setDlg({ kind: 'new' })}><Plus className="size-4" />{t('New holiday list')}</Button> : undefined} />
      {d.problems.map((p: any, i: number) => (
        <div key={i} className={`flex flex-wrap items-start gap-3 rounded-xl border p-3 text-sm ${p.level === 'error' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-0 flex-1">{p.text}
            {p.employees?.length > 0 && <div className="mt-1 text-xs">{p.employees.map((e: any) => e.employee_name).join(', ')}</div>}
          </div>
          {d.can_edit && p.action === 'extend' && byName(p.list) && <Button size="sm" onClick={() => setDlg({ kind: 'extend', list: byName(p.list) })}><CalendarPlus className="size-4" />{t('Extend to {0}').replace('{0}', fmtDate(byName(p.list).next_year_end, lang))}</Button>}
          {d.can_edit && p.action === 'assign' && <Button size="sm" onClick={() => setDlg({ kind: 'new' })}>{t('Create and set a list')}</Button>}
        </div>
      ))}
      {d.problems.length === 0 && d.lists.length > 0 && <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand">{t('All employees have a current holiday list.')}</p>}
      {d.lists.length === 0 ? <Card><Empty title={t('No holiday lists yet')} icon={<CalendarRange />} /></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {d.lists.map((l: any) => (
            <Card key={l.name}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{l.name}</span>
                <Badge tone={TONE[l.status]}>{t(l.status)}</Badge>
                {l.default_for.map((c: string) => <Badge key={c}>{t('Default for {0}').replace('{0}', c)}</Badge>)}
              </div>
              <div className="mt-1 text-sm text-muted">{fmtDate(l.from_date, lang)} → {fmtDate(l.to_date, lang)}
                {l.status === 'Ends soon' && ` · ${t('ends in {0} days').replace('{0}', String(l.days))}`}
                {l.status === 'Ended' && ` · ${t('ended {0} days ago').replace('{0}', String(l.days))}`}</div>
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                <span>{t('Weekly off')}: <b>{l.weekly_off.map((x: string) => t(x)).join(', ') || '—'}</b></span>
                <span>{t('Public holidays')}: <b>{l.public_holidays}</b></span>
                <span className="inline-flex items-center gap-1"><Users className="size-4 text-muted" />{l.employees}{l.personal_lists ? ` (${l.personal_lists} ${t('with own week-offs')})` : ''}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={() => setDlg({ kind: 'holidays', list: l })}>{t('Public holidays')}</Button>
                {d.can_edit && <Button size="sm" variant={l.status === 'Current' ? 'secondary' : 'primary'} onClick={() => setDlg({ kind: 'extend', list: l })}><CalendarPlus className="size-4" />{t('Extend')}</Button>}
                {d.can_edit && <Button size="sm" variant="secondary" onClick={() => setDlg({ kind: 'assign', list: l })}><Users className="size-4" />{t('Set on employees')}</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      {dlg?.kind === 'new' && <NewList meta={d} onClose={() => setDlg(null)} />}
      {dlg?.kind === 'extend' && dlg.list && <Extend list={dlg.list} onClose={() => setDlg(null)} />}
      {dlg?.kind === 'holidays' && dlg.list && <Holidays list={dlg.list} canEdit={d.can_edit} onClose={() => setDlg(null)} />}
      {dlg?.kind === 'assign' && dlg.list && <Assign list={dlg.list} meta={d} onClose={() => setDlg(null)} />}
    </div>
  )
}
