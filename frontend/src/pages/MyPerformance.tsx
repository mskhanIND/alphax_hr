import { useQuery } from '@tanstack/react-query'
import { Send, Star } from 'lucide-react'
import { useState } from 'react'
import { AppraisalForm } from '../components/AppraisalForm'
import { RequestForm } from '../components/RequestForm'
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

const STAGE_TONE: Record<string, string> = { 'Waiting for self': 'amber', 'Self done': 'blue', Reviewed: 'blue', Final: 'green' }

export default function MyPerformance() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['my-appraisals'], queryFn: api.myAppraisals })
  const [open, setOpen] = useState<string | null>(null)
  const [ask, setAsk] = useState(false)
  return (
    <div>
      <PageHeader title={t('My performance')} subtitle={t('Rate yourself, see your manager\'s review and your final score')}
        actions={<Button variant="secondary" onClick={() => setAsk(true)}><Send className="size-4" />{t('Request an appraisal / promotion')}</Button>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length
        ? <Card><Empty title={t('No appraisals yet')} icon={<Star />}>{t('Your appraisals appear here when a cycle starts.')}</Empty></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data.map((a: any) => (
            <Card key={a.name} title={a.appraisal_cycle} subtitle={`${fmtDate(a.start_date, lang)} → ${fmtDate(a.end_date, lang)}`}
              action={<Badge tone={STAGE_TONE[a.stage] ?? 'gray'}>{t(a.stage === 'Waiting for self' ? 'Your self-appraisal is due' : a.stage)}</Badge>}>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-muted">{t('Goals')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.total_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Feedback')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.avg_feedback_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Self')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.self_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Final score')}</dt><dd className="text-lg font-semibold text-brand">{fmtNumber(a.final_score, lang, 2)}</dd></div>
              </dl>
              <Button className="mt-3" size="sm" variant={a.stage === 'Waiting for self' ? 'primary' : 'secondary'} onClick={() => setOpen(a.name)}>
                {a.docstatus === 0 ? t('Open my self-appraisal') : t('View')}
              </Button>
            </Card>
          ))}
        </div>
      )}
      <AppraisalForm name={open} onClose={() => setOpen(null)} />
      <RequestForm open={ask} onClose={() => setAsk(false)} initialType="Appraisal Request" category="Performance" />
    </div>
  )
}
