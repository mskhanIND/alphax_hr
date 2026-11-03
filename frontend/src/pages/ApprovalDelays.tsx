import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Badge, Card, Empty, ErrorBox, PageHeader, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TONE: Record<string, string> = { 'On time': 'green', Reminded: 'amber', Overdue: 'red', Escalated: 'red' }

function age(h: number, t: (s: string) => string) {
  return h >= 48 ? `${Math.floor(h / 24)} ${t('days')}` : `${Math.round(h)} ${t('hours')}`
}

export default function ApprovalDelays() {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['approvalDelays'], queryFn: api.approvalDelays, refetchInterval: 300_000 })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Approval delays')}
        subtitle={d.remind_hours || d.escalate_hours
          ? `${t('Reminder after')} ${d.remind_hours || '—'} h · ${t('escalation after')} ${d.escalate_hours || '—'} h`
          : t('Reminders and escalation are off. Set them in Leave setup → Approval delays.')} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Waiting')} value={d.rows.length} />
        <Stat label={t('Reminded')} value={d.counts.Reminded} tone="amber" />
        <Stat label={t('Overdue')} value={d.counts.Overdue} tone="red" />
        <Stat label={t('Escalated')} value={d.counts.Escalated} tone="red" />
      </div>
      {d.is_hr && d.approvers.length > 0 && (
        <Card title={t('By approver')} subtitle={t('Pending now, and average time to decide over the last 90 days.')}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted"><tr>
                <th className="pb-2 text-start">{t('Approver')}</th><th className="pb-2 text-start">{t('Pending')}</th>
                <th className="pb-2 text-start">{t('Overdue')}</th><th className="pb-2 text-start">{t('Oldest')}</th>
                <th className="pb-2 text-start">{t('Average decision time')}</th>
              </tr></thead>
              <tbody className="divide-y divide-line">
                {d.approvers.map((a: any) => (
                  <tr key={a.approver}>
                    <td className="py-2 pe-3 font-medium">{a.approver_name}</td>
                    <td className="py-2 pe-3">{a.pending}</td>
                    <td className="py-2 pe-3">{a.overdue ? <Badge tone="red">{a.overdue}</Badge> : 0}</td>
                    <td className="py-2 pe-3">{a.pending ? age(a.oldest_hours, t) : '—'}</td>
                    <td className="py-2">{a.avg_hours != null ? `${age(a.avg_hours, t)} (${a.decided})` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Card title={t('Waiting for a decision')}>
        {d.rows.length === 0 ? <Empty title={t('Nothing is waiting.')} /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="delay-rows">
              <thead className="text-xs text-muted"><tr>
                <th className="pb-2 text-start">{t('Employee')}</th><th className="pb-2 text-start">{t('Request')}</th>
                <th className="pb-2 text-start">{t('Waiting with')}</th><th className="pb-2 text-start">{t('Since')}</th>
                <th className="pb-2 text-start">{t('Waiting')}</th><th className="pb-2 text-start">{t('Stage')}</th>
              </tr></thead>
              <tbody className="divide-y divide-line">
                {d.rows.map((r: any) => (
                  <tr key={r.doctype + r.name}>
                    <td className="py-2 pe-3">{r.employee_name}</td>
                    <td className="py-2 pe-3"><Link className="text-brand-700 hover:underline" to="/approvals">{t(r.kind)}: {r.what}</Link></td>
                    <td className="py-2 pe-3">{r.approver_name}</td>
                    <td className="py-2 pe-3">{fmtDate(r.since)}</td>
                    <td className="py-2 pe-3">{age(r.age_hours, t)}</td>
                    <td className="py-2"><Badge tone={TONE[r.stage]}>{t(r.stage)}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
