import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, ClipboardCheck, LogOut, Timer } from 'lucide-react'
import { RequestForm } from './RequestForm'
import { useState } from 'react'
import { api } from '../lib/api'
import { fmtDate, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox, Field, Input, Modal, Select, StatusBadge, Textarea } from './ui'

function CorrectionForm({ onDone }: { onDone: () => void }) {
  const { t } = useI18n()
  const today = todayISO()
  const [f, setF] = useState({ from_date: today, to_date: today, reason: 'On Duty', explanation: '' })
  const m = useMutation({ mutationFn: () => api.requestAttendance(f), onSuccess: onDone })
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
      <Field label={t('Reason')}>
        <Select value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })}>
          <option value="On Duty">{t('Missed punch / on duty')}</option>
          <option value="Work From Home">{t('Work From Home')}</option>
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('From')}><Input type="date" required max={today} value={f.from_date} onChange={(e) => setF({ ...f, from_date: e.target.value, to_date: e.target.value > f.to_date ? e.target.value : f.to_date })} /></Field>
        <Field label={t('To')}><Input type="date" required min={f.from_date} max={today} value={f.to_date} onChange={(e) => setF({ ...f, to_date: e.target.value })} /></Field>
      </div>
      <Field label={t('What happened?')} hint={t('e.g. Forgot to punch out at 17:00; device was down; client visit.')}>
        <Textarea required maxLength={1000} value={f.explanation} onChange={(e) => setF({ ...f, explanation: e.target.value })} />
      </Field>
      {m.error && <ErrorBox error={m.error} />}
      <Button type="submit" loading={m.isPending}>{t('Send request')}</Button>
    </form>
  )
}

function ShiftForm({ onDone }: { onDone: () => void }) {
  const { t } = useI18n()
  const types = useQuery<any[]>({ queryKey: ['shiftTypes'], queryFn: api.shiftTypes })
  const today = todayISO()
  const [f, setF] = useState({ shift_type: '', from_date: today, to_date: '' })
  const m = useMutation({ mutationFn: () => api.requestShift({ ...f, to_date: f.to_date || undefined }), onSuccess: onDone })
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
      <Field label={t('Shift')}>
        <Select required value={f.shift_type} onChange={(e) => setF({ ...f, shift_type: e.target.value })}>
          <option value="">—</option>
          {(types.data ?? []).map((s) => <option key={s.name} value={s.name}>{s.name} ({String(s.start_time).slice(0, 5)}–{String(s.end_time).slice(0, 5)})</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('From')}><Input type="date" required value={f.from_date} onChange={(e) => setF({ ...f, from_date: e.target.value })} /></Field>
        <Field label={t('To')} hint={t('Blank = until changed')}><Input type="date" min={f.from_date} value={f.to_date} onChange={(e) => setF({ ...f, to_date: e.target.value })} /></Field>
      </div>
      {m.error && <ErrorBox error={m.error} />}
      <Button type="submit" loading={m.isPending}>{t('Send request')}</Button>
    </form>
  )
}

export function AttendanceRequests() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [open, setOpen] = useState<'correction' | 'shift' | null>(null)
  const [permit, setPermit] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const q = useQuery<any[]>({ queryKey: ['myRequests'], queryFn: api.myRequests })
  const done = () => { setOpen(null); setSent(true); qc.invalidateQueries({ queryKey: ['myRequests'] }) }
  return (
    <Card title={t('Requests')}
      action={<div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={() => { setSent(false); setOpen('correction') }}><ClipboardCheck className="size-4" />{t('Correct attendance')}</Button>
        <Button size="sm" variant="secondary" onClick={() => { setSent(false); setOpen('shift') }}><CalendarClock className="size-4" />{t('Change shift')}</Button>
        <Button size="sm" variant="secondary" onClick={() => setPermit('Late Arrival Permission')}><Timer className="size-4" />{t('Late arrival')}</Button>
        <Button size="sm" variant="secondary" onClick={() => setPermit('Early Exit Permission')}><LogOut className="size-4" />{t('Early exit')}</Button>
      </div>}>
      {sent && <p className="mb-2 text-sm text-emerald-700">{t('Request sent to your approver.')}</p>}
      {q.error ? <ErrorBox error={q.error} /> : !(q.data ?? []).length ? <p className="text-sm text-muted">{t('No requests yet.')}</p> : (
        <ul className="divide-y divide-line text-sm">
          {(q.data ?? []).slice(0, 8).map((r) => (
            <li key={r.name} className="flex items-center justify-between gap-3 py-2">
              <span>
                <span className="font-medium">{r.type === 'Shift Request' ? `${t('Shift')}: ${r.shift_type}` : r.type === 'Permission' ? `${t(r.request_type)}${r.time ? ` · ${r.time}` : ''}` : t(r.reason === 'On Duty' ? 'Missed punch / on duty' : r.reason)}</span>
                <span className="block text-xs text-muted">{fmtDate(r.from_date, lang)}{r.to_date && r.to_date !== r.from_date ? ` → ${fmtDate(r.to_date, lang)}` : ''}</span>
              </span>
              <StatusBadge status={r.status === 'Draft' ? 'Open' : r.status} />
            </li>
          ))}
        </ul>
      )}
      <Modal open={open === 'correction'} onClose={() => setOpen(null)} title={t('Correct attendance')}><CorrectionForm onDone={done} /></Modal>
      <RequestForm open={!!permit} initialType={permit ?? undefined} category="Attendance" onClose={() => setPermit(null)} />
      <Modal open={open === 'shift'} onClose={() => setOpen(null)} title={t('Change shift')}><ShiftForm onDone={done} /></Modal>
    </Card>
  )
}
