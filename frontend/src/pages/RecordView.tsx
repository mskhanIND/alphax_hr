import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, History, Paperclip } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { Badge, Button, Card, ErrorBox, Modal, PageHeader, Spinner, Textarea, statusTone } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

/** Any HR record, read inside AlphaX in the record's own layout (every field the user may see). */
export default function RecordView() {
  const { doctype = '', name = '' } = useParams()
  const { t } = useI18n()
  const nav = useNavigate()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['record', doctype, name], queryFn: () => api.record(doctype, name) })
  const [showEmpty, setShowEmpty] = useState(false)
  const [activity, setActivity] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [comment, setComment] = useState('')
  const act = useMutation({
    mutationFn: (action: string) => api.act(doctype, name, action, comment || undefined),
    onSuccess: () => { setPending(null); setComment(''); qc.invalidateQueries({ queryKey: ['record', doctype, name] }); qc.invalidateQueries({ queryKey: ['inbox'] }) },
  })
  // opened from a notification or a shared link there is no page to go back to: go to the approvals list instead
  const back = () => ((window.history.state?.idx ?? 0) > 0 ? nav(-1) : nav('/approvals'))
  const backBtn = <Button size="sm" variant="secondary" className="self-start" onClick={back}><ArrowLeft className="size-4 flip-rtl" />{t('Back')}</Button>
  if (q.isLoading) return <div className="flex flex-col gap-5">{backBtn}<Spinner /></div>
  if (q.error) return <div className="flex flex-col gap-5">{backBtn}<ErrorBox error={q.error} onRetry={() => q.refetch()} /></div>
  const d = q.data
  const openable = new Set<string>(d.openable)
  const linkTo = (f: any) => {
    if (!f.display || !f.link_doctype) return null
    if (f.link_doctype === 'Employee') return `/people/${encodeURIComponent(f.value)}`
    if (openable.has(f.link_doctype)) return `/r/${encodeURIComponent(f.link_doctype)}/${encodeURIComponent(f.value)}`
    return null
  }
  const negative = (a: string) => /reject|decline|cancel/i.test(a)
  return (
    <div className="flex flex-col gap-5">
      {backBtn}
      <PageHeader title={d.title} subtitle={`${t(d.doctype)} · ${d.name}`}
        actions={<div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone(d.status)}>{t(d.status)}</Badge>
          {d.actions.map((a: string) => <Button key={a} variant={negative(a) ? 'secondary' : 'primary'} onClick={() => setPending(a)}>{t(a)}</Button>)}
          <Button variant="secondary" onClick={() => setActivity(true)}><History className="size-4" />{t('Activity')}</Button>
          {d.desk_url && <a href={d.desk_url} target="_blank" rel="noreferrer"><Button variant="ghost"><ExternalLink className="size-4" />{t('Desk')}</Button></a>}
        </div>} />
      {d.employee && d.doctype !== 'Employee' && <Link to={`/people/${encodeURIComponent(d.employee)}`} className="self-start text-sm text-brand hover:underline">{t('Open employee profile')}</Link>}
      <label className="flex items-center gap-2 self-end text-sm text-muted"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={showEmpty} onChange={(e) => setShowEmpty(e.target.checked)} />{t('Show empty fields')}</label>
      {d.sections.map((sec: any, i: number) => {
        const fields = sec.fields.filter((f: any) => f.fieldtype === 'Table' || showEmpty || f.display)
        if (!fields.length) return null
        return (
          <Card key={i} title={sec.label || undefined}>
            <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {fields.map((f: any) => f.fieldtype === 'Table' ? (
                <div key={f.fieldname} className="sm:col-span-2">
                  <div className="mb-1 text-sm text-muted">{f.label}</div>
                  <div className="overflow-x-auto"><table className="w-full whitespace-nowrap text-sm">
                    <thead className="text-xs text-muted"><tr className="border-b border-line">{f.columns.map((c: string) => <th key={c} className="px-2 pb-1 text-start font-medium">{c}</th>)}</tr></thead>
                    <tbody className="divide-y divide-line">{f.rows.map((r: any[], j: number) => <tr key={j}>{r.map((v, k) => <td key={k} className="px-2 py-1.5">{v ?? '—'}</td>)}</tr>)}</tbody>
                  </table></div>
                </div>
              ) : (
                <div key={f.fieldname} className={['Small Text', 'Text', 'Long Text', 'Text Editor'].includes(f.fieldtype) ? 'text-sm sm:col-span-2' : 'text-sm'}>
                  <div className="text-muted">{f.label}</div>
                  <div className="font-medium whitespace-pre-wrap">
                    {!f.display ? <span className="text-muted">—</span>
                      : linkTo(f) ? <Link to={linkTo(f)!} className="text-brand hover:underline">{f.display}</Link>
                      : f.fieldtype.startsWith('Attach') ? <a href={f.value} target="_blank" rel="noreferrer" className="text-brand hover:underline">{f.display.split('/').pop()}</a>
                      : f.display}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )
      })}
      {d.files.length > 0 && (
        <Card title={t('Attachments')}>
          <ul className="flex flex-col gap-1 text-sm">{d.files.map((f: any) => <li key={f.file_url}><a href={f.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-brand hover:underline"><Paperclip className="size-4" />{f.file_name}</a></li>)}</ul>
        </Card>
      )}
      {activity && <ActivityDrawer doctype={d.doctype} name={d.name} onClose={() => setActivity(false)} hideOpen />}
      <Modal open={!!pending} onClose={() => setPending(null)} title={pending ? `${t(pending)} · ${d.title}` : ''}
        footer={<>
          <Button variant="secondary" onClick={() => setPending(null)}>{t('Cancel')}</Button>
          <Button variant={pending && negative(pending) ? 'danger' : 'primary'} loading={act.isPending} onClick={() => pending && act.mutate(pending)}>{pending ? t(pending) : ''}</Button>
        </>}>
        <Textarea placeholder={t('Comment (optional)')} value={comment} onChange={(e) => setComment(e.target.value)} />
        {act.error && <div className="mt-3"><ErrorBox error={act.error} /></div>}
      </Modal>
    </div>
  )
}
