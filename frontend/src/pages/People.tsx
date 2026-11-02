import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search, UserPlus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Input, PageHeader, Select, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PAGE = 25

export default function People() {
  const { t, lang } = useI18n()
  const nav = useNavigate()
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [status, setStatus] = useState('Active')
  const [saudi, setSaudi] = useState('')
  const [start, setStart] = useState(0)
  useEffect(() => { const h = setTimeout(() => { setDebounced(search); setStart(0) }, 300); return () => clearTimeout(h) }, [search])
  const q = useQuery<any>({
    queryKey: ['employees', debounced, status, saudi, start],
    queryFn: () => api.employees({ search: debounced, status, saudi, start, page_length: PAGE }),
    placeholderData: keepPreviousData,
  })
  return (
    <div>
      <PageHeader title={t('People')} subtitle={q.data ? `${fmtNumber(q.data.total, lang)} ${t('employees')}` : undefined}
        actions={<Link to="/people/new"><Button><UserPlus className="size-4" />{t('Add employee')}</Button></Link>} />
      <Card>
        <div className="mb-4 flex flex-wrap gap-2">
          <div className="relative min-w-60 flex-1">
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input className="ps-9" placeholder={t('Search people, ID or Iqama…')} value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select className="w-36" value={status} onChange={(e) => { setStatus(e.target.value); setStart(0) }}>
            {['Active', 'Inactive', 'Left', 'All'].map((s) => <option key={s} value={s === 'All' ? '' : s}>{t(s)}</option>)}
          </Select>
          <Select className="w-36" value={saudi} onChange={(e) => { setSaudi(e.target.value); setStart(0) }}>
            <option value="">{t('All')}</option><option value="1">{t('Saudi')}</option><option value="0">{t('Non-Saudi')}</option>
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data.rows.length ? <Empty title={t('All caught up')} /> : (
          <ul className="divide-y divide-line">
            {q.data.rows.map((e: any) => (
              <li key={e.name}>
                <button onClick={() => nav(`/people/${encodeURIComponent(e.name)}`)} className="flex w-full items-center gap-3 rounded-xl px-2 py-3 text-start hover:bg-surface">
                  <Avatar name={e.employee_name} image={e.image} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{e.employee_name}</span>
                      {e.alphax_is_saudi ? <Badge tone="green">{t('Saudi')}</Badge> : null}</div>
                    <div className="truncate text-sm text-muted">{[e.designation, e.department].filter(Boolean).join(' · ') || e.name}</div>
                  </div>
                  <div className="hidden text-end text-sm text-muted sm:block"><div>{e.name}</div><div>{t('Joined')} {fmtDate(e.date_of_joining, lang)}</div></div>
                  <StatusBadge status={e.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {q.data && q.data.total > PAGE && (
          <div className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>{fmtNumber(start + 1, lang)}–{fmtNumber(Math.min(start + PAGE, q.data.total), lang)} / {fmtNumber(q.data.total, lang)}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={start === 0} onClick={() => setStart(Math.max(0, start - PAGE))}>{t('Previous')}</Button>
              <Button size="sm" variant="secondary" disabled={start + PAGE >= q.data.total} onClick={() => setStart(start + PAGE)}>{t('Next')}</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
