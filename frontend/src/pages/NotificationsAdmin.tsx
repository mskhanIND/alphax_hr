import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Button, Card, ErrorBox, Input, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const COLS: [string, string][] = [['enabled', 'On'], ['app', 'App & phone'], ['email', 'Email'], ['to_employee', 'Employee'], ['to_manager', 'Manager / approver'], ['to_hr', 'HR']]
const NEEDS_MINUTES = new Set(['Late arrival', 'Missing check-in'])

export default function NotificationsAdmin() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['alertSettings'], queryFn: api.alertSettings })
  const [rows, setRows] = useState<any[]>([])
  useEffect(() => { if (q.data) setRows(q.data.rules) }, [q.data])
  const save = useMutation({ mutationFn: () => api.saveAlertSettings(rows), onSuccess: (d) => qc.setQueryData(['alertSettings'], d) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const can = q.data.can_edit
  const dirty = JSON.stringify(rows) !== JSON.stringify(q.data.rules)
  const set = (i: number, k: string, v: number) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Notifications')} subtitle={t('Who hears about what, by email and in the app (with phone push for installed apps).')}
        actions={can ? <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button> : undefined} />
      {save.error && <ErrorBox error={save.error} />}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted"><tr>
              <th className="pb-2 text-start">{t('Event')}</th>
              {COLS.map(([k, l]) => <th key={k} className="px-2 pb-2 text-center">{t(l)}</th>)}
              <th className="pb-2 text-start">{t('Minutes')}</th>
            </tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((r, i) => (
                <tr key={r.event} className={r.enabled ? '' : 'opacity-60'}>
                  <td className="py-2.5 pe-3"><div className="font-medium">{t(r.event)}</div><div className="text-xs text-muted">{t(r.help)}</div></td>
                  {COLS.map(([k, l]) => (
                    <td key={k} className="px-2 py-2.5 text-center">
                      <input type="checkbox" aria-label={`${t(r.event)}: ${t(l)}`} className="size-4 accent-[var(--color-brand)]" disabled={!can || (k !== 'enabled' && !r.enabled)}
                        checked={!!r[k]} onChange={(e) => set(i, k, e.target.checked ? 1 : 0)} />
                    </td>
                  ))}
                  <td className="py-2.5">
                    {NEEDS_MINUTES.has(r.event) ? <Input type="number" min={0} className="!w-20" value={r.minutes} disabled={!can}
                      onChange={(e) => set(i, 'minutes', Number(e.target.value) || 0)} /> : <span className="text-muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">{t('Approval reminder and escalation timing is set in Leave setup → Approval delays.')} ({t('Reminder')}: {q.data.approval_remind_hours || '—'} h · {t('Escalation')}: {q.data.leave_escalation_hours || '—'} h)</p>
      </Card>
    </div>
  )
}
