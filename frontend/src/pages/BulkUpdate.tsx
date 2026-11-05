import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { BankSelect } from '../components/BankSelect'
import { FieldInput } from '../components/FieldInput'
import { LinkInput } from '../components/LinkInput'
import { Button, Card, ErrorBox, Field, Input, PageHeader, Select, Spinner, Table, Tabs } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

/** Required employee fields that are empty: fill several at once, only where empty. */
function FillMissing({ filters }: { filters: Record<string, string> }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['bulk-missing', filters], queryFn: () => api.bulkMissing(filters) })
  const [values, setValues] = useState<Record<string, any>>({})
  const m = useMutation({ mutationFn: () => api.bulkFillMissing(values, filters), onSuccess: () => { setValues({}); qc.invalidateQueries({ queryKey: ['bulk-missing'] }) } })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const rows = q.data.fields as any[]
  if (!rows.length && !m.data) return <p className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{t('Every active employee has all required fields filled.')}</p>
  const filled = Object.values(values).filter((v) => v !== '' && v !== undefined && v !== null).length
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t('Enter a value for the fields you want to fill. Only employees where the field is empty get it; values already there are kept. Each employee is saved once.')}</p>
      <Table head={[t('Field'), t('Employees missing it'), t('Value to fill')]}>
        {rows.map((f) => (
          <tr key={f.fieldname}>
            <td className="py-2 font-medium">{f.label}<div className="text-xs text-muted">{f.fieldname}</div></td>
            <td><span className="rounded-full bg-amber-50 px-2 py-0.5 text-sm text-amber-800">{f.missing} / {q.data.employees}</span></td>
            <td className="min-w-64">{f.personal
              ? <span className="text-xs text-muted">{t('Different for each person — fill it on the employee profile.')}</span>
              : <FieldInput spec={f} value={values[f.fieldname] ?? ''} onChange={(v) => setValues((s) => ({ ...s, [f.fieldname]: v }))} />}</td>
          </tr>
        ))}
      </Table>
      <div><Button disabled={!filled} loading={m.isPending} onClick={() => m.mutate()}>{t('Fill empty fields')} {filled ? `(${filled})` : ''}</Button></div>
      {m.error && <ErrorBox error={m.error} />}
      {m.data && (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-emerald-700">{t('Updated')}: {m.data.done.length}{m.data.failed.length ? ` · ${t('Not updated')}: ${m.data.failed.length}` : ''}</p>
          {m.data.failed.length > 0 && <ul className="list-disc rounded-xl bg-red-50 p-3 ps-8 text-red-800">{m.data.failed.map((f: any) => <li key={f.employee}><b>{f.employee}</b>: {f.error}</li>)}</ul>}
          {m.data.still_missing.length > 0 && (
            <div className="rounded-xl bg-amber-50 p-3 text-amber-900">
              <div className="mb-1 font-medium">{t('Still missing')}</div>
              <ul className="list-disc ps-5">{m.data.still_missing.slice(0, 50).map((x: any) => <li key={x.employee}><b>{x.employee_name}</b> ({x.employee}): {x.missing.join(', ')}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function BulkUpdate() {
  const { t } = useI18n()
  const [mode, setMode] = useState<'one' | 'missing'>('one')
  const [onlyEmpty, setOnlyEmpty] = useState(false)
  const o = useQuery({ queryKey: ['bulk-options'], queryFn: api.bulkOptions })
  const [field, setField] = useState('')
  const [value, setValue] = useState<any>('')
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [ids, setIds] = useState<string[]>([])
  const [pick, setPick] = useState('')
  const spec = o.data?.fields.find((f: any) => f.fieldname === field)
  const args = { filters, employees: ids.length ? ids : undefined }
  const pv = useMutation({ mutationFn: () => api.bulkPreview(field, args) })
  const ap = useMutation({ mutationFn: () => api.bulkApply(field, value, { ...args, only_empty: onlyEmpty ? 1 : 0 }), onSuccess: () => pv.mutate() })
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
      <Tabs value={mode} onChange={(v) => setMode(v as 'one' | 'missing')} tabs={[{ value: 'one', label: t('One field for many employees') }, { value: 'missing', label: t('Fill missing required fields') }]} />
      {mode === 'missing' ? <Card><FillMissing filters={filters} /></Card> : <>
      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('Field')}>
            <Select value={field} onChange={(e) => { setField(e.target.value); setValue(''); reset() }}>
              <option value="">{t('Choose…')}</option>
              <optgroup label={t('Employee record')}>{o.data.fields.filter((f: any) => f.group === 'employee').map((f: any) => <option key={f.fieldname} value={f.fieldname}>{f.label}</option>)}</optgroup>
              {o.data.fields.some((f: any) => f.group === 'required') && <optgroup label={t('Required by your company')}>{o.data.fields.filter((f: any) => f.group === 'required').map((f: any) => <option key={f.fieldname} value={f.fieldname}>{f.label}</option>)}</optgroup>}
              {o.data.fields.some((f: any) => f.group === 'other') && <optgroup label={t('Other employee fields')}>{o.data.fields.filter((f: any) => f.group === 'other').map((f: any) => <option key={f.fieldname} value={f.fieldname}>{f.label}</option>)}</optgroup>}
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
        {spec && spec.group !== 'attendance' && (
          <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={onlyEmpty} onChange={(e) => setOnlyEmpty(e.target.checked)} />{t('Only where it is empty (keep values already there)')}</label>
        )}
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
      </>}
    </div>
  )
}
