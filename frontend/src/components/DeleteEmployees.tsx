import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Button, ErrorBox, Modal } from './ui'

/** Confirm and delete one or more employees. Employees with history are kept and the reason is shown. */
export function DeleteEmployees({ people, onClose, onDone }: {
  people: { name: string; employee_name: string }[]; onClose: () => void; onDone: (deleted: string[]) => void
}) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const del = useMutation({
    mutationFn: () => api.deleteEmployees(people.map((p) => p.name)),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['employees'] })
      qc.invalidateQueries({ queryKey: ['orgChart'] })
      onDone(r.deleted.map((d) => d.employee))
    },
  })
  const r = del.data
  return (
    <Modal open onClose={onClose} title={people.length === 1 ? t('Delete employee') : `${t('Delete employees')} (${people.length})`}
      footer={r ? <Button onClick={onClose}>{t('Close')}</Button> : <>
        <Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button variant="danger" loading={del.isPending} onClick={() => del.mutate()}>{t('Delete permanently')}</Button>
      </>}>
      {!r ? (
        <div className="flex flex-col gap-3 text-sm">
          <div className="flex gap-2 rounded-xl bg-red-50 p-3 text-red-800">
            <AlertTriangle className="size-4 shrink-0" />
            <span>{t('This removes the employee record and cannot be undone. Employees with attendance, leave, payroll or a team reporting to them are not deleted — set their status to Left instead to keep the history.')}</span>
          </div>
          <ul className="max-h-60 divide-y divide-line overflow-auto rounded-xl border border-line">
            {people.map((p) => <li key={p.name} className="flex justify-between px-3 py-1.5"><span className="font-medium">{p.employee_name}</span><span className="text-muted">{p.name}</span></li>)}
          </ul>
          {del.error && <ErrorBox error={del.error} />}
        </div>
      ) : (
        <div className="flex flex-col gap-3 text-sm">
          {r.deleted.length > 0 && <div className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-emerald-800"><CheckCircle2 className="size-4" />{r.deleted.length} {t('deleted')}</div>}
          {r.blocked.length > 0 && (
            <div>
              <div className="mb-1 font-medium text-amber-900">{r.blocked.length} {t('kept')}</div>
              <ul className="max-h-72 divide-y divide-line overflow-auto rounded-xl border border-line">
                {r.blocked.map((b) => <li key={b.employee} className="px-3 py-2"><div className="font-medium">{b.employee_name} <span className="text-xs text-muted">{b.employee}</span></div><div className="text-xs text-amber-800">{b.reason}</div></li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
