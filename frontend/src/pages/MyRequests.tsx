import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, MessageCircle, Plus } from 'lucide-react'
import { useState } from 'react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { RequestForm, typeTitle } from '../components/RequestForm'
import { RequestThread } from '../components/RequestThread'
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

export function detailsText(d: Record<string, any>) {
  if (d?.changes) return Object.values(d.changes).map((c: any) => `${c.label}: ${c.from || '—'} → ${c.to}`).join(' · ')
  return Object.entries(d ?? {}).filter(([k]) => k !== 'short_notice').map(([, v]) => String(v)).join(' · ')
}

export default function MyRequests() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [trail, setTrail] = useState<string | null>(null)
  const [thread, setThread] = useState<any>(null)
  const q = useQuery({ queryKey: ['my-requests'], queryFn: api.myAlphaxRequests })
  const types = useQuery({ queryKey: ['request-types'], queryFn: () => api.requestTypes() })
  const cancel = useMutation({ mutationFn: api.cancelRequest, onSuccess: () => qc.invalidateQueries({ queryKey: ['my-requests'] }) })
  const typeOf = (n: string) => types.data?.find((x) => x.name === n)
  return (
    <div>
      <PageHeader title={t('My Requests')} subtitle={t('Letters, government services, advances, travel, assets and more')}
        actions={<Button onClick={() => setOpen(true)}><Plus className="size-4" />{t('New request')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? (
          <Empty title={t('No requests yet')} icon={<FileText />}>{t('Raise a request and track it here until it is done.')}</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {q.data.map((r: any) => (
              <li key={r.name} className="flex flex-wrap items-center gap-3 py-3">
                <button type="button" className="min-w-0 flex-1 text-start" onClick={() => setTrail(r.name)} title={t('Show activity')}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{typeTitle(typeOf(r.request_type), lang, r.request_type)}</span>
                    <StatusBadge status={r.status} />
                    {r.overdue && <Badge tone="red">{t('Overdue')}</Badge>}
                  </div>
                  <div className="truncate text-sm text-muted">{r.name} · {fmtDate(r.creation, lang)}{detailsText(r.details) ? ` · ${detailsText(r.details)}` : ''}</div>
                  {r.details?.short_notice && <div className="text-xs text-amber-800">{r.details.short_notice}</div>}
                </button>
                <Button size="sm" variant="secondary" onClick={() => setThread(r)}><MessageCircle className="size-4" />{r.messages ? r.messages : t('Message HR')}</Button>
                {r.letter && <a className="text-sm font-medium text-brand underline" href={r.letter} target="_blank" rel="noreferrer">{t('Download letter')}</a>}
                {['Pending Manager', 'Pending HR'].includes(r.status) && (
                  <Button size="sm" variant="secondary" loading={cancel.isPending && cancel.variables === r.name} onClick={() => cancel.mutate(r.name)}>{t('Withdraw')}</Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {cancel.error && <ErrorBox error={cancel.error} />}
      </Card>
      <RequestForm open={open} onClose={() => setOpen(false)} />
      {trail && <ActivityDrawer doctype="AlphaX Request" name={trail} onClose={() => setTrail(null)} />}
      {thread && <RequestThread name={thread.name} title={`${typeTitle(typeOf(thread.request_type), lang, thread.request_type)} · ${thread.name}`} onClose={() => setThread(null)} />}
    </div>
  )
}
