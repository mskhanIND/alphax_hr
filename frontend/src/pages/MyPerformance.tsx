import { useQuery } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, Empty, ErrorBox, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'

export default function MyPerformance() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['my-appraisals'], queryFn: api.myAppraisals })
  return (
    <div>
      <PageHeader title={t('My performance')} subtitle={t('Your appraisals and scores')} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length
        ? <Card><Empty title={t('No appraisals yet')} icon={<Star />}>{t('Your appraisals appear here when a cycle starts.')}</Empty></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data.map((a: any) => (
            <Card key={a.name} title={a.appraisal_cycle} subtitle={`${fmtDate(a.start_date, lang)} → ${fmtDate(a.end_date, lang)}`} action={<StatusBadge status={a.status} />}>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-muted">{t('Goals')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.total_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Feedback')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.avg_feedback_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Self')}</dt><dd className="text-lg font-semibold">{fmtNumber(a.self_score, lang, 1)}</dd></div>
                <div><dt className="text-muted">{t('Final score')}</dt><dd className="text-lg font-semibold text-brand">{fmtNumber(a.final_score, lang, 2)}</dd></div>
              </dl>
              {a.can_open && <Link className="mt-3 inline-block text-sm text-brand underline" to={recordPath('Appraisal', a.name)}>{t('Open')}</Link>}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
