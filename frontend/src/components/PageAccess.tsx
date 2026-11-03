import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox, Select, Spinner } from './ui'

/** Settings: hide AlphaX pages, or limit them to some roles. */
export function PageAccess() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['page-access'], queryFn: api.pageAccess })
  const [rows, setRows] = useState<any[]>([])
  useEffect(() => { if (q.data) setRows(q.data.pages) }, [q.data])
  const m = useMutation({ mutationFn: () => api.savePageAccess(rows), onSuccess: (d) => { qc.setQueryData(['page-access'], d); qc.invalidateQueries({ queryKey: ['session'] }) } })
  if (q.isLoading) return <Card title={t('Pages')}><Spinner /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  const can = q.data.can_edit
  const set = (i: number, patch: any) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const dirty = JSON.stringify(rows) !== JSON.stringify(q.data.pages)
  let area = ''
  return (
    <Card title={t('Pages')} subtitle={t('Hide pages for everyone, or show them only to some roles. Users see the change after reloading.')}
      action={can ? <Button size="sm" disabled={!dirty} loading={m.isPending} onClick={() => m.mutate()}>{t('Save')}</Button> : undefined}>
      {m.error && <ErrorBox error={m.error} />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="page-access">
          <tbody>
            {rows.map((r, i) => {
              const header = r.area !== area ? (area = r.area) : null
              return [
                header && <tr key={`h-${r.area}`}><td colSpan={3} className="pt-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t(r.area)}</td></tr>,
                <tr key={r.page} className={r.hidden ? 'opacity-60' : undefined}>
                  <td className="py-1.5 pe-3">{t(r.label)} <span className="text-xs text-muted">{r.page}</span></td>
                  <td className="py-1.5 pe-3"><label className="flex items-center gap-1.5 text-xs">
                    <input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={!can} checked={!!r.hidden} onChange={(e) => set(i, { hidden: e.target.checked ? 1 : 0 })} />{t('Hide')}</label></td>
                  <td className="py-1.5">
                    <div className="flex flex-wrap items-center gap-1">
                      {r.roles.map((role: string) => <button key={role} disabled={!can} className="rounded-full bg-surface px-2 py-0.5 text-xs" onClick={() => set(i, { roles: r.roles.filter((x: string) => x !== role) })}>{role} ×</button>)}
                      {can && !r.hidden && (
                        <Select className="!h-7 !w-40 !py-0 text-xs" value="" onChange={(e) => e.target.value && set(i, { roles: [...r.roles, e.target.value] })}>
                          <option value="">{r.roles.length ? t('+ role') : t('Everyone allowed')}</option>
                          {q.data.roles.filter((x: string) => !r.roles.includes(x)).map((x: string) => <option key={x}>{x}</option>)}
                        </Select>
                      )}
                    </div>
                  </td>
                </tr>,
              ]
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
