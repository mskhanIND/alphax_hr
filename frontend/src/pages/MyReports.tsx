import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bug, CheckCircle2, MessageSquare, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, Empty, ErrorBox, Field, Modal, PageHeader, Spinner, Tabs, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDateTime } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

const TONE: Record<string, string> = {
  'Received': 'gray', 'Being worked on': 'blue', 'Question for you': 'amber', 'Fixed - please check': 'green',
  'Answered': 'blue', 'Reopened': 'red', 'Closed': 'gray',
}

function Detail({ name, onClose }: { name: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['report', name], queryFn: () => api.reportDetail(name) })
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const check = useMutation({
    mutationFn: (result: 'Pass' | 'Fail' | 'Reply') => result === 'Reply' ? api.replyReport(name, note) : api.retestReport(name, result, note),
    onSuccess: (d) => { qc.setQueryData(['report', name], d); qc.invalidateQueries({ queryKey: ['my-reports'] }); setNote(''); setErr('') },
    onError: (e: any) => setErr(e?.message || String(e)),
  })
  const d = q.data
  return (
    <Modal open onClose={onClose} wide title={<>{name}{d && <span className="ms-2"><Badge tone={TONE[d.status] ?? 'gray'}>{t(d.status)}</Badge></span>}</>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : d && (
        <div className="flex flex-col gap-4 text-sm">
          <div>
            <div className="text-xs font-medium uppercase text-muted">{t('What went wrong?')}</div>
            <p className="whitespace-pre-wrap">{d.went_wrong}</p>
            {d.doing && <><div className="mt-2 text-xs font-medium uppercase text-muted">{t('What were you trying to do?')}</div><p className="whitespace-pre-wrap">{d.doing}</p></>}
            <p className="mt-2 text-xs text-muted">{t('Page')}: {d.page} · {fmtDateTime(d.creation, lang)}</p>
          </div>
          {d.screenshot && <img src={d.screenshot} alt="" className="max-h-64 w-full rounded-lg border border-line object-contain object-top" />}
          <div>
            <div className="mb-2 flex items-center gap-2 font-medium"><MessageSquare className="size-4" />{t('Conversation with the AlphaX team')}</div>
            {d.replies?.length ? (
              <ul className="flex flex-col gap-2">
                {d.replies.map((r: any, i: number) => (
                  <li key={i} className={`rounded-xl p-3 ${r.mine ? 'ms-8 bg-surface' : 'me-8 bg-brand-50'}`}>
                    <p className="whitespace-pre-wrap">{r.text}</p>
                    <p className="mt-1 text-xs text-muted">{fmtDateTime(r.on?.replace('T', ' '), lang)}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="text-muted">{d.sent ? t('No answer yet. Answers usually come the next morning.') : t('Waiting to be sent to the AlphaX team.')}</p>}
          </div>
          {d.retest && <p className="text-muted">{t('Your check')}: <b>{t(d.retest)}</b>{d.retest_note ? ` · ${d.retest_note}` : ''}</p>}
          {d.status === 'Question for you' && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3">
              <Field label={t('Your answer')}>
                <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
              <div className="mt-2"><Button onClick={() => check.mutate('Reply')} loading={check.isPending}>{t('Send answer')}</Button></div>
              {err && <p className="mt-2 text-red-600">{err}</p>}
            </div>
          )}
          {['Fixed - please check', 'Answered', 'Reopened'].includes(d.status) && (
            <div className="rounded-xl border border-line p-3">
              <div className="mb-2 font-medium">{d.status === 'Reopened' ? t('Checked it again?') : t('Please try again and tell us:')}</div>
              <Field label={t('Remarks (needed if it still fails)')}>
                <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
              <div className="mt-2 flex gap-2">
                <Button onClick={() => check.mutate('Pass')} loading={check.isPending && check.variables === 'Pass'}><CheckCircle2 className="size-4" />{t('Pass, it works')}</Button>
                <Button variant="secondary" onClick={() => check.mutate('Fail')} loading={check.isPending && check.variables === 'Fail'}><XCircle className="size-4" />{t('Fail, still wrong')}</Button>
              </div>
              {err && <p className="mt-2 text-red-600">{err}</p>}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

export default function MyReports() {
  const { t, lang } = useI18n()
  const s = useSession()
  const [scope, setScope] = useState('mine')
  const everyone = scope === 'all'
  const q = useQuery({ queryKey: ['my-reports', everyone], queryFn: () => api.myReports(everyone) })
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t('My reports')} subtitle={t('Problems you reported with the Report a problem button, and the answers.')} />
      {s.persona.hr_manager && <Tabs value={scope} onChange={setScope} tabs={[{ value: 'mine', label: t('Mine') }, { value: 'all', label: t('Everyone') }]} />}
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? (
          <Empty title={t('No reports yet')} icon={<Bug className="size-6" />}>{t('Use the Report a problem button at the bottom of any page.')}</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {q.data.map((r) => (
              <li key={r.name}>
                <button type="button" onClick={() => setOpen(r.name)} className="flex w-full items-center gap-3 px-1 py-3 text-start hover:bg-surface">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{r.title}</div>
                    <div className="text-xs text-muted">{r.name} · {fmtDateTime(r.creation, lang)}{r.reporter ? ` · ${r.reporter}` : ''}</div>
                  </div>
                  <Badge tone={TONE[r.status] ?? 'gray'}>{t(r.status)}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {open && <Detail name={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
