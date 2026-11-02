import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { CheckCircle2, Clock, ExternalLink, FilePlus2, MessageSquare, Paperclip, PencilLine, Send, X, XCircle } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Badge, ErrorBox, Spinner, statusTone } from './ui'

function when(at: string, lang: string) {
  return `${fmtDate(at, lang)} · ${at.slice(11, 16)}`
}

function valueText(v: any, t: (s: string) => string) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number' && [0, 1, 2].includes(v)) return t({ 0: 'Draft', 1: 'Submitted', 2: 'Cancelled' }[v]!)
  return t(String(v))
}

function icon(kind: string, e: any): ReactNode {
  if (kind === 'created') return <FilePlus2 className="size-4" />
  if (kind === 'comment') return <MessageSquare className="size-4" />
  if (kind.startsWith('attachment')) return <Paperclip className="size-4" />
  if (kind === 'submitted' || kind === 'workflow_action') return <Send className="size-4" />
  if (kind === 'cancelled') return <XCircle className="size-4" />
  if (kind === 'changed') {
    const to = String(e.changes?.find((c: any) => ['status', 'workflow_state', 'approval_status'].includes(c.field))?.to ?? '')
    if (/approv/i.test(to)) return <CheckCircle2 className="size-4" />
    if (/reject|cancel/i.test(to)) return <XCircle className="size-4" />
  }
  return <PencilLine className="size-4" />
}

function tone(kind: string, e: any) {
  const to = String(e.changes?.find((c: any) => ['status', 'workflow_state', 'approval_status'].includes(c.field))?.to ?? '')
  if (/approv/i.test(to) || kind === 'submitted') return 'bg-emerald-100 text-emerald-700'
  if (/reject|cancel/i.test(to) || kind === 'cancelled') return 'bg-red-100 text-red-700'
  if (kind === 'comment') return 'bg-blue-100 text-blue-700'
  return 'bg-surface text-muted'
}

/** Side panel: the complete approval chain of one request, with a link to the record. */
export function ActivityDrawer({ doctype, name, onClose }: { doctype: string; name: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['activity', doctype, name], queryFn: () => api.trail(doctype, name) })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const d = q.data
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onMouseDown={onClose}>
      <aside role="dialog" aria-label={t('Activity')} className="h-full w-full max-w-lg overflow-y-auto bg-white shadow-xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white px-5 py-3">
          <span className="font-semibold">{t('Activity')}</span>
          <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-surface" aria-label={t('Close')}><X className="size-5" /></button>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <div className="p-5"><ErrorBox error={q.error} /></div> : (
          <div className="flex flex-col gap-5 p-5">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-semibold">{d.title}</span>
                <Badge tone="blue">{t(d.doctype)}</Badge>
                <Badge tone={statusTone(d.status)}>{t(d.status)}</Badge>
              </div>
              <div className="text-sm text-muted">{d.name}</div>
            </div>
            {d.pending_with.length > 0 && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <Clock className="size-4 shrink-0" />
                {t('Waiting for')}: {d.pending_with.map((p: any) => p.name ?? p.user ?? t(p.role)).join(', ')}
              </div>
            )}
            <ol className="relative flex flex-col gap-4 border-s-2 border-line ps-6">
              {d.events.map((e: any, i: number) => (
                <li key={i} className="relative">
                  <span className={clsx('absolute -start-[37px] grid size-7 place-items-center rounded-full ring-4 ring-white', tone(e.kind, e))}>{icon(e.kind, e)}</span>
                  <div className="text-sm">
                    <span className="font-medium">{e.name ?? e.user ?? t('System')}</span>{' '}
                    <span className="text-muted">
                      {e.kind === 'created' ? t('created the request')
                        : e.kind === 'comment' ? t('commented')
                        : e.kind === 'workflow_action' ? `${t('moved it to')} ${t(e.text)}`
                        : e.kind === 'changed' ? t('updated')
                        : e.kind === 'deleted' ? t('deleted it')
                        : t(e.kind.replace(/_/g, ' '))}
                    </span>
                  </div>
                  <div className="text-xs text-muted">{when(e.at, lang)}</div>
                  {e.kind === 'changed' && (
                    <ul className="mt-1 space-y-0.5 text-sm">
                      {e.changes.map((c: any, j: number) => (
                        <li key={j}><span className="text-muted">{c.label}:</span> <s className="text-muted">{valueText(c.from, t)}</s> → <b>{valueText(c.to, t)}</b></li>
                      ))}
                    </ul>
                  )}
                  {e.text && e.kind !== 'workflow_action' && <p className="mt-1 rounded-lg bg-surface px-3 py-2 text-sm">{e.text}</p>}
                </li>
              ))}
            </ol>
            {d.files.length > 0 && (
              <div>
                <div className="mb-2 text-sm font-medium">{t('Attachments')}</div>
                <ul className="flex flex-col gap-1 text-sm">
                  {d.files.map((f: any) => (
                    <li key={f.file_url}><a href={f.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-brand hover:underline"><Paperclip className="size-4" />{f.file_name}</a></li>
                  ))}
                </ul>
              </div>
            )}
            <a href={d.desk_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 self-start rounded-xl border border-line px-4 py-2 text-sm font-medium hover:bg-surface">
              <ExternalLink className="size-4" />{t('Open record')}
            </a>
          </div>
        )}
      </aside>
    </div>
  )
}
