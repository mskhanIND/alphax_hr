import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { api } from '../lib/api'
import { Input } from './ui'

/** Text input with server-side suggestions for a Frappe Link field. */
export function LinkInput({ doctype, value, onChange, disabled, required, source = 'hr', placeholder }: { doctype: string; value: string; onChange: (v: string) => void; disabled?: boolean; required?: boolean; source?: 'hr' | 'ess'; placeholder?: string }) {
  const id = useId()
  const [txt, setTxt] = useState(value ?? '')
  const [debounced, setDebounced] = useState('')
  useEffect(() => setTxt(value ?? ''), [value])
  useEffect(() => { const h = setTimeout(() => setDebounced(txt), 250); return () => clearTimeout(h) }, [txt])
  const q = useQuery({ queryKey: ['lookup', source, doctype, debounced], queryFn: () => (source === 'ess' ? api.essLookup : api.lookup)(doctype, debounced), enabled: !disabled, staleTime: 60_000 })
  return (
    <>
      <Input list={id} value={txt} placeholder={placeholder} disabled={disabled} required={required} autoComplete="off"
        onChange={(e) => { setTxt(e.target.value); onChange(e.target.value) }} />
      <datalist id={id}>
        {(q.data ?? []).map((o) => <option key={o.value} value={o.value}>{o.description || o.label || ''}</option>)}
      </datalist>
    </>
  )
}
