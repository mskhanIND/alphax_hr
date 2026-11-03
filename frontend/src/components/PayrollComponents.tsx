import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Badge, Button, Card, ErrorBox, Spinner, Table } from './ui'

/** Settings: the standard Saudi payroll components and which one AlphaX uses for each purpose. */
export function PayrollComponents() {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['component-catalogue'], queryFn: api.componentCatalogue })
  const m = useMutation({ mutationFn: api.createStandardComponents, onSuccess: (d) => qc.setQueryData(['component-catalogue'], d) })
  if (q.isLoading) return <Card title={t('Payroll components')}><Spinner /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  const missing = q.data.rows.filter((r: any) => !r.exists).length
  return (
    <Card title={t('Payroll components')} subtitle={t('Salary, allowances, overtime, leave, end of service, accruals and deductions used by AlphaX. Change which component is used in the settings below.')}
      action={q.data.can_edit && missing > 0 ? <Button size="sm" loading={m.isPending} onClick={() => m.mutate()}>{t('Create missing standard components')} ({missing})</Button> : undefined}>
      {m.error && <ErrorBox error={m.error} />}
      <Table head={[t('Purpose'), t('Group'), t('Type'), t('Component in use'), t('Wage mapping')]}>
        {q.data.rows.map((r: any) => (
          <tr key={r.key}>
            <td className="py-1.5">{lang === 'ar' ? r.name_ar : t(r.name)}{r.statistical && <span className="ms-1 text-xs text-muted">({t('accrual, not paid')})</span>}</td>
            <td className="text-sm">{t(r.group)}</td>
            <td><Badge tone={r.type === 'Earning' ? 'green' : 'red'}>{t(r.type)}</Badge></td>
            <td className="text-sm">{r.exists ? r.in_use : <span className="text-red-700">{t('Missing')}</span>}</td>
            <td className="text-xs text-muted">{r.map.map((x: string) => t(x)).join(', ')}</td>
          </tr>
        ))}
      </Table>
    </Card>
  )
}
