import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, FileText, Folder, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, Empty, ErrorBox, Modal, PageHeader, Select, Spinner } from '../components/ui'
import { api, downloadFile, uploadFile } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

const isImage = (u: string) => /\.(png|jpe?g|gif|webp)$/i.test(u)
const isPdf = (u: string) => /\.pdf$/i.test(u) || /download_pdf|get_pdf|letter/i.test(u)

/** View a file inside the app (PDF or picture); anything else is offered as a download. */
function Viewer({ file, onClose }: { file: { url: string; name: string } | null; onClose: () => void }) {
  const { t } = useI18n()
  if (!file) return null
  return (
    <Modal open onClose={onClose} wide title={file.name}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Close')}</Button>
        <Button onClick={() => downloadFile(file.url, file.name)}><Download className="size-4" />{t('Download')}</Button></>}>
      {isImage(file.url) ? <img src={file.url} alt={file.name} className="mx-auto max-h-[70vh] rounded-lg" />
        : isPdf(file.url) ? <iframe src={file.url} title={file.name} className="h-[70vh] w-full rounded-lg border border-line" />
        : <p className="text-sm text-muted">{t('This file cannot be shown here. Download it to open it.')}</p>}
    </Modal>
  )
}

export default function MyDocuments() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['my-documents'], queryFn: api.myDocuments })
  const [view, setView] = useState<{ url: string; name: string } | null>(null)
  const [kind, setKind] = useState('Iqama / ID')
  const input = useRef<HTMLInputElement>(null)
  const up = useMutation({
    mutationFn: async (file: File) => { const f = await uploadFile('', '', file, true); return api.attachMyDocument(f.name, kind) },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['my-documents'] }); if (input.current) input.current.value = '' },
  })
  const rm = useMutation({ mutationFn: (name: string) => api.removeMyDocument(name), onSuccess: () => qc.invalidateQueries({ queryKey: ['my-documents'] }) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
  const actions = (url: string, name: string) => (
    <span className="flex shrink-0 items-center gap-1">
      <Button size="sm" variant="ghost" onClick={() => setView({ url, name })}><Eye className="size-4" />{t('View')}</Button>
      <Button size="sm" variant="ghost" onClick={() => downloadFile(url, name)} aria-label={t('Download')}><Download className="size-4" /></Button>
    </span>
  )
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('My documents')} subtitle={t('Expiry dates, your files and letters issued to you')} />
      <Card title={t('Document expiry')}>
        {!d.documents.length ? <p className="text-sm text-muted">—</p> : (
          <ul className="divide-y divide-line">
            {d.documents.map((x: any) => (
              <li key={x.document} className="flex items-center justify-between py-2.5 text-sm">
                <span className="font-medium">{t(x.document)}</span>
                <span className="flex items-center gap-2">{fmtDate(x.expiry, lang)}
                  <Badge tone={x.state === 'expired' ? 'red' : x.state === 'soon' ? 'amber' : 'green'}>
                    {x.state === 'expired' ? t('Expired') : `${x.days_left} ${t('days')}`}</Badge>
                  {x.state !== 'valid' && x.document !== 'Contract' && <Link to="/me/profile" className="text-xs font-medium text-brand underline">{t('Update')}</Link>}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('Letters')}>
        {!d.letters.length ? <Empty title={t('No letters yet')} icon={<FileText />}>{t('Request one from Services.')}</Empty> : (
          <ul className="divide-y divide-line">
            {d.letters.map((l: any) => (
              <li key={l.name} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{t(l.request_type)} <span className="text-muted">· {fmtDate(l.modified, lang)}</span></span>
                {actions(l.letter, `${l.request_type}.pdf`)}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('My files')} subtitle={t('Add a copy of your Iqama, passport, certificates and other papers. HR sees them in your file.')}
        action={<div className="flex items-center gap-2">
          <Select className="!w-40" value={kind} onChange={(e) => setKind(e.target.value)} aria-label={t('Document')}>
            {(d.kinds ?? []).map((k: string) => <option key={k} value={k}>{t(k)}</option>)}
          </Select>
          <input ref={input} type="file" accept="image/*,application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
          <Button size="sm" loading={up.isPending} onClick={() => input.current?.click()}><Upload className="size-4" />{t('Add document')}</Button>
        </div>}>
        {up.error && <ErrorBox error={up.error} />}
        {!d.files.length ? <Empty title={t('No files')} icon={<Folder />}>{t('Use Add document to upload a PDF or a photo.')}</Empty> : (
          <ul className="divide-y divide-line">
            {d.files.map((f: any) => (
              <li key={f.name} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0 truncate">{f.file_name} <span className="text-xs text-muted">· {fmtDate(f.creation, lang)}{f.mine ? '' : ` · ${t('added by HR')}`}</span></span>
                <span className="flex items-center">
                  {actions(f.file_url, f.file_name)}
                  {f.mine && <Button size="sm" variant="ghost" aria-label={t('Remove')} loading={rm.isPending && rm.variables === f.name}
                    onClick={() => { if (window.confirm(t('Remove this file?'))) rm.mutate(f.name) }}><Trash2 className="size-4" /></Button>}
                </span>
              </li>
            ))}
          </ul>
        )}
        {rm.error && <ErrorBox error={rm.error} />}
      </Card>
      <Viewer file={view} onClose={() => setView(null)} />
    </div>
  )
}
