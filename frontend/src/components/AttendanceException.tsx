import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Badge, Button, Card, ErrorBox, Field, Input, Select, Spinner } from './ui'

/** Profile: check-in / attendance rules for this employee, with an exception of their own. */
export function AttendanceException({ employee, canWrite }: { employee: string; canWrite: boolean }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['att-exception', employee], queryFn: () => api.attendanceException(employee) })
  const [edit, setEdit] = useState(false)
  const [draft, setDraft] = useState<Record<string, any>>({})
  useEffect(() => { if (q.data) setDraft(q.data.rules) }, [q.data])
  const done = (d: any) => { qc.setQueryData(['att-exception', employee], d); setEdit(false) }
  const save = useMutation({ mutationFn: () => api.saveAttendanceException(employee, draft), onSuccess: done })
  const remove = useMutation({ mutationFn: () => api.removeAttendanceException(employee), onSuccess: done })
  if (q.isLoading) return <Card title={t('Check-in & attendance rules')}><Spinner /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
  const show = (f: any) => {
    const v = d.rules[f.fieldname]
    if (f.fieldtype === 'Check') return v ? t('Yes') : t('No')
    if (v === null || v === undefined || v === '') {
      if (f.fieldname === 'checkin_location_rule') return `${t(d.defaults.checkin_location_rule)} (${t('company setting')})`
      if (f.fieldname === 'min_punch_gap') return `${d.defaults.min_punch_gap} (${t('company setting')})`
      return '—'
    }
    return t(String(v))
  }
  return (
    <Card title={t('Check-in & attendance rules')}
      subtitle={d.own ? t('This employee has an exception of their own.') : d.source ? `${t('From policy')}: ${d.source}` : t('Company settings apply.')}
      action={canWrite && !edit ? <Button size="sm" variant="ghost" onClick={() => setEdit(true)}>{d.own ? t('Edit exception') : t('Give an exception')}</Button> : undefined}>
      {!edit ? (
        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          {d.fields.map((f: any) => <div key={f.fieldname}><dt className="text-xs text-muted">{f.label}</dt><dd>{show(f)}</dd></div>)}
          {d.own && <div><Badge tone="amber">{t('Exception')}</Badge></div>}
        </dl>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {d.fields.map((f: any) => (
            <Field key={f.fieldname} label={f.label}>
              {f.fieldtype === 'Check'
                ? <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!draft[f.fieldname]} onChange={(e) => setDraft({ ...draft, [f.fieldname]: e.target.checked ? 1 : 0 })} />
                : f.fieldtype === 'Select'
                  ? <Select value={draft[f.fieldname] ?? ''} onChange={(e) => setDraft({ ...draft, [f.fieldname]: e.target.value })}>
                      {f.options.map((o: string) => <option key={o} value={o}>{o ? t(o) : t('Company setting')}</option>)}</Select>
                  : <Input type="number" min={0} placeholder={t('Blank = default')} value={draft[f.fieldname] ?? ''} onChange={(e) => setDraft({ ...draft, [f.fieldname]: e.target.value })} />}
            </Field>
          ))}
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button>
            <Button variant="secondary" onClick={() => setEdit(false)}>{t('Cancel')}</Button>
            {d.own && <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>{t('Remove exception')}</Button>}
          </div>
          {(save.error || remove.error) && <div className="sm:col-span-2"><ErrorBox error={save.error || remove.error} /></div>}
        </div>
      )}
    </Card>
  )
}
