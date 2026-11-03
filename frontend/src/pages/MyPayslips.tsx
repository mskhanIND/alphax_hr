import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Wallet } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, Modal, PageHeader, Spinner } from '../components/ui'
import { api, downloadFile } from '../lib/api'
import { fmtMoney, fmtMonth } from '../lib/format'
import { useI18n } from '../lib/i18n'

function SlipDetail({ name }: { name: string }) {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['payslip', name], queryFn: () => api.payslip(name) })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const s = q.data
  const Lines = ({ title, rows }: { title: string; rows: any[] }) => (
    <div>
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <ul className="divide-y divide-line text-sm">
        {rows.map((r) => <li key={r.component} className="flex justify-between py-1.5"><span>{r.component}</span><span className="tabular-nums">{fmtMoney(r.amount, lang, s.currency)}</span></li>)}
      </ul>
    </div>
  )
  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-2xl bg-brand p-5 text-white">
        <div className="text-sm text-white/70">{t('Net pay')}</div>
        <div className="text-3xl font-semibold tabular-nums">{fmtMoney(s.net_pay, lang, s.currency)}</div>
        <div className="mt-1 text-sm text-white/70">{t('Payment days')}: {s.payment_days} / {s.total_working_days}</div>
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <Lines title={t('Earnings')} rows={s.earnings} />
        <Lines title={t('Deductions')} rows={s.deductions} />
      </div>
      <DownloadButton url={s.pdf_url} filename={`${s.name}.pdf`} />
    </div>
  )
}

function DownloadButton({ url, filename }: { url: string; filename: string }) {
  const { t } = useI18n()
  const m = useMutation({ mutationFn: () => downloadFile(url, filename) })
  return (
    <div className="flex flex-col gap-2">
      <Button variant="secondary" className="self-start" loading={m.isPending} onClick={() => m.mutate()}><Download className="size-4" /> {t('Download PDF')}</Button>
      {m.error && <ErrorBox error={m.error} />}
    </div>
  )
}

export default function MyPayslips() {
  const { t, lang } = useI18n()
  const q = useQuery<any[]>({ queryKey: ['payslips'], queryFn: api.payslips })
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div>
      <PageHeader title={t('My Payslips')} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? (
          <Empty title={t('No payslips yet')} icon={<Wallet />} />
        ) : (
          <ul className="divide-y divide-line">
            {q.data.map((s) => (
              <li key={s.name}>
                <button className="flex w-full items-center justify-between gap-3 py-3 text-start hover:bg-surface/60" onClick={() => setOpen(s.name)}>
                  <div>
                    <div className="font-medium">{fmtMonth(s.start_date, lang)}</div>
                    <div className="text-sm text-muted">{t('Gross pay')} {fmtMoney(s.gross_pay, lang, s.currency)} · {t('Deductions')} {fmtMoney(s.total_deduction, lang, s.currency)}</div>
                  </div>
                  <div className="text-lg font-semibold tabular-nums">{fmtMoney(s.net_pay, lang, s.currency)}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title={t('My Payslips')}>{open && <SlipDetail name={open} />}</Modal>
    </div>
  )
}
