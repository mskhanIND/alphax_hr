import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import { useState } from 'react'
import { JobProgress } from './JobProgress'
import { Button, ErrorBox, Input, Modal, Select, Spinner, Stat, Table } from './ui'
import { call } from '../lib/api'
import { useI18n } from '../lib/i18n'

/** Employees without a login: create them in bulk, and the setting that creates them on save. */
export function Logins({ onClose }: { onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['logins'], queryFn: () => call('alphax_hr.logins.overview') })
  const [sel, setSel] = useState<Record<string, boolean>>({})
  const [mail, setMail] = useState<Record<string, string>>({})
  const rows: any[] = q.data?.without ?? []
  const email = (r: any) => mail[r.employee] ?? r.email ?? ''
  const ok = (r: any) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email(r)) && (!r.problem || !!mail[r.employee])
  const chosen = rows.filter((r) => (sel[r.employee] ?? ok(r)) && ok(r))
  const run = useMutation({
    mutationFn: () => call<any>('alphax_hr.logins.create', { employees: JSON.stringify(chosen.map((r) => r.employee)),
      emails: JSON.stringify(Object.fromEntries(chosen.filter((r) => mail[r.employee]).map((r) => [r.employee, mail[r.employee]]))), background: 1 }),
    onSuccess: () => { q.refetch(); qc.invalidateQueries({ queryKey: ['people'] }); setSel({}); setMail({}) },
  })
  const settings = useMutation({ mutationFn: (v: { auto: number; source: string }) => call('alphax_hr.logins.save_settings', v), onSuccess: (d) => qc.setQueryData(['logins'], d) })
  const r = run.data
  return (
    <Modal open wide onClose={onClose} title={t('Employee logins')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Close')}</Button>
        <Button loading={run.isPending} disabled={!chosen.length} onClick={() => run.mutate()}><KeyRound className="size-4" />{t('Create logins')} ({chosen.length})</Button></>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <div className="flex flex-col gap-4 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <Stat label={t('Active employees')} value={q.data.total} />
            <Stat label={t('With a login')} value={q.data.with_login} />
            <Stat label={t('Without a login')} value={rows.length} tone={rows.length ? 'amber' : 'brand'} />
          </div>
          <p className="rounded-xl bg-brand-50 p-3 text-xs text-brand">{t('Each login gets the Employee role, is linked to the employee and receives a welcome e-mail to set a password; they sign in at')} <b>{location.origin}/alphax</b>. {t('Managers need nothing extra: their menu appears once employees report to them. HR roles are given in User settings.')}</p>
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
            <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!q.data.auto}
              onChange={(e) => settings.mutate({ auto: e.target.checked ? 1 : 0, source: q.data.source })} />{t('Create the login automatically when a new employee is saved with an e-mail')}</label>
            <Select value={q.data.source} onChange={(e) => settings.mutate({ auto: q.data.auto, source: e.target.value })} className="ms-auto !w-56">
              {['Company e-mail first', 'Personal e-mail first', 'Company e-mail only'].map((o) => <option key={o} value={o}>{t(o)}</option>)}
            </Select>
          </div>
          {rows.length > 0 && <Table head={[<input key="all" type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={chosen.length > 0 && chosen.length === rows.filter(ok).length}
            onChange={(e) => setSel(Object.fromEntries(rows.map((x) => [x.employee, e.target.checked])))} />, t('Employee'), t('Department'), t('Login e-mail')]}>
            {rows.slice(0, 500).map((x) => <tr key={x.employee}>
              <td><input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={!ok(x)} checked={(sel[x.employee] ?? ok(x)) && ok(x)} onChange={(e) => setSel((s) => ({ ...s, [x.employee]: e.target.checked }))} /></td>
              <td><div className="font-medium">{x.employee_name}</div><div className="text-xs text-muted">{x.employee}</div></td>
              <td>{x.department ?? '—'}</td>
              <td className="min-w-64"><Input value={email(x)} placeholder={t('e-mail')} onChange={(e) => setMail((m) => ({ ...m, [x.employee]: e.target.value.trim() }))} />
                {x.problem && !mail[x.employee] && <div className="mt-0.5 text-[11px] text-amber-700">{t(x.problem)}</div>}</td>
            </tr>)}
          </Table>}
          {r?.status ? <JobProgress job="create-logins" onDone={() => q.refetch()}>{(res) => res && <Result r={res} />}</JobProgress> : r && <Result r={r} />}
          {run.error && <ErrorBox error={run.error} />}
        </div>
      )}
    </Modal>
  )
}

function Result({ r }: { r: any }) {
  const { t } = useI18n()
  return (
    <div className="rounded-xl bg-emerald-50 p-3 text-emerald-800">
      {t('Created')}: {r.created} · {t('Linked to an existing user')}: {r.linked}{r.exists ? ` · ${t('Already had one')}: ${r.exists}` : ''}
      {r.skipped?.length > 0 && <ul className="mt-1 list-disc ps-5 text-amber-800">{r.skipped.map((s: any) => <li key={s.employee}>{s.employee_name}: {s.reason}</li>)}</ul>}
    </div>
  )
}
