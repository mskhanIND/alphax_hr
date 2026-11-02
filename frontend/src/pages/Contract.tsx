import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, FileCheck2, Printer } from 'lucide-react'
import { useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button, ErrorBox, PageHeader, Spinner } from '../components/ui'
import { api, downloadUrl } from '../lib/api'
import { useI18n } from '../lib/i18n'

/** Bilingual employment contract (Qiwa layout): preview, print, download or save to the employee's file. */
export default function Contract() {
  const { id = '' } = useParams()
  const { t } = useI18n()
  const frame = useRef<HTMLIFrameElement>(null)
  const q = useQuery<any>({ queryKey: ['contract', id], queryFn: () => api.contractHtml(id) })
  const save = useMutation({ mutationFn: () => api.saveContract(id) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  return (
    <div className="flex flex-col gap-4">
      <Link to={`/people/${encodeURIComponent(id)}`} className="inline-flex items-center gap-1 self-start text-sm text-muted hover:text-ink"><ArrowLeft className="size-4 flip-rtl" />{q.data.employee_name}</Link>
      <PageHeader title={t('Employment contract')} subtitle={t('English and Arabic, in the layout of the Qiwa unified contract.')}
        actions={<div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => frame.current?.contentWindow?.print()}><Printer className="size-4" />{t('Print')}</Button>
          <a href={downloadUrl('contract.pdf', { employee: id })}><Button variant="secondary"><Download className="size-4" />{t('Download PDF')}</Button></a>
          <Button loading={save.isPending} onClick={() => save.mutate()}><FileCheck2 className="size-4" />{t("Save to employee's file")}</Button>
        </div>} />
      {save.isSuccess && <p className="text-sm text-emerald-700">{t('Saved as an attachment on the employee.')}</p>}
      {save.error && <ErrorBox error={save.error} />}
      <iframe ref={frame} title={t('Employment contract')} srcDoc={q.data.html} className="h-[80vh] w-full rounded-2xl border border-line bg-white" />
    </div>
  )
}
