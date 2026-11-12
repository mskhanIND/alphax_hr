import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, FilterNote, Input, Modal, PageHeader, Spinner, Stat, Textarea } from '../components/ui'
import { call } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TONE: Record<string, string> = { 'On probation': 'blue', Extended: 'amber', Confirmed: 'green', 'Not confirmed': 'red' }

function Decide({ row, maxDays, onClose, onDone }: { row: any; maxDays: number; onClose: () => void; onDone: () => void }) {
  const { t, lang } = useI18n()
  const [decision, setDecision] = useState('Confirmed')
  const [note, setNote] = useState('')
  const [end, setEnd] = useState(row.suggested_end ?? row.max_end ?? row.end)
  const m = useMutation({ mutationFn: () => call('alphax_hr.probation.decide', { employee: row.employee, decision, note, new_end: ['Extended', 'Adjust end'].includes(decision) ? end : undefined }), onSuccess: () => { onDone(); onClose() } })
  return (
    <Modal open onClose={onClose} title={`${t('Probation')} · ${row.employee_name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={m.isPending} onClick={() => m.mutate()}>{t('Save decision')}</Button></>}>
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-muted">{t('Joined')} {fmtDate(row.date_of_joining, lang)} · {t('ends')} {fmtDate(row.end, lang)} ({row.length_days} {t('days')})</p>
        <div className="flex flex-wrap gap-2">
          {[['Confirmed', 'Confirm'], ['Extended', 'Extend'], ['Not confirmed', 'Not confirmed'], ['Adjust end', 'Move the end date']].map(([k, l]) => (
            <button key={k} type="button" onClick={() => setDecision(k)} className={clsx('rounded-lg px-3 py-1.5', decision === k ? 'bg-brand text-white' : 'border border-line bg-white')}>{t(l)}</button>))}
        </div>
        {['Extended', 'Adjust end'].includes(decision) && (
          <Field label={t('New end date')} hint={`${t('At most')} ${maxDays} ${t('days from joining, not counting Eid holidays and sick leave')}: ${t('latest')} ${fmtDate(row.max_end, lang)}`}>
            <Input type="date" value={end} max={row.max_end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
        )}
        {decision === 'Adjust end' && row.suggested_end && <p className="rounded-xl bg-brand-50 p-2 text-xs text-brand">{t('Suggested')}: {fmtDate(row.suggested_end, lang)} ({row.excluded_days} {t('days of Eid holidays or sick leave do not count')})</p>}
        <Field label={decision === 'Extended' ? t('Reason (the extension must be agreed with the employee in writing)') : decision === 'Not confirmed' ? t('Reason') : t('Note (optional)')}>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        {decision === 'Not confirmed' && <p className="text-xs text-amber-800">{t('Record the decision here, then start the separation and final settlement from the employee profile.')}</p>}
        {m.error && <ErrorBox error={m.error} />}
      </div>
    </Modal>
  )
}

export default function Probation() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['probation'], queryFn: () => call('alphax_hr.probation.overview') })
  const [show, setShow] = useState('open')
  const [row, setRow] = useState<any | null>(null)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const pick = (k: string) => setShow((x) => (x === k ? 'open' : k))
  const FILTER: Record<string, (r: any) => boolean> = {
    open: (r) => ['On probation', 'Extended'].includes(r.status), ending_soon: (r) => r.ending_soon, overdue: (r) => r.overdue,
    extended: (r) => r.status === 'Extended', confirmed: (r) => r.status === 'Confirmed', all: () => true }
  const LABEL: Record<string, string> = { open: 'On probation', ending_soon: 'Ending within 30 days', overdue: 'Decision overdue', extended: 'Extended', confirmed: 'Confirmed', all: 'All' }
  const rows = d.rows.filter(FILTER[show])
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Probation')} subtitle={t('Up to 180 days by law (Eid holidays and sick leave not counted). Managers and HR are reminded 30 and 7 days before the end.')} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label={t('On probation')} value={d.counts.open} onClick={() => setShow('open')} active={show === 'open'} />
        <Stat label={t('Ending within 30 days')} value={d.counts.ending_soon} tone="amber" onClick={() => pick('ending_soon')} active={show === 'ending_soon'} />
        <Stat label={t('Decision overdue')} value={d.counts.overdue} tone="red" onClick={() => pick('overdue')} active={show === 'overdue'} />
        <Stat label={t('Extended')} value={d.counts.extended} onClick={() => pick('extended')} active={show === 'extended'} />
        <Stat label={t('Confirmed')} value={d.counts.confirmed} tone="blue" onClick={() => pick('confirmed')} active={show === 'confirmed'} />
      </div>
      {show !== 'open' && <FilterNote label={t(LABEL[show])} count={rows.length} onClear={() => setShow('open')} />}
      <Card>
        {!rows.length ? <Empty title={t('Nobody here')}>{t('Employees with a probation end date appear here.')}</Empty> : (
          <ul className="divide-y divide-line">
            {rows.map((r: any) => (
              <li key={r.employee} className="flex flex-wrap items-center gap-3 py-3">
                <Avatar name={r.employee_name} image={r.image} />
                <div className="min-w-48 flex-1">
                  <Link to={`/people/${encodeURIComponent(r.employee)}`} className="font-medium hover:underline">{r.employee_name}</Link>
                  <div className="text-xs text-muted">{[r.designation, r.department, r.manager && `${t('Manager')}: ${r.manager}`].filter(Boolean).join(' · ')}</div>
                </div>
                <div className="text-sm">
                  <div>{t('Ends')} {fmtDate(r.end, lang)}</div>
                  <div className={clsx('text-xs', r.overdue ? 'text-red-700' : r.ending_soon ? 'text-amber-700' : 'text-muted')}>
                    {['On probation', 'Extended'].includes(r.status) ? (r.days_left < 0 ? `${-r.days_left} ${t('days ago, no decision')}` : `${r.days_left} ${t('days left')}`) : r.decided_on ? `${t('Decided')} ${fmtDate(r.decided_on, lang)}` : ''}
                  </div>
                  {r.suggested_end && <div className="text-xs text-brand">{t('Adjusted end')}: {fmtDate(r.suggested_end, lang)} (+{r.excluded_days})</div>}
                </div>
                <Badge tone={TONE[r.status]}>{t(r.status)}</Badge>
                {['On probation', 'Extended'].includes(r.status) && <Button size="sm" onClick={() => setRow(r)}>{t('Decide')}</Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {row && <Decide row={row} maxDays={d.max_days} onClose={() => setRow(null)} onDone={() => qc.invalidateQueries({ queryKey: ['probation'] })} />}
    </div>
  )
}
