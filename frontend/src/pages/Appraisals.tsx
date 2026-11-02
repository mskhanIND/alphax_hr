import { useQuery } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Empty, ErrorBox, PageHeader, Select, Spinner, StatusBadge, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { recordPath } from '../lib/links'

export function AppraisalTable({ rows }: { rows: any[] }) {
  const { t, lang } = useI18n()
  return (
    <Table head={[t('Employee'), t('Appraisal cycle'), t('Goals'), t('Feedback'), t('Self'), t('Final score'), t('Status')]}>
      {rows.map((r) => (
        <tr key={r.name}>
          <td className="py-2"><Link className="font-medium text-brand hover:underline" to={recordPath('Appraisal', r.name)}>{r.employee_name}</Link>
            <div className="text-xs text-muted">{r.department}</div></td>
          <td className="text-sm">{r.appraisal_cycle}<div className="text-xs text-muted">{fmtDate(r.start_date, lang)} → {fmtDate(r.end_date, lang)}</div></td>
          <td>{fmtNumber(r.total_score, lang, 1)}</td><td>{fmtNumber(r.avg_feedback_score, lang, 1)}</td>
          <td>{fmtNumber(r.self_score, lang, 1)}</td><td className="font-semibold">{fmtNumber(r.final_score, lang, 2)}</td>
          <td><StatusBadge status={r.status} /></td>
        </tr>
      ))}
    </Table>
  )
}

export default function Appraisals() {
  const { t, lang } = useI18n()
  const cycles = useQuery({ queryKey: ['appraisal-cycles'], queryFn: api.appraisalCycles })
  const [cycle, setCycle] = useState('')
  const q = useQuery({ queryKey: ['appraisals', cycle], queryFn: () => api.appraisals(cycle || undefined) })
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Appraisals')} subtitle={t('Performance cycles and scores (HRMS appraisals)')}
        actions={<Select className="w-64" value={cycle} onChange={(e) => setCycle(e.target.value)}>
          <option value="">{t('All cycles')}</option>
          {(cycles.data?.cycles ?? []).map((c: any) => <option key={c.name} value={c.name}>{c.cycle_name || c.name}</option>)}
        </Select>} />
      {cycles.data?.cycles?.length > 0 && (
        <Card title={t('Appraisal cycles')}>
          <Table head={[t('Appraisal cycle'), t('Period'), t('Appraisals'), t('Submitted'), t('Average score'), t('Status')]}>
            {cycles.data.cycles.map((c: any) => (
              <tr key={c.name}>
                <td className="py-2"><Link className="font-medium text-brand hover:underline" to={recordPath('Appraisal Cycle', c.name)}>{c.cycle_name || c.name}</Link></td>
                <td className="text-sm">{fmtDate(c.start_date, lang)} → {fmtDate(c.end_date, lang)}</td>
                <td>{c.appraisals}</td><td>{c.submitted}</td><td>{fmtNumber(c.average, lang, 2)}</td><td><StatusBadge status={c.status} /></td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length
          ? <Empty title={t('No appraisals yet')} icon={<Star />}>{t('Appraisal cycles started in HRMS appear here.')}</Empty>
          : <AppraisalTable rows={q.data} />}
      </Card>
    </div>
  )
}
