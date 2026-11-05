import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TONE: Record<string, string> = { 'On time': 'green', Reminded: 'amber', Overdue: 'red', Escalated: 'red', 'HR reminded': 'red' }

function age(h: number, t: (s: string) => string) {
  return h >= 48 ? `${Math.floor(h / 24)} ${t('days')}` : `${Math.round(h)} ${t('hours')}`
}

export default function ApprovalDelays() {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['approvalDelays'], queryFn: api.approvalDelays, refetchInterval: 300_000 })
  const qc = useQueryClient()
  const remind = useMutation({ mutationFn: (r: any) => api.remindApprover(r.doctype, r.name), onSuccess: () => qc.invalidateQueries({ queryKey: ['approvalDelays'] }) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Approval delays')}
        subtitle={d.remind_hours || d.escalate_hours
          ? `${t('Reminder after')} ${d.remind_hours || '—'} h · ${t('escalation after')} ${d.escalate_hours || '—'} h`
          : t('Reminders and escalation are off. Set them in Leave setup → Approval delays.')}
        actions={d.is_hr ? <Link to="/approval-policies"><Button variant="secondary">{t('Approval policies')}{d.policies ? ` (${d.policies})` : ''}</Button></Link> : undefined} />
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
      {remind.error && <ErrorBox error={remind.error} />}
      {remind.data && <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand">{t('Reminder sent.')}{remind.data.reject_on ? ` ${t('Rejected automatically on')} ${fmtDate(remind.data.reject_on)} ${t('if nobody decides.')}` : ''}</p>}
      <Card title={t('Waiting for a decision')}>
        {d.rows.length === 0 ? <Empty title={t('Nothing is waiting.')} /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="delay-rows">
              <thead className="text-xs text-muted"><tr>
                <th className="pb-2 text-start">{t('Employee')}</th><th className="pb-2 text-start">{t('Request')}</th>
                <th className="pb-2 text-start">{t('Waiting with')}</th><th className="pb-2 text-start">{t('Since')}</th>
                <th className="pb-2 text-start">{t('Waiting')}</th><th className="pb-2 text-start">{t('Stage')}</th>
                <th className="pb-2 text-start">{t('Next')}</th>{d.is_hr && <th className="pb-2" />}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {d.rows.map((r: any) => (
                  <tr key={r.doctype + r.name}>
                    <td className="py-2 pe-3">{r.employee_name}</td>
                    <td className="py-2 pe-3"><Link className="text-brand-700 hover:underline" to="/approvals">{t(r.kind)}: {r.what}</Link></td>
                    <td className="py-2 pe-3">{r.approver_name}</td>
                    <td className="py-2 pe-3">{fmtDate(r.since)}</td>
                    <td className="py-2 pe-3">{r.working_days != null ? `${r.working_days} ${t('working days')}` : age(r.age_hours, t)}</td>
                    <td className="py-2 pe-3"><Badge tone={TONE[r.stage]}>{t(r.stage)}</Badge></td>
                    <td className="py-2 pe-3 text-xs text-muted">
                      {r.next_step ? `${t(r.next_step)} ${fmtDate(r.next_on)}` : ''}
                      {r.reject_on && <div className="text-red-700">{t('Rejected automatically on')} {fmtDate(r.reject_on)}</div>}
                    </td>
                    {d.is_hr && <td className="py-2 text-end">
                      <Button size="sm" variant="secondary" loading={remind.isPending && remind.variables?.name === r.name} onClick={() => remind.mutate(r)}
                        title={t('Remind the approver now. Under a policy, the automatic rejection is counted from this reminder.')}>
                        <BellRing className="size-4" />{t('Remind')}</Button>
                    </td>}
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
