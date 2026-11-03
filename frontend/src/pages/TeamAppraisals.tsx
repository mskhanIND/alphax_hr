import { useQuery } from '@tanstack/react-query'
import { Send, Star } from 'lucide-react'
import { useState } from 'react'
import { AppraisalForm } from '../components/AppraisalForm'
import { RequestForm } from '../components/RequestForm'
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner, StatusBadge, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

const STAGE_TONE: Record<string, string> = { 'Waiting for self': 'gray', 'Self done': 'amber', Reviewed: 'blue', Final: 'green' }

export default function TeamAppraisals() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['team-appraisals'], queryFn: api.teamAppraisals })
  const [open, setOpen] = useState<string | null>(null)
  const [recommend, setRecommend] = useState<string | null>(null)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Team appraisals')} subtitle={t('Review your direct reports, and recommend increments or promotions (HR and management approve).')} />
      <Card title={t('Appraisals to review')}>
        {!d.appraisals.length ? <Empty title={t('No appraisals for your team yet')} icon={<Star />} /> : (
          <Table head={[t('Employee'), t('Appraisal cycle'), t('Self'), t('Manager'), t('Final score'), t('Stage'), '']}>
            {d.appraisals.map((a: any) => (
              <tr key={a.name}>
                <td className="py-2 font-medium">{a.employee_name}</td>
                <td className="text-sm">{a.appraisal_cycle}<div className="text-xs text-muted">{fmtDate(a.start_date, lang)} → {fmtDate(a.end_date, lang)}</div></td>
                <td>{fmtNumber(a.self_score, lang, 1)}</td><td>{fmtNumber(a.avg_feedback_score, lang, 1)}</td>
                <td className="font-semibold">{fmtNumber(a.final_score, lang, 2)}</td>
                <td><Badge tone={STAGE_TONE[a.stage]}>{t(a.stage)}</Badge></td>
                <td><Button size="sm" variant={a.stage === 'Self done' ? 'primary' : 'secondary'} onClick={() => setOpen(a.name)}>{a.docstatus === 0 ? t('Review') : t('View')}</Button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Card title={t('Recommend an increment or promotion')} subtitle={t('Raised by you, it goes to HR and then management.')}>
        <div className="flex flex-wrap gap-2">
          {d.reports.map((e: any) => (
            <Button key={e.name} size="sm" variant="secondary" onClick={() => setRecommend(e.name)}><Send className="size-4" />{e.employee_name}</Button>
          ))}
          {!d.reports.length && <span className="text-sm text-muted">{t('Nobody reports to you.')}</span>}
        </div>
        {d.requests.length > 0 && (
          <ul className="mt-4 divide-y divide-line text-sm">
            {d.requests.map((r: any) => (
              <li key={r.name} className="flex items-center justify-between py-2"><span>{r.employee_name} · {r.request_type} · {fmtDate(r.creation, lang)}</span><StatusBadge status={r.status} /></li>
            ))}
          </ul>
        )}
      </Card>
      <AppraisalForm name={open} onClose={() => setOpen(null)} />
      <RequestForm open={!!recommend} onClose={() => setRecommend(null)} employee={recommend ?? undefined} initialType="Appraisal Request" category="Performance" />
    </div>
  )
}
