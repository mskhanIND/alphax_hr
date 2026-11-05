import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Input, PageHeader, Select, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const COLS: [string, string][] = [['enabled', 'On'], ['app', 'App & phone'], ['email', 'Email'], ['to_employee', 'Employee'], ['to_manager', 'Manager / approver'], ['to_hr', 'HR']]
const NEEDS_MINUTES = new Set(['Late arrival', 'Missing check-in'])

export default function NotificationsAdmin() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['alertSettings'], queryFn: api.alertSettings })
  const [rows, setRows] = useState<any[]>([])
  const [aud, setAud] = useState<any[]>([])
  const [bellAll, setBellAll] = useState(0)
  useEffect(() => { if (q.data) { setRows(q.data.rules); setAud(q.data.audience ?? []); setBellAll(q.data.bell_all ?? 0) } }, [q.data])
  const save = useMutation({ mutationFn: () => api.saveAlertSettings(rows, aud, bellAll), onSuccess: (d) => qc.setQueryData(['alertSettings'], d) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const can = q.data.can_edit
  const dirty = JSON.stringify(rows) !== JSON.stringify(q.data.rules) || JSON.stringify(aud) !== JSON.stringify(q.data.audience ?? []) || bellAll !== (q.data.bell_all ?? 0)
  const setA = (i: number, k: string, v: string) => setAud(aud.map((r, j) => (j === i ? { ...r, [k]: v, ...(k === 'target_type' ? { target: '' } : {}) } : r)))
  const LINK: Record<string, string> = { Department: 'Department', Branch: 'Branch', Designation: 'Designation', Role: 'Role', Employee: 'Employee', User: 'User' }
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
        <label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={!can} checked={!!bellAll} onChange={(e) => setBellAll(e.target.checked ? 1 : 0)} />
          {t('The bell shows every notification')} <span className="text-xs text-muted">({t('off: only HR notifications; other apps stay in the Desk')})</span></label>
        <p className="mt-3 text-xs text-muted">{t('Approval reminder and escalation timing is set in Leave setup → Approval delays.')} ({t('Reminder')}: {q.data.approval_remind_hours || '—'} h · {t('Escalation')}: {q.data.leave_escalation_hours || '—'} h)</p>
      </Card>
      <Card title={t('Extra recipients and exceptions')} subtitle={t('Add people to an event — for every service or one request / leave type — or make sure they never get it. Exceptions win.')}
        action={can ? <Button size="sm" variant="secondary" onClick={() => setAud([...aud, { event: 'Request submitted', service: '', action: 'Also notify', target_type: 'Department', target: '' }])}><Plus className="size-4" />{t('Add rule')}</Button> : undefined}>
        {!aud.length ? <p className="text-sm text-muted">{t('No extra recipients or exceptions. The table above decides who is told.')}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted"><tr>
                {['Event', 'Only for service', 'Action', 'Who', 'Name', ''].map((h) => <th key={h} className="pb-2 pe-2 text-start">{t(h)}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {aud.map((r, i) => (
                  <tr key={i}>
                    <td className="py-2 pe-2"><Select value={r.event} disabled={!can} onChange={(e) => setA(i, 'event', e.target.value)}>{q.data.events.map((x: string) => <option key={x} value={x}>{t(x)}</option>)}</Select></td>
                    <td className="py-2 pe-2"><Select value={r.service ?? ''} disabled={!can} onChange={(e) => setA(i, 'service', e.target.value)}><option value="">{t('Every service')}</option>{q.data.services.map((x: string) => <option key={x} value={x}>{t(x)}</option>)}</Select></td>
                    <td className="py-2 pe-2"><Select value={r.action} disabled={!can} onChange={(e) => setA(i, 'action', e.target.value)}><option value="Also notify">{t('Also notify')}</option><option value="Never notify">{t('Never notify')}</option></Select></td>
                    <td className="py-2 pe-2"><Select value={r.target_type} disabled={!can} onChange={(e) => setA(i, 'target_type', e.target.value)}>{q.data.targets.map((x: string) => <option key={x} value={x}>{t(x)}</option>)}</Select></td>
                    <td className="min-w-56 py-2 pe-2">{r.target_type === 'All employees' ? <span className="text-muted">—</span>
                      : <LinkInput doctype={LINK[r.target_type]} value={r.target ?? ''} onChange={(v) => setA(i, 'target', v)} />}</td>
                    <td className="py-2">{can && <button aria-label={t('Remove')} className="text-red-700" onClick={() => setAud(aud.filter((_x, j) => j !== i))}><Trash2 className="size-4" /></button>}</td>
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
