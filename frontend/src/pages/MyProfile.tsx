import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { FileCheck2 } from 'lucide-react'
import { Modal, Textarea } from '../components/ui'
import { FieldInput } from '../components/FieldInput'
import { NotificationSettings } from '../components/NotificationSettings'
import { uploadFile } from '../lib/api'
import { Avatar, Badge, Button, Card, ErrorBox, Field, Input, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

/** Details only HR may change (documents, marital status, bank): the employee asks, HR checks and applies. */
function ChangeRequest() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['profile-change'], queryFn: api.profileChangeForm })
  const [open, setOpen] = useState(false)
  const [vals, setVals] = useState<Record<string, any>>({})
  const [reason, setReason] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const changed = Object.fromEntries(Object.entries(vals).filter(([k, v]) => v !== '' && v !== null && v !== undefined &&
    String(v) !== (q.data?.fields.find((f: any) => f.fieldname === k)?.value ?? '')))
  const needsDoc = (q.data?.fields ?? []).some((f: any) => f.document && f.fieldname in changed)
  const m = useMutation({
    mutationFn: async () => { const r = await api.requestProfileChange(changed, reason || undefined); if (file) await uploadFile('AlphaX Request', r.name, file); return r },
    onSuccess: () => { setOpen(false); setVals({}); setReason(''); setFile(null); qc.invalidateQueries({ queryKey: ['profile-change'] }); qc.invalidateQueries({ queryKey: ['my-requests'] }) },
  })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
  if (!d.enabled) return null
  const show = (f: any) => f.fieldtype === 'Date' && f.value ? fmtDate(f.value, lang) : f.value
  return (
    <Card title={t('Documents & personal details')} subtitle={t('Changed by HR after checking your document')} className="lg:col-span-3"
      action={!d.pending && <Button size="sm" onClick={() => setOpen(true)}><FileCheck2 className="size-4" />{t('Request a change')}</Button>}>
      {d.pending && (
        <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          {t('Waiting for HR')} ({d.pending.name}): {Object.values(d.pending.changes).map((c: any) => `${c.label} → ${c.to}`).join(' · ')}
        </div>
      )}
      <div className="grid gap-x-8 sm:grid-cols-2">
        {d.fields.map((f: any) => (
          <div key={f.fieldname} className="flex justify-between gap-4 border-b border-line py-2 text-sm">
            <span className="text-muted">{t(f.label)}</span><span className="text-end font-medium">{show(f) || '—'}</span>
          </div>
        ))}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} wide title={t('Request a change')}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>{t('Cancel')}</Button>
          <Button disabled={!Object.keys(changed).length || (needsDoc && !file)} loading={m.isPending} onClick={() => m.mutate()}>{t('Send to HR')}</Button></>}>
        <p className="mb-3 text-sm text-muted">{t('Fill in only what changed. HR reviews the request and updates your file.')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {d.fields.map((f: any) => (
            <Field key={f.fieldname} label={t(f.label)} hint={f.value ? `${t('Now')}: ${show(f)}` : undefined}>
              <FieldInput spec={{ ...f, reqd: 0 }} value={vals[f.fieldname] ?? ''} onChange={(v) => setVals((s) => ({ ...s, [f.fieldname]: v ?? '' }))} />
            </Field>
          ))}
        </div>
        <div className="mt-3 grid gap-3">
          <Field label={t('Copy of the new document') + (needsDoc ? ' *' : '')} hint={t('Photo or PDF of the new passport / Iqama page.')}>
            <input type="file" accept="image/*,application/pdf" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
          </Field>
          <Field label={t('Note to HR')}><Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        </div>
        {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
      </Modal>
    </Card>
  )
}

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
        <ChangeRequest />
        <div className="lg:col-span-3"><NotificationSettings /></div>
      </div>
    </div>
  )
}
