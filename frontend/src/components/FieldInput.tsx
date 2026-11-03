import { LinkInput } from './LinkInput'
import { useState } from 'react'
import { uploadFile } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Input, Select, Textarea } from './ui'

/** Upload a file and keep its URL (private by default); shows the current file with a preview for images. */
function AttachInput({ value, onChange, image }: { value: any; onChange: (v: any) => void; image?: boolean }) {
  const { t } = useI18n()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  return (
    <div className="flex flex-wrap items-center gap-3">
      {value && (image ? <img src={value} alt="" className="h-14 max-w-40 rounded border border-line object-contain" />
        : <a href={value} target="_blank" rel="noreferrer" className="text-sm text-brand underline">{String(value).split('/').pop()}</a>)}
      <input type="file" accept={image ? 'image/*' : undefined} className="text-sm" disabled={busy} onChange={async (e) => {
        const f = e.target.files?.[0]; if (!f) return
        setBusy(true); setErr('')
        try { onChange((await uploadFile('', '', f))?.file_url ?? null) } catch (x: any) { setErr(x?.message ?? String(x)) } finally { setBusy(false) }
      }} />
      {value && <button type="button" className="text-xs text-muted underline" onClick={() => onChange(null)}>{t('Remove')}</button>}
      {err && <span className="text-xs text-red-600">{err}</span>}
    </div>
  )
}

export interface FieldSpec {
  fieldname: string
  label: string
  fieldtype: string
  reqd?: number
  options?: string | string[]
  default?: string | null
  description?: string | null
}

/** Renders an input for any Frappe field type the site defines on Employee. */
export function FieldInput({ spec, value, onChange, invalid, lookupSource }: { spec: FieldSpec; value: any; onChange: (v: any) => void; invalid?: boolean; lookupSource?: 'hr' | 'ess' }) {
  const cls = invalid ? 'border-red-400 ring-2 ring-red-100' : undefined
  switch (spec.fieldtype) {
    case 'Check':
      return <input type="checkbox" className="size-5 accent-[var(--color-brand)]" checked={!!value} onChange={(e) => onChange(e.target.checked ? 1 : 0)} />
    case 'Link':
      return <div className={invalid ? 'rounded-xl ring-2 ring-red-100' : undefined}><LinkInput doctype={String(spec.options)} value={value ?? ''} onChange={onChange} source={lookupSource} /></div>
    case 'Select': {
      const opts = Array.isArray(spec.options) ? spec.options : String(spec.options ?? '').split('\n')
      return (
        <Select className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
          {!opts.includes('') && <option value="">—</option>}
          {opts.map((o) => <option key={o} value={o}>{o || '—'}</option>)}
        </Select>
      )
    }
    case 'Date':
      return <Input className={cls} type="date" value={value ? String(value).slice(0, 10) : ''} onChange={(e) => onChange(e.target.value || null)} />
    case 'Datetime':
      return <Input className={cls} type="datetime-local" value={value ? String(value).slice(0, 16).replace(' ', 'T') : ''} onChange={(e) => onChange(e.target.value ? e.target.value.replace('T', ' ') + ':00' : null)} />
    case 'Int':
    case 'Float':
    case 'Currency':
    case 'Percent':
      return <Input className={cls} type="number" step={spec.fieldtype === 'Int' ? 1 : 'any'} value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
    case 'Attach':
    case 'Attach Image':
      return <AttachInput value={value} onChange={onChange} image={spec.fieldtype === 'Attach Image'} />
    case 'Small Text':
    case 'Text':
    case 'Long Text':
      return <Textarea className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    default:
      return <Input className={cls} value={value ?? ''} inputMode={spec.fieldtype === 'Phone' ? 'tel' : undefined} onChange={(e) => onChange(e.target.value)} />
  }
}

export const isEmpty = (v: unknown) => v === null || v === undefined || v === ''
