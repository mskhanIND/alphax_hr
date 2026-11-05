import { AttendanceException } from '../components/AttendanceException'
import { BankSelect } from '../components/BankSelect'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Camera, ChevronDown, ChevronsDownUp, ChevronsUpDown, History, Pencil, Printer, FileText } from 'lucide-react'
import { ActivityDrawer } from '../components/ActivityDrawer'
import { LeaveLedger } from '../components/LeaveLedger'
import { SalaryCard } from '../components/SalaryCard'
import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { FieldInput } from '../components/FieldInput'
import { LinkInput } from '../components/LinkInput'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, statusTone } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const SECTION_TITLES: Record<string, string> = {
  personal: 'Personal', job: 'Organization & role', attendance_leave: 'Attendance & Leave', contact: 'Contact', saudi: 'Saudi compliance', exit: 'Exit',
  company_required: 'Required by your company', bank: 'Bank',
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
  if (field === 'alphax_annual_leave_days' && !Number(value)) return <span className="text-muted">{t('Company policy')}</span>
  if (value === null || value === undefined || value === '') return <span className="text-muted">—</span>
  if (field === 'alphax_is_saudi') return <>{value ? t('Saudi') : t('Non-Saudi')}</>
  if (DATE.test(field)) return <>{fmtDate(String(value), lang)}</>
  return <>{String(value)}</>
}

function Editor({ field, value, onChange, spec }: { field: string; value: any; onChange: (v: any) => void; spec?: any }) {
  if (field === 'bank_name') return <BankSelect value={value ?? ''} onChange={onChange} />
  if (spec && spec.fieldtype !== 'Data' && !LINKS[field] && !SELECTS[field]) return <FieldInput spec={spec} value={value} onChange={onChange} />
  if (field === 'alphax_is_saudi') return <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!value} onChange={(e) => onChange(e.target.checked ? 1 : 0)} />
  if (LINKS[field]) return <LinkInput doctype={LINKS[field]} value={value ?? ''} onChange={onChange} />
  if (SELECTS[field]) return <Select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>{SELECTS[field].map((o) => <option key={o} value={o}>{o || '—'}</option>)}</Select>
  if (DATE.test(field)) return <Input type="date" value={value ? String(value).slice(0, 10) : ''} onChange={(e) => onChange(e.target.value || null)} />
  return <Input value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
}

// Fields that only apply to non-Saudis (Iqama holders); hidden for Saudi nationals.
const NON_SAUDI_ONLY = new Set(['alphax_counts_as_saudi', 'alphax_iqama_expiry', 'alphax_border_number', 'alphax_work_permit_expiry', 'passport_number', 'valid_upto'])
const COLLAPSE_KEY = 'alphax-profile-collapsed'

function loadCollapsed(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(COLLAPSE_KEY) ?? '[]')) } catch { return new Set() }
}

export default function EmployeeDetail() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['employee', id], queryFn: () => api.employee(id) })
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, any>>({})
  const [params] = useSearchParams()
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed)
  const saveCollapsed = (next: Set<string>) => {
    setCollapsed(next)
    try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...next])) } catch { /* storage blocked */ }
  }
  const photo = useMutation({
    mutationFn: async (file: File) => {
      const f: any = await uploadFile('Employee', id, file, false)
      return api.setPhoto(id, f.file_url)
    },
    onSuccess: (d) => qc.setQueryData(['employee', id], d),
  })
  const [popup, setPopup] = useState(false)
  const [showActivity, setShowActivity] = useState(false)
  const seenKey = `alphax-missing-${id}`
  useEffect(() => {
    // Pop the missing mandatory fields once per employee per browser session.
    if (!q.data?.missing_fields?.length || !q.data.can_write) return
    try { if (sessionStorage.getItem(seenKey)) return; sessionStorage.setItem(seenKey, '1') } catch { /* storage blocked */ }
    setPopup(true)
  }, [q.data, seenKey])
  useEffect(() => {
    if (params.get('print') && q.data) setTimeout(() => window.print(), 300)
  }, [params, q.data])
  const [fill, setFill] = useState<Record<string, any>>({})
  const fillAll = useMutation({
    mutationFn: () => api.updateEmployee(id, fill, q.data.modified),
    onSuccess: (d: any) => { qc.setQueryData(['employee', id], d); setFill({}); if (!d.missing_fields?.length) setPopup(false) },
    onError: (err: any) => { if (/changed this employee|TimestampMismatch/i.test(String(err?.message ?? err))) q.refetch() },
  })
  const save = useMutation({
    mutationFn: () => api.updateEmployee(id, draft, q.data.modified),
    onSuccess: (d) => { qc.setQueryData(['employee', id], d); setEditing(null); setDraft({}) },
    // Changed meanwhile (another card, a document upload, a background job): load the latest and keep the edits.
    onError: (err: any) => { if (/changed this employee|TimestampMismatch/i.test(String(err?.message ?? err))) q.refetch() },
  })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const e = q.data
  const missing = new Set<string>(e.missing_fields ?? [])
  // A checkbox is always answered (ticked or not), so it is never "required".
  const needs = (f: string) => missing.has(f) && e.fields?.[f]?.fieldtype !== 'Check' && !(draft[f] ?? '')
  const isSaudi = !!(editing === 'saudi' && 'alphax_is_saudi' in draft ? draft.alphax_is_saudi : e.sections.saudi?.alphax_is_saudi)
  const visible = (f: string) => !(isSaudi && NON_SAUDI_ONLY.has(f))
  const label = (f: string) => (f === 'alphax_iqama_number' && isSaudi ? t('National ID') : e.labels[f] ?? f)
  const sectionOf = (f: string) => Object.entries(e.sections).find(([, fields]: [string, any]) => f in fields)?.[0]
  const fillNow = (f?: string) => {
    setPopup(false)
    const key = sectionOf(f ?? [...missing][0])
    if (!key) return
    setEditing(key); setDraft({})
    if (collapsed.has(key)) { const n = new Set(collapsed); n.delete(key); saveCollapsed(n) }
    setTimeout(() => document.getElementById(`section-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }
  return (
    <div>
      <Link to="/people" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{t('People')}</Link>
      <PageHeader title={e.employee_name} subtitle={[e.name, e.sections.personal?.alphax_employee_name_ar].filter(Boolean).join(' · ')}
        actions={<div className="flex gap-2 print:hidden">
          <Button variant="ghost" onClick={() => saveCollapsed(new Set())}><ChevronsUpDown className="size-4" />{t('Expand all')}</Button>
          <Button variant="ghost" onClick={() => saveCollapsed(new Set(Object.keys(e.sections)))}><ChevronsDownUp className="size-4" />{t('Collapse all')}</Button>
          <Button variant="secondary" onClick={() => setShowActivity(true)}><History className="size-4" />{t('Activity')}</Button>
          <Link to={`/people/${encodeURIComponent(id)}/contract`}><Button variant="secondary"><FileText className="size-4" />{t('Contract')}</Button></Link>
          <Button variant="secondary" onClick={() => window.print()}><Printer className="size-4" />{t('Print / PDF')}</Button>
        </div>} />
      {showActivity && <ActivityDrawer doctype="Employee" name={id} onClose={() => setShowActivity(false)} />}
      {e.missing_required?.length > 0 && (
        <div className="mb-4 flex flex-wrap items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 print:hidden">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span className="flex-1">{t('Saving this employee needs these mandatory fields first')}: {e.missing_required.join(', ')}</span>
          {e.can_write && <Button size="sm" onClick={() => { setFill({}); fillAll.reset(); setPopup(true) }}>{t('Fill now')}</Button>}
        </div>
      )}
      <Modal open={popup} onClose={() => setPopup(false)} wide
        title={<span className="flex items-center gap-2"><AlertTriangle className="size-5 text-red-600" />{t('Mandatory fields missing')}</span>}
        footer={<>
          <Button variant="secondary" onClick={() => setPopup(false)}>{t('Later')}</Button>
          <Button loading={fillAll.isPending} disabled={!Object.values(fill).some((x) => x !== '' && x != null)} onClick={() => fillAll.mutate()}>{t('Save')}</Button>
        </>}>
        <p className="mb-3 text-sm text-muted">{t('Fill them here and save once. You can also save what you have now and finish the rest later — other sections can still be edited meanwhile.')}</p>
        <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {[...missing].filter((f) => visible(f) && e.fields?.[f]).map((f) => (
            <Field key={f} label={label(f) + ' *'}>
              <Editor field={f} spec={e.fields[f]} value={f in fill ? fill[f] : ''} onChange={(nv) => setFill((x) => ({ ...x, [f]: nv }))} />
            </Field>
          ))}
        </div>
        {[...missing].some((f) => !e.fields?.[f]) && (
          <ul className="mt-3 flex flex-col gap-1">
            {[...missing].filter((f) => !e.fields?.[f]).map((f) => (
              <li key={f}><button onClick={() => fillNow(f)} className="w-full rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-start text-sm text-red-800 hover:bg-red-100">{e.labels[f] ?? f}</button></li>
            ))}
          </ul>
        )}
        {fillAll.error && <div className="mt-3"><ErrorBox error={fillAll.error} /></div>}
      </Modal>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5">
          <Card>
            <div className="flex items-center gap-4">
              <label className={e.can_write ? 'group relative cursor-pointer' : 'relative'} title={e.can_write ? t('Change photo') : undefined}>
                <Avatar name={e.employee_name} image={e.image} size={64} />
                {e.can_write && <>
                  <span className="absolute inset-0 grid place-items-center rounded-full bg-black/40 text-white opacity-0 transition group-hover:opacity-100 print:hidden">
                    {photo.isPending ? '…' : <Camera className="size-5" />}
                  </span>
                  <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" aria-label={t('Change photo')}
                    onChange={(ev) => { const file = ev.target.files?.[0]; if (file) photo.mutate(file); ev.target.value = '' }} />
                </>}
              </label>
              <div>
                <div className="font-semibold">{e.sections.job.designation ?? '—'}</div>
                <div className="text-sm text-muted">{e.sections.job.department ?? '—'}</div>
                <div className="mt-1"><Badge tone={statusTone(e.sections.job.status)}>{t(e.sections.job.status)}</Badge></div>
              </div>
            </div>
            {photo.error && <div className="mt-3"><ErrorBox error={photo.error} /></div>}
          </Card>
          <Card title={t('Documents')}>
            <ul className="divide-y divide-line text-sm">
              {Object.entries(e.documents).filter(([k]) => !(isSaudi && ['iqama', 'passport', 'work_permit'].includes(k))).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between py-2">
                  <span>{t(k === 'work_permit' ? 'Work permit' : k.charAt(0).toUpperCase() + k.slice(1))}</span>
                  <Badge tone={statusTone(String(v))}>{t(String(v))}</Badge>
                </li>
              ))}
            </ul>
          </Card>
          <SalaryCard employee={id} isSaudi={!!e.sections.saudi?.alphax_is_saudi} gosiDate={e.sections.saudi?.alphax_gosi_registration_date ?? undefined}
            company={e.sections.job?.company} canWrite={e.can_write} />
          <AttendanceException employee={id} canWrite={e.can_write} />
          {e.issues.length > 0 && (
            <Card title={t('Data issues')}>
              <ul className="flex flex-col gap-3 text-sm">
                {e.issues.map((i: string) => (
                  <IssueRow key={i} issue={i} fix={e.issue_fixes?.[i]} employee={id} canWrite={e.can_write}
                    onOpen={(section) => (section ? fillNow(Object.keys(e.sections[section] ?? {})[0]) : fillNow())}
                    onFixed={(d) => qc.setQueryData(['employee', id], d)} />
                ))}
              </ul>
            </Card>
          )}
        </div>
        <div className="flex flex-col gap-5 lg:col-span-2">
          {Object.entries(e.sections).map(([key, fields]: [string, any]) => {
            const isEditing = editing === key
            const sectionMissing = Object.keys(fields).filter((f) => missing.has(f) && visible(f)).length
            const closed = collapsed.has(key) && !isEditing
            return (
              <div key={key} id={`section-${key}`} className="scroll-mt-4 break-inside-avoid">
              <Card title={<button type="button" className="flex items-center gap-2" aria-expanded={!closed}
                  onClick={() => { const n = new Set(collapsed); if (n.has(key)) n.delete(key); else n.add(key); saveCollapsed(n) }}>
                  <ChevronDown className={`size-4 text-muted transition print:hidden ${closed ? '-rotate-90 rtl:rotate-90' : ''}`} />
                  {t(SECTION_TITLES[key] ?? key)}
                  {sectionMissing > 0 && <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">{sectionMissing} {t('missing')}</span>}
                </button>}
                action={e.can_write && !isEditing ? <Button size="sm" variant="ghost" className="print:hidden" onClick={() => { setEditing(key); setDraft({}) }}><Pencil className="size-4" />{t('Edit')}</Button> : undefined}>
                {!closed && <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  {Object.entries(fields).filter(([f]) => visible(f)).map(([f, v]) => (
                    isEditing && f !== 'status' ? (
                      <div key={f} className={needs(f) ? 'rounded-xl ring-2 ring-red-300 ring-offset-2' : undefined}>
                        <Field label={label(f) + (missing.has(f) && e.fields?.[f]?.fieldtype !== 'Check' ? ' *' : '')} error={needs(f) ? t('Required') : undefined}>
                          <Editor field={f} spec={e.fields?.[f]} value={f in draft ? draft[f] : v} onChange={(nv) => setDraft({ ...draft, [f]: nv })} />
                        </Field>
                      </div>
                    ) : (
                      <div key={f} className={missing.has(f) ? 'rounded-lg bg-red-50 px-2 py-1 text-sm ring-1 ring-red-200' : 'text-sm'}>
                        <div className={missing.has(f) ? 'text-red-700' : 'text-muted'}>{label(f)}{missing.has(f) && ' *'}</div>
                        <div className="font-medium">{missing.has(f) ? <span className="text-red-700">{t('Required')}</span> : <Value field={f} value={v} lang={lang} t={t} />}</div>
                      </div>
                    )
                  ))}
                </div>}
                {isEditing && (
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button loading={save.isPending} disabled={!Object.keys(draft).length} onClick={() => save.mutate()}>{t('Save')}</Button>
                    <Button variant="secondary" onClick={() => { setEditing(null); setDraft({}); save.reset() }}>{t('Cancel')}</Button>
                    {save.error && <div className="w-full"><ErrorBox error={save.error} onRetry={() => q.refetch()} /></div>}
                  </div>
                )}
              </Card>
              </div>
            )
          })}
          <div className="break-inside-avoid">
            <Card title={<button type="button" className="flex items-center gap-2" aria-expanded={!collapsed.has('leave')}
                onClick={() => { const n = new Set(collapsed); if (n.has('leave')) n.delete('leave'); else n.add('leave'); saveCollapsed(n) }}>
                <ChevronDown className={`size-4 text-muted transition print:hidden ${collapsed.has('leave') ? '-rotate-90 rtl:rotate-90' : ''}`} />{t('Leave')}
              </button>}>
              {!collapsed.has('leave') && <LeaveLedger employee={id} />}
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}

/** One data issue with its fix: a suggested value to apply in one click, account creation, or a jump to the section. */
function IssueRow({ issue, fix, employee, canWrite, onOpen, onFixed }: {
  issue: string; fix?: { section?: string; doctype?: string; suggest?: string; action?: string }; employee: string; canWrite: boolean
  onOpen: (section?: string) => void; onFixed: (d: any) => void
}) {
  const { t } = useI18n()
  const [value, setValue] = useState(fix?.suggest ?? '')
  const m = useMutation({ mutationFn: () => api.fixEmployeeIssue(employee, issue, value || undefined), onSuccess: onFixed })
  const quick = canWrite && fix && (fix.doctype || fix.action === 'create_user')
  return (
    <li className="flex flex-col gap-2 rounded-xl bg-amber-50/60 p-3">
      <div className="flex items-center gap-2 font-medium text-amber-900"><AlertTriangle className="size-4 shrink-0" />{t(issue)}</div>
      {quick ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-48 flex-1">{fix!.action === 'create_user'
            ? <Input type="email" placeholder={t('E-mail for the login')} value={value} onChange={(ev) => setValue(ev.target.value)} />
            : <LinkInput doctype={fix!.doctype!} value={value} onChange={setValue} />}</div>
          <Button size="sm" disabled={!value} loading={m.isPending} onClick={() => m.mutate()}>
            {fix!.action === 'create_user' ? t('Create login') : t('Set')}
          </Button>
        </div>
      ) : null}
      {fix?.action === 'create_user' && <p className="text-xs text-muted">{t('The employee gets an e-mail with a link to set a password.')}</p>}
      {m.error && <ErrorBox error={m.error} />}
      {canWrite && fix?.section && <button type="button" className="self-start text-xs text-brand hover:underline" onClick={() => onOpen(fix.section)}>{t('Open in the profile')}</button>}
    </li>
  )
}
