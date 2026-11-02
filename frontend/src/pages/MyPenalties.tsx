import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, Modal, PageHeader, Spinner, StatusBadge, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { stepText } from './Penalties'

export default function MyPenalties() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['my-penalties'], queryFn: api.myPenalties })
  const [obj, setObj] = useState<any>(null)
  const [reply, setReply] = useState('')
  const m = useMutation({ mutationFn: (a: { name: string; action: string; reply?: string }) => api.respondPenalty(a.name, a.action, a.reply),
    onSuccess: () => { setObj(null); setReply(''); qc.invalidateQueries({ queryKey: ['my-penalties'] }) } })
  return (
    <div>
      <PageHeader title={t('My warnings')} subtitle={t('You can acknowledge a warning or object to it within 15 days.')} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? (
          <Empty title={t('No warnings')} icon={<ShieldCheck />}>{t('Keep it up!')}</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {q.data.map((p: any) => (
              <li key={p.name} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{p.violation_type}</span><StatusBadge status={p.status} /></div>
                  <div className="text-sm text-muted">{fmtDate(p.violation_date, lang)} · {stepText(p, t)}{p.amount ? ` · ${fmtMoney(p.amount, lang)}` : ''}</div>
                  {p.description && <div className="text-sm">{p.description}</div>}
                  {p.employee_reply && <div className="text-xs text-muted">{t('Your reply')}: “{p.employee_reply}”</div>}
                </div>
                {p.status === 'Issued' && <>
                  <Button size="sm" loading={m.isPending} onClick={() => m.mutate({ name: p.name, action: 'Acknowledge' })}>{t('Acknowledge')}</Button>
                  {p.can_object && <Button size="sm" variant="secondary" onClick={() => setObj(p)}>{t('Object')}</Button>}
                </>}
              </li>
            ))}
          </ul>
        )}
        {m.error && <ErrorBox error={m.error} />}
      </Card>
      <Modal open={!!obj} onClose={() => setObj(null)} title={t('Object')}
        footer={<><Button variant="secondary" onClick={() => setObj(null)}>{t('Cancel')}</Button>
          <Button disabled={!reply.trim()} loading={m.isPending} onClick={() => m.mutate({ name: obj.name, action: 'Object', reply })}>{t('Send')}</Button></>}>
        <Textarea placeholder={t('Explain your objection')} value={reply} onChange={(e) => setReply(e.target.value)} />
        {m.error && <ErrorBox error={m.error} />}
      </Modal>
    </div>
  )
}
