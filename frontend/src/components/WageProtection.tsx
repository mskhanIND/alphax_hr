import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Download, FileSpreadsheet, Upload } from 'lucide-react'
import { useState } from 'react'
import { Badge, Button, ErrorBox, Modal, Spinner, Stat, Table } from './ui'
import { call, downloadFile, downloadUrl, uploadFile } from '../lib/api'
import { fmtMoney, fmtMonth } from '../lib/format'
import { useI18n } from '../lib/i18n'

const FIELD: Record<string, string> = { basic: 'Basic salary', housing: 'Housing allowance', transport: 'Transportation allowance', total: 'Total salary',
  other: 'Other allowances', overtime: 'Overtime', commission: 'Commissions', deductions: 'Deductions', net: 'Net salary', name: 'Employee name', id: 'ID number' }

/** Wage protection for one payroll run: checks before paying, the bank file, and the Mudad template filled from the run. */
export function WageProtection({ company, month, run, onClose }: { company: string; month: string; run?: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const q = useQuery<any>({ queryKey: ['wps-check', company, month, run], queryFn: () => call('alphax_hr.wps.check', { company, month, run }) })
  const [busy, setBusy] = useState(false)
  const bank = useMutation({ mutationFn: () => downloadFile(downloadUrl('payroll_control.salary_file', { company, month, run }), `salary-file-${month.slice(0, 7)}.xlsx`) })
  const mudad = useMutation({
    mutationFn: async (file: File) => {
      setBusy(true)
      try {
        const up = await uploadFile('', '', file)
        return await call<any>('alphax_hr.wps.mudad', { company, month, run, file_url: up.file_url })
      } finally { setBusy(false) }
    },
  })
  const d = q.data
  const r = mudad.data
  return (
    <Modal open wide onClose={onClose} title={`${t('Wage protection (WPS / Mudad)')} · ${fmtMonth(month, lang)}`}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : d && (
        <div className="flex flex-col gap-4 text-sm">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t('Employees')} value={d.employees} />
            <Stat label={t('Net to pay')} value={fmtMoney(d.net, lang)} />
            <Stat label={t('Will be rejected')} value={d.errors} tone={d.errors ? 'red' : 'brand'} />
            <Stat label={t('To check')} value={d.warnings} tone={d.warnings ? 'amber' : 'brand'} />
          </div>
          <div className={clsx('rounded-xl p-3', d.ready ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800')}>
            {d.ready ? t('Ready: every row has a valid ID, IBAN and net salary.') : t('Fix the rows below before sending the file: the bank or Mudad would reject them, or pay the wrong account.')}
          </div>
          {d.issues.length > 0 && <Table head={[t('Employee'), t('Problem'), '']}>
            {d.issues.map((i: any, n: number) => <tr key={n}><td>{i.employee_name}<div className="text-xs text-muted">{i.employee}</div></td><td>{i.message}</td>
              <td><Badge tone={i.level === 'error' ? 'red' : 'amber'}>{t(i.level === 'error' ? 'Rejected' : 'Check')}</Badge></td></tr>)}
          </Table>}
          {d.by_bank.length > 0 && <div><div className="mb-1 font-medium">{t('By bank')}</div>
            <div className="flex flex-wrap gap-2">{d.by_bank.map((b: any) => <span key={b.bank} className="rounded-lg border border-line px-2 py-1 text-xs">{b.bank}: {b.employees} · {fmtMoney(b.net, lang)}</span>)}</div></div>}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-line p-3">
              <div className="mb-1 flex items-center gap-2 font-medium"><Download className="size-4" />{t('Bank salary file')}</div>
              <p className="mb-2 text-xs text-muted">{t('ID, name, bank, IBAN, basic, housing, other earnings, deductions and net, with totals. Check the layout your bank asks for.')}</p>
              <Button size="sm" variant="secondary" loading={bank.isPending} onClick={() => bank.mutate()}>{t('Download')}</Button>
            </div>
            <div className="rounded-xl border border-line p-3">
              <div className="mb-1 flex items-center gap-2 font-medium"><FileSpreadsheet className="size-4" />{t('Mudad payroll file')}</div>
              <p className="mb-2 text-xs text-muted">{t('In Mudad: Payroll Management → Create Payroll → the month → Upload Payroll File → Download Template. Upload that template here: AlphaX fills it from this run and keeps the columns Mudad does not allow to change.')}</p>
              <label className={clsx('inline-flex cursor-pointer items-center gap-2 rounded-lg border border-line bg-white px-3 py-1.5 text-sm font-medium', busy && 'opacity-60')}>
                <Upload className="size-4" />{busy ? t('Filling…') : t('Upload Mudad template')}
                <input type="file" accept=".xlsx" className="hidden" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) mudad.mutate(f); e.target.value = '' }} />
              </label>
            </div>
          </div>
          {mudad.error && <ErrorBox error={mudad.error} />}
          {r && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <b className="flex-1">{t('Mudad file ready')}: {r.matched} {t('employees filled')} · {t('net')} {fmtMoney(r.totals.net, lang)}</b>
                <Button size="sm" onClick={() => downloadFile(r.file_url, r.file_name)}><Download className="size-4" />{t('Download for Mudad')}</Button>
              </div>
              <div className="mt-1 text-xs text-muted">{t('Filled')}: {r.filled.map((k: string) => t(FIELD[k] ?? k)).join(', ') || '—'} · {t('Kept as in Mudad')}: {r.kept.map((k: string) => t(FIELD[k] ?? k)).join(', ')}</div>
              {r.differences.length > 0 && <div className="mt-3"><div className="font-medium text-amber-800">{t('Mudad and AlphaX disagree')} ({r.differences.length})</div>
                <p className="text-xs text-muted">{t('Mudad keeps these as registered. Update the contract in Qiwa / the wage in GOSI, or the salary in AlphaX, so they match.')}</p>
                <Table head={[t('Employee'), t('Item'), 'Mudad', 'AlphaX']}>{r.differences.map((x: any, n: number) => <tr key={n}><td>{x.employee_name}</td><td>{t(FIELD[x.field] ?? x.field)}</td><td>{fmtMoney(x.mudad, lang)}</td><td>{fmtMoney(x.alphax, lang)}</td></tr>)}</Table></div>}
              {r.not_in_template.length > 0 && <div className="mt-3"><div className="font-medium text-amber-800">{t('Paid in AlphaX but not in the Mudad template')} ({r.not_in_template.length})</div>
                <p className="text-xs">{r.not_in_template.map((x: any) => `${x.employee_name}${x.id ? ` (${x.id})` : ` (${t('no ID')})`}`).join(', ')}</p></div>}
              {r.not_in_payroll.length > 0 && <div className="mt-3"><div className="font-medium text-amber-800">{t('In the Mudad template but no salary slip this month')} ({r.not_in_payroll.length})</div>
                <p className="text-xs">{r.not_in_payroll.map((x: any) => `${x.name ?? ''} (${x.id})`).join(', ')}</p></div>}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
