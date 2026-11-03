import { useMutation, useQuery } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { BankSelect } from '../components/BankSelect'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, Input, PageHeader, Select, Spinner, Table } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

export default function BulkUpdate() {
  const { t } = useI18n()
  const o = useQuery({ queryKey: ['bulk-options'], queryFn: api.bulkOptions })
  const [field, setField] = useState('')
  const [value, setValue] = useState<any>('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const spec = o.data?.fields.find((f: any) => f.fieldname === field)
  const args = { filters, employees: ids.length ? ids : undefined }
  const pv = useMutation({ mutationFn: () => api.bulkPreview(field, args) })
  const ap = useMutation({ mutationFn: () => api.bulkApply(field, value, args), onSuccess: () => pv.mutate() })
  const reset = () => { pv.reset(); ap.reset() }
  if (o.isLoading) return <Spinner />
  if (o.error) return <ErrorBox error={o.error} />
  const input = !spec ? null
    : spec.fieldname === 'bank_name' ? <BankSelect value={value} onChange={setValue} />
    : spec.fieldtype === 'Link' ? <LinkInput doctype={spec.options} value={value} onChange={setValue} />
    : spec.fieldtype === 'Select' ? <Select value={value} onChange={(e) => setValue(e.target.value)}>{(spec.options ?? []).map((x: string) => <option key={x} value={x}>{x ? t(x) : '—'}</option>)}</Select>
    : spec.fieldtype === 'Check' ? <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!value} onChange={(e) => setValue(e.target.checked ? 1 : 0)} />
    : <Input type={['Int', 'Float', 'Currency'].includes(spec.fieldtype) ? 'number' : 'text'} value={value} onChange={(e) => setValue(e.target.value)} />
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Bulk update employees')} subtitle={t('Set one field for many employees at once; each employee is saved and checked on its own.')} />
      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('Field')}>
            <Select value={field} onChange={(e) => { setField(e.target.value); setValue(''); reset() }}>
              <option value="">{t('Choose…')}</option>
              <optgroup label={t('Employee record')}>{o.data.fields.filter((f: any) => f.group === 'employee').map((f: any) => <option key={f.fieldname} value={f.fieldname}>{f.label}</option>)}</optgroup>
              <optgroup label={t('Check-in & attendance rules')}>{o.data.fields.filter((f: any) => f.group === 'attendance').map((f: any) => <option key={f.fieldname} value={f.fieldname}>{f.label}</option>)}</optgroup>
            </Select>
          </Field>
          <Field label={t('New value')}>{input ?? <Input disabled />}</Field>
          {(['company', 'department', 'branch', 'designation'] as const).map((k) => (
            <Field key={k} label={t(k[0].toUpperCase() + k.slice(1))}>
              <Select value={filters[k] ?? ''} onChange={(e) => { setFilters({ ...filters, [k]: e.target.value }); reset() }}>
                <option value="">{t('All')}</option>
                {(o.data[k === 'company' ? 'companies' : `${k}s`] ?? []).map((x: string) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
          ))}
          <Field label={t('Or only these employees')}>
            <div className="flex gap-2"><div className="flex-1"><LinkInput doctype="Employee" value={pick} onChange={setPick} placeholder={t('Employee ID or name')} /></div>
              <Button size="sm" variant="secondary" disabled={!pick} onClick={() => { if (!ids.includes(pick)) setIds([...ids, pick]); setPick(''); reset() }}><Plus className="size-4" />{t('Add')}</Button></div>
            <div className="mt-2 flex flex-wrap gap-1.5">{ids.map((e) => <span key={e} className="flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs">{e}<button aria-label={t('Remove')} onClick={() => setIds(ids.filter((x) => x !== e))}><X className="size-3" /></button></span>)}</div>
          </Field>
        </div>
        <div className="mt-4 flex gap-2">
          <Button variant="secondary" disabled={!field} loading={pv.isPending} onClick={() => pv.mutate()}>{t('Preview')}</Button>
          <Button disabled={!field || !pv.data?.count} loading={ap.isPending} onClick={() => ap.mutate()}>{t('Update')} {pv.data?.count ? `(${pv.data.count})` : ''}</Button>
        </div>
        {(pv.error || ap.error) && <div className="mt-3"><ErrorBox error={pv.error || ap.error} /></div>}
        {ap.data && <p className="mt-3 text-sm text-emerald-700">{t('Updated')}: {ap.data.done.length}{ap.data.failed.length ? ` · ${t('Not updated')}: ${ap.data.failed.length}` : ''}</p>}
        {ap.data?.failed?.length > 0 && <ul className="mt-2 list-disc rounded-xl bg-amber-50 p-3 ps-8 text-sm text-amber-900">{ap.data.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error}</li>)}</ul>}
      </Card>
      {pv.data && (
        <Card title={`${pv.data.count} ${t('employees')}`}>
          <Table head={[t('Employee'), t('Department'), t('Now')]}>
            {pv.data.rows.map((r: any) => <tr key={r.name}><td className="py-1.5">{r.employee_name}<div className="text-xs text-muted">{r.name}</div></td><td>{r.department}</td><td>{r.current === null || r.current === '' || r.current === undefined ? '—' : String(r.current)}</td></tr>)}
          </Table>
        </Card>
      )}
    </div>
  )
}
