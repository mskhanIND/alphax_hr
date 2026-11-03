import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'

const ROUTES: Record<string, string> = {
  'Leave Application': '/approvals', 'AlphaX Request': '/me/requests', 'AlphaX Penalty': '/me/warnings',
  'AlphaX Announcement': '/', 'AlphaX Leave Plan': '/approvals', 'Employee': '/me/attendance',
}

export default function NotificationBell() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const q = useQuery({ queryKey: ['myNotifications'], queryFn: api.myNotifications, refetchInterval: 60_000 })
  const read = useMutation({ mutationFn: (name?: string) => api.markNotificationsRead(name), onSuccess: (d) => qc.setQueryData(['myNotifications'], d) })
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const unread = q.data?.unread ?? 0
  const go = (n: any) => {
    if (!n.read) read.mutate(n.name)
    setOpen(false)
    const route = ROUTES[n.document_type]
    if (route) nav(route)
    else if (n.document_type && n.document_name) nav(recordPath(n.document_type, n.document_name))
  }
  return (
    <div className="relative" ref={box}>
      <button className="relative rounded-lg p-2 text-muted hover:bg-surface" aria-label={t('Notifications')} title={t('Notifications')}
        data-testid="bell" onClick={() => setOpen(!open)}>
        <Bell className="size-5" />
        {unread > 0 && <span className="absolute -end-0.5 -top-0.5 min-w-4 rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-4 text-white">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="fixed inset-x-2 top-16 z-40 overflow-hidden rounded-2xl border border-line bg-white shadow-xl sm:absolute sm:inset-x-auto sm:end-0 sm:top-11 sm:w-[22rem]">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="text-sm font-semibold">{t('Notifications')}</span>
            {unread > 0 && <button className="flex items-center gap-1 text-xs text-brand-700 hover:underline" onClick={() => read.mutate(undefined)}>
              <CheckCheck className="size-3.5" />{t('Mark all read')}</button>}
          </div>
          <div className="max-h-[70vh] overflow-y-auto sm:max-h-96" data-testid="bell-list">
            {(q.data?.items ?? []).length === 0 && <p className="p-4 text-sm text-muted">{t('No notifications yet.')}</p>}
            {(q.data?.items ?? []).map((n: any) => (
              <button key={n.name} onClick={() => go(n)}
                className={`block w-full border-b border-line px-4 py-2.5 text-start text-sm last:border-0 hover:bg-surface ${n.read ? '' : 'bg-brand-50/60'}`}>
                <div className={n.read ? '' : 'font-medium'}>{n.subject}</div>
                {n.email_content && <div className="line-clamp-2 text-xs text-muted">{n.email_content}</div>}
                <div className="mt-0.5 text-[11px] text-muted">{fmtDate(n.creation)} {String(n.creation).slice(11, 16)}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
