import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { LinkInput } from '../components/LinkInput'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Input, PageHeader, Select, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { addDaysISO, fmtDate, fmtNumber, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PAGE = 50

function verb(i: any, t: (s: string) => string) {
  if (i.kind === 'changed') return t('updated')
  if (i.kind === 'comment') return t('commented on')
  if (i.kind === 'deleted') return t('deleted')
  if (i.kind === 'attachment') return t('attached a file to')
  if (i.kind === 'workflow') return t('moved')
  return t(i.kind.replace(/_/g, ' '))
}

function show(v: any, t: (s: string) => string) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number' && [0, 1, 2].includes(v)) return t({ 0: 'Draft', 1: 'Submitted', 2: 'Cancelled' }[v]!)
  return String(v).length > 60 ? String(v).slice(0, 60) + '…' : String(v)
}

export default function ActivityLog() {
  const { t, lang } = useI18n()
  const today = todayISO()
  const [f, setF] = useState({ doctype: '', user: '', employee: '', from_date: addDaysISO(today, -7), to_date: today })
  const [start, setStart] = useState(0)
  const [open, setOpen] = useState<{ doctype: string; name: string } | null>(null)
  const q = useQuery<any>({ queryKey: ['activityFeed', f, start], queryFn: () => api.activityFeed({ ...f, start, limit: PAGE }), placeholderData: keepPreviousData })
  const set = (k: string, v: string) => { setF((x) => ({ ...x, [k]: v })); setStart(0) }
  let lastDay = ''
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Activity log')} subtitle={t('Every change to HR records — who, what and when — from AlphaX, the desk, imports and scheduled jobs.')} />
      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label={t('Record type')}>
            <Select value={f.doctype} onChange={(e) => set('doctype', e.target.value)}>
              <option value="">{t('All')}</option>
              {(q.data?.doctypes ?? []).map((d: string) => <option key={d} value={d}>{t(d)}{q.data?.by_type?.[d] ? ` · ${q.data.by_type[d]}` : ''}</option>)}
            </Select>
          </Field>
          <Field label={t('Employee')}><LinkInput doctype="Employee" value={f.employee} onChange={(v: string) => set('employee', v)} /></Field>
          <Field label={t('Changed by (user)')}><LinkInput doctype="User" value={f.user} onChange={(v: string) => set('user', v)} /></Field>
          <Field label={t('From')}><Input type="date" value={f.from_date} max={f.to_date} onChange={(e) => set('from_date', e.target.value)} /></Field>
          <Field label={t('To')}><Input type="date" value={f.to_date} min={f.from_date} onChange={(e) => set('to_date', e.target.value)} /></Field>
        </div>
      </Card>
      <Card title={q.data ? `${fmtNumber(q.data.total, lang)} ${t('events')}` : undefined}>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data.items.length ? <Empty title={t('No activity in this period')} /> : (
          <ul className="flex flex-col">
            {q.data.items.map((i: any, idx: number) => {
              const day = i.at.slice(0, 10)
              const header = day !== lastDay
              lastDay = day
              return (
                <li key={idx}>
                  {header && <div className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted first:mt-0">{fmtDate(day, lang, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>}
                  <button disabled={!i.exists} onClick={() => setOpen({ doctype: i.doctype, name: i.docname })}
                    className="flex w-full items-start gap-3 rounded-xl px-2 py-2 text-start hover:bg-surface disabled:cursor-default disabled:hover:bg-transparent">
                    <Avatar name={i.name ?? i.user} size={32} />
                    <div className="min-w-0 flex-1 text-sm">
                      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
                        <span className="font-medium">{i.name ?? i.user}</span>
                        <span className="text-muted">{verb(i, t)}</span>
                        <span className="font-medium">{i.title}</span>
                        <Badge tone="blue">{t(i.doctype)}</Badge>
                        {!i.exists && <Badge tone="red">{t('deleted')}</Badge>}
                        <span className="ms-auto text-xs text-muted tabular-nums">{i.at.slice(11, 16)}</span>
                      </div>
                      {i.kind === 'changed' && (
                        <ul className="mt-0.5 text-xs text-muted">
                          {i.changes.map((c: any, j: number) => <li key={j}>{c.label}: <s>{show(c.from, t)}</s> → <b className="text-ink">{show(c.to, t)}</b></li>)}
                          {i.more > 0 && <li>+{i.more} {t('more')}</li>}
                        </ul>
                      )}
                      {i.text && <p className="mt-0.5 line-clamp-2 text-xs text-muted">{i.text}</p>}
                    </div>
                  </button>
                </li>
              )
            })}
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
      {open && <ActivityDrawer doctype={open.doctype} name={open.name} onClose={() => setOpen(null)} />}
    </div>
  )
}
