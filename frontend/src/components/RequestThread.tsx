import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Send } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtDate, fmtTime } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Button, ErrorBox, Modal, Spinner, Textarea } from './ui'

/** Messages between the employee and HR (or the approver) on one request. */
export function RequestThread({ name, title, onClose }: { name: string; title: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['request-thread', name], queryFn: () => api.requestMessages(name), refetchInterval: 30_000 })
  const [text, setText] = useState('')
  const m = useMutation({ mutationFn: () => api.postRequestMessage(name, text), onSuccess: (d) => {
    qc.setQueryData(['request-thread', name], d); setText('')
    for (const k of ['my-requests', 'requests']) qc.invalidateQueries({ queryKey: [k] })
  } })
  return (
    <Modal open onClose={onClose} title={title}
      footer={<div className="flex w-full gap-2">
        <Textarea rows={2} className="flex-1" placeholder={t('Write a message…')} value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim()) m.mutate() }} />
        <Button disabled={!text.trim()} loading={m.isPending} onClick={() => m.mutate()} aria-label={t('Send')}><Send className="size-4 flip-rtl" /></Button>
      </div>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? (
        <p className="py-6 text-center text-sm text-muted">{t('No messages yet. Ask a question or add details here.')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {q.data.map((msg, i) => (
            <li key={i} className={clsx('max-w-[85%] rounded-2xl px-3 py-2 text-sm', msg.mine ? 'self-end bg-brand text-white' : 'self-start bg-surface')}>
              <div className={clsx('mb-0.5 text-[11px]', msg.mine ? 'text-white/70' : 'text-muted')}>{msg.by} · {fmtDate(msg.at, lang)} {fmtTime(msg.at)}</div>
              <div className="whitespace-pre-wrap">{msg.text}</div>
            </li>
          ))}
        </ul>
      )}
      {m.error && <div className="mt-2"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}
