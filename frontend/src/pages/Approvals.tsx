import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck } from 'lucide-react'
import { useState } from 'react'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Modal, PageHeader, Spinner, Textarea } from '../components/ui'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { api } from '../lib/api'
import { fmtDate, fmtMoney, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

function summary(r: any, t: (s: string) => string, lang: string) {
  if (r.doctype === 'Leave Application') return `${r.leave_type} · ${fmtDate(r.from_date, lang)} → ${fmtDate(r.to_date, lang)} · ${fmtNumber(r.total_leave_days, lang, 1)} ${t('days')}`
  if (r.doctype === 'Expense Claim') return `${fmtMoney(r.total_claimed_amount, lang)} · ${fmtDate(r.posting_date, lang)}`
  if (r.from_date) return `${fmtDate(r.from_date, lang)} → ${fmtDate(r.to_date, lang)}`
  return ''
}

export default function Approvals() {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['inbox'], queryFn: api.inbox })
  const qc = useQueryClient()
  const [filter, setFilter] = useState<string>('')
  const [pending, setPending] = useState<{ row: any; action: string } | null>(null)
  const [comment, setComment] = useState('')
  const [tab, setTab] = useState<'pending' | 'decided'>('pending')
  const [trail, setTrail] = useState<{ doctype: string; name: string } | null>(null)
  const done = useQuery<any>({ queryKey: ['decided'], queryFn: api.decided, enabled: tab === 'decided' })
  const m = useMutation({
    mutationFn: ({ row, action }: { row: any; action: string }) => api.act(row.doctype, row.name, action, comment || undefined),
    onSuccess: () => { setPending(null); setComment(''); qc.invalidateQueries({ queryKey: ['inbox'] }) },
  })
  const source = tab === 'pending' ? q : done
  const items = (source.data?.items ?? []).filter((r: any) => !filter || r.doctype === filter)
  const isNegative = (a: string) => /reject|decline|cancel/i.test(a)
  return (
    <div>
      <PageHeader title={t('Approvals')} subtitle={q.data ? `${fmtNumber(q.data.total, lang)} ${t('requests')}` : undefined}
        actions={<div className="flex rounded-xl border border-line p-0.5" role="tablist">
          {(['pending', 'decided'] as const).map((v) => (
            <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
              className={`rounded-lg px-3 py-1.5 text-sm ${tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface'}`}>{t(v === 'pending' ? 'Waiting' : 'Decided')}</button>
          ))}
        </div>} />
      {q.data && Object.keys(q.data.counts).length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <Button size="sm" variant={filter ? 'secondary' : 'primary'} onClick={() => setFilter('')}>{t('All')}</Button>
          {Object.entries(q.data.counts).map(([dt, n]) => (
            <Button key={dt} size="sm" variant={filter === dt ? 'primary' : 'secondary'} onClick={() => setFilter(dt)}>{t(dt)} · {String(n)}</Button>
          ))}
        </div>
      )}
      <Card>
        {source.isLoading ? <Spinner /> : source.error ? <ErrorBox error={source.error} onRetry={() => source.refetch()} /> : !items.length ? (
          <Empty title={t('All caught up')} icon={<BadgeCheck />}>{t('Nothing is waiting for you.')}</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {items.map((r: any) => (
              <li key={r.doctype + r.name} className="flex flex-wrap items-center gap-3 py-3">
                <button type="button" onClick={() => setTrail({ doctype: r.doctype, name: r.name })} className="flex min-w-0 flex-1 items-center gap-3 rounded-xl text-start hover:bg-surface" title={t('Show activity')}>
                <Avatar name={r.employee_name ?? r.owner} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{r.employee_name ?? r.owner}</span>
                    <Badge tone="blue">{t(r.doctype)}</Badge>
                    {r.workflow_state && <Badge>{r.workflow_state}</Badge>}
                  </div>
                  <div className="truncate text-sm text-muted">{summary(r, t, lang)}</div>
                  {(r.description || r.reason || r.remark) && <div className="mt-0.5 line-clamp-1 text-sm text-ink/80">“{r.description || r.reason || r.remark}”</div>}
                  {(r.alphax_event_date || r.alphax_relation) && <div className="mt-0.5 text-xs text-muted">{[r.alphax_relation && t(r.alphax_relation), r.alphax_event_date && `${t('Event date')}: ${fmtDate(r.alphax_event_date, lang)}`].filter(Boolean).join(' · ')}</div>}
                  {r.alphax_sick_breakdown && <div className="mt-0.5 text-xs font-medium text-amber-800">{r.alphax_sick_breakdown}</div>}
                  {r.attachments > 0 && <div className="mt-0.5 text-xs text-muted">📎 {r.attachments}</div>}
                </div>
                </button>
                <div className="flex gap-2">
                  {(r.actions ?? []).map((a: string) => (
                    <Button key={a} size="sm" variant={isNegative(a) ? 'secondary' : 'primary'} onClick={() => setPending({ row: r, action: a })}>{t(a)}</Button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {trail && <ActivityDrawer doctype={trail.doctype} name={trail.name} onClose={() => setTrail(null)} />}
      <Modal
        open={!!pending}
        onClose={() => setPending(null)}
        title={pending ? `${t(pending.action)} · ${pending.row.employee_name ?? pending.row.name}` : ''}
        footer={<>
          <Button variant="secondary" onClick={() => setPending(null)}>{t('Cancel')}</Button>
          <Button variant={pending && isNegative(pending.action) ? 'danger' : 'primary'} loading={m.isPending} onClick={() => pending && m.mutate(pending)}>{pending ? t(pending.action) : ''}</Button>
        </>}
      >
        {pending && <p className="mb-3 text-sm text-muted">{summary(pending.row, t, lang)}</p>}
        <Textarea placeholder={t('Comment (optional)')} value={comment} onChange={(e) => setComment(e.target.value)} />
        {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
      </Modal>
    </div>
  )
}
