import { useMutation } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, Input, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'

export default function NewEmployee() {
  const { t } = useI18n()
  const s = useSession()
  const nav = useNavigate()
  const [f, setF] = useState<Record<string, any>>({ company: s.company ?? '', date_of_joining: todayISO(), alphax_is_saudi: 0 })
  const set = (k: string, v: any) => setF((x) => ({ ...x, [k]: v }))
  const m = useMutation({ mutationFn: () => api.createEmployee(f), onSuccess: (d: any) => nav(`/people/${encodeURIComponent(d.name)}`) })
  return (
    <div>
      <Link to="/people" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{t('People')}</Link>
      <PageHeader title={t('New employee')} />
      <Card>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); m.mutate() }}>
          <Field label={t('First name')}><Input required value={f.first_name ?? ''} onChange={(e) => set('first_name', e.target.value)} /></Field>
          <Field label={t('Last name')}><Input value={f.last_name ?? ''} onChange={(e) => set('last_name', e.target.value)} /></Field>
          <Field label={t('Gender')}><LinkInput doctype="Gender" required value={f.gender ?? ''} onChange={(v) => set('gender', v)} /></Field>
          <Field label={t('Date of birth')}><Input type="date" required value={f.date_of_birth ?? ''} onChange={(e) => set('date_of_birth', e.target.value)} /></Field>
          <Field label={t('Company')}><LinkInput doctype="Company" required value={f.company} onChange={(v) => set('company', v)} /></Field>
          <Field label={t('Date of joining')}><Input type="date" required value={f.date_of_joining} onChange={(e) => set('date_of_joining', e.target.value)} /></Field>
          <Field label={t('Department')}><LinkInput doctype="Department" value={f.department ?? ''} onChange={(v) => set('department', v)} /></Field>
          <Field label={t('Designation')}><LinkInput doctype="Designation" value={f.designation ?? ''} onChange={(v) => set('designation', v)} /></Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!f.alphax_is_saudi} onChange={(e) => set('alphax_is_saudi', e.target.checked ? 1 : 0)} /> {t('Saudi')}
          </label>
          {f.alphax_is_saudi ? (
            <Field label={t('First GOSI registration date')} hint={t('Decides Legacy vs New GOSI system — not the hire date.')}><Input type="date" value={f.alphax_gosi_registration_date ?? ''} onChange={(e) => set('alphax_gosi_registration_date', e.target.value)} /></Field>
          ) : (
            <>
              <Field label={t('Iqama')}><Input value={f.alphax_iqama_number ?? ''} onChange={(e) => set('alphax_iqama_number', e.target.value)} inputMode="numeric" /></Field>
              <Field label={t('Iqama expiry')}><Input type="date" value={f.alphax_iqama_expiry ?? ''} onChange={(e) => set('alphax_iqama_expiry', e.target.value)} /></Field>
            </>
          )}
          {m.error && <div className="sm:col-span-2"><ErrorBox error={m.error} /></div>}
          <div className="sm:col-span-2"><Button type="submit" loading={m.isPending}>{t('Create')}</Button></div>
        </form>
      </Card>
    </div>
  )
}
