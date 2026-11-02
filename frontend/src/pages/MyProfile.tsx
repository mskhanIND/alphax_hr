import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Input, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function MyProfile() {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['profile'], queryFn: api.profile })
  const qc = useQueryClient()
  const [form, setForm] = useState<Record<string, string>>({})
  useEffect(() => {
    if (q.data) setForm({ cell_number: q.data.cell_number ?? '', personal_email: q.data.personal_email ?? '', person_to_be_contacted: q.data.person_to_be_contacted ?? '', emergency_phone_number: q.data.emergency_phone_number ?? '' })
  }, [q.data])
  const m = useMutation({ mutationFn: () => api.updateContact(form), onSuccess: (d) => qc.setQueryData(['profile'], d) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const p = q.data
  const Row = ({ label, value }: { label: string; value: any }) => (
    <div className="flex justify-between gap-4 py-2 text-sm"><span className="text-muted">{label}</span><span className="text-end font-medium">{value || '—'}</span></div>
  )
  return (
    <div>
      <PageHeader title={t('My Profile')} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <div className="flex flex-col items-center gap-2 text-center">
            <Avatar name={p.employee_name} image={p.image} size={88} />
            <div className="text-lg font-semibold">{p.employee_name}</div>
            <div className="text-sm text-muted">{p.designation} · {p.department}</div>
            <Badge tone={p.alphax_is_saudi ? 'green' : 'gray'}>{p.alphax_is_saudi ? t('Saudi') : t('Non-Saudi')}</Badge>
          </div>
          <div className="mt-4 divide-y divide-line">
            <Row label={t('Employee')} value={p.name} />
            <Row label={t('Joined')} value={fmtDate(p.date_of_joining, lang)} />
            <Row label={t('Reports to')} value={p.reports_to_name} />
            <Row label={t('Annual leave entitlement')} value={p.annual_entitlement_days ? `${p.annual_entitlement_days} ${t('days')} ${t('per year')}` : null} />
            {!p.alphax_is_saudi && <Row label={t('Iqama')} value={p.alphax_iqama_expiry ? fmtDate(p.alphax_iqama_expiry, lang) : null} />}
          </div>
        </Card>
        <Card title={t('Contact')} className="lg:col-span-2">
          <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
            <Field label={t('Mobile')}><Input value={form.cell_number ?? ''} onChange={(e) => setForm({ ...form, cell_number: e.target.value })} inputMode="tel" /></Field>
            <Field label={t('Personal email')}><Input type="email" value={form.personal_email ?? ''} onChange={(e) => setForm({ ...form, personal_email: e.target.value })} /></Field>
            <Field label={t('Emergency contact')}><Input value={form.person_to_be_contacted ?? ''} onChange={(e) => setForm({ ...form, person_to_be_contacted: e.target.value })} /></Field>
            <Field label={t('Emergency phone')}><Input value={form.emergency_phone_number ?? ''} onChange={(e) => setForm({ ...form, emergency_phone_number: e.target.value })} inputMode="tel" /></Field>
            <div className="sm:col-span-2 flex items-center gap-3">
              <Button type="submit" loading={m.isPending}>{t('Save')}</Button>
              {m.isSuccess && <span className="text-sm text-emerald-700">{t('Saved')}</span>}
            </div>
            {m.error && <div className="sm:col-span-2"><ErrorBox error={m.error} /></div>}
          </form>
        </Card>
      </div>
    </div>
  )
}
