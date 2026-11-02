import { useQuery } from '@tanstack/react-query'
import { Download, X } from 'lucide-react'
import { useState } from 'react'
import { LeaveLedger } from '../components/LeaveLedger'
import { Button, Card, Empty, ErrorBox, Input, PageHeader, Select, Spinner } from '../components/ui'
import { api, downloadUrl } from '../lib/api'
import { fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'

export default function LeaveBalances() {
  const { t, lang } = useI18n()
  const [department, setDepartment] = useState('')
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState<{ id: string; name: string } | null>(null)
  const deps = useQuery<any>({ queryKey: ['employees', '', 'Active', '', '', 0], queryFn: () => api.employees({ status: 'Active', page_length: 1 }) })
  const q = useQuery<any>({ queryKey: ['leaveWorkforce', department], queryFn: () => api.leaveWorkforce({ department }) })
  const rows = (q.data?.rows ?? []).filter((r: any) => !search || r.employee_name.toLowerCase().includes(search.toLowerCase()) || r.employee.toLowerCase().includes(search.toLowerCase()))
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Leave balances')} subtitle={t('Balance per leave type for every active employee. Click a name for the full ledger.')}
        actions={<a href={downloadUrl('leave_ledger.export_workforce', { department, file_format: 'xlsx' })}><Button variant="secondary"><Download className="size-4" />{t('Export')}</Button></a>} />
      <Card>
        <div className="mb-4 flex flex-wrap gap-2">
          <Input className="!w-64" placeholder={t('Search people, ID or Iqama…')} value={search} onChange={(e) => setSearch(e.target.value)} />
          <Select aria-label={t('Department')} className="!w-56" value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">{t('All departments')}</option>
            {(deps.data?.departments ?? []).map((d: string) => <option key={d} value={d}>{d}</option>)}
          </Select>
        </div>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : !rows.length ? <Empty title={t('No employees found')} /> : (
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-sm">
              <thead className="text-xs text-muted"><tr className="border-b border-line">
                <th className="px-2 pb-2 text-start font-medium">{t('Employee')}</th>
                {q.data.leave_types.map((lt: string) => <th key={lt} className="px-2 pb-2 text-end font-medium">{lt}</th>)}
                <th className="px-2 pb-2 text-end font-medium">{t('Sick left (of 120)')}</th>
              </tr></thead>
              <tbody className="divide-y divide-line">
                {rows.map((r: any) => (
                  <tr key={r.employee} className="cursor-pointer hover:bg-surface" onClick={() => setOpen({ id: r.employee, name: r.employee_name })}>
                    <td className="px-2 py-2"><div className="font-medium">{r.employee_name}</div><div className="text-xs text-muted">{r.department ?? r.employee}</div></td>
                    {q.data.leave_types.map((lt: string) => {
                      const b = r.balances[lt]
                      return <td key={lt} className="px-2 py-2 text-end tabular-nums" title={b ? `${t('Allocated')} ${b.allocated} · ${t('Taken')} ${b.taken} · ${t('Pending')} ${b.pending}` : ''}>
                        {b ? <span className={b.balance < 0 ? 'font-semibold text-red-700' : ''}>{fmtNumber(b.balance, lang, 1)}</span> : <span className="text-muted">—</span>}</td>
                    })}
                    <td className="px-2 py-2 text-end tabular-nums">{r.sick_left == null ? '—' : fmtNumber(r.sick_left, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {open && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onMouseDown={() => setOpen(null)}>
          <aside role="dialog" aria-label={t('Leave ledger')} className="h-full w-full max-w-2xl overflow-y-auto bg-white p-5 shadow-xl" onMouseDown={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <span className="text-lg font-semibold">{open.name}</span>
              <button onClick={() => setOpen(null)} className="rounded-lg p-1 text-muted hover:bg-surface" aria-label={t('Close')}><X className="size-5" /></button>
            </div>
            <LeaveLedger employee={open.id} compact />
          </aside>
        </div>
      )}
    </div>
  )
}
