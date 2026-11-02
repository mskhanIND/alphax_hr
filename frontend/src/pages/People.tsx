import { keepPreviousData, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, Download, LayoutList, Network, Search, Table2, UserPlus, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { OrgChart } from '../components/OrgChart'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Input, PageHeader, Select, Spinner, StatusBadge, statusTone } from '../components/ui'
import { api, downloadUrl } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PAGE = 25
type View = 'list' | 'table' | 'org'

function ExportMenu({ args }: { args: Record<string, unknown> }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return (
    <div className="relative" ref={ref}>
      <Button variant="secondary" onClick={() => setOpen((o) => !o)}><Download className="size-4" />{t('Export')}</Button>
      {open && (
        <div className="absolute end-0 z-20 mt-1 w-48 overflow-hidden rounded-xl border border-line bg-white shadow-lg">
          <a className="block px-4 py-2 text-sm hover:bg-surface" href={downloadUrl('hr.export_employees', { ...args, file_format: 'xlsx' })} onClick={() => setOpen(false)}>{t('Excel (.xlsx)')}</a>
          <a className="block px-4 py-2 text-sm hover:bg-surface" href={downloadUrl('hr.export_employees', { ...args, file_format: 'csv' })} onClick={() => setOpen(false)}>{t('CSV')}</a>
        </div>
      )}
    </div>
  )
}

function QuickView({ id, onClose }: { id: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['employee', id], queryFn: () => api.employee(id) })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const e = q.data
  const row = (label: string, value: any, date = false) => (
    <div className="flex justify-between gap-3 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="text-end font-medium">{value ? (date ? fmtDate(String(value), lang) : String(value)) : <span className="text-muted">—</span>}</dd>
    </div>
  )
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onMouseDown={onClose}>
      <aside role="dialog" aria-label={t('Quick view')} className="h-full w-full max-w-md overflow-y-auto bg-white shadow-xl" onMouseDown={(ev) => ev.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between border-b border-line bg-white px-5 py-3">
          <span className="font-semibold">{t('Quick view')}</span>
          <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-surface" aria-label={t('Close')}><X className="size-5" /></button>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <div className="p-5"><ErrorBox error={q.error} /></div> : (
          <div className="flex flex-col gap-4 p-5">
            <div className="flex items-center gap-4">
              <Avatar name={e.employee_name} image={e.image} size={56} />
              <div className="min-w-0">
                <div className="truncate text-lg font-semibold">{e.employee_name}</div>
                <div className="text-sm text-muted">{e.name} · {e.sections.job.designation ?? '—'}</div>
                <div className="mt-1"><Badge tone={statusTone(e.sections.job.status)}>{t(e.sections.job.status)}</Badge></div>
              </div>
            </div>
            {e.missing_required?.length > 0 && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                <div className="mb-1 flex items-center gap-2 font-medium"><AlertTriangle className="size-4" />{e.missing_required.length} {t('mandatory fields missing')}</div>
                <ul className="list-disc ps-5">{e.missing_required.map((m: string) => <li key={m}>{m}</li>)}</ul>
              </div>
            )}
            <dl className="divide-y divide-line">
              {row(t('Department'), e.sections.job.department)}
              {row(t('Reports to'), e.sections.job.reports_to)}
              {row(t('Joined'), e.sections.job.date_of_joining, true)}
              {row(t('Mobile'), e.sections.contact.cell_number)}
              {row(t('Email'), e.sections.contact.company_email || e.sections.contact.personal_email)}
              {row(t('National ID / Iqama'), e.sections.saudi.alphax_iqama_number)}
              {row(t('Iqama expiry'), e.sections.saudi.alphax_iqama_expiry, true)}
              {row(t('Nationality'), e.sections.saudi.alphax_is_saudi ? t('Saudi') : t('Non-Saudi'))}
            </dl>
            <div>
              <div className="mb-2 text-sm font-medium">{t('Documents')}</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(e.documents).map(([k, v]) => (
                  <Badge key={k} tone={statusTone(String(v))}>{t(k === 'work_permit' ? 'Work permit' : k.charAt(0).toUpperCase() + k.slice(1))}: {t(String(v))}</Badge>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Link to={`/people/${encodeURIComponent(e.name)}`} className="flex-1"><Button className="w-full">{t('Open full profile')}</Button></Link>
              <Link to={`/people/${encodeURIComponent(e.name)}?print=1`}><Button variant="secondary">{t('Print / PDF')}</Button></Link>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}

export default function People() {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const view = (params.get('view') as View) || 'list'
  const setView = (v: View) => { params.set('view', v); setParams(params, { replace: true }) }
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [status, setStatus] = useState('Active')
  const [saudi, setSaudi] = useState('')
  const [department, setDepartment] = useState(params.get('department') ?? '')
  const [start, setStart] = useState(0)
  const [quick, setQuick] = useState<string | null>(null)
  useEffect(() => { const h = setTimeout(() => { setDebounced(search); setStart(0) }, 300); return () => clearTimeout(h) }, [search])
  const filters = { search: debounced, status, saudi, department }
  const q = useQuery<any>({
    queryKey: ['employees', debounced, status, saudi, department, start],
    queryFn: () => api.employees({ ...filters, start, page_length: PAGE }),
    placeholderData: keepPreviousData,
  })
  const views: [View, string, ReactNode][] = [
    ['list', 'List', <LayoutList key="l" className="size-4" />],
    ['table', 'Table', <Table2 key="t" className="size-4" />],
    ['org', 'Org chart', <Network key="o" className="size-4" />],
  ]
  const missingBadge = (e: any) => e.missing?.length
    ? <span title={e.missing.join(', ')} className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200"><AlertTriangle className="size-3" />{e.missing.length} {t('missing')}</span>
    : null

  return (
    <div>
      <PageHeader title={t('People')} subtitle={q.data && view !== 'org' ? `${fmtNumber(q.data.total, lang)} ${t('employees')}` : undefined}
        actions={<div className="flex gap-2"><ExportMenu args={filters} /><Link to="/people/new"><Button><UserPlus className="size-4" />{t('Add employee')}</Button></Link></div>} />
      <Card>
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input className="ps-9" placeholder={t('Search people, ID or Iqama…')} value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-2 lg:flex">
            <Select aria-label={t('Department')} className="lg:!w-52" value={department} onChange={(e) => { setDepartment(e.target.value); setStart(0) }}>
              <option value="">{t('All departments')}</option>
              {(q.data?.departments ?? []).map((d: string) => <option key={d} value={d}>{d}</option>)}
            </Select>
            <Select aria-label={t('Status')} className="lg:!w-32" value={status} disabled={view === 'org'} onChange={(e) => { setStatus(e.target.value); setStart(0) }}>
              {['Active', 'Inactive', 'Left', 'All'].map((s) => <option key={s} value={s === 'All' ? '' : s}>{t(s)}</option>)}
            </Select>
            <Select aria-label={t('Nationality')} className="lg:!w-32" value={saudi} onChange={(e) => { setSaudi(e.target.value); setStart(0) }}>
              <option value="">{t('All')}</option><option value="1">{t('Saudi')}</option><option value="0">{t('Non-Saudi')}</option>
            </Select>
          </div>
          <div className="flex rounded-xl border border-line p-0.5" role="tablist">
            {views.map(([v, label, icon]) => (
              <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                className={clsx('flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm', view === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>
                {icon}{t(label)}
              </button>
            ))}
          </div>
        </div>

        {view === 'org' ? <OrgChart department={department || undefined} search={debounced} onOpen={setQuick} />
          : q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data.rows.length ? <Empty title={t('No employees found')} />
          : view === 'list' ? (
            <ul className="divide-y divide-line">
              {q.data.rows.map((e: any) => (
                <li key={e.name}>
                  <button onClick={() => setQuick(e.name)} className="flex w-full items-center gap-3 rounded-xl px-2 py-3 text-start hover:bg-surface">
                    <Avatar name={e.employee_name} image={e.image} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{e.employee_name}</span>
                        {e.alphax_is_saudi ? <Badge tone="green">{t('Saudi')}</Badge> : null}{missingBadge(e)}</div>
                      <div className="truncate text-sm text-muted">{[e.designation, e.department].filter(Boolean).join(' · ') || e.name}</div>
                    </div>
                    <div className="hidden text-end text-sm text-muted sm:block"><div>{e.name}</div><div>{t('Joined')} {fmtDate(e.date_of_joining, lang)}</div></div>
                    <StatusBadge status={e.status} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] whitespace-nowrap text-sm">
                <thead className="text-xs text-muted"><tr className="border-b border-line">
                  {['Employee', 'ID', 'Designation', 'Department', 'Mobile', 'National ID / Iqama', 'Iqama expiry', 'Joined', 'Status', 'Data'].map((h) =>
                    <th key={h} className="px-2 pb-2 text-start font-medium">{t(h)}</th>)}
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {q.data.rows.map((e: any) => (
                    <tr key={e.name} className="cursor-pointer hover:bg-surface" onClick={() => setQuick(e.name)}>
                      <td className="px-2 py-2"><div className="flex items-center gap-2"><Avatar name={e.employee_name} image={e.image} size={28} /><span className="font-medium">{e.employee_name}</span></div></td>
                      <td className="px-2 py-2 text-muted">{e.name}</td>
                      <td className="px-2 py-2">{e.designation ?? '—'}</td>
                      <td className="px-2 py-2">{e.department ?? '—'}</td>
                      <td className="px-2 py-2 tabular-nums">{e.cell_number ?? '—'}</td>
                      <td className="px-2 py-2 tabular-nums">{e.alphax_iqama_number ?? '—'}</td>
                      <td className="px-2 py-2">{e.alphax_iqama_expiry ? fmtDate(e.alphax_iqama_expiry, lang) : '—'}</td>
                      <td className="px-2 py-2">{fmtDate(e.date_of_joining, lang)}</td>
                      <td className="px-2 py-2"><StatusBadge status={e.status} /></td>
                      <td className="px-2 py-2">{missingBadge(e) ?? <span className="text-xs text-emerald-700">✓</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        {view !== 'org' && q.data && q.data.total > PAGE && (
          <div className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>{fmtNumber(start + 1, lang)}–{fmtNumber(Math.min(start + PAGE, q.data.total), lang)} / {fmtNumber(q.data.total, lang)}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={start === 0} onClick={() => setStart(Math.max(0, start - PAGE))}>{t('Previous')}</Button>
              <Button size="sm" variant="secondary" disabled={start + PAGE >= q.data.total} onClick={() => setStart(start + PAGE)}>{t('Next')}</Button>
            </div>
          </div>
        )}
      </Card>
      {quick && <QuickView id={quick} onClose={() => setQuick(null)} />}
    </div>
  )
}
