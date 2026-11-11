import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Copy, ExternalLink, Mail, Plus, RefreshCw, UserPlus, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, FilterNote, Input, Modal, PageHeader, Spinner, Stat, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtDateTime, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

const TONE: Record<string, string> = { Invited: 'blue', Submitted: 'amber', 'Changes requested': 'amber', Converted: 'green', Cancelled: 'gray' }

function Invite({ onClose, onDone }: { onClose: () => void; onDone: (r: any) => void }) {
  const { t } = useI18n()
  const [v, setV] = useState<any>({ full_name: '', mobile: '', email: '', company: '', department: '', designation: '', branch: '', date_of_joining: todayISO() })
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const m = useMutation({ mutationFn: () => api.inviteJoiner(v), onSuccess: onDone })
  return (
    <Modal open onClose={onClose} title={t('Invite a new joiner')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={m.isPending} onClick={() => m.mutate()}>{t('Create link')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Name')}><Input value={v.full_name} onChange={(e) => set('full_name', e.target.value)} /></Field>
        <Field label={t('Joining date')}><Input type="date" value={v.date_of_joining} onChange={(e) => set('date_of_joining', e.target.value)} /></Field>
        <Field label={t('Mobile')}><Input value={v.mobile} onChange={(e) => set('mobile', e.target.value)} placeholder="05xxxxxxxx" /></Field>
        <Field label={t('E-mail')}><Input type="email" value={v.email} onChange={(e) => set('email', e.target.value)} /></Field>
        <Field label={t('Company')}><LinkInput doctype="Company" value={v.company} onChange={(x) => set('company', x)} /></Field>
        <Field label={t('Department')}><LinkInput doctype="Department" value={v.department} onChange={(x) => set('department', x)} /></Field>
        <Field label={t('Designation')}><LinkInput doctype="Designation" value={v.designation} onChange={(x) => set('designation', x)} /></Field>
        <Field label={t('Branch')}><LinkInput doctype="Branch" value={v.branch} onChange={(x) => set('branch', x)} /></Field>
      </div>
      <p className="mt-3 text-xs text-muted">{t('AlphaX makes a private link valid for 14 days. The joiner opens it on the phone without an account, fills in the form in Arabic or English and uploads documents.')}</p>
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

function Detail({ row, form, onClose, onData }: { row: any; form: any; onClose: () => void; onData: () => void }) {
  const { t, lang } = useI18n()
  const nav = useNavigate()
  const [note, setNote] = useState('')
  const [copied, setCopied] = useState(false)
  const act = useMutation({
    mutationFn: async (what: string) => {
      if (what === 'send') return api.sendJoinerLink(row.name)
      if (what === 'renew') return api.renewJoiner(row.name)
      if (what === 'back') return api.joinerChanges(row.name, note)
      if (what === 'cancel') return api.cancelJoiner(row.name)
    },
    onSuccess: (_r, what) => { onData(); if (what !== 'send') onClose() },
  })
  const copy = async () => { try { await navigator.clipboard.writeText(row.link); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch { /* ignore */ } }
  const open = row.status === 'Invited' || row.status === 'Changes requested'
  const value = (f: any) => {
    const x = row.data?.[f.key]
    if (!x) return <span className="text-muted">—</span>
    if (f.type === 'file') return <a className="text-brand hover:underline" href={x} target="_blank" rel="noreferrer">{t('Open')} <ExternalLink className="inline size-3" /></a>
    return String(x)
  }
  return (
    <Modal open wide onClose={onClose} title={row.full_name}
      footer={<div className="flex w-full flex-wrap justify-end gap-2">
        {row.status !== 'Converted' && row.status !== 'Cancelled' && <Button variant="ghost" onClick={() => { if (confirm(t('Cancel this joining form? The link stops working.'))) act.mutate('cancel') }}><X className="size-4" />{t('Cancel form')}</Button>}
        {row.status === 'Submitted' && <Button onClick={() => nav(`/people/new?joiner=${encodeURIComponent(row.name)}`)}><UserPlus className="size-4" />{t('Create employee')}</Button>}
        {row.status === 'Converted' && row.employee && <Button onClick={() => nav(`/people/${encodeURIComponent(row.employee)}`)}>{t('Open employee')}</Button>}
      </div>}>
      <div className="flex flex-col gap-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={TONE[row.status]}>{t(row.status)}</Badge>
          {row.expired && <Badge tone="red">{t('Link expired')}</Badge>}
          <span className="text-muted">{[row.designation, row.department, row.date_of_joining && `${t('Joining date')} ${fmtDate(row.date_of_joining, lang)}`, row.submitted_on && `${t('Sent')} ${fmtDateTime(row.submitted_on, lang)}`].filter(Boolean).join(' · ')}</span>
        </div>
        {open && row.link && (
          <div className="rounded-xl bg-brand-50 p-3">
            <div className="mb-2 text-xs text-brand">{t('Share this link with the joiner (WhatsApp, SMS or e-mail). Valid until')} {fmtDate(row.expires_on, lang)}.</div>
            <div className="flex flex-wrap gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-white px-2 py-1.5 text-xs">{row.link}</code>
              <Button size="sm" variant="secondary" onClick={copy}><Copy className="size-4" />{copied ? t('Copied') : t('Copy')}</Button>
              {row.mobile && <a href={`https://wa.me/${row.mobile.replace(/\D/g, '').replace(/^0/, '966')}?text=${encodeURIComponent(row.link)}`} target="_blank" rel="noreferrer"><Button size="sm" variant="secondary">WhatsApp</Button></a>}
              {row.email && <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'send'} onClick={() => act.mutate('send')}><Mail className="size-4" />{t('E-mail it')}</Button>}
              <Button size="sm" variant="ghost" onClick={() => act.mutate('renew')}><RefreshCw className="size-4" />{t('New link')}</Button>
            </div>
            {act.data && (act.data as any).sent && <div className="mt-2 text-xs text-emerald-700">{t('Sent to')} {(act.data as any).sent}</div>}
          </div>
        )}
        {row.hr_note && row.status === 'Changes requested' && <p className="rounded-xl bg-amber-50 p-3 text-amber-900">{t('Asked to correct')}: {row.hr_note}</p>}
        {form.sections.map((s: any) => (
          <div key={s.key}>
            <div className="mb-1 font-medium">{lang === 'ar' ? s.ar : s.en}</div>
            <div className="grid gap-x-6 gap-y-1 rounded-xl border border-line p-3 sm:grid-cols-2">
              {form.fields.filter((f: any) => f.section === s.key).map((f: any) => (
                <div key={f.key} className="flex justify-between gap-3 border-b border-line/60 py-1 last:border-0">
                  <span className="text-muted">{lang === 'ar' ? f.ar : f.en}</span><span className="text-end">{value(f)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {row.status === 'Submitted' && (
          <div className="rounded-xl border border-line p-3">
            <Field label={t('Something to correct? Tell the joiner')}><Textarea value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            <Button size="sm" variant="secondary" className="mt-2" disabled={!note.trim()} loading={act.isPending && act.variables === 'back'} onClick={() => act.mutate('back')}>{t('Send back for changes')}</Button>
          </div>
        )}
        {act.error && <ErrorBox error={act.error} />}
      </div>
    </Modal>
  )
}

export default function Joiners() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['joiners'], queryFn: () => api.joiners() })
  const [show, setShow] = useState('')
  const [invite, setInvite] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['joiners'] })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const rows = d.rows.filter((r: any) => (show ? r.status === show : r.status !== 'Cancelled'))
  const pick = (k: string) => setShow((x) => (x === k ? '' : k))
  const row = d.rows.find((r: any) => r.name === open)
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('New joiners')} subtitle={t('Joiners fill in their own details and documents before their first day; HR reviews and creates the employee.')}
        actions={<Button onClick={() => setInvite(true)}><Plus className="size-4" />{t('Invite a new joiner')}</Button>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Waiting for the joiner')} value={d.counts.Invited + d.counts['Changes requested']} tone="blue" onClick={() => pick('Invited')} active={show === 'Invited'} />
        <Stat label={t('To review')} value={d.counts.Submitted} tone="amber" onClick={() => pick('Submitted')} active={show === 'Submitted'} />
        <Stat label={t('Sent back for changes')} value={d.counts['Changes requested']} onClick={() => pick('Changes requested')} active={show === 'Changes requested'} />
        <Stat label={t('Employees created')} value={d.counts.Converted} onClick={() => pick('Converted')} active={show === 'Converted'} />
      </div>
      {show && <FilterNote label={t(show)} count={rows.length} onClear={() => setShow('')} />}
      <Card>
        {!rows.length ? <Empty title={t('No joining forms yet')} icon={<UserPlus />}>{t('Invite a new joiner to send them their form.')}</Empty> : (
          <ul className="divide-y divide-line">
            {rows.map((r: any) => (
              <li key={r.name}>
                <button type="button" onClick={() => setOpen(r.name)} className="flex w-full flex-wrap items-center gap-3 py-3 text-start hover:bg-surface/60">
                  <div className="min-w-48 flex-1"><div className="font-medium">{r.full_name}</div>
                    <div className="text-xs text-muted">{[r.designation, r.department, r.mobile || r.email].filter(Boolean).join(' · ')}</div></div>
                  <span className="text-xs text-muted">{r.date_of_joining ? `${t('Joining date')} ${fmtDate(r.date_of_joining, lang)}` : ''}</span>
                  <span className={clsx('text-xs', r.expired ? 'text-red-700' : 'text-muted')}>{r.expired ? t('Link expired') : r.submitted_on ? `${t('Sent')} ${fmtDate(r.submitted_on, lang)}` : ''}</span>
                  <Badge tone={TONE[r.status]}>{t(r.status)}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {invite && <Invite onClose={() => setInvite(false)} onDone={(r) => { setInvite(false); refresh(); setOpen(r.name) }} />}
      {row && <Detail row={row} form={d.form} onClose={() => setOpen(null)} onData={refresh} />}
    </div>
  )
}
