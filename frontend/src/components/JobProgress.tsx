import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { type ReactNode, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

const STUCK_SECONDS = 120

const clock = (s: number) => (s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m` : s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`)

/** Follows a long job (alphax_hr.progress): step, how far, elapsed time, and a warning when nothing moves. It keeps
 * running on the server if the window is closed; opening it again shows the same job. */
export function JobProgress({ job, onDone, children }: { job: string; onDone?: (result: any) => void; children?: (result: any) => ReactNode }) {
  const { t } = useI18n()
  const [, tick] = useState(0)
  const q = useQuery<any>({ queryKey: ['job', job], queryFn: async () => ({ ...(await api.jobStatus(job)), _at: Date.now() }),
    refetchInterval: (x) => (x.state.data && ['queued', 'running'].includes(x.state.data.status) ? 2000 : false) })
  const d = q.data
  const live = d && ['queued', 'running'].includes(d.status)
  useEffect(() => { if (!live) return; const h = setInterval(() => tick((x) => x + 1), 1000); return () => clearInterval(h) }, [live])
  useEffect(() => { if (d?.status === 'done') onDone?.(d.result) }, [d?.status]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return null
  const pct = d.total ? Math.min(100, Math.round((100 * (d.done ?? 0)) / d.total)) : null
  const since = live ? Math.round((Date.now() - (d._at ?? Date.now())) / 1000) : 0  // seconds since the server answered
  const elapsed = (d.elapsed ?? 0) + since
  const quiet = live ? (d.quiet ?? 0) + since : 0
  return (
    <div className={clsx('rounded-xl border p-3 text-sm', d.status === 'failed' ? 'border-red-200 bg-red-50' : d.status === 'done' ? 'border-emerald-200 bg-emerald-50' : 'border-line bg-surface')}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={clsx('size-2.5 rounded-full', live ? 'animate-pulse bg-brand' : d.status === 'done' ? 'bg-emerald-500' : 'bg-red-500')} />
        <b className="flex-1">{d.title}</b>
        <span className="text-xs text-muted">{t(d.status === 'queued' ? 'Waiting to start' : d.status === 'running' ? 'Working' : d.status === 'done' ? 'Finished' : 'Failed')} · {clock(elapsed)}</span>
      </div>
      {live && <>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
          <div className={clsx('h-full rounded-full bg-brand transition-all', pct === null && 'w-1/3 animate-pulse')} style={pct !== null ? { width: `${Math.max(3, pct)}%` } : undefined} />
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted">
          {d.step && <span>{d.step}</span>}
          {d.total ? <span>{d.done ?? 0} / {d.total} ({pct}%)</span> : d.done ? <span>{d.done}</span> : null}
        </div>
        {d.status === 'queued' && elapsed > 60 && <p className="mt-2 text-xs text-amber-800">{t('Not started after a minute: the background workers may be stopped. The server administrator can check them with "bench doctor" and start them with "bench restart".')}</p>}
        {d.status === 'running' && quiet > STUCK_SECONDS && <p className="mt-2 text-xs text-amber-800">{t('No progress for')} {clock(quiet)}. {t('A large step can take a while; if this stays, the job may have stopped. You can start it again: nothing is done twice.')}</p>}
        <p className="mt-1 text-[11px] text-muted">{t('You can close this window; the work continues and shows here when you come back.')}</p>
      </>}
      {d.status === 'failed' && <p className="mt-1 text-red-800">{d.error}</p>}
      {d.status === 'done' && children?.(d.result)}
    </div>
  )
}
