import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Plus } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Table, Textarea } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { useI18n } from '../lib/i18n'

const CATS = ['Leave', 'Attendance', 'Payroll', 'Benefits', 'Policies', 'Documents', 'Travel', 'Other']

function Form({ initial, onClose }: { initial: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [f, setF] = useState<any>(initial ?? { category: 'Policies', published: 1 })
  const [file, setFile] = useState<File | null>(null)
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }))
  const m = useMutation({
    mutationFn: async () => { const d = { ...f }; if (file) d.attachment = (await uploadFile('', '', file, false))?.file_url; return api.saveHelpArticle(d, initial?.name) },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['help-admin'] }); qc.invalidateQueries({ queryKey: ['help'] }); onClose() },
  })
  return (
    <Modal open wide onClose={onClose} title={initial ? t('Edit article') : t('New article')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button disabled={!f.title || !f.body} loading={m.isPending} onClick={() => m.mutate()}>{t('Save')}</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t('Title')}><Input value={f.title ?? ''} onChange={(e) => set('title', e.target.value)} /></Field>
        <Field label={t('Title (Arabic)')}><Input dir="rtl" value={f.title_ar ?? ''} onChange={(e) => set('title_ar', e.target.value)} /></Field>
        <Field label={t('Content')}><Textarea rows={10} value={f.body ?? ''} onChange={(e) => set('body', e.target.value)} /></Field>
        <Field label={t('Content (Arabic)')}><Textarea rows={10} dir="rtl" value={f.body_ar ?? ''} onChange={(e) => set('body_ar', e.target.value)} /></Field>
        <Field label={t('Category')}><Select value={f.category} onChange={(e) => set('category', e.target.value)}>{CATS.map((c) => <option key={c} value={c}>{t(c)}</option>)}</Select></Field>
        <Field label={t('Attachment')}><input type="file" className="text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.published} onChange={(e) => set('published', e.target.checked ? 1 : 0)} />{t('Published')}</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.pinned} onChange={(e) => set('pinned', e.target.checked ? 1 : 0)} />{t('Pin to the top')}</label>
      </div>
      {m.error && <div className="mt-3"><ErrorBox error={m.error} /></div>}
    </Modal>
  )
}

export default function KnowledgeAdmin() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['help-admin'], queryFn: api.allHelpArticles })
  const [edit, setEdit] = useState<any>(undefined)
  const del = useMutation({ mutationFn: api.deleteHelpArticle, onSuccess: () => qc.invalidateQueries({ queryKey: ['help-admin'] }) })
  return (
    <div>
      <PageHeader title={t('Help centre articles')} subtitle={t('Policies, how-tos and FAQs employees can search. Questions arrive in Requests as “Ask HR”.')}
        actions={<Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New article')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No articles yet')} icon={<BookOpen />} /> : (
          <Table head={[t('Title'), t('Category'), t('Views'), t('Helpful'), '']}>
            {q.data.map((a: any) => (
              <tr key={a.name}>
                <td className="py-2 font-medium">{a.title} {!a.published && <Badge>{t('Draft')}</Badge>}{a.pinned ? <> <Badge tone="blue">{t('Pinned')}</Badge></> : null}</td>
                <td>{t(a.category)}</td><td>{a.views || 0}</td><td className="text-sm">👍 {a.helpful || 0} · 👎 {a.not_helpful || 0}</td>
                <td className="whitespace-nowrap"><Button size="sm" variant="secondary" onClick={() => setEdit(a)}>{t('Edit')}</Button>
                  <Button size="sm" variant="secondary" loading={del.isPending && del.variables === a.name} onClick={() => del.mutate(a.name)}>{t('Delete')}</Button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {edit !== undefined && <Form initial={edit} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
