import { useQuery } from '@tanstack/react-query'
import { Check, Clock, X } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDateTime } from '../lib/format'
import { useI18n } from '../lib/i18n'

/** The approval levels of one request or leave, when an approval policy with levels applies to it. */
export function ApprovalChain({ doctype, name }: { doctype: string; name: string }) {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['approval-chain', doctype, name], queryFn: () => api.approvalChain(doctype, name) })
  if (!q.data?.levels?.length) return null
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs" aria-label={t('Approval levels')}>
      {q.data.levels.map((l: any, i: number) => {
        const done = l.state === 'Approved'
        const bad = l.state.startsWith('Rejected')
        const wait = l.state === 'Waiting'
        return (
          <li key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted">→</span>}
            <span title={[l.approver_name, l.by_name && `${t(l.state)}: ${l.by_name}`, l.at && fmtDateTime(l.at, lang), l.comment, l.carried ? t('Kept from the earlier request') : '']
              .filter(Boolean).join('\n')}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${done ? 'bg-brand-50 text-brand' : bad ? 'bg-red-50 text-red-700' : wait ? 'bg-amber-50 text-amber-900' : 'bg-gray-100 text-muted'}`}>
              {done ? <Check className="size-3" /> : bad ? <X className="size-3" /> : wait ? <Clock className="size-3" /> : null}
              {l.label}{wait ? ` · ${l.approver_name}` : ''}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
