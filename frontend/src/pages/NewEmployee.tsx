import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FieldInput, isEmpty, type FieldSpec } from '../components/FieldInput'
import { Button, Card, ErrorBox, Field, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

const SAUDI_ONLY = new Set(['alphax_gosi_registration_date'])
const FOREIGN_ONLY = new Set(['alphax_iqama_expiry']) // the ID number applies to Saudis too (National ID)
const CORE_REQUIRED = new Set(['first_name', 'gender', 'date_of_birth', 'company', 'date_of_joining'])

interface Spec extends FieldSpec { mirrors?: string }

export default function NewEmployee() {
  const { t } = useI18n()
  const s = useSession()
  const nav = useNavigate()
  const form = useQuery<{ core: FieldSpec[]; required: Spec[] }>({ queryKey: ['newEmployeeForm'], queryFn: api.newEmployeeForm })
  const [f, setF] = useState<Record<string, any>>({ company: s.company ?? '', date_of_joining: todayISO(), alphax_is_saudi: 0 })
  const [tried, setTried] = useState(false)
  useEffect(() => {
    // Apply site defaults for required fields once the form definition arrives.
    if (!form.data) return
    setF((cur) => {
      const next = { ...cur }
      for (const spec of form.data.required) if (isEmpty(next[spec.fieldname]) && spec.default) next[spec.fieldname] = spec.default
      return next
    })
  }, [form.data])
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }))
  const m = useMutation({ mutationFn: () => api.createEmployee(f), onSuccess: (d: any) => nav(`/people/${encodeURIComponent(d.name)}`) })

  if (form.isLoading) return <Spinner />
  if (form.error) return <ErrorBox error={form.error} onRetry={() => form.refetch()} />
  const core = form.data!.core.filter((c) => (f.alphax_is_saudi ? !FOREIGN_ONLY.has(c.fieldname) : !SAUDI_ONLY.has(c.fieldname)))
  // Legacy fields that mirror an AlphaX field (e.g. 'Identity Number' = Iqama) are filled automatically.
  const mirrored = form.data!.required.filter((c) => c.mirrors && core.some((k) => k.fieldname === c.mirrors))
  const required = form.data!.required.filter((c) => !mirrored.includes(c))
  const mirrorSources = new Set(mirrored.map((c) => c.mirrors).filter((m) => m !== 'alphax_is_saudi'))
  const coreRequired = (name: string) => CORE_REQUIRED.has(name) || mirrorSources.has(name)
  const missing = [...core.filter((c) => coreRequired(c.fieldname)), ...required].filter((c) => isEmpty(f[c.fieldname]))
  const submit = () => {
    setTried(true)
    if (missing.length) return
    m.mutate()
  }
  const render = (spec: FieldSpec, mandatory: boolean) => (
    <Field key={spec.fieldname} label={spec.label + (mandatory ? ' *' : '')}
      hint={spec.fieldname === 'alphax_gosi_registration_date' ? t('Decides Legacy vs New GOSI system — not the hire date.') : spec.description ?? undefined}
      error={tried && mandatory && isEmpty(f[spec.fieldname]) ? t('Required') : undefined}>
      <FieldInput spec={spec} value={f[spec.fieldname]} onChange={(v) => set(spec.fieldname, v)} invalid={tried && mandatory && isEmpty(f[spec.fieldname])} />
    </Field>
  )
  return (
    <div>
      <Link to="/people" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{t('People')}</Link>
      <PageHeader title={t('New employee')} />
      <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <Card title={t('Basic details')}>
          <div className="grid gap-4 sm:grid-cols-2">
            {core.map((spec) => spec.fieldname === 'alphax_is_saudi' ? (
              <label key="saudi" className="flex items-center gap-2 self-end pb-2 text-sm font-medium">
                <FieldInput spec={spec} value={f.alphax_is_saudi} onChange={(v) => set('alphax_is_saudi', v)} /> {t('Saudi')}
              </label>
            ) : render(spec, coreRequired(spec.fieldname)))}
          </div>
        </Card>
        {mirrored.length > 0 && (
          <p className="-mt-2 text-xs text-muted">{t('Also filled automatically')}: {mirrored.map((m) => m.label).join(', ')}</p>
        )}
        {required.length > 0 && (
          <Card title={t('Required by your company')} subtitle={t('These fields are mandatory in your HR setup.')}>
            <div className="grid gap-4 sm:grid-cols-2">{required.map((spec) => render(spec, true))}</div>
          </Card>
        )}
        {tried && missing.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
            {t('Please fill in')}: {missing.map((m) => m.label).join(', ')}
          </div>
        )}
        {m.error && <ErrorBox error={m.error} />}
        <div><Button type="submit" loading={m.isPending}>{t('Create')}</Button></div>
      </form>
    </div>
  )
}
