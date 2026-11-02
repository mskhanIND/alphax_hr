import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { FieldInput } from '../components/FieldInput'
import { LinkInput } from '../components/LinkInput'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Input, PageHeader, Select, Spinner, statusTone } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const SECTION_TITLES: Record<string, string> = {
  personal: 'Personal', job: 'Job', attendance_leave: 'Attendance & Leave', contact: 'Contact', saudi: 'Saudi compliance', exit: 'Exit',
  company_required: 'Required by your company',
}
const LINKS: Record<string, string> = {
  company: 'Company', department: 'Department', designation: 'Designation', branch: 'Branch', employment_type: 'Employment Type',
  grade: 'Employee Grade', reports_to: 'Employee', holiday_list: 'Holiday List', default_shift: 'Shift Type', gender: 'Gender',
  leave_approver: 'User', expense_approver: 'User', shift_request_approver: 'User', user_id: 'User',
}
const DATE = /date|_upto|expiry|joining|birth/
const SELECTS: Record<string, string[]> = {
  marital_status: ['', 'Single', 'Married', 'Divorced', 'Widowed'],
  blood_group: ['', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
  salutation: ['', 'Mr', 'Ms', 'Mrs', 'Dr'],
  prefered_contact_email: ['', 'Company Email', 'Personal Email', 'User ID'],
}

function Value({ field, value, lang, t }: { field: string; value: any; lang: string; t: (s: string) => string }) {
  if (value === null || value === undefined || value === '') return <span className="text-muted">—</span>
  if (field === 'alphax_is_saudi') return <>{value ? t('Saudi') : t('Non-Saudi')}</>
  if (DATE.test(field)) return <>{fmtDate(String(value), lang)}</>
  return <>{String(value)}</>
}

function Editor({ field, value, onChange, spec }: { field: string; value: any; onChange: (v: any) => void; spec?: any }) {
  if (spec && spec.fieldtype !== 'Data' && !LINKS[field] && !SELECTS[field]) return <FieldInput spec={spec} value={value} onChange={onChange} />
  if (field === 'alphax_is_saudi') return <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!value} onChange={(e) => onChange(e.target.checked ? 1 : 0)} />
  if (LINKS[field]) return <LinkInput doctype={LINKS[field]} value={value ?? ''} onChange={onChange} />
  if (SELECTS[field]) return <Select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>{SELECTS[field].map((o) => <option key={o} value={o}>{o || '—'}</option>)}</Select>
  if (DATE.test(field)) return <Input type="date" value={value ? String(value).slice(0, 10) : ''} onChange={(e) => onChange(e.target.value || null)} />
  return <Input value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
}

export default function EmployeeDetail() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['employee', id], queryFn: () => api.employee(id) })
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, any>>({})
  const save = useMutation({
    mutationFn: () => api.updateEmployee(id, draft, q.data.modified),
    onSuccess: (d) => { qc.setQueryData(['employee', id], d); setEditing(null); setDraft({}) },
  })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const e = q.data
  return (
    <div>
      <Link to="/people" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{t('People')}</Link>
      <PageHeader title={e.employee_name} subtitle={e.name} />
      {e.missing_required?.length > 0 && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{t('Saving this employee needs these mandatory fields first')}: {e.missing_required.join(', ')}</span>
        </div>
      )}
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5">
          <Card>
            <div className="flex items-center gap-4">
              <Avatar name={e.employee_name} image={e.image} size={64} />
              <div>
                <div className="font-semibold">{e.sections.job.designation ?? '—'}</div>
                <div className="text-sm text-muted">{e.sections.job.department ?? '—'}</div>
                <div className="mt-1"><Badge tone={statusTone(e.sections.job.status)}>{t(e.sections.job.status)}</Badge></div>
              </div>
            </div>
          </Card>
          <Card title={t('Documents')}>
            <ul className="divide-y divide-line text-sm">
              {Object.entries(e.documents).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between py-2">
                  <span>{t(k === 'work_permit' ? 'Work permit' : k.charAt(0).toUpperCase() + k.slice(1))}</span>
                  <Badge tone={statusTone(String(v))}>{t(String(v))}</Badge>
                </li>
              ))}
            </ul>
          </Card>
          {e.issues.length > 0 && (
            <Card title={t('Data issues')}>
              <ul className="flex flex-col gap-2 text-sm">
                {e.issues.map((i: string) => <li key={i} className="flex items-center gap-2 text-amber-800"><AlertTriangle className="size-4 shrink-0" />{t(i)}</li>)}
              </ul>
            </Card>
          )}
        </div>
        <div className="flex flex-col gap-5 lg:col-span-2">
          {Object.entries(e.sections).map(([key, fields]: [string, any]) => {
            const isEditing = editing === key
            return (
              <Card key={key} title={t(SECTION_TITLES[key] ?? key)}
                action={e.can_write && !isEditing ? <Button size="sm" variant="ghost" onClick={() => { setEditing(key); setDraft({}) }}><Pencil className="size-4" />{t('Edit')}</Button> : undefined}>
                <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  {Object.entries(fields).map(([f, v]) => (
                    isEditing && f !== 'status' ? (
                      <Field key={f} label={e.labels[f] ?? f}><Editor field={f} spec={e.fields?.[f]} value={f in draft ? draft[f] : v} onChange={(nv) => setDraft({ ...draft, [f]: nv })} /></Field>
                    ) : (
                      <div key={f} className="text-sm"><div className="text-muted">{e.labels[f] ?? f}</div><div className="font-medium"><Value field={f} value={v} lang={lang} t={t} /></div></div>
                    )
                  ))}
                </div>
                {isEditing && (
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button loading={save.isPending} disabled={!Object.keys(draft).length} onClick={() => save.mutate()}>{t('Save')}</Button>
                    <Button variant="secondary" onClick={() => { setEditing(null); setDraft({}); save.reset() }}>{t('Cancel')}</Button>
                    {save.error && <div className="w-full"><ErrorBox error={save.error} onRetry={() => q.refetch()} /></div>}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
