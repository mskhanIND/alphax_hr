import { useMutation, useQuery } from '@tanstack/react-query'
import { BookOpen, LifeBuoy, MessageCircle, Search, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { RequestForm } from '../components/RequestForm'
import { RequestThread } from '../components/RequestThread'
import { Badge, Button, Card, Empty, ErrorBox, Input, Modal, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

function Article({ name, onClose, onAsk }: { name: string; onClose: () => void; onAsk: () => void }) {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['help-article', name], queryFn: () => api.helpArticle(name) })
  const fb = useMutation({ mutationFn: (h: number) => api.helpFeedback(name, h) })
  const a = q.data
  return (
    <Modal open wide onClose={onClose} title={a ? ((lang === 'ar' && a.title_ar) || a.title) : ''}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : a && (
        <div className="flex flex-col gap-4">
          <div className="whitespace-pre-wrap text-sm leading-relaxed" dir={lang === 'ar' && a.body_ar ? 'rtl' : undefined}>{(lang === 'ar' && a.body_ar) || a.body}</div>
          {a.attachment && <a className="text-sm font-medium text-brand underline" href={a.attachment} target="_blank" rel="noreferrer">{t('Attachment')}</a>}
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-sm">
            {fb.isSuccess ? <span className="text-emerald-700">{t('Thanks for the feedback.')}</span> : (<>
              <span className="text-muted">{t('Was this helpful?')}</span>
              <Button size="sm" variant="secondary" onClick={() => fb.mutate(1)}><ThumbsUp className="size-4" />{t('Yes')}</Button>
              <Button size="sm" variant="secondary" onClick={() => { fb.mutate(0); onAsk() }}><ThumbsDown className="size-4" />{t('No, ask HR')}</Button>
            </>)}
          </div>
        </div>
      )}
    </Modal>
  )
}

export default function HelpCentre() {
  const { t, lang } = useI18n()
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [cat, setCat] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [ask, setAsk] = useState(false)
  const [thread, setThread] = useState<any>(null)
  useEffect(() => { const h = setTimeout(() => setDebounced(search), 300); return () => clearTimeout(h) }, [search])
  const q = useQuery({ queryKey: ['help', debounced, cat], queryFn: () => api.helpArticles(debounced || undefined, cat || undefined) })
  const mine = useQuery({ queryKey: ['my-requests'], queryFn: api.myAlphaxRequests })
  const questions = (mine.data ?? []).filter((r: any) => r.request_type === 'Ask HR')
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Help centre')} subtitle={t('Answers from HR. Still stuck? Ask HR privately.')}
        actions={<Button onClick={() => setAsk(true)}><MessageCircle className="size-4" />{t('Ask HR')}</Button>} />
      <div className="relative">
        <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <Input className="ps-9" placeholder={t('Search: leave, payslip, Iqama, overtime…')} value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      {!!q.data?.categories?.length && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={cat ? 'secondary' : 'primary'} onClick={() => setCat('')}>{t('All')}</Button>
          {q.data.categories.map((c: any) => <Button key={c.category} size="sm" variant={cat === c.category ? 'primary' : 'secondary'} onClick={() => setCat(c.category)}>{t(c.category)} · {c.count}</Button>)}
        </div>
      )}
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.articles?.length ? (
          <Empty title={t('No articles found')} icon={<BookOpen />}>{t('Ask HR and they will answer you directly.')}</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {q.data.articles.map((a: any) => (
              <li key={a.name}>
                <button type="button" className="w-full py-3 text-start hover:text-brand" onClick={() => setOpen(a.name)}>
                  <div className="flex items-center gap-2 font-medium">{(lang === 'ar' && a.title_ar) || a.title}{a.pinned ? <Badge tone="blue">{t('Pinned')}</Badge> : null}<Badge>{t(a.category)}</Badge></div>
                  <div className="line-clamp-2 text-sm text-muted">{(lang === 'ar' && a.excerpt_ar) || a.excerpt}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('My questions to HR')}>
        {!questions.length ? <p className="text-sm text-muted">{t('No questions yet.')}</p> : (
          <ul className="divide-y divide-line">
            {questions.map((r: any) => (
              <li key={r.name} className="flex flex-wrap items-center gap-3 py-2.5">
                <LifeBuoy className="size-4 text-brand" />
                <div className="min-w-0 flex-1"><div className="font-medium">{r.details?.subject || r.name}</div>
                  <div className="text-xs text-muted">{t(r.details?.topic || '')} · {fmtDate(r.creation, lang)}</div></div>
                <StatusBadge status={r.status} />
                <Button size="sm" variant="secondary" onClick={() => setThread(r)}><MessageCircle className="size-4" />{r.messages || t('Open')}</Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {open && <Article name={open} onClose={() => setOpen(null)} onAsk={() => { setOpen(null); setAsk(true) }} />}
      <RequestForm open={ask} initialType="Ask HR" category="Help" onClose={() => setAsk(false)} />
      {thread && <RequestThread name={thread.name} title={thread.details?.subject || thread.name} onClose={() => setThread(null)} />}
    </div>
  )
}
