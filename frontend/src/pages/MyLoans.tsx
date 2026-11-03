import { useQuery } from '@tanstack/react-query'
import { HandCoins, Send } from 'lucide-react'
import { useState } from 'react'
import { RequestForm } from '../components/RequestForm'
import { Button, Card, Empty, ErrorBox, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { api } from '../lib/api'
import { fmtMoney } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { LoanSchedule } from './Loans'

export default function MyLoans() {
  const { t, lang } = useI18n()
  const q = useQuery({ queryKey: ['my-loans'], queryFn: api.myLoans })
  const [ask, setAsk] = useState<string | null>(null)
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('My loans')} subtitle={t('Loans and salary advances, and what is left to repay')}
        actions={<div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setAsk('Salary Advance')}><Send className="size-4" />{t('Salary advance')}</Button>
          <Button variant="secondary" onClick={() => setAsk('Loan Request')}><Send className="size-4" />{t('Loan request')}</Button>
          <Button variant="secondary" onClick={() => setAsk('Loan Postponement')}>{t('Postpone an installment')}</Button>
        </div>} />
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <>
          {q.data.loan_cap > 0 && <p className="text-sm text-muted">{t('Without your written consent a loan installment is at most 10% of your wage')}: <b>{fmtMoney(q.data.loan_cap, lang)}</b> {t('a month')} (Art. 92).</p>}
          {!q.data.loans.length ? <Card><Empty title={t('No loans or advances')} icon={<HandCoins />} /></Card> : q.data.loans.map((l: any) => (
            <Card key={l.name} title={`${t(l.loan_type)} · ${fmtMoney(l.amount, lang)}`} subtitle={`${l.name}${l.purpose ? ` · ${l.purpose}` : ''}`} action={<StatusBadge status={l.status} />}>
              <div className="mb-3 flex flex-wrap gap-4 text-sm">
                <span>{t('Repaid')}: <b>{fmtMoney(l.repaid, lang)}</b></span>
                <span>{t('Outstanding')}: <b>{fmtMoney(l.outstanding, lang)}</b></span>
                {l.paid_by && <span>{t('Paid by')}: {t(l.paid_by)}</span>}
              </div>
              <LoanSchedule loan={l} />
            </Card>
          ))}
        </>
      )}
      <RequestForm open={!!ask} onClose={() => setAsk(null)} initialType={ask ?? undefined} category="Finance" />
    </div>
  )
}
