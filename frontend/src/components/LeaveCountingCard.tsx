import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox, Field, Input, Modal, Select, Spinner, Textarea } from './ui'

const BLANK = { leave_type: '', count_mode: 'Calendar days', sandwich: 'Off', sandwich_holidays: 0, working_day_edges: 0,
  min_notice_days: 0, max_days_per_request: 0, emergency: 0, notes: '' }

const MODE_HINT: Record<string, string> = {
  'Calendar days': 'Every day between the dates counts, weekends and public holidays too.',
  'Working days only': 'Weekends and public holidays inside the leave are not counted.',
  'Skip public holidays': 'Public holidays are not counted; weekends are.',
  'Skip weekends': 'Weekends are not counted; public holidays are.',
}
const SANDWICH_HINT: Record<string, string> = {
  Off: 'Off days are never counted when the mode skips them.',
  'Inside one request': 'A weekend between two leave days of the same request is counted (e.g. Thursday to Sunday = 4 days).',
  'Also across requests': 'Also counted when the employee takes separate leaves right before and after the weekend.',
}

function Check({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

export default function LeaveCountingCard() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['countingRules'], queryFn: api.countingRules })
  const [edit, setEdit] = useState<any | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['countingRules'] })
  const save = useMutation({ mutationFn: () => api.saveCountingRule(edit), onSuccess: () => { setEdit(null); refresh() } })
  const del = useMutation({ mutationFn: (name: string) => api.deleteCountingRule(name), onSuccess: refresh })
  if (q.isLoading) return <Card title={t('How leave days are counted')}><Spinner /></Card>
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const used = new Set(d.rules.map((r: any) => r.leave_type))
  const set = (k: string, v: unknown) => setEdit({ ...edit, [k]: v })
  return (
    <Card title={t('How leave days are counted')}
      subtitle={t('Per leave type: weekends and public holidays inside a leave, the sandwich rule, notice and limits. Checked on every request.')}
      action={d.can_edit ? <Button size="sm" onClick={() => setEdit({ ...BLANK })}><Plus className="size-4" />{t('Add rule')}</Button> : undefined}>
      {del.error && <ErrorBox error={del.error} />}
      {d.rules.length === 0 ? (
        <p className="text-sm text-muted">{t('No counting rules yet. Leave types follow their own "include holidays" setting.')}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted"><tr>
              <th className="pb-2 text-start">{t('Leave type')}</th><th className="pb-2 text-start">{t('Counting')}</th>
              <th className="pb-2 text-start">{t('Sandwich rule')}</th><th className="pb-2 text-start">{t('Limits')}</th><th />
            </tr></thead>
            <tbody className="divide-y divide-line">
              {d.rules.map((r: any) => (
                <tr key={r.name} className="align-top">
                  <td className="py-2.5 pe-3 font-medium">{r.leave_type}{r.emergency ? <span className="ms-2 text-xs text-red-700">{t('Emergency')}</span> : null}</td>
                  <td className="py-2.5 pe-3">{t(r.count_mode)}</td>
                  <td className="py-2.5 pe-3">{t(r.sandwich)}{r.sandwich !== 'Off' && r.sandwich_holidays ? ` · ${t('holidays too')}` : ''}</td>
                  <td className="py-2.5 pe-3 text-xs text-muted">
                    {[r.working_day_edges && t('Start and end on working days'), r.min_notice_days && `${t('Notice')}: ${r.min_notice_days} ${t('days')}`,
                      r.max_days_per_request && `${t('Max')}: ${r.max_days_per_request} ${t('days')}`].filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td className="py-2.5 text-end whitespace-nowrap">
                    {d.can_edit && <>
                      <Button size="sm" variant="secondary" onClick={() => setEdit({ ...r })}>{t('Edit')}</Button>
                      <Button size="sm" variant="ghost" aria-label={t('Delete')} loading={del.isPending} onClick={() => del.mutate(r.name)}><Trash2 className="size-4" /></Button>
                    </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={t('Leave counting rule')}
        footer={<><Button variant="secondary" onClick={() => setEdit(null)}>{t('Cancel')}</Button>
          <Button loading={save.isPending} disabled={!edit?.leave_type} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
        {edit && (
          <div className="flex flex-col gap-3">
            <Field label={t('Leave type')}>
              <Select value={edit.leave_type} disabled={!!edit.name} onChange={(e) => set('leave_type', e.target.value)}>
                <option value="">{t('Choose…')}</option>
                {d.leave_types.filter((lt: any) => lt.name === edit.leave_type || !used.has(lt.name)).map((lt: any) =>
                  <option key={lt.name} value={lt.name}>{lt.name}</option>)}
              </Select>
            </Field>
            <Field label={t('Count')} hint={t(MODE_HINT[edit.count_mode] ?? '')}>
              <Select value={edit.count_mode} onChange={(e) => set('count_mode', e.target.value)}>
                {d.options.count_mode.map((o: string) => <option key={o} value={o}>{t(o)}</option>)}
              </Select>
            </Field>
            {edit.count_mode !== 'Calendar days' && <Field label={t('Sandwich rule')} hint={t(SANDWICH_HINT[edit.sandwich] ?? '')}>
              <Select value={edit.sandwich} onChange={(e) => set('sandwich', e.target.value)}>
                {d.options.sandwich.map((o: string) => <option key={o} value={o}>{t(o)}</option>)}
              </Select>
            </Field>}
            {edit.count_mode !== 'Calendar days' && edit.sandwich !== 'Off' && <Check label={t('Public holidays between leave days count too')} checked={!!edit.sandwich_holidays} onChange={(v) => set('sandwich_holidays', v ? 1 : 0)} />}
            <Check label={t('Must start and end on a working day')} checked={!!edit.working_day_edges} onChange={(v) => set('working_day_edges', v ? 1 : 0)} />
            <Check label={t('Emergency leave (no notice needed, HR and manager alerted at once)')} checked={!!edit.emergency} onChange={(v) => set('emergency', v ? 1 : 0)} />
            <div className="grid grid-cols-2 gap-3">
              <Field label={t('Notice (days before)')} hint={t('0 = none')}>
                <Input type="number" min={0} value={edit.min_notice_days ?? 0} disabled={!!edit.emergency} onChange={(e) => set('min_notice_days', Number(e.target.value) || 0)} />
              </Field>
              <Field label={t('Max counted days per request')} hint={t('0 = no limit')}>
                <Input type="number" min={0} value={edit.max_days_per_request ?? 0} onChange={(e) => set('max_days_per_request', Number(e.target.value) || 0)} />
              </Field>
            </div>
            <Field label={t('Notes for employees')}>
              <Textarea rows={2} value={edit.notes ?? ''} onChange={(e) => set('notes', e.target.value)} />
            </Field>
            {save.error && <ErrorBox error={save.error} />}
          </div>
        )}
      </Modal>
    </Card>
  )
}
