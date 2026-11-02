import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Circle, Info } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, ErrorBox, Modal, PageHeader, Spinner, Table } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const ICON: Record<string, any> = {
  ok: <CheckCircle2 className="size-5 text-emerald-600" />, todo: <Circle className="size-5 text-red-600" />,
  warn: <AlertTriangle className="size-5 text-amber-600" />, info: <Info className="size-5 text-blue-600" />,
}

export default function Cutover() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['cutover'], queryFn: api.cutoverReadiness })
  const [plan, setPlan] = useState<any>(null)
  const dry = useMutation({ mutationFn: (kind: string) => api.importLegacy(kind, 1), onSuccess: setPlan })
  const run = useMutation({ mutationFn: (kind: string) => api.importLegacy(kind, 0), onSuccess: () => { setPlan(null); qc.invalidateQueries({ queryKey: ['cutover'] }) } })
  const fieldsAtRisk = (i: any) => { try { return JSON.parse(i.detail) } catch { return [] } }
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Cut-over readiness')} subtitle={t('Bring everything over from the previous HR app before it is uninstalled.')} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <Card>
            <div className="flex items-center gap-3">
              {q.data.ready ? <CheckCircle2 className="size-6 text-emerald-600" /> : <AlertTriangle className="size-6 text-amber-600" />}
              <div className="font-medium">{q.data.ready ? t('Ready: nothing left to bring over.') : `${q.data.todo} ${t('item(s) to finish before uninstalling')}`}</div>
            </div>
          </Card>
          <Card>
            <ul className="divide-y divide-line">
              {q.data.items.map((i: any) => (
                <li key={i.key} className="flex flex-wrap items-start gap-3 py-3">
                  {ICON[i.status]}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{i.label}</div>
                    {i.key === 'legacy_fields' && i.count ? (
                      <ul className="mt-1 text-sm text-muted">{fieldsAtRisk(i).map((f: any) => <li key={f.doctype + f.fieldname}>{f.doctype} · {f.label || f.fieldname} — {f.records}</li>)}</ul>
                    ) : i.detail && <div className="text-sm text-muted">{i.detail}</div>}
                  </div>
                  {i.action && i.count > 0 && <Button size="sm" loading={dry.isPending && dry.variables === i.action} onClick={() => dry.mutate(i.action)}>{t('Preview import')}</Button>}
                  {i.link && i.status !== 'ok' && <Link className="text-sm text-brand underline" to={i.link}>{t('Open')}</Link>}
                </li>
              ))}
            </ul>
            {dry.error && <ErrorBox error={dry.error} />}
          </Card>
          {q.data.request_types?.length > 0 && (
            <Card title={t('Legacy requests')}>
              <Table head={[t('Legacy document'), t('Becomes'), t('Records'), t('Not yet imported')]}>
                {q.data.request_types.map((r: any) => (
                  <tr key={r.doctype}><td className="py-2">{r.doctype}</td><td>{t(r.target)}</td><td>{r.records}</td>
                    <td>{r.left ? <Badge tone="amber">{r.left}</Badge> : '0'}</td></tr>
                ))}
              </Table>
            </Card>
          )}
        </>
      )}
      <Modal open={!!plan} onClose={() => setPlan(null)} wide title={plan ? `${t('Preview import')} · ${plan.count}` : ''}
        footer={<><Button variant="secondary" onClick={() => setPlan(null)}>{t('Close')}</Button>
          <Button disabled={!plan?.count} loading={run.isPending} onClick={() => run.mutate(plan.kind)}>{t('Import now')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{t('Records are copied once; running again only brings over new ones. Nothing in the old app is changed.')}</p>
        <pre className="max-h-96 overflow-auto rounded-xl bg-surface p-3 text-xs">{JSON.stringify(plan?.sample ?? [], null, 2)}</pre>
        {run.error && <ErrorBox error={run.error} />}
      </Modal>
    </div>
  )
}
