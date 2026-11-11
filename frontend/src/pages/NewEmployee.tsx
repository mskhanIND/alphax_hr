import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, ArrowLeft, Check } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FieldInput, isEmpty, type FieldSpec } from '../components/FieldInput'
import { Button, Card, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner } from '../components/ui'
import { SalaryEditor, packageReady, type SalaryPackage } from '../components/SalaryEditor'
import { api, uploadFile } from '../lib/api'
import { todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

interface Spec extends FieldSpec { mirrors?: string; step?: string; auto?: 'contract_start' | 'contract_end' | 'nationality'; saudi_value?: string | null }

const STEPS = [
  { key: 'employee', label: 'Employee' },
  { key: 'contract', label: 'Contract' },
  { key: 'personal', label: 'Personal & contact' },
  { key: 'organization', label: 'Organization & role' },
  { key: 'salary', label: 'Salary' },
  { key: 'bank', label: 'Bank' },
  { key: 'review', label: 'Review' },
] as const
const ALWAYS = new Set(['review', 'salary'])
const CORE_REQUIRED = new Set(['first_name', 'last_name', 'gender', 'date_of_birth', 'company', 'date_of_joining', 'alphax_iqama_number', 'alphax_contract_years'])
const NON_SAUDI_ONLY = new Set(['alphax_iqama_expiry', 'passport_number', 'valid_upto'])
const NON_SAUDI_REQUIRED = new Set(['alphax_iqama_expiry', 'passport_number'])
const HIDDEN = new Set(['alphax_is_saudi']) // derived from the ID number (1 = Saudi)

/** What the ID number says about the employee (Saudi national ID starts with 1, Iqama with 2). */
function idKind(id: unknown): 'saudi' | 'iqama' | 'border' | null {
  const d = String(id ?? '').trim()[0]
  return d === '1' ? 'saudi' : d === '2' ? 'iqama' : d === '3' || d === '4' ? 'border' : null
}

function contractEnd(joining: string, years: number) {
  const d = new Date(joining + 'T00:00:00Z')
  d.setUTCFullYear(d.getUTCFullYear() + years)
  d.setUTCDate(d.getUTCDate() - 1)
  return d.toISOString().slice(0, 10)
}

export default function NewEmployee() {
  const { t } = useI18n()
  const s = useSession()
  const nav = useNavigate()
  const form = useQuery<{ core: Spec[]; required: Spec[] }>({ queryKey: ['newEmployeeForm'], queryFn: api.newEmployeeForm })
  const [f, setF] = useState<Record<string, any>>({ company: s.company ?? '', date_of_joining: todayISO() })
  const [step, setStep] = useState(0)
  const [salary, setSalary] = useState<SalaryPackage>({ mode: 'total' })
  const [salaryLater, setSalaryLater] = useState(false)
  const [tried, setTried] = useState<Set<string>>(new Set())
  const [popup, setPopup] = useState<Spec[] | null>(null)
  useEffect(() => {
    if (!form.data) return
    setF((cur) => {
      const next = { ...cur }
      for (const spec of form.data.required) if (isEmpty(next[spec.fieldname]) && spec.default) next[spec.fieldname] = spec.default
      return next
    })
  }, [form.data])
  // created from a joiner's own form: fill in what they sent
  const [params] = useSearchParams()
  const joiner = params.get('joiner')
  const pre = useQuery<any>({ queryKey: ['joiner-prefill', joiner], queryFn: () => api.joinerPrefill(joiner!), enabled: !!joiner })
  useEffect(() => { if (pre.data) setF((cur) => ({ ...cur, ...pre.data.values })) }, [pre.data])
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }))
  const kind = idKind(f.alphax_iqama_number)
  const payload = () => {
    const out: Record<string, any> = { ...f, alphax_is_saudi: kind === 'saudi' ? 1 : 0 }
    if (joiner) out.joiner = joiner
    if (!salaryLater && packageReady(salary)) out.salary = salary
    if (kind === 'saudi') for (const k of NON_SAUDI_ONLY) delete out[k]
    return out
  }
  const m = useMutation({ mutationFn: () => api.createEmployee(payload()), onSuccess: (d: any) => nav(`/people/${encodeURIComponent(d.name)}`) })
  const [extra, setExtra] = useState<(Spec & { mandatory: boolean })[]>([])
  const [uploading, setUploading] = useState<string | null>(null)
  const allSpecs: Spec[] = form.data ? [...form.data.core, ...form.data.required] : []
  const years = String(f.alphax_contract_years ?? '')
  // Derived values: contract dates from the joining date and period, nationality from an ID starting with 1.
  useEffect(() => {
    if (!form.data) return
    setF((cur) => {
      const next = { ...cur }
      let changed = false
      const put = (k: string, v: any) => { if (next[k] !== v) { next[k] = v; changed = true } }
      for (const spec of allSpecs) {
        if (spec.auto === 'contract_start' && cur.date_of_joining) put(spec.fieldname, cur.date_of_joining)
        if (spec.auto === 'contract_end' && cur.date_of_joining && /^\d$/.test(years)) put(spec.fieldname, contractEnd(cur.date_of_joining, Number(years)))
        if (spec.auto === 'nationality' && spec.saudi_value) {
          if (kind === 'saudi') put(spec.fieldname, spec.saudi_value)
          else if (cur[spec.fieldname] === spec.saudi_value) put(spec.fieldname, '')
        }
      }
      return changed ? next : cur
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.data, f.date_of_joining, years, kind])
  const locked = (spec: Spec) => (spec.auto === 'contract_start')
    || (spec.auto === 'contract_end' && /^\d$/.test(years))
    || (spec.auto === 'nationality' && kind === 'saudi' && !!spec.saudi_value)

  const fields = useMemo(() => {
    if (!form.data) return [] as (Spec & { mandatory: boolean })[]
    const coreNames = new Set(form.data.core.map((c) => c.fieldname))
    const visibleCore = form.data.core.filter((c) => {
      if (HIDDEN.has(c.fieldname)) return false
      if (c.fieldname === 'alphax_gosi_registration_date') return kind === 'saudi'
      if (NON_SAUDI_ONLY.has(c.fieldname)) return kind !== 'saudi'
      return true
    })
    // Company fields that duplicate an AlphaX field (another "National ID / Iqama" box) are filled automatically.
    const required = form.data.required.filter((c) => !(c.mirrors && coreNames.has(c.mirrors)))
    return [
      ...visibleCore.map((c) => ({ ...c, mandatory: CORE_REQUIRED.has(c.fieldname) || (kind !== null && kind !== 'saudi' && NON_SAUDI_REQUIRED.has(c.fieldname)) })),
      ...required.filter((c) => !(kind === 'saudi' && NON_SAUDI_ONLY.has(c.fieldname))).map((c) => ({ ...c, mandatory: true })),
    ]
  }, [form.data, kind])

  // On the Review step, ask the server which mandatory fields Frappe would still reject (attachments, hidden fields …).
  const stepKeys = STEPS.filter((st) => ALWAYS.has(st.key) || fields.some((x) => (x.step ?? 'personal') === st.key)).map((st) => st.key)
  const onReview = stepKeys[step] === 'review'
  useEffect(() => {
    if (!onReview) return
    const h = setTimeout(() => {
      api.checkNewEmployee(payload()).then((r) => {
        const known = new Set(fields.map((x) => x.fieldname))
        setExtra(r.missing.filter((x: any) => !known.has(x.fieldname)).map((x: any) => ({ ...x, step: 'review', mandatory: true })))
      }).catch(() => setExtra([]))
    }, 300)
    return () => clearTimeout(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onReview, f])
  if (form.isLoading) return <Spinner />
  if (form.error) return <ErrorBox error={form.error} onRetry={() => form.refetch()} />

  const steps = STEPS.filter((st) => ALWAYS.has(st.key) || fields.some((x) => (x.step ?? 'personal') === st.key))
  const current = steps[step]
  const inStep = (key: string) => fields.filter((x) => (x.step ?? 'personal') === key)
  const missingIn = (key: string) => inStep(key).filter((x) => x.mandatory && isEmpty(f[x.fieldname]))
  const extraMissing = extra.filter((x) => isEmpty(f[x.fieldname]))
  const allMissing = [...fields.filter((x) => x.mandatory && isEmpty(f[x.fieldname])), ...extraMissing]
  const autoFilled = form.data!.required.filter((c) => c.mirrors && fields.some((x) => x.fieldname === c.mirrors))

  const salaryMissing = !salaryLater && !packageReady(salary)
  const next = () => {
    if (current.key === 'salary' && salaryMissing) {
      setTried((x) => new Set(x).add('salary'))
      setPopup([{ fieldname: '__salary', label: t('Salary package (or tick "Set salary later")'), fieldtype: 'Data', step: 'salary' } as any])
      return
    }
    const miss = missingIn(current.key)
    setTried((x) => new Set(x).add(current.key))
    if (miss.length) { setPopup(miss); return }
    setStep((i) => Math.min(i + 1, steps.length - 1))
  }
  const create = () => {
    setTried(new Set([...steps.map((x) => x.key), 'review']))
    if (allMissing.length || salaryMissing) {
      setPopup([...allMissing, ...(salaryMissing ? [{ fieldname: '__salary', label: t('Salary package (or tick "Set salary later")'), fieldtype: 'Data', step: 'salary' } as any] : [])])
      return
    }
    m.mutate()
  }
  const goTo = (spec: Spec) => {
    setPopup(null)
    setStep(Math.max(0, steps.findIndex((x) => x.key === (spec.step ?? 'personal'))))
    setTimeout(() => document.querySelector<HTMLElement>(`[data-field="${spec.fieldname}"] input, [data-field="${spec.fieldname}"] select`)?.focus(), 50)
  }

  const render = (spec: Spec & { mandatory: boolean }) => {
    const bad = tried.has(spec.step ?? 'personal') && spec.mandatory && isEmpty(f[spec.fieldname])
    return (
      <div key={spec.fieldname} data-field={spec.fieldname} className={clsx((spec.fieldtype === 'Text' || spec.fieldtype === 'Long Text') && 'sm:col-span-2')}>
        <Field label={spec.label + (spec.mandatory ? ' *' : '')}
          hint={spec.fieldname === 'alphax_iqama_number' ? t('National ID (starts with 1), Iqama (2) or border number (3/4).')
            : spec.fieldname === 'alphax_gosi_registration_date' ? t('Decides Legacy vs New GOSI system. Defaults to the joining date if left blank.')
            : spec.fieldname === 'alphax_contract_years' ? (f.date_of_joining && /^\d$/.test(String(f.alphax_contract_years ?? '')) ? `${t('Contract ends')} ${contractEnd(f.date_of_joining, Number(f.alphax_contract_years))}` : t('Sets the contract end date from the joining date.'))
            : spec.description ?? undefined}
          error={bad ? t('Required') : undefined}>
          {locked(spec) ? (
            <div className="flex h-10 items-center rounded-xl border border-line bg-surface px-3 text-sm" title={t('Filled automatically')}>
              {String(f[spec.fieldname] ?? '') || '—'}<span className="ms-auto text-xs text-muted">{t('auto')}</span>
            </div>
          ) : spec.fieldtype === 'Attach' || spec.fieldtype === 'Attach Image' ? (
            <div className="flex items-center gap-2">
              <Input type="file" className="py-1.5" onChange={async (e) => {
                const file = e.target.files?.[0]; if (!file) return
                setUploading(spec.fieldname)
                try { const r: any = await uploadFile('', '', file, true); set(spec.fieldname, r.file_url) } finally { setUploading(null) }
              }} />
              {uploading === spec.fieldname ? <span className="text-xs text-muted">…</span> : f[spec.fieldname] ? <span className="text-xs text-emerald-700">✓</span> : null}
            </div>
          ) : spec.fieldname === 'gender' ? (
            <Select className={bad ? 'border-red-400 ring-2 ring-red-100' : undefined} value={f.gender ?? ''} onChange={(e) => set('gender', e.target.value)}>
              <option value="">—</option><option value="Male">{t('Male')}</option><option value="Female">{t('Female')}</option>
            </Select>
          ) : spec.fieldname === 'alphax_employee_name_ar' ? (
            <Input dir="rtl" lang="ar" className={bad ? 'border-red-400 ring-2 ring-red-100' : undefined} value={f[spec.fieldname] ?? ''} onChange={(e) => set(spec.fieldname, e.target.value)} placeholder="الاسم الكامل" />
          ) : <FieldInput spec={spec} value={f[spec.fieldname]} onChange={(v) => set(spec.fieldname, v)} invalid={bad} />}
        </Field>
        {spec.fieldname === 'alphax_iqama_number' && kind && (
          <span className={clsx('mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium', kind === 'saudi' ? 'bg-emerald-50 text-emerald-700' : 'bg-blue-50 text-blue-700')}>
            {kind === 'saudi' ? t('Saudi national') : kind === 'iqama' ? t('Non-Saudi (Iqama)') : t('Border number')}
          </span>
        )}
      </div>
    )
  }

  return (
    <div>
      <Link to="/people" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{t('People')}</Link>
      <PageHeader title={t('New employee')} />
      {pre.data && <div className="rounded-xl bg-brand-50 p-3 text-sm text-brand">{t('Filled in from the joining form of')} <b>{pre.data.full_name}</b>. {t('Check each step, add the job and salary, then create. Their documents move to the employee.')}
        {Object.keys(pre.data.extra ?? {}).length > 0 && <div className="mt-1 text-xs">{t('Also sent (not employee fields)')}: {Object.entries(pre.data.extra).map(([k, v]) => `${k}: ${v}`).join(' · ')}</div>}</div>}
      {pre.error && <ErrorBox error={pre.error} />}
      <ol className="mb-5 flex flex-wrap gap-2" aria-label={t('Steps')}>
        {steps.map((st, i) => {
          const done = i < step && missingIn(st.key).length === 0
          const warn = tried.has(st.key) && st.key !== 'review' && missingIn(st.key).length > 0
          return (
            <li key={st.key}>
              <button type="button" onClick={() => setStep(i)} aria-current={i === step ? 'step' : undefined}
                className={clsx('flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition',
                  i === step ? 'border-brand bg-brand text-white' : warn ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-line bg-white text-ink hover:bg-surface')}>
                <span className={clsx('grid size-5 place-items-center rounded-full text-xs', i === step ? 'bg-white/20' : 'bg-surface')}>
                  {done ? <Check className="size-3.5" /> : warn ? <AlertTriangle className="size-3.5" /> : i + 1}
                </span>
                {t(st.label)}
              </button>
            </li>
          )
        })}
      </ol>

      <Card title={t(current.label)}>
        {current.key === 'salary' ? (
          <div className="flex flex-col gap-4">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={salaryLater} onChange={(e) => setSalaryLater(e.target.checked)} />{t('Set salary later')}</label>
            {!salaryLater && <SalaryEditor value={salary} onChange={setSalary} isSaudi={kind === 'saudi'} gosiDate={f.alphax_gosi_registration_date || f.date_of_joining} startDate={f.date_of_joining} company={f.company} />}
            {!salaryLater && <p className="text-xs text-muted">{t('Creates the employee\'s own salary structure and assignment from the joining date (same as CentralHRMS).')}</p>}
          </div>
        ) : current.key !== 'review' ? (
          <div className="grid gap-4 sm:grid-cols-2">{inStep(current.key).flatMap((spec) => spec.fieldname === 'alphax_employee_name_ar' ? [
            <div key="name_en">
              <Field label={t('Full Name (English)')}>
                <div className="flex h-10 items-center rounded-xl border border-line bg-surface px-3 text-sm">{[f.first_name, f.last_name].filter(Boolean).join(' ') || '—'}<span className="ms-auto text-xs text-muted">{t('auto')}</span></div>
              </Field>
            </div>, render(spec)] : [render(spec)])}</div>
        ) : (
          <div className="flex flex-col gap-4">
            {steps.filter((st) => st.key !== 'review').map((st) => (
              <div key={st.key} className="rounded-xl border border-line p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-medium">{t(st.label)}</span>
                  <button type="button" className="text-sm text-brand hover:underline" onClick={() => setStep(steps.indexOf(st))}>{t('Edit')}</button>
                </div>
                <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                  {inStep(st.key).map((x) => (
                    <div key={x.fieldname} className="flex justify-between gap-3">
                      <dt className="text-muted">{x.label}</dt>
                      <dd className={clsx('text-end', x.mandatory && isEmpty(f[x.fieldname]) ? 'font-medium text-red-700' : '')}>
                        {isEmpty(f[x.fieldname]) ? (x.mandatory ? t('Required') : '—') : String(f[x.fieldname])}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
            <div className="rounded-xl border border-line p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-medium">{t('Salary')}</span>
                <button type="button" className="text-sm text-brand hover:underline" onClick={() => setStep(steps.findIndex((x) => x.key === 'salary'))}>{t('Edit')}</button>
              </div>
              <p className={clsx('text-sm', salaryMissing ? 'font-medium text-red-700' : '')}>
                {salaryLater ? t('Set salary later') : salary.mode === 'total' ? `${t('Total monthly package')}: ${salary.total ?? '—'}` : `${t('Basic')}: ${salary.basic ?? '—'}`}
              </p>
            </div>
            {extra.length > 0 && (
              <div className="rounded-xl border border-red-200 bg-red-50/40 p-3">
                <div className="mb-2 font-medium text-red-800">{t('Also required by your company')}</div>
                <div className="grid gap-4 sm:grid-cols-2">{extra.map(render)}</div>
              </div>
            )}
            {autoFilled.length > 0 && <p className="text-xs text-muted">{t('Also filled automatically')}: {autoFilled.map((x) => x.label).join(', ')}</p>}
          </div>
        )}
      </Card>

      {m.error && <div className="mt-4"><ErrorBox error={m.error} /></div>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <Button type="button" variant="secondary" disabled={step === 0} onClick={() => setStep((i) => Math.max(0, i - 1))}>{t('Back')}</Button>
        <span className="text-sm text-muted">{t('Step')} {step + 1} / {steps.length}</span>
        {current.key === 'review'
          ? <Button type="button" loading={m.isPending} onClick={create}>{t('Create employee')}</Button>
          : <Button type="button" onClick={next}>{t('Next')}</Button>}
      </div>

      <Modal open={!!popup} onClose={() => setPopup(null)} title={<span className="flex items-center gap-2"><AlertTriangle className="size-5 text-amber-600" />{t('Please fill in')}</span>}>
        <p className="mb-3 text-sm text-muted">{t('These fields are mandatory. Click one to go to it.')}</p>
        <ul className="flex flex-col gap-1">
          {(popup ?? []).map((x) => (
            <li key={x.fieldname}>
              <button type="button" onClick={() => goTo(x)} className="flex w-full items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-start text-sm text-red-800 hover:bg-red-100">
                {x.label}<span className="text-xs text-red-600">{t(STEPS.find((st) => st.key === (x.step ?? 'personal'))?.label ?? '')}</span>
              </button>
            </li>
          ))}
        </ul>
      </Modal>
    </div>
  )
}
