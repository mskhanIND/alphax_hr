import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { LinkInput } from './LinkInput'
import { Button, ErrorBox, Field, Modal } from './ui'

/** HR builds a team: pick the manager, add the members; they report to the manager (and the manager approves them). */
export function TeamBuilder({ onClose }: { onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [manager, setManager] = useState('')
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const [approvers, setApprovers] = useState(true)
  const add = (v: string) => { if (v && v !== manager && !ids.includes(v)) setIds([...ids, v]); setPick('') }
  const members = pick && !ids.includes(pick) ? [...ids, pick] : ids
  const m = useMutation({ mutationFn: () => api.setTeam(manager, members, approvers ? 1 : 0), onSuccess: () => { qc.invalidateQueries({ queryKey: ['my-team'] }); qc.invalidateQueries({ queryKey: ['employees'] }) } })
  const res: any = m.data
  return (
    <Modal open onClose={onClose} title={t('Build a team')}
      footer={res ? <Button onClick={onClose}>{t('Close')}</Button> : <>
        <Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button disabled={!manager || !members.length} loading={m.isPending} onClick={() => m.mutate()}>{t('Save team')}</Button></>}>
      {res ? (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-emerald-700">{t('Now reporting to the manager')}: {res.done.length}</p>
          {!res.manager_has_login && <p className="text-amber-800">{t('The manager has no user login yet, so approvals were not set. Create their login from the employee profile.')}</p>}
          {res.failed.length > 0 && <ul className="list-disc rounded-xl bg-amber-50 p-3 ps-8 text-amber-900">{res.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error}</li>)}</ul>}
        </div>
      ) : (
        <div className="grid gap-4">
          <Field label={t('Team manager')}><LinkInput doctype="Employee" value={manager} onChange={setManager} /></Field>
          <Field label={t('Team members')}>
            <div className="flex items-end gap-2">
              <div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={setPick} onSelect={add} placeholder={t('Employee ID or name')} /></div>
              <Button size="sm" variant="secondary" disabled={!pick} onClick={() => add(pick)}><Plus className="size-4" />{t('Add')}</Button>
            </div>
          </Field>
          {ids.length > 0 && <div className="flex flex-wrap gap-1.5">{ids.map((i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs">{i}
              <button type="button" aria-label={t('Remove')} onClick={() => setIds(ids.filter((x) => x !== i))}><X className="size-3" /></button></span>
          ))}</div>}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4" checked={approvers} onChange={(e) => setApprovers(e.target.checked)} />
            {t('The manager also approves their leave, expenses and shift requests')}</label>
          {m.error && <ErrorBox error={m.error} />}
        </div>
      )}
    </Modal>
  )
}
