import { useQuery } from '@tanstack/react-query'
import { FileText, Folder } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, Card, Empty, ErrorBox, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function MyDocuments() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['my-documents'], queryFn: api.myDocuments })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
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
              <li key={l.name} className="flex items-center justify-between py-2.5 text-sm">
                <span>{t(l.request_type)} <span className="text-muted">· {fmtDate(l.modified, lang)}</span></span>
                <a className="font-medium text-brand underline" href={l.letter} target="_blank" rel="noreferrer">{t('Download')}</a>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('My files')}>
        {!d.files.length ? <Empty title={t('No files')} icon={<Folder />} /> : (
          <ul className="divide-y divide-line">
            {d.files.map((f: any) => (
              <li key={f.name} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span className="truncate">{f.file_name}</span>
                <a className="shrink-0 font-medium text-brand underline" href={f.file_url} target="_blank" rel="noreferrer">{t('Open')}</a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
