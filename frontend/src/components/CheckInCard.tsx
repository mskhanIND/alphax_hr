import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LogIn, LogOut, MapPin } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtTime } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox } from './ui'

function position(): Promise<GeolocationPosition | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null)
    navigator.geolocation.getCurrentPosition(resolve, () => resolve(null), { timeout: 8000, maximumAge: 60_000 })
  })
}

export function CheckInCard() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const today = useQuery<any>({ queryKey: ['today'], queryFn: api.todayStatus })
  const [err, setErr] = useState<unknown>(null)
  const m = useMutation({
    mutationFn: async (type: 'IN' | 'OUT') => {
      const pos = await position()
      if (!pos && d?.location_rule && d.location_rule !== 'Anywhere') throw new Error(t('Allow location access for this app, then try again.'))
      return api.checkIn(type, pos?.coords.latitude, pos?.coords.longitude)
    },
    onSuccess: (data) => { setErr(null); qc.setQueryData(['today'], data) },
    onError: setErr,
  })
  const d = today.data
  const firstIn = d?.logs?.find((l: any) => l.log_type === 'IN')
  const next: 'IN' | 'OUT' = d?.next_action ?? 'IN'
  return (
    <Card title={t('Today')} subtitle={d?.shift ? `${t('Shift')}: ${d.shift}` : undefined}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-3xl font-semibold tabular-nums">{firstIn ? fmtTime(firstIn.time) : '--:--'}</div>
          <div className="text-sm text-muted">{firstIn ? t('Checked in at') : t('Not checked in yet')}</div>
          {!!d?.logs?.length && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {d.logs.map((l: any) => (
                <span key={l.name} className={`rounded-md px-2 py-0.5 text-xs tabular-nums ${l.alphax_outside ? 'bg-amber-50 text-amber-800' : 'bg-surface text-muted'}`}
                  title={l.alphax_location ?? undefined}>{l.log_type} {fmtTime(l.time)}{l.alphax_location ? ` · ${l.alphax_location}` : ''}</span>
              ))}
            </div>
          )}
        </div>
        <Button size="md" className="h-12 px-6 text-base" loading={m.isPending} onClick={() => m.mutate(next)}>
          {next === 'IN' ? <LogIn className="size-5 flip-rtl" /> : <LogOut className="size-5 flip-rtl" />}
          {next === 'IN' ? t('Check in') : t('Check out')}
        </Button>
      </div>
      {d?.location_rule === 'Inside a work location' && <p className="mt-3 flex items-center gap-1.5 text-xs text-muted"><MapPin className="size-3.5" />{t('Check in from your work location.')}</p>}
      {!!err && <div className="mt-3"><ErrorBox error={err} /></div>}
    </Card>
  )
}
