import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, MessageCircle, Plus } from 'lucide-react'
import { useState } from 'react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { RequestForm, typeTitle } from '../components/RequestForm'
import { RequestThread } from '../components/RequestThread'
import { Avatar, Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Table, Textarea } from '../components/ui'
import { LinkInput } from '../components/LinkInput'
import { api, type RequestType } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { detailsText } from './MyRequests'

const STATUSES = ['open', 'Pending Manager', 'Pending HR', 'Approved', 'Completed', 'Rejected', 'Cancelled']

function TypeSettings() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['request-types', 'all'], queryFn: () => api.requestTypes(1) })
  const [edit, setEdit] = useState<RequestType | null>(null)
  const [fieldsText, setFieldsText] = useState('')
  const m = useMutation({
    mutationFn: (d: { name: string; data: Record<string, unknown> }) => api.updateRequestType(d.name, d.data),
    onSuccess: () => { setEdit(null); qc.invalidateQueries({ queryKey: ['request-types'] }) },
  })
  const toggle = (rt: RequestType, key: keyof RequestType) => m.mutate({ name: rt.name, data: { [key]: rt[key] ? 0 : 1 } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  return (
    <Card title={t('Request types')} subtitle={t('Choose who approves each request, the target time and the details asked for.')}>
      <Table head={[t('Request type'), t('Category'), t('Enabled'), t('Manager approval'), t('HR approval'), t('Attachment required'), t('Target (days)'), '']}>
        {q.data!.map((rt) => (
          <tr key={rt.name}>
            <td className="py-2 font-medium">{typeTitle(rt, lang)}</td>
            <td>{t(rt.category)}</td>
            {(['enabled', 'needs_manager', 'needs_hr', 'requires_attachment'] as const).map((k) => (
              <td key={k}><input type="checkbox" className="size-4" checked={!!rt[k]} onChange={() => toggle(rt, k)} aria-label={k} /></td>
            ))}
            <td><Input type="number" className="w-20" defaultValue={rt.sla_days} onBlur={(e) => Number(e.target.value) !== rt.sla_days && m.mutate({ name: rt.name, data: { sla_days: Number(e.target.value) } })} /></td>
            <td><Button size="sm" variant="secondary" onClick={() => { setEdit(rt); setFieldsText(JSON.stringify(rt.fields, null, 2)) }}>{t('Fields')}</Button></td>
          </tr>
        ))}
      </Table>
      {m.error && <ErrorBox error={m.error} />}
      <Modal open={!!edit} onClose={() => setEdit(null)} wide title={edit ? `${t('Fields')} · ${typeTitle(edit, lang)}` : ''}
        footer={<><Button variant="secondary" onClick={() => setEdit(null)}>{t('Cancel')}</Button>
          <Button loading={m.isPending} onClick={() => { try { m.mutate({ name: edit!.name, data: { fields: JSON.parse(fieldsText || '[]') } }) } catch { alert(t('The field list is not valid JSON.')) } }}>{t('Save')}</Button></>}>
        <p className="mb-2 text-sm text-muted">{t('Each field: fieldname, label, label_ar, type (Data, Date, Int, Currency, Select, Text, Check), reqd, options.')}</p>
        <Textarea rows={14} className="font-mono text-xs" value={fieldsText} onChange={(e) => setFieldsText(e.target.value)} />
        {m.error && <ErrorBox error={m.error} />}
      </Modal>
    </Card>
  )
}

export default function Requests() {
  const { t, lang } = useI18n()
  const [tab, setTab] = useState<'list' | 'types'>('list')
  const [status, setStatus] = useState('open')
  const [rtype, setRtype] = useState('')
  const [overdue, setOverdue] = useState(false)
  const [trail, setTrail] = useState<string | null>(null)
  const [thread, setThread] = useState<any>(null)
  const [raise, setRaise] = useState(false)
  const [forEmp, setForEmp] = useState('')
  const [act, setAct] = useState<{ row: any; action: string } | null>(null)
  const [comment, setComment] = useState('')
  const qc = useQueryClient()
  const types = useQuery({ queryKey: ['request-types'], queryFn: () => api.requestTypes() })
  const q = useQuery({ queryKey: ['requests', status, rtype, overdue], queryFn: () => api.allRequests({ status, request_type: rtype, overdue: overdue ? 1 : 0 }), enabled: tab === 'list' })
  const inbox = useQuery<any>({ queryKey: ['inbox'], queryFn: api.inbox })
  const actions = (name: string) => (inbox.data?.items ?? []).find((i: any) => i.doctype === 'AlphaX Request' && i.name === name)?.actions ?? []
  const m = useMutation({
    mutationFn: () => api.act('AlphaX Request', act!.row.name, act!.action, comment || undefined),
    onSuccess: () => { setAct(null); setComment(''); qc.invalidateQueries({ queryKey: ['requests'] }); qc.invalidateQueries({ queryKey: ['inbox'] }) },
  })
  const typeOf = (n: string) => types.data?.find((x) => x.name === n)
  return (
    <div>
      <PageHeader title={t('Requests')} subtitle={q.data ? `${q.data.rows.length} ${t('requests')}` : undefined}
        actions={<div className="flex gap-2">
          <div className="flex rounded-xl border border-line p-0.5" role="tablist">
            {(['list', 'types'] as const).map((v) => (
              <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
                className={`rounded-lg px-3 py-1.5 text-sm ${tab === v ? 'bg-brand text-white' : 'text-muted hover:bg-surface'}`}>{t(v === 'list' ? 'Requests' : 'Request types')}</button>
            ))}
          </div>
          <Button onClick={() => setRaise(true)}><Plus className="size-4" />{t('Raise for employee')}</Button>
        </div>} />
      {tab === 'types' ? <TypeSettings /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {STATUSES.map((s) => (
              <Button key={s} size="sm" variant={status === s ? 'primary' : 'secondary'} onClick={() => setStatus(s)}>
                {t(s === 'open' ? 'Open' : s)}{s !== 'open' && q.data?.counts?.[s] ? ` · ${q.data.counts[s]}` : ''}
              </Button>
            ))}
            <Select className="w-56" value={rtype} onChange={(e) => setRtype(e.target.value)}>
              <option value="">{t('All request types')}</option>
              {(types.data ?? []).map((x) => <option key={x.name} value={x.name}>{typeTitle(x, lang)}</option>)}
            </Select>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} />{t('Overdue only')}</label>
          </div>
          <Card>
            {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data?.rows.length ? (
              <Empty title={t('No requests')} icon={<FileText />}>{t('Nothing matches these filters.')}</Empty>
            ) : (
              <ul className="divide-y divide-line">
                {q.data.rows.map((r: any) => (
                  <li key={r.name} className="flex flex-wrap items-center gap-3 py-3">
                    <button type="button" className="flex min-w-0 flex-1 items-center gap-3 text-start" onClick={() => setTrail(r.name)} title={t('Show activity')}>
                      <Avatar name={r.employee_name} size={36} />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{r.employee_name}</span>
                          <Badge tone="blue">{typeTitle(typeOf(r.request_type), lang, r.request_type)}</Badge>
                          <StatusBadge status={r.status} />
                          {r.overdue && <Badge tone="red">{t('Overdue')}</Badge>}
                        </div>
                        <div className="truncate text-sm text-muted">{r.name} · {fmtDate(r.creation, lang)} · {t('Due')} {fmtDate(r.due_on, lang)}{detailsText(r.details) ? ` · ${detailsText(r.details)}` : ''}</div>
                        {r.reason && <div className="line-clamp-1 text-sm">“{r.reason}”</div>}
                        {r.details?.short_notice && <div className="text-xs text-amber-800">{r.details.short_notice}</div>}
                      </div>
                    </button>
                    <Button size="sm" variant={r.last_from_employee ? 'primary' : 'secondary'} onClick={() => setThread(r)} title={r.last_from_employee ? t('The employee is waiting for a reply') : undefined}>
                      <MessageCircle className="size-4" />{r.messages || ''}</Button>
                    {r.letter && <a className="text-sm font-medium text-brand underline" href={r.letter} target="_blank" rel="noreferrer">{t('Letter')}</a>}
                    {actions(r.name).map((a: string) => (
                      <Button key={a} size="sm" variant={a === 'Reject' ? 'secondary' : 'primary'} onClick={() => setAct({ row: r, action: a })}>{t(a)}</Button>
                    ))}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
      {trail && <ActivityDrawer doctype="AlphaX Request" name={trail} onClose={() => setTrail(null)} />}
      {thread && <RequestThread name={thread.name} title={`${thread.employee_name} · ${typeTitle(typeOf(thread.request_type), lang, thread.request_type)}`} onClose={() => setThread(null)} />}
      <Modal open={!!act} onClose={() => setAct(null)} title={act ? `${t(act.action)} · ${act.row.employee_name}` : ''}
        footer={<><Button variant="secondary" onClick={() => setAct(null)}>{t('Cancel')}</Button>
          <Button variant={act?.action === 'Reject' ? 'danger' : 'primary'} loading={m.isPending} onClick={() => m.mutate()}>{act ? t(act.action) : ''}</Button></>}>
        <Textarea placeholder={act?.action === 'Complete' ? t('What was done (e.g. visa number)') : t('Comment (optional)')} value={comment} onChange={(e) => setComment(e.target.value)} />
        {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
      </Modal>
      {raise && !forEmp && (
        <Modal open onClose={() => setRaise(false)} title={t('Raise for employee')}>
          <Field label={t('Employee')}><LinkInput doctype="Employee" value={forEmp} onChange={setForEmp} /></Field>
        </Modal>
      )}
      <RequestForm open={raise && !!forEmp} employee={forEmp || undefined} onClose={() => { setRaise(false); setForEmp('') }} />
    </div>
  )
}
