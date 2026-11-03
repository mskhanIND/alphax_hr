import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Megaphone, Plus } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Textarea } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { fmtDate, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'

function Form({ initial, onClose }: { initial: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [f, setF] = useState<any>(initial ?? { audience: 'Everyone', priority: 'Normal', publish_on: todayISO() })
  const [file, setFile] = useState<File | null>(null)
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }))
  const m = useMutation({
    mutationFn: async () => {
      const data = { ...f }
      if (file) data.attachment = (await uploadFile('', '', file, false))?.file_url
      return api.saveAnnouncement(data, initial?.name)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['announcements'] }); qc.invalidateQueries({ queryKey: ['all-announcements'] }); onClose() },
  })
  return (
    <Modal open onClose={onClose} wide title={initial ? t('Edit announcement') : t('New announcement')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button disabled={!f.title || !f.body} loading={m.isPending} onClick={() => m.mutate()}>{t('Publish')}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t('Title')}><Input value={f.title ?? ''} onChange={(e) => set('title', e.target.value)} /></Field>
        <Field label={t('Title (Arabic)')}><Input dir="rtl" value={f.title_ar ?? ''} onChange={(e) => set('title_ar', e.target.value)} /></Field>
        <Field label={t('Message')}><Textarea rows={6} value={f.body ?? ''} onChange={(e) => set('body', e.target.value)} /></Field>
        <Field label={t('Message (Arabic)')}><Textarea rows={6} dir="rtl" value={f.body_ar ?? ''} onChange={(e) => set('body_ar', e.target.value)} /></Field>
        <Field label={t('Audience')}>
          <Select value={f.audience} onChange={(e) => set('audience', e.target.value)}>{['Everyone', 'Company', 'Department'].map((x) => <option key={x} value={x}>{t(x)}</option>)}</Select>
        </Field>
        {f.audience !== 'Everyone' ? (
          <Field label={t(f.audience)}><LinkInput doctype={f.audience} value={f[f.audience.toLowerCase()] ?? ''} onChange={(v) => set(f.audience.toLowerCase(), v)} /></Field>
        ) : <div />}
        <Field label={t('Publish on')}><Input type="date" value={f.publish_on ?? ''} onChange={(e) => set('publish_on', e.target.value)} /></Field>
        <Field label={t('Show until')}><Input type="date" value={f.expires_on ?? ''} onChange={(e) => set('expires_on', e.target.value)} /></Field>
        <Field label={t('Priority')}>
          <Select value={f.priority} onChange={(e) => set('priority', e.target.value)}><option value="Normal">{t('Normal')}</option><option value="Important">{t('Important')}</option></Select>
        </Field>
        <Field label={t('Attachment')}><input type="file" className="text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.pinned} onChange={(e) => set('pinned', e.target.checked ? 1 : 0)} />{t('Pin to the top')}</label>
      </div>
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

export default function AnnouncementsAdmin() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['all-announcements'], queryFn: api.allAnnouncements })
  const [edit, setEdit] = useState<any>(undefined)
  const del = useMutation({ mutationFn: api.deleteAnnouncement, onSuccess: () => qc.invalidateQueries({ queryKey: ['all-announcements'] }) })
  const today = new Date().toISOString().slice(0, 10)
  return (
    <div>
      <PageHeader title={t('Announcements')} subtitle={t('News from HR on every employee’s home screen')}
        actions={<Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New announcement')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No announcements yet')} icon={<Megaphone />} /> : (
          <ul className="divide-y divide-line">
            {q.data.map((a: any) => {
              const live = a.publish_on <= today && (!a.expires_on || a.expires_on >= today)
              return (
                <li key={a.name} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{a.title}</span>
                      <Badge tone={live ? 'green' : 'gray'}>{live ? t('Live') : a.publish_on > today ? t('Scheduled') : t('Ended')}</Badge>
                      {a.priority === 'Important' && <Badge tone="red">{t('Important')}</Badge>}{a.pinned ? <Badge tone="blue">{t('Pinned')}</Badge> : null}</div>
                    <div className="text-sm text-muted">{t(a.audience)}{a.company || a.department ? `: ${a.company || a.department}` : ''} · {fmtDate(a.publish_on, lang)}{a.expires_on ? ` → ${fmtDate(a.expires_on, lang)}` : ''}</div>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => setEdit(a)}>{t('Edit')}</Button>
                  <Button size="sm" variant="secondary" loading={del.isPending && del.variables === a.name} onClick={() => del.mutate(a.name)}>{t('Delete')}</Button>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
      {edit !== undefined && <Form initial={edit} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
