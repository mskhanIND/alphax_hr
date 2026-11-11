import { useQuery } from '@tanstack/react-query'
import { Phone, Users } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Avatar, Badge, Card, Empty, ErrorBox, PageHeader, Spinner, Stat, FilterNote } from '../components/ui'
import { api } from '../lib/api'
import { fmtTime } from '../lib/format'
import { useI18n } from '../lib/i18n'

const STATE: Record<string, { label: string; tone: string }> = {
  in: { label: 'Checked in', tone: 'green' }, out: { label: 'Checked out', tone: 'gray' },
  on_leave: { label: 'On leave', tone: 'blue' }, not_in: { label: 'Not checked in', tone: 'amber' },
}

export default function MyTeam() {
  const { t } = useI18n()
  const [show, setShow] = useState('')
  const pick = (k: string) => setShow((x: string) => (x === k ? '' : k))
  const navigate = useNavigate()
  const q = useQuery({ queryKey: ['my-team'], queryFn: api.myTeam, refetchInterval: 60_000 })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const { team, summary } = q.data
  const shown = team.filter((m: any) => !show || m.state === show)
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('My team')} subtitle={t('Who is in today')} />
      {!team.length ? <Card><Empty title={t('No team members')} icon={<Users />}>{t('People who report to you appear here.')}</Empty></Card> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('Checked in')} value={summary.in} tone="brand" onClick={() => pick('in')} active={show === 'in'} />
            <Stat label={t('Not checked in')} value={summary.not_in} tone="amber" onClick={() => pick('not_in')} active={show === 'not_in'} />
            <Stat label={t('On leave')} value={summary.on_leave} tone="blue" onClick={() => pick('on_leave')} active={show === 'on_leave'} />
            <Stat label={t('Leave requests waiting')} value={summary.pending_leave} tone="red" onClick={() => navigate('/approvals')} />
          </div>
          {show && <FilterNote label={t(STATE[show]?.label ?? show)} count={shown.length} onClear={() => setShow('')} />}
          <Card>
            <ul className="divide-y divide-line">
              {shown.map((m: any) => (
                <li key={m.name} className="flex items-center gap-3 py-3">
                  <Avatar name={m.employee_name} image={m.image} size={40} />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{m.employee_name}</div>
                    <div className="truncate text-xs text-muted">{m.designation}{m.first_in ? ` · ${t('In')} ${fmtTime(m.first_in)}` : ''}{m.leave_type ? ` · ${m.leave_type}` : ''}</div>
                  </div>
                  <Badge tone={STATE[m.state].tone}>{t(STATE[m.state].label)}</Badge>
                  {m.cell_number && <a href={`tel:${m.cell_number}`} className="rounded-lg p-2 text-brand hover:bg-surface" aria-label={t('Call')}><Phone className="size-4" /></a>}
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}
