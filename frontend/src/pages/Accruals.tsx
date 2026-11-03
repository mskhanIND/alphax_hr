import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, BookOpenCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Card, ErrorBox, Input, PageHeader, Select, Spinner, Stat, StatusBadge, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtMoney, fmtMonth, fmtNumber, monthStart, shiftMonth, todayISO } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'

export default function Accruals() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const r = useQuery({ queryKey: ['accrual-runs'], queryFn: () => api.accrualRuns() })
  const [company, setCompany] = useState('')
  const [month, setMonth] = useState(shiftMonth(monthStart(todayISO()), -1))
  useEffect(() => { if (!company && r.data?.companies?.length) setCompany(r.data.companies[0]) }, [r.data, company])
  const pv = useQuery({ queryKey: ['accrual-preview', company, month], queryFn: () => api.accrualPreview(company, month), enabled: !!company })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['accrual-runs'] }); qc.invalidateQueries({ queryKey: ['accrual-preview'] }) }
  const post = useMutation({ mutationFn: () => api.accrualPost(company, month), onSuccess: refresh })
  const cancel = useMutation({ mutationFn: (name: string) => api.accrualCancel(name), onSuccess: refresh })
  const d = pv.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Accruals')} subtitle={t('Monthly provisions for end of service and annual leave, posted to the accounts')}
        actions={<div className="flex flex-wrap items-center gap-2">
          {(r.data?.companies?.length ?? 0) > 1 && <Select className="w-56" value={company} onChange={(e) => setCompany(e.target.value)}>{r.data!.companies.map((c: string) => <option key={c}>{c}</option>)}</Select>}
          <Input type="month" className="!w-40" value={month.slice(0, 7)} onChange={(e) => setMonth(`${e.target.value}-01`)} />
        </div>} />
      <Card>
        <div className="flex gap-3 text-sm text-muted"><BookOpenCheck className="size-5 shrink-0 text-brand" />
          <p>{t('Each month the obligation is measured again per employee — end-of-service award as if they left at month end, and unused annual leave × daily wage — and only the difference is booked (Dr expense, Cr provision). Raises, extra service and used leave are picked up automatically.')}</p></div>
      </Card>
      {pv.isLoading ? <Spinner /> : pv.error ? <ErrorBox error={pv.error} /> : d && (
        <>
          {d.warnings.map((w: string, i: number) => <div key={i} className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="size-4 shrink-0" />{w}</div>)}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('EOS this month')} value={fmtMoney(d.eos_total, lang)} />
            <Stat label={t('Leave this month')} value={fmtMoney(d.leave_total, lang)} tone="blue" />
            <Stat label={t('EOS obligation')} value={fmtMoney(d.eos_balance, lang)} tone="amber" />
            <Stat label={t('Leave obligation')} value={fmtMoney(d.leave_balance, lang)} tone="amber" />
          </div>
          <Card title={`${fmtMonth(d.month, lang)} · ${d.basis}`}
            action={r.data?.can_post && !d.existing ? <Button loading={post.isPending} disabled={d.accounts_missing} onClick={() => post.mutate()}>{t('Post accruals')}</Button>
              : d.existing ? <span className="text-sm text-muted">{t('Already posted')}: {d.existing}</span> : undefined}>
            {(post.error || cancel.error) && <ErrorBox error={post.error || cancel.error} />}
            {post.data && <p className="mb-2 text-sm text-emerald-700">{t('Posted')} {post.data.name} · {post.data.journal_entry}</p>}
            <Table head={[t('Employee'), t('Service'), t('EOS obligation'), t('Before'), t('This month'), t('Leave days'), t('Leave obligation'), t('This month')]}>
              {d.lines.map((x: any) => (
                <tr key={x.employee}>
                  <td className="py-1.5">{x.employee_name}<div className="text-xs text-muted">{x.employee}{x.note ? ` · ${x.note}` : ''}</div></td>
                  <td>{fmtNumber(x.service_years, lang, 2)}</td>
                  <td>{fmtMoney(x.eos_obligation, lang)}</td><td className="text-muted">{fmtMoney(x.eos_previous, lang)}</td>
                  <td className="font-semibold">{fmtMoney(x.eos_charge, lang)}</td>
                  <td>{fmtNumber(x.leave_days, lang, 2)}</td><td>{fmtMoney(x.leave_obligation, lang)}</td>
                  <td className="font-semibold">{fmtMoney(x.leave_charge, lang)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </>
      )}
      <Card title={t('Posted runs')}>
        {r.isLoading ? <Spinner /> : !r.data?.rows?.length ? <p className="text-sm text-muted">{t('Nothing posted yet.')}</p> : (
          <Table head={[t('Month'), t('Company'), t('EOS'), t('Leave'), t('Journal Entry'), t('Status'), '']}>
            {r.data.rows.map((x: any) => (
              <tr key={x.name}>
                <td className="py-1.5">{fmtMonth(x.month, lang)}</td><td className="text-sm">{x.company}</td>
                <td>{fmtMoney(x.eos_total, lang)}</td><td>{fmtMoney(x.leave_total, lang)}</td>
                <td>{x.journal_entry && <Link className="text-brand hover:underline" to={recordPath('Journal Entry', x.journal_entry)}>{x.journal_entry}</Link>}</td>
                <td><StatusBadge status={x.status} /></td>
                <td>{r.data.can_post && x.status === 'Posted' && <Button size="sm" variant="ghost" loading={cancel.isPending && cancel.variables === x.name} onClick={() => cancel.mutate(x.name)}>{t('Cancel')}</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  )
}
