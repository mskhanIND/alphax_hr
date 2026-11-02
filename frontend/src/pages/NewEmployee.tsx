import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, ArrowLeft, Check } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FieldInput, isEmpty, type FieldSpec } from '../components/FieldInput'
import { Button, Card, ErrorBox, Field, Modal, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

interface Spec extends FieldSpec { mirrors?: string; step?: string }

const STEPS = [
  { key: 'personal', label: 'Personal & contact' },
  { key: 'job', label: 'Job' },
  { key: 'identity', label: 'Identity & Saudi details' },
  { key: 'contract', label: 'Contract & other' },
  { key: 'review', label: 'Review' },
] as const
const CORE_REQUIRED = new Set(['first_name', 'gender', 'date_of_birth', 'company', 'date_of_joining', 'alphax_iqama_number'])
const HIDDEN = new Set(['alphax_is_saudi']) // derived from the ID number (1 = Saudi)

/** What the ID number says about the employee (Saudi national ID starts with 1, Iqama with 2). */
function idKind(id: unknown): 'saudi' | 'iqama' | 'border' | null {
  const d = String(id ?? '').trim()[0]
  return d === '1' ? 'saudi' : d === '2' ? 'iqama' : d === '3' || d === '4' ? 'border' : null
}

export default function NewEmployee() {
  const { t } = useI18n()
  const s = useSession()
  const nav = useNavigate()
  const form = useQuery<{ core: Spec[]; required: Spec[] }>({ queryKey: ['newEmployeeForm'], queryFn: api.newEmployeeForm })
  const [f, setF] = useState<Record<string, any>>({ company: s.company ?? '', date_of_joining: todayISO() })
  const [step, setStep] = useState(0)
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
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }))
  const kind = idKind(f.alphax_iqama_number)
  const payload = () => ({ ...f, alphax_is_saudi: kind === 'saudi' ? 1 : 0 })
  const m = useMutation({ mutationFn: () => api.createEmployee(payload()), onSuccess: (d: any) => nav(`/people/${encodeURIComponent(d.name)}`) })

  const fields = useMemo(() => {
    if (!form.data) return [] as (Spec & { mandatory: boolean })[]
    const coreNames = new Set(form.data.core.map((c) => c.fieldname))
    const visibleCore = form.data.core.filter((c) => {
      if (HIDDEN.has(c.fieldname)) return false
      if (c.fieldname === 'alphax_gosi_registration_date') return kind === 'saudi'
      if (c.fieldname === 'alphax_iqama_expiry') return kind !== 'saudi'
      return true
    })
    // Company fields that duplicate an AlphaX field (another "National ID / Iqama" box) are filled automatically.
    const required = form.data.required.filter((c) => !(c.mirrors && coreNames.has(c.mirrors)))
    return [
      ...visibleCore.map((c) => ({ ...c, mandatory: CORE_REQUIRED.has(c.fieldname) })),
      ...required.map((c) => ({ ...c, mandatory: true })),
    ]
  }, [form.data, kind])

  if (form.isLoading) return <Spinner />
  if (form.error) return <ErrorBox error={form.error} onRetry={() => form.refetch()} />

  const steps = STEPS.filter((st) => st.key === 'review' || fields.some((x) => (x.step ?? 'contract') === st.key))
  const current = steps[step]
  const inStep = (key: string) => fields.filter((x) => (x.step ?? 'contract') === key)
  const missingIn = (key: string) => inStep(key).filter((x) => x.mandatory && isEmpty(f[x.fieldname]))
  const allMissing = fields.filter((x) => x.mandatory && isEmpty(f[x.fieldname]))
  const autoFilled = form.data!.required.filter((c) => c.mirrors && fields.some((x) => x.fieldname === c.mirrors))

  const next = () => {
    const miss = missingIn(current.key)
    setTried((x) => new Set(x).add(current.key))
    if (miss.length) { setPopup(miss); return }
    setStep((i) => Math.min(i + 1, steps.length - 1))
  }
  const create = () => {
    setTried(new Set(steps.map((x) => x.key)))
    if (allMissing.length) { setPopup(allMissing); return }
    m.mutate()
  }
  const goTo = (spec: Spec) => {
    setPopup(null)
    setStep(steps.findIndex((x) => x.key === (spec.step ?? 'contract')))
    setTimeout(() => document.querySelector<HTMLElement>(`[data-field="${spec.fieldname}"] input, [data-field="${spec.fieldname}"] select`)?.focus(), 50)
  }

  const render = (spec: Spec & { mandatory: boolean }) => {
    const bad = tried.has(spec.step ?? 'contract') && spec.mandatory && isEmpty(f[spec.fieldname])
    return (
      <div key={spec.fieldname} data-field={spec.fieldname} className={clsx(spec.fieldtype === 'Small Text' || spec.fieldtype === 'Text' ? 'sm:col-span-2' : '')}>
        <Field label={spec.label + (spec.mandatory ? ' *' : '')}
          hint={spec.fieldname === 'alphax_iqama_number' ? t('National ID (starts with 1), Iqama (2) or border number (3/4).')
            : spec.fieldname === 'alphax_gosi_registration_date' ? t('Decides Legacy vs New GOSI system — not the hire date.') : spec.description ?? undefined}
          error={bad ? t('Required') : undefined}>
          <FieldInput spec={spec} value={f[spec.fieldname]} onChange={(v) => set(spec.fieldname, v)} invalid={bad} />
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
        {current.key !== 'review' ? (
          <div className="grid gap-4 sm:grid-cols-2">{inStep(current.key).map(render)}</div>
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
                {x.label}<span className="text-xs text-red-600">{t(STEPS.find((st) => st.key === (x.step ?? 'contract'))?.label ?? '')}</span>
              </button>
            </li>
          ))}
        </ul>
      </Modal>
    </div>
  )
}
